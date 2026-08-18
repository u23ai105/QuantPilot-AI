"""Conversation API endpoints.

POST /conversations           — Create a new conversation
POST /conversations/{id}/messages — Send a message (returns SSE stream)
GET  /conversations/{id}/messages — Retrieve message history
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import AgentService
from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.conversations import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    MessagesListResponse,
)
from app.services.conversation_service import ConversationService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Singleton agent service (constructed once, reused across requests)
_agent_service: AgentService | None = None


def _get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Create a new conversation."""
    service = ConversationService(session)
    conv = await service.create_conversation(user.id, data.title)
    return conv


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Send a message and receive an SSE-streamed AI response."""
    conv_service = ConversationService(session)

    # Verify ownership
    await conv_service.get_conversation(conversation_id, user.id)

    agent = _get_agent_service()

    async def event_generator():
        async for event in agent.handle_message(
            conversation_id=conversation_id,
            user_id=user.id,
            content=data.content,
            conversation_service=conv_service,
        ):
            yield event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{conversation_id}/messages", response_model=MessagesListResponse)
async def get_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Retrieve all messages for a conversation."""
    service = ConversationService(session)
    messages = await service.get_messages(conversation_id, user.id)
    return MessagesListResponse(
        conversation_id=conversation_id,
        messages=[MessageResponse.model_validate(m) for m in messages],
    )
