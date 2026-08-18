import asyncio
import logging
from datetime import datetime, timezone

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.embedding import GeminiEmbeddingAdapter
from app.core.config import settings
from app.models.document import DocumentChunk
from app.repositories.document_repo import DocumentRepository
from app.services.rag.pdf_extractor import PDFExtractor
from app.services.rag.text_chunker import TextChunker
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def process_document_async(document_id: int) -> None:
    """Async business logic for embedding a document."""
    # Create task-local engine
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
    )
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with AsyncSessionLocal() as session:
            repo = DocumentRepository(session)
            doc = await repo.get(document_id)

            if not doc:
                logger.error(f"Document {document_id} not found.")
                return

            try:
                # 1. Extraction (could fail permanently if PDF is broken)
                pages = PDFExtractor.extract_pages(doc.storage_path)

                # 2. Chunking
                chunker = TextChunker()
                chunks_data = chunker.chunk_pages(pages)

                if not chunks_data:
                    raise ValueError("No extractable text found in PDF.")

                # 3. Embedding (could fail transiently)
                texts_to_embed = [c["chunk_text"] for c in chunks_data]
                adapter = GeminiEmbeddingAdapter()
                vectors = await adapter.embed_documents(texts_to_embed)

                # Prepare chunks
                db_chunks = []
                for chunk_info, vector in zip(chunks_data, vectors, strict=True):
                    db_chunks.append(
                        DocumentChunk(
                            document_id=doc.id,
                            page_number=chunk_info["page_number"],
                            chunk_index=chunk_info["chunk_index"],
                            chunk_text=chunk_info["chunk_text"],
                            embedding=vector,
                        )
                    )

                # Idempotency: clear existing chunks if any
                await repo.clear_chunks(doc.id)

                # Insert new chunks
                await repo.bulk_insert_chunks(db_chunks)

                # Success
                doc.status = "READY"
                doc.page_count = len(pages)
                doc.processed_at = datetime.now(timezone.utc)
                doc.error_message = None
                await repo.update(doc)

            except ValueError as e:
                # Permanent failure (e.g. invalid dimensions, unreadable PDF)
                doc.status = "FAILED"
                doc.error_message = str(e)
                doc.processed_at = datetime.now(timezone.utc)
                await repo.update(doc)
                logger.error(f"Permanent failure for document {document_id}: {e}")
            except Exception as e:
                # Let transient errors (network, API, etc.) bubble up for retry
                # but we shouldn't mark it FAILED yet unless max retries exceeded.
                raise e

    finally:
        # Crucial: Dispose task-local engine
        await engine.dispose()


@celery_app.task(bind=True, max_retries=3)
def embed_document(self, document_id: int):
    """Celery task to embed a document with retries."""
    try:
        asyncio.run(process_document_async(document_id))
    except Exception as exc:
        logger.warning(f"Transient error processing document {document_id}: {exc}")
        try:
            # Retry with exponential backoff
            self.retry(exc=exc, countdown=2**self.request.retries)
        except MaxRetriesExceededError:
            # If max retries exceeded, we must mark as FAILED
            asyncio.run(mark_document_failed(document_id, str(exc)))


async def mark_document_failed(document_id: int, error_message: str):
    engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with AsyncSessionLocal() as session:
            repo = DocumentRepository(session)
            doc = await repo.get(document_id)
            if doc:
                doc.status = "FAILED"
                doc.error_message = f"Max retries exceeded: {error_message}"
                doc.processed_at = datetime.now(timezone.utc)
                await repo.update(doc)
    finally:
        await engine.dispose()
