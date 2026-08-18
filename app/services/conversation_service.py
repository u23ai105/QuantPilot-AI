"""Conversation service — application-level orchestration."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.models.conversation import Conversation, Message
from app.repositories.conversation_repo import ConversationRepository


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.repo = ConversationRepository(session)

    async def create_conversation(self, user_id: uuid.UUID, title: str | None = None) -> Conversation:
        return await self.repo.create_conversation(user_id, title)

    async def get_conversation(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        """Get a conversation, verifying ownership."""
        conv = await self.repo.get_by_id(conversation_id)
        if not conv:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        if conv.user_id != user_id:
            raise AuthorizationError("Not authorized to access this conversation")
        return conv

    async def get_messages(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
        """Get messages for a conversation, verifying ownership."""
        await self.get_conversation(conversation_id, user_id)
        return await self.repo.get_messages(conversation_id)

    async def add_user_message(self, conversation_id: uuid.UUID, content: str) -> Message:
        return await self.repo.add_message(
            conversation_id=conversation_id,
            role="USER",
            content=content,
        )

    async def add_assistant_message(
        self,
        conversation_id: uuid.UUID,
        content: str,
        tool_calls_json: dict | None = None,
        citations_json: list | None = None,
    ) -> Message:
        return await self.repo.add_message(
            conversation_id=conversation_id,
            role="ASSISTANT",
            content=content,
            tool_calls_json=tool_calls_json,
            citations_json=citations_json,
        )

    async def list_conversations(self, user_id: uuid.UUID) -> list[Conversation]:
        return await self.repo.list_for_user(user_id)
