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

from app.ai.model_registry import LLMConfigurationError
from app.ai.service import AgentService
from app.api.deps import get_current_user, get_db_session
from app.core.exceptions import DataProviderError
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


class SSEResponse(StreamingResponse):
    """A `StreamingResponse` that carries its media type on the class.

    `StreamingResponse.media_type` is `None`, so FastAPI would otherwise document the streaming
    endpoint as returning `application/json` — the one thing it never returns.
    """

    media_type = "text/event-stream"


# Singleton agent service (constructed once, reused across requests)
_agent_service: AgentService | None = None


def _get_agent_service() -> AgentService:
    """Lazily construct the singleton, reporting invalid provider settings as a 502."""
    global _agent_service
    if _agent_service is None:
        try:
            _agent_service = AgentService()
        except LLMConfigurationError as exc:
            raise DataProviderError(f"AI agent unavailable: {exc}") from exc
    return _agent_service


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=201,
    summary="Start a conversation",
    description="Creates an empty conversation and returns its id, which every later message is posted to. `title` is "
    "optional and purely a label.\n\n"
    "A conversation is the unit of memory: the agent reloads this conversation's full message history from "
    "Postgres on every turn, so posting to a new id starts the agent with no prior context.",
)
async def create_conversation(
    data: ConversationCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    service = ConversationService(session)
    conv = await service.create_conversation(user.id, data.title)
    return conv


@router.post(
    "/{conversation_id}/messages",
    response_class=SSEResponse,
    summary="Send a message (SSE stream)",
    description="Posts a user message and streams the agent's reply as Server-Sent Events. The response is "
    "`text/event-stream`, not JSON — `EventSource` cannot be used because this is a POST, so read the body "
    "as a stream and split on a blank line.\n\n"
    "Five event types are emitted, each `event: <name>` with a JSON `data:` payload:\n\n"
    "- `tool_start` — `{tool, args}`, the agent is calling one of its tools\n"
    "- `tool_end` — `{tool, result_summary}`, truncated to 200 characters; a failed tool also arrives here, with "
    "the summary prefixed `Error:` (the agent sees the failure and recovers rather than aborting the turn)\n"
    "- `token` — `{content}`, an incremental chunk of the answer; concatenate them in order\n"
    "- `error` — `{message}`, a generic message; the specific cause is logged server-side, not returned\n"
    "- `done` — always last, closing the turn\n\n"
    "Both the user message and the finished reply are persisted, so the next turn sees them. Rate limited to 20 "
    "requests per minute per caller, this being the endpoint that spends chat-model quota. Disconnecting cancels the "
    "turn server-side.",
    responses={
        200: {"description": "SSE stream of `tool_start` / `tool_end` / `token` / `error` / `done` events", "content": {"text/event-stream": {}}},
        403: {"description": "Conversation belongs to another user"},
        404: {"description": "No such conversation"},
        422: {"description": "`content` is empty or longer than 10000 characters"},
        429: {"description": "Rate limit exceeded — see `Retry-After`"},
        502: {"description": "The selected provider/model is invalid or its GEMINI_API_KEY/NVIDIA_API_KEY is not configured"},
    },
)
async def send_message(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
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

    return SSEResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=MessagesListResponse,
    summary="Get conversation history",
    description="The full message history in order, user and assistant turns alike — this is what the chat UI renders "
    "on reload, since the stream itself is not replayable. Document citations are inline in the answer text in "
    "the form `[Source: <filename>, Page: <n>]`; the `citations_json` column is reserved and currently always "
    "null.",
    responses={
        403: {"description": "Conversation belongs to another user"},
        404: {"description": "No such conversation"},
    },
)
async def get_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    service = ConversationService(session)
    messages = await service.get_messages(conversation_id, user.id)
    return MessagesListResponse(
        conversation_id=conversation_id,
        messages=[MessageResponse.model_validate(m) for m in messages],
    )
