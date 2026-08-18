from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding import GeminiEmbeddingAdapter
from app.repositories.document_repo import DocumentRepository
from app.schemas.documents import ChunkWithCitation


class RetrievalService:
    def __init__(self, session: AsyncSession):
        self.repo = DocumentRepository(session)
        self.embedding_adapter = GeminiEmbeddingAdapter()

    async def search(self, user_id: UUID, query: str, limit: int = 5, document_id: int | None = None) -> list[ChunkWithCitation]:
        # Enforce document ownership if document_id is provided
        if document_id is not None:
            doc = await self.repo.get(document_id)
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            if doc.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to access this document")
            # If status is not READY, maybe we shouldn't search it, but we can just let it yield 0 chunks
            if doc.status != "READY":
                pass  # Can still try to search if it has chunks, but realistically it's empty

        # Embed query
        try:
            query_embedding = await self.embedding_adapter.embed_query(query)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Embedding provider error: {str(e)}")

        # Search chunks
        # The repo returns a sequence of (DocumentChunk, similarity_score, filename)
        # We must filter by user_id if document_id is None, to prevent searching other users' docs.
        # Wait, the repo method `search_chunks` doesn't filter by user_id!
        # Let's update search_chunks in DocumentRepository or handle it here.
        # It's safer to handle it in DocumentRepository. I'll modify search_chunks.
        results = await self.repo.search_user_chunks(user_id, query_embedding, limit, document_id)

        citations = []
        for chunk, similarity, filename in results:
            citations.append(
                ChunkWithCitation(
                    document_id=chunk.document_id,
                    filename=filename,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.chunk_text,
                    similarity_score=similarity,
                )
            )

        return citations
