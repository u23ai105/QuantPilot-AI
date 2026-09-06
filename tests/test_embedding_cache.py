"""Tests for the Redis JSON cache and the RAG query-embedding cache on top of it.

Redis is faked, as in `test_rate_limit.py`: what matters here is the cache's contract — when a call
reaches the embedder, when it does not, what a broken or corrupt store does — and a real Redis would add
nothing to those assertions. **No test in this file makes a live embedding call**: the embedder is always
a counting stub, so "how many API calls did this save" is directly observable.
"""

from __future__ import annotations

import json

import pytest

from app.ai.embedding_cache import QUERY_EMBEDDING_TTL_SECONDS, CachedQueryEmbedder, query_cache_key
from app.core.cache import RedisJSONCache

VECTOR = [0.25] * 768


class _FakeRedis:
    """Enough of `redis.asyncio.Redis` for `RedisJSONCache`, plus the TTLs it was asked for."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex


class _BrokenRedis:
    async def get(self, key: str):
        raise ConnectionError("redis is down")

    async def set(self, key: str, value: str, ex: int | None = None):
        raise ConnectionError("redis is down")


class _CountingEmbedder:
    """Stands in for `GeminiEmbeddingAdapter`, counting the calls a real one would bill for."""

    def __init__(self, vector: list[float] | None = None) -> None:
        self.vector = VECTOR if vector is None else vector
        self.calls: list[str] = []

    async def embed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        return self.vector


def _cache(client) -> RedisJSONCache:
    cache = RedisJSONCache("redis://unused", key_prefix="test")
    cache._client = client
    return cache


# --- RedisJSONCache -------------------------------------------------------------------------------


async def test_cache_roundtrips_json_and_namespaces_the_key():
    fake = _FakeRedis()
    cache = _cache(fake)

    await cache.set("k", {"a": [1, 2]}, ttl_seconds=60)

    assert await cache.get("k") == {"a": [1, 2]}
    # Namespaced, so two callers with different prefixes cannot collide on a bare key name.
    assert "test:k" in fake.store


async def test_cache_always_sets_a_ttl():
    """Nothing here is authoritative, so an entry must expire on its own rather than linger."""
    fake = _FakeRedis()
    await _cache(fake).set("k", "v", ttl_seconds=123)
    assert fake.ttls["test:k"] == 123


async def test_cache_miss_returns_none():
    assert await _cache(_FakeRedis()).get("absent") is None


async def test_cache_fails_open_when_redis_is_down():
    """A Redis outage must degrade to a miss, not raise — the cache guards cost, not correctness."""
    cache = _cache(_BrokenRedis())

    assert await cache.get("k") is None
    await cache.set("k", "v", ttl_seconds=60)  # must not raise either


async def test_undecodable_entry_is_treated_as_a_miss():
    fake = _FakeRedis()
    fake.store["test:k"] = "{not json"
    assert await _cache(fake).get("k") is None


# --- the cache key --------------------------------------------------------------------------------


def test_key_is_stable_and_normalizes_whitespace():
    assert query_cache_key("  what is  the\nrevenue?  ") == query_cache_key("what is the revenue?")


def test_key_does_not_fold_case():
    """Embeddings are case-sensitive, so folding would serve a vector for text never embedded."""
    assert query_cache_key("Revenue") != query_cache_key("revenue")


def test_key_includes_model_and_dimensions():
    """A vector from another model or truncation is not interchangeable, so it must not share a key."""
    base = query_cache_key("q")
    assert query_cache_key("q", model="models/other-embedding") != base
    assert query_cache_key("q", dimensions=1536) != base


def test_key_does_not_contain_the_query_text():
    """Hashed, so Redis holds no readable record of what users asked."""
    assert "revenue" not in query_cache_key("what was revenue")


# --- CachedQueryEmbedder --------------------------------------------------------------------------


async def test_repeated_query_costs_one_embedding_call():
    """The whole point: N identical questions spend one call against the Gemini quota, not N."""
    embedder = _CountingEmbedder()
    cached = CachedQueryEmbedder(embedder, _cache(_FakeRedis()))

    first = await cached.embed_query("what was revenue?")
    second = await cached.embed_query("what was revenue?")
    third = await cached.embed_query("  what was   revenue? ")  # same query, sloppier whitespace

    assert first == second == third == VECTOR
    assert embedder.calls == ["what was revenue?"]


async def test_distinct_queries_each_embed():
    embedder = _CountingEmbedder()
    cached = CachedQueryEmbedder(embedder, _cache(_FakeRedis()))

    await cached.embed_query("revenue?")
    await cached.embed_query("margins?")

    assert len(embedder.calls) == 2


async def test_stored_entry_carries_the_query_ttl():
    fake = _FakeRedis()
    await CachedQueryEmbedder(_CountingEmbedder(), _cache(fake)).embed_query("q")
    assert set(fake.ttls.values()) == {QUERY_EMBEDDING_TTL_SECONDS}


async def test_redis_down_still_returns_an_embedding():
    """Fail-open end to end: every call reaches the embedder, and nothing raises."""
    embedder = _CountingEmbedder()
    cached = CachedQueryEmbedder(embedder, _cache(_BrokenRedis()))

    assert await cached.embed_query("q") == VECTOR
    assert await cached.embed_query("q") == VECTOR
    assert len(embedder.calls) == 2


async def test_entry_with_the_wrong_dimensionality_is_recomputed():
    """The check that keeps a stale entry out of pgvector.

    An entry written when the model or truncation was different would otherwise be handed to a
    `Vector(768)` comparison and fail inside the SQL query instead of degrading to a recompute.
    """
    fake = _FakeRedis()
    key = query_cache_key("q")
    fake.store[f"test:{key}"] = json.dumps([0.1] * 1536)

    embedder = _CountingEmbedder()
    result = await CachedQueryEmbedder(embedder, _cache(fake)).embed_query("q")

    assert len(result) == 768
    assert embedder.calls == ["q"]
    # ...and the bad entry is replaced, so the next call is a hit.
    assert json.loads(fake.store[f"test:{key}"]) == VECTOR


async def test_non_numeric_entry_is_recomputed():
    fake = _FakeRedis()
    fake.store[f"test:{query_cache_key('q')}"] = json.dumps(["nan"] * 768)

    embedder = _CountingEmbedder()
    assert await CachedQueryEmbedder(embedder, _cache(fake)).embed_query("q") == VECTOR
    assert embedder.calls == ["q"]


async def test_a_bad_embedder_result_is_never_cached():
    """Only what would pass a hit's validation is stored, so a bad vector cannot poison the cache."""
    fake = _FakeRedis()
    embedder = _CountingEmbedder(vector=[0.1] * 10)

    await CachedQueryEmbedder(embedder, _cache(fake)).embed_query("q")

    assert fake.store == {}


async def test_cache_counters_split_hit_from_miss():
    from app.core import metrics

    def outcome(label: str) -> float:
        return metrics.query_embedding_cache_total.labels(outcome=label)._value.get()

    before_hits, before_misses = outcome("hit"), outcome("miss")

    cached = CachedQueryEmbedder(_CountingEmbedder(), _cache(_FakeRedis()))
    await cached.embed_query("counted query")
    await cached.embed_query("counted query")

    assert outcome("miss") - before_misses == 1
    assert outcome("hit") - before_hits == 1


async def test_retrieval_service_wires_the_cache(db_session, monkeypatch):
    """The service must go through the cache — the wiring is the whole feature at the call site.

    Constructing the service builds a `GeminiEmbeddingAdapter`, which needs a key present to construct
    (it makes no call), hence the fake one.
    """
    from app.ai import embedding
    from app.services.retrieval_service import RetrievalService

    monkeypatch.setattr(embedding.settings, "gemini_api_key", "fake-key-for-tests")

    service = RetrievalService(db_session)
    assert isinstance(service.embedding_adapter, CachedQueryEmbedder)


@pytest.mark.parametrize("query", ["", "   "])
async def test_empty_query_is_still_keyed_consistently(query):
    """Not special-cased: whether an empty query is worth embedding is the caller's decision, and the
    cache must not crash on one."""
    embedder = _CountingEmbedder()
    cached = CachedQueryEmbedder(embedder, _cache(_FakeRedis()))

    await cached.embed_query(query)
    await cached.embed_query(query)

    assert len(embedder.calls) == 1
