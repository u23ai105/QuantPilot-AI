from typing import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def get(self, document_id: int) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.id == document_id))
        return result.scalars().first()

    async def list_by_user(self, user_id: UUID) -> Sequence[Document]:
        result = await self.session.execute(select(Document).where(Document.user_id == user_id).order_by(Document.uploaded_at.desc()))
        return result.scalars().all()

    async def update(self, document: Document) -> Document:
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def delete(self, document_id: int) -> bool:
        result = await self.session.execute(delete(Document).where(Document.id == document_id))
        await self.session.commit()
        return result.rowcount > 0

    async def clear_chunks(self, document_id: int) -> None:
        """Idempotency: delete any existing chunks for a document."""
        await self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        await self.session.commit()

    async def bulk_insert_chunks(self, chunks: list[DocumentChunk]) -> None:
        if chunks:
            self.session.add_all(chunks)
            await self.session.commit()

    async def search_user_chunks(
        self, user_id: UUID, query_embedding: list[float], limit: int = 5, document_id: int | None = None
    ) -> Sequence[tuple[DocumentChunk, float, str]]:
        """
        Return top-K chunks using cosine similarity for a specific user.
        Returns: [(DocumentChunk, similarity_score, filename), ...]
        """
        similarity = 1 - DocumentChunk.embedding.cosine_distance(query_embedding)

        stmt = (
            select(DocumentChunk, similarity.label("similarity_score"), Document.filename)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.user_id == user_id)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )

        if document_id is not None:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        result = await self.session.execute(stmt)
        return result.all()
