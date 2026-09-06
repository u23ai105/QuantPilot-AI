"""Redis cache for RAG *query* embeddings.

Why only queries. Every `RetrievalService.search` call embeds the user's question before it can run the
pgvector similarity search, and that embedding is a paid call against the Gemini quota. Queries repeat —
the eval harness replays a fixed question set, a user rephrases and re-asks, the agent calls
`search_documents` several times in one turn — and the same text under the same model always produces
the same vector, so recomputing it buys nothing. Document embeddings are *not* cached: they are embedded
once at ingestion and then stored in `document_chunks.embedding`, which already is the cache.

What the key covers. A SHA-256 of the query text, plus the model id and output dimensionality, because a
vector from a different model or a different Matryoshka truncation is not interchangeable with one from
these. Hashed rather than stored verbatim so that key length is bounded and Redis holds no readable
record of what users asked. Not scoped per user: an embedding is a pure function of the text, and the
ownership filter that decides *which* chunks a caller may see lives in the SQL query
(`search_user_chunks`), not in the vector. Two users asking the same question share a cache entry and
still get their own documents back.

Correctness note. A cached vector is only usable if it still has the expected dimensionality, so a
decoded hit is validated before use and treated as a miss if it fails — otherwise a stale entry written
under a different configuration would reach pgvector and raise there instead.
"""

from __future__ import annotations

import hashlib

import structlog

from app.ai.embedding import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from app.core import metrics
from app.core.cache import RedisJSONCache, get_cache

logger = structlog.get_logger(__name__)

#: One day. Long, because the mapping from text to vector never changes for a fixed model — the TTL is
#: here to reclaim space for questions asked once, not to bound staleness.
QUERY_EMBEDDING_TTL_SECONDS = 86_400


def query_cache_key(query: str, *, model: str = EMBEDDING_MODEL, dimensions: int = EMBEDDING_DIMENSIONS) -> str:
    """Cache key for one query's embedding.

    The query is normalized (stripped, whitespace collapsed) before hashing so that trailing spaces and
    a line break pasted mid-question hit the same entry. Case is *not* folded: embeddings are
    case-sensitive, so folding would serve a vector for text that was never embedded.
    """
    normalized = " ".join(query.split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"embed:query:{model}:{dimensions}:{digest}"


class CachedQueryEmbedder:
    """Wraps an object with `embed_query`, serving repeats from Redis.

    Takes the embedder rather than constructing one so the caller keeps ownership of it (and so tests can
    pass a counting stub). Any failure in the cache path falls through to the wrapped embedder.
    """

    def __init__(self, embedder, cache: RedisJSONCache | None = None, *, ttl_seconds: int = QUERY_EMBEDDING_TTL_SECONDS) -> None:
        self._embedder = embedder
        self._cache = cache if cache is not None else get_cache()
        self._ttl_seconds = ttl_seconds

    async def embed_query(self, text: str) -> list[float]:
        key = query_cache_key(text)

        cached = await self._cache.get(key)
        if _is_usable_vector(cached):
            metrics.query_embedding_cache_total.labels(outcome="hit").inc()
            logger.debug("query_embedding_cache_hit")
            return cached

        # A miss covers three cases — absent, Redis down, unusable entry — deliberately counted as one:
        # what the metric answers is "how many embedding API calls did the cache fail to save".
        metrics.query_embedding_cache_total.labels(outcome="miss").inc()
        vector = await self._embedder.embed_query(text)
        # Only cache what passes the same validation a hit has to pass, so a bad vector is never stored.
        if _is_usable_vector(vector):
            await self._cache.set(key, vector, self._ttl_seconds)
        return vector


def _is_usable_vector(value: object) -> bool:
    """Whether `value` is a vector this deployment can hand to pgvector.

    The length check is what makes a hit safe: JSON gives back a plain list, and an entry written when
    `EMBEDDING_DIMENSIONS` was something else would otherwise be passed straight into a `Vector(768)`
    comparison and fail deep in the query instead of degrading to a recompute.
    """
    return isinstance(value, list) and len(value) == EMBEDDING_DIMENSIONS and all(isinstance(component, (int, float)) for component in value)
