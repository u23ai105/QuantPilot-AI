"""Tool execution context — provides DB sessions and user context for tools.

Tools execute inside the LangGraph graph which is invoked from the
AgentService.  They need fresh DB sessions since the request-scoped
session from FastAPI may not be available in the async tool context.
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker

# Context variable holding the authenticated user ID during tool execution.
_current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)
_current_embedding_provider: ContextVar[str | None] = ContextVar("current_embedding_provider", default=None)
_current_embedding_model: ContextVar[str | None] = ContextVar("current_embedding_model", default=None)


def set_current_user_id(user_id: UUID) -> None:
    """Set the authenticated user ID for the current tool execution context."""
    _current_user_id.set(user_id)


def set_current_embedding_config(provider: str | None, model: str | None) -> None:
    """Set the active embedding provider and model for document search tools."""
    _current_embedding_provider.set(provider)
    _current_embedding_model.set(model)


def get_current_user_id() -> UUID:
    """Get the authenticated user ID.  Raises if not set."""
    uid = _current_user_id.get()
    if uid is None:
        raise RuntimeError("No authenticated user in tool context")
    return uid


def get_current_embedding_config() -> tuple[str | None, str | None]:
    """Get the active embedding provider and model."""
    return _current_embedding_provider.get(), _current_embedding_model.get()


async def get_db_session_for_tool() -> AsyncSession:
    """Create a fresh async DB session for tool execution."""
    return async_session_maker()
