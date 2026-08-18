from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    user_id: UUID
    filename: str
    file_size: int
    page_count: int | None
    status: str
    error_message: str | None
    uploaded_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ChunkWithCitation(BaseModel):
    document_id: int
    filename: str
    page_number: int
    chunk_index: int
    chunk_text: str
    similarity_score: float

    model_config = ConfigDict(from_attributes=True)
