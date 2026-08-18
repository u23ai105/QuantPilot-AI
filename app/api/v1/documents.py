from typing import Sequence

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.documents import DocumentResponse
from app.services.document_service import DocumentService
from app.workers.embedding_task import embed_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """Upload a new document for processing and embedding."""
    service = DocumentService(session)
    doc = await service.ingest_document(current_user.id, file)

    # Dispatch Celery task
    embed_document.delay(doc.id)

    return doc


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Sequence[DocumentResponse]:
    """List all documents for the current user."""
    service = DocumentService(session)
    return await service.list_documents(current_user.id)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """Get document details."""
    service = DocumentService(session)
    return await service.get_document(current_user.id, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a document and its chunks."""
    service = DocumentService(session)
    await service.delete_document(current_user.id, document_id)


@router.get("/{document_id}/search")
async def search_document_chunks(
    document_id: int,
    query: str,
    top_k: int = 5,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Search for relevant chunks within a specific document."""
    from app.services.retrieval_service import RetrievalService

    # Ensure user owns document
    doc_service = DocumentService(session)
    await doc_service.get_document(current_user.id, document_id)

    retrieval = RetrievalService(session)
    chunks = await retrieval.search(current_user.id, query, top_k, document_id)
    return [
        {
            "chunk_id": getattr(c, "id", None) or f"{c.document_id}-{c.page_number}-{c.chunk_index}",
            "document_id": c.document_id,
            "page_number": c.page_number,
            "text": c.chunk_text,
            "score": c.similarity_score,
        }
        for c in chunks
    ]
