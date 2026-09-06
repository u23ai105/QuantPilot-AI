from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import SecretStr

from app.core.config import settings

#: Exported so the query-embedding cache can key on them: a vector produced by a different model or at a
#: different dimensionality is not interchangeable with one produced by these, so both belong in the key.
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


class GeminiEmbeddingAdapter:
    """Adapter for Google Gemini Embedding API.

    Uses the ``gemini-embedding-001`` model with Matryoshka output reduced to
    768 dimensions (``output_dimensionality=768``) to match the ``Vector(768)``
    column used for storage and cosine similarity search.
    """

    def __init__(self):
        self.embeddings_doc = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=SecretStr(settings.gemini_api_key),
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIMENSIONS,
        )
        self.embeddings_query = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=SecretStr(settings.gemini_api_key),
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIMENSIONS,
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = await self.embeddings_doc.aembed_documents(texts)
        for v in vectors:
            if len(v) != EMBEDDING_DIMENSIONS:
                raise ValueError(f"Invalid embedding dimension: expected {EMBEDDING_DIMENSIONS}, got {len(v)}")
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vector = await self.embeddings_query.aembed_query(text)
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"Invalid embedding dimension: expected {EMBEDDING_DIMENSIONS}, got {len(vector)}")
        return vector
