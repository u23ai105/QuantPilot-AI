import os

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.user import User


@pytest.mark.asyncio
async def test_upload_document_invalid_mime(client: AsyncClient, test_user_token: str):
    files = {"file": ("test.txt", b"not a pdf", "text/plain")}
    response = await client.post(
        "/api/v1/documents",
        files=files,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 400
    assert "Only PDF files" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_document_invalid_magic_bytes(client: AsyncClient, test_user_token: str):
    files = {"file": ("test.pdf", b"still not a pdf", "application/pdf")}
    response = await client.post(
        "/api/v1/documents",
        files=files,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 400
    assert "Invalid PDF format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_document_success(client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    user_id = test_user.id
    pdf_content = b"%PDF-1.4\n%EOF"
    files = {"file": ("sample.pdf", pdf_content, "application/pdf")}
    response = await client.post(
        "/api/v1/documents",
        files=files,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["filename"] == "sample.pdf"
    assert data["status"] == "PROCESSING"

    # Verify db
    from sqlalchemy import select

    res = await db_session.execute(select(Document).where(Document.id == data["id"]))
    doc = res.scalars().first()
    assert doc is not None
    assert doc.user_id == user_id
    assert os.path.exists(doc.storage_path)

    # Clean up local file
    os.remove(doc.storage_path)
