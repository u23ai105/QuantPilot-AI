import asyncio
import logging
import re
from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import SecretStr

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Exported so the query-embedding cache can key on them: a vector produced by a different model or at a
#: different dimensionality is not interchangeable with one produced by these, so both belong in the key.
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


def resolve_gemini_embedding_model(model: str | None = None) -> str:
    """Normalize Gemini embedding model names.

    Supports aliases such as 'gemini-embedding-2', 'gemini-embedding-001',
    and standard canonical names like 'models/gemini-embedding-001'.
    """
    selected = model or settings.gemini_embedding_model
    if selected in ("gemini-embedding-2", "models/gemini-embedding-2"):
        # Official Gemini Embedding 2 / text-embedding-004
        return "models/text-embedding-004"
    if selected in ("gemini-embedding-001", "models/gemini-embedding-001"):
        return "models/gemini-embedding-001"
    if not selected.startswith("models/"):
        return f"models/{selected}"
    return selected


class GeminiEmbeddingAdapter:
    """Adapter for Google Gemini Embedding API.

    Uses Gemini embedding models with Matryoshka output reduced to
    768 dimensions (``output_dimensionality=768``) to match the ``Vector(768)``
    column used for storage and cosine similarity search.
    """

    def __init__(self, model: str | None = None):
        self.model_name = resolve_gemini_embedding_model(model)
        self.dimensions = EMBEDDING_DIMENSIONS

        self.embeddings_doc = GoogleGenerativeAIEmbeddings(
            model=self.model_name,
            google_api_key=SecretStr(settings.gemini_api_key),
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=self.dimensions,
        )
        self.embeddings_query = GoogleGenerativeAIEmbeddings(
            model=self.model_name,
            google_api_key=SecretStr(settings.gemini_api_key),
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=self.dimensions,
        )

    async def embed_documents(self, texts: list[str], batch_size: int = 50) -> list[list[float]]:
        """Embed a list of document texts with client-side batching and backoff for rate limits."""
        all_vectors: list[list[float]] = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            max_attempts = 5

            for attempt in range(max_attempts):
                try:
                    vectors = await self.embeddings_doc.aembed_documents(batch)
                    for v in vectors:
                        if len(v) != self.dimensions:
                            raise ValueError(f"Invalid embedding dimension: expected {self.dimensions}, got {len(v)}")
                    all_vectors.extend(vectors)
                    logger.info("Embedded batch %d/%d (%d/%d total chunks)", batch_num, total_batches, len(all_vectors), len(texts))
                    break
                except Exception as e:
                    err_str = str(e)
                    is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate limit" in err_str.lower()
                    if is_rate_limit:
                        m = re.search(r"retry\s+(?:after|in)\s+([\d\.]+)\s*s?", err_str, re.I) or re.search(
                            r"retryDelay[\'\"]?\s*:\s*[\'\"]?([\d\.]+)", err_str, re.I
                        )
                        raw_delay = float(m.group(1)) if m else 60.0
                        # If Google requests a delay > 65s (e.g. 38556s = 10.7 hours), daily quota is exhausted.
                        # Do not sleep for hours inside the task; fail fast so the UI and user are informed.
                        if raw_delay > 65.0 or "daily" in err_str.lower() or "per day" in err_str.lower():
                            raise RuntimeError(
                                f"Gemini embedding daily quota exceeded (Google retryDelay: {raw_delay:.0f}s). "
                                "Free tier allows 1,000 texts/day. Please switch to local embedding or retry when quota resets."
                            )

                        if attempt < max_attempts - 1:
                            delay = min(raw_delay + 1.0, 60.0)
                            logger.warning(
                                "Embedding rate limit hit (batch %d/%d, attempt %d/%d). Backing off %.1fs: %s",
                                batch_num,
                                total_batches,
                                attempt + 1,
                                max_attempts,
                                delay,
                                e,
                            )
                            await asyncio.sleep(delay)
                        else:
                            raise
                    else:
                        raise

            # Courtesy delay between batches to stay within API rate limits
            if i + batch_size < len(texts):
                await asyncio.sleep(0.5)

        return all_vectors

    async def embed_query(self, text: str) -> list[float]:
        vector = await self.embeddings_query.aembed_query(text)
        if len(vector) != self.dimensions:
            raise ValueError(f"Invalid embedding dimension: expected {self.dimensions}, got {len(vector)}")
        return vector


class LocalEmbeddingAdapter:
    """Local CPU ONNX embeddings via FastEmbed (BAAI/bge-base-en-v1.5).

    Produces normalized 768-dimensional vectors directly on CPU.
    Zero external API calls, zero rate limits, unlimited usage.
    """

    _model_instance: Any = None

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5"):
        self.model_name = model_name
        self.dimensions = EMBEDDING_DIMENSIONS

    def _get_embedder(self):
        if LocalEmbeddingAdapter._model_instance is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as err:
                raise RuntimeError(
                    "FastEmbed is not installed. Run `pip install fastembed` to use local embeddings, or set EMBEDDING_PROVIDER=gemini."
                ) from err
            logger.info("Initializing LocalEmbeddingAdapter with model '%s' (threads=2)...", self.model_name)
            # Limit ONNX runtime thread pool to 2 threads to prevent massive memory spikes in containers
            LocalEmbeddingAdapter._model_instance = TextEmbedding(model_name=self.model_name, threads=2)
        return LocalEmbeddingAdapter._model_instance

    async def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Embed a list of document texts locally using ONNX runtime in a background thread."""
        embedder = self._get_embedder()

        def _run() -> list[list[float]]:
            results: list[list[float]] = []
            step = 64
            for i in range(0, len(texts), step):
                batch_texts = texts[i : i + step]
                batch_embeddings = list(embedder.embed(batch_texts, batch_size=batch_size))
                results.extend([vec.tolist() for vec in batch_embeddings])
            return results

        vectors = await asyncio.to_thread(_run)
        for v in vectors:
            if len(v) != self.dimensions:
                raise ValueError(f"Invalid local embedding dimension: expected {self.dimensions}, got {len(v)}")
        logger.info("Locally embedded %d chunks in batches of %d", len(vectors), batch_size)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query locally."""
        embedder = self._get_embedder()

        def _run() -> list[float]:
            embeddings = list(embedder.embed([text]))
            return embeddings[0].tolist()

        vector = await asyncio.to_thread(_run)
        if len(vector) != self.dimensions:
            raise ValueError(f"Invalid local embedding dimension: expected {self.dimensions}, got {len(vector)}")
        return vector


def get_embedding_adapter(
    provider: str | None = None,
    model: str | None = None,
) -> LocalEmbeddingAdapter | GeminiEmbeddingAdapter:
    """Factory returning the configured embedding adapter.

    Args:
        provider: "local" (default) or "gemini"
        model: Model name override (e.g. "BAAI/bge-base-en-v1.5", "models/gemini-embedding-001", "gemini-embedding-2")
    """
    selected_provider = provider or settings.embedding_provider
    if selected_provider == "local":
        return LocalEmbeddingAdapter(model_name=model or "BAAI/bge-base-en-v1.5")
    elif selected_provider == "gemini":
        return GeminiEmbeddingAdapter(model=model or settings.gemini_embedding_model)
    else:
        raise ValueError(f"Unknown embedding provider '{selected_provider}'. Allowed: 'local', 'gemini'.")
