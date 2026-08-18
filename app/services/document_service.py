import os
import uuid
from typing import Sequence
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.repositories.document_repo import DocumentRepository


class DocumentService:
    def __init__(self, session: AsyncSession, storage_dir: str = "uploads"):
        self.repo = DocumentRepository(session)
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    async def ingest_document(self, user_id: UUID, file: UploadFile) -> Document:
        # 1. Validation
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename missing")

        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # Read into memory for initial validation
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")

        if file_size > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File exceeds 50MB limit")

        # Magic byte validation for PDF (%PDF-)
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF format")

        # 2. Secure storage
        # Generate safe UUID filename to prevent path traversal
        safe_filename = f"{uuid.uuid4()}.pdf"
        storage_path = os.path.join(self.storage_dir, safe_filename)

        # Double check containment
        if not os.path.abspath(storage_path).startswith(os.path.abspath(self.storage_dir)):
            raise HTTPException(status_code=500, detail="Storage path error")

        # Write to disk
        with open(storage_path, "wb") as f:
            f.write(content)

        # 3. Create Database Record
        doc = Document(
            user_id=user_id,
            filename=file.filename,  # Original filename for display
            storage_path=storage_path,
            file_size=file_size,
            status="PROCESSING",
        )

        created_doc = await self.repo.create(doc)

        # Dispatch to Celery happens in the router after this returns.
        return created_doc

    async def list_documents(self, user_id: UUID) -> Sequence[Document]:
        return await self.repo.list_by_user(user_id)

    async def get_document(self, user_id: UUID, document_id: int) -> Document:
        doc = await self.repo.get(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this document")
        return doc

    async def delete_document(self, user_id: UUID, document_id: int) -> None:
        doc = await self.get_document(user_id, document_id)

        # Cleanup local file
        if os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
            except Exception:
                pass  # Best effort cleanup

        await self.repo.delete(document_id)
