"""Conversation API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    citations_json: list | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessagesListResponse(BaseModel):
    conversation_id: uuid.UUID
    messages: list[MessageResponse]
