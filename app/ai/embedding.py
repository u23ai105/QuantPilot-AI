from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import SecretStr

from app.core.config import settings


class GeminiEmbeddingAdapter:
    """Adapter for Google Gemini Embedding API.

    Uses `gemini-embedding-2` model and enforces exactly 768 dimensions.
    """

    def __init__(self):
        self.embeddings_doc = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-2",
            google_api_key=SecretStr(settings.gemini_api_key),
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768,
        )
        self.embeddings_query = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-2",
            google_api_key=SecretStr(settings.gemini_api_key),
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # For gemini-embedding-2 we should override the model.
        # Actually GoogleGenerativeAIEmbeddings doesn't technically support gemini-embedding-2 if it's not a real model,
        # but wait, gemini-embedding-2 doesn't exist? Wait, maybe "models/text-embedding-004" is what they meant,
        # NO! The user explicitly said:
        # "Do NOT use text-embedding-004." (Must use `gemini-embedding-2`).
        # I will strictly use `models/gemini-embedding-2` because that's the explicit instruction.

        # The prompt says: "Implement Gemini embedding adapter using the approved embedding model/configuration."
        # The schema metadata says: `embedding_model: gemini-embedding-2`

        # We will use the GoogleGenerativeAIEmbeddings class and pass `model="models/gemini-embedding-2"`.
        # However, to be safe under concurrency and network boundaries, we use aio.

        vectors = await self.embeddings_doc.aembed_documents(texts)
        for v in vectors:
            if len(v) != 768:
                raise ValueError(f"Invalid embedding dimension: expected 768, got {len(v)}")
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vector = await self.embeddings_query.aembed_query(text)
        if len(vector) != 768:
            raise ValueError(f"Invalid embedding dimension: expected 768, got {len(vector)}")
        return vector
