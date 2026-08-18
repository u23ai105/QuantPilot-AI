"""Tests for the Conversations API endpoints.

These tests use the existing Pytest DB fixtures and mock the AgentService
to avoid hitting the live Gemini API during CI runs.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.conversation import Conversation


@pytest.fixture
def mock_agent_service():
    """Mock AgentService to return a canned SSE stream."""
    with patch("app.api.v1.conversations._get_agent_service") as mock_get_agent:
        mock_agent = AsyncMock()

        async def fake_stream(*args, **kwargs):
            from app.ai.service import StreamEvent

            yield StreamEvent("token", {"content": "Hello"})
            yield StreamEvent("token", {"content": " World"})
            yield StreamEvent("done", {"message_id": None})

        mock_agent.handle_message = fake_stream
        mock_get_agent.return_value = mock_agent
        yield mock_agent


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient, test_user_token: str):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    payload = {"title": "Test Chat"}

    response = await client.post("/api/v1/conversations", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Chat"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_messages_empty(client: AsyncClient, test_user_token: str, db_session, test_user):
    # Setup conversation
    headers = {"Authorization": f"Bearer {test_user_token}"}
    conv = Conversation(user_id=test_user.id, title="Empty Chat")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    response = await client.get(f"/api/v1/conversations/{conv.id}/messages", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == str(conv.id)
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_send_message_streaming(
    client: AsyncClient,
    test_user_token: str,
    db_session,
    test_user,
    mock_agent_service,
):
    # Setup conversation
    headers = {"Authorization": f"Bearer {test_user_token}"}
    conv = Conversation(user_id=test_user.id, title="Stream Chat")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    payload = {"content": "Say hello"}

    response = await client.post(f"/api/v1/conversations/{conv.id}/messages", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    # Read SSE lines
    lines = [line for line in response.iter_lines() if line]

    # We expect our mocked stream events
    assert "event: token" in lines[0]
    assert 'data: {"content": "Hello"}' in lines[1]

    assert "event: token" in lines[2]
    assert 'data: {"content": " World"}' in lines[3]

    assert "event: done" in lines[4]
    assert 'data: {"message_id": null}' in lines[5]


@pytest.mark.asyncio
async def test_cross_user_conversation_access_denied(
    client: AsyncClient,
    test_user_token: str,
    db_session,
    test_user,
):
    # Create conversation owned by a DIFFERENT dummy user
    from app.core.security import get_password_hash
    from app.models.user import User

    other_user = User(email="other@example.com", hashed_password=get_password_hash("password123"))
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    conv = Conversation(user_id=other_user.id, title="Private Chat")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    headers = {"Authorization": f"Bearer {test_user_token}"}

    # test_user trying to access other_user's conversation
    response = await client.get(f"/api/v1/conversations/{conv.id}/messages", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTHORIZATION_ERROR"
