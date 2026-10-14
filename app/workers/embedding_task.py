import asyncio
import gc
import logging
from datetime import datetime, timezone

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.embedding import get_embedding_adapter
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

                page_count = len(pages)
                doc.page_count = page_count
                doc.status = "PROCESSING"
                doc.error_message = None
                await repo.update(doc)
                del pages
                gc.collect()

                # 3. Embedding (supports local FastEmbed or Gemini Embedding 2)
                texts_to_embed = [c["chunk_text"] for c in chunks_data]
                adapter = get_embedding_adapter()
                logger.info("Starting embedding of %d chunks using %s...", len(texts_to_embed), adapter.__class__.__name__)
                vectors = await adapter.embed_documents(texts_to_embed)
                logger.info("Finished embedding, received %d vectors", len(vectors))

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
                del chunks_data
                del texts_to_embed
                del vectors
                gc.collect()

                # Idempotency: clear existing chunks if any
                await repo.clear_chunks(doc.id)

                # Insert new chunks in safe batches
                await repo.bulk_insert_chunks(db_chunks, batch_size=40)
                logger.info("Successfully inserted %d chunks for document %d", len(db_chunks), doc.id)

                # Success
                doc.status = "READY"
                doc.page_count = page_count
                doc.processed_at = datetime.now(timezone.utc)
                doc.error_message = None
                await repo.update(doc)
                logger.info("Document %d marked READY in database", doc.id)

            except ValueError as e:
                # Permanent failure (e.g. invalid dimensions, unreadable PDF)
                doc.status = "FAILED"
                doc.error_message = str(e)
                doc.processed_at = datetime.now(timezone.utc)
                await repo.update(doc)
                logger.error(f"Permanent failure for document {document_id}: {e}")
            except Exception as e:
                logger.error("Transient error processing document %d: %s", document_id, e)
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
        logger.warning(f"Error processing document {document_id}: {exc}")
        exc_msg = str(exc)
        is_quota_exhausted = "daily quota" in exc_msg.lower() or "quota exceeded" in exc_msg.lower()

        if is_quota_exhausted or self.request.retries >= self.max_retries:
            logger.error(f"Permanent or quota failure for document {document_id}; marking as FAILED: {exc}")
            asyncio.run(mark_document_failed(document_id, exc_msg))
            return
        try:
            # Retry with exponential backoff (15s, 30s, 60s) for transient network glitches
            countdown = 15 * (2**self.request.retries)
            self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            asyncio.run(mark_document_failed(document_id, str(exc)))
        except Exception:
            if self.request.retries >= self.max_retries:
                asyncio.run(mark_document_failed(document_id, str(exc)))
            raise


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
