from typing import Sequence

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.documents import DocumentResponse
from app.services.document_service import DocumentService
from app.workers.embedding_task import embed_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentResponse,
    summary="Upload a PDF",
    description="Accepts a PDF and queues it for text extraction, chunking and embedding. 202, not 201: the row comes "
    "back immediately with `status: PROCESSING` while a Celery worker does the slow part, so poll "
    "`GET /documents/{document_id}` until the status becomes `READY` (or `FAILED`, which fills in "
    "`error_message`) before searching it.\n\n"
    "Must be a real PDF — the content type, a non-empty body, the 50 MB ceiling and the `%PDF-` magic bytes are "
    "all checked, so a renamed `.docx` is rejected rather than stored. The file is written under a generated "
    "UUID name; `filename` keeps the original only for display. Rate limited to 10 uploads per minute per "
    "caller.",
    responses={
        400: {"description": "Not a PDF, empty, or larger than 50 MB"},
        429: {"description": "Rate limit exceeded — see `Retry-After`"},
    },
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    service = DocumentService(session)
    doc = await service.ingest_document(current_user.id, file)

    # Dispatch Celery task
    embed_document.delay(doc.id)

    return doc


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List your documents",
    description="Every document owned by the caller with its current `status`, so a UI can show which uploads are "
    "still `PROCESSING`. Scoped to the authenticated user.",
)
async def list_documents(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Sequence[DocumentResponse]:
    service = DocumentService(session)
    return await service.list_documents(current_user.id)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a document",
    description="One document's metadata, including `page_count` and `processed_at` once ingestion finished. This is "
    "the endpoint to poll after an upload: `status` moves `PROCESSING → READY`, or `FAILED` with "
    "`error_message` set.",
    responses={
        403: {"description": "Document belongs to another user"},
        404: {"description": "No such document"},
    },
)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    service = DocumentService(session)
    return await service.get_document(current_user.id, document_id)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
    description="Removes the document, its stored PDF and its embedded chunks, so it stops appearing in retrieval. "
    "Returns 204 with no body. Deleting the file from disk is best effort — a missing or unreadable file "
    "does not block the database delete.",
    responses={
        403: {"description": "Document belongs to another user"},
        404: {"description": "No such document"},
    },
)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = DocumentService(session)
    await service.delete_document(current_user.id, document_id)


@router.get(
    "/{document_id}/search",
    summary="Search inside one document",
    description="Vector similarity search over a single document's chunks, returning the `top_k` closest with their "
    "page numbers and scores. Useful for inspecting what retrieval would feed the agent, without spending a "
    "chat turn — the agent's own `search_documents` tool covers all of your documents by default.\n\n"
    "The query is embedded with Gemini (cached in Redis, so repeating a query costs no quota) and compared "
    "against the stored chunk vectors. A document that is not `READY` yet simply has no chunks and returns "
    "an empty list.",
    responses={
        403: {"description": "Document belongs to another user"},
        404: {"description": "No such document"},
        502: {"description": "The embedding provider failed, so the query could not be vectorized"},
    },
)
async def search_document_chunks(
    document_id: int,
    query: str = Query(..., description="Natural-language question; it is embedded and compared against chunk vectors."),
    top_k: int = Query(5, description="How many chunks to return, closest first."),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
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
