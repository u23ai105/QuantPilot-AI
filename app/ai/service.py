"""Agent service — entry point for AI agent interactions.

Constructs the LangGraph graph, invokes it with streaming, persists
messages, and yields SSE events.  Per AI_ARCHITECTURE.md §9.
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.ai.graph import build_graph
from app.ai.llm_factory import create_chat_model
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.tools._context import set_current_user_id
from app.ai.tools.backtest import run_backtest
from app.ai.tools.documents import search_documents
from app.ai.tools.indicators import calculate_indicators
from app.ai.tools.market_data import get_market_data
from app.ai.tools.performance import get_performance_metrics
from app.services.conversation_service import ConversationService

logger = structlog.get_logger(__name__)

# All five approved tools
ALL_TOOLS = [
    get_market_data,
    calculate_indicators,
    run_backtest,
    get_performance_metrics,
    search_documents,
]


class StreamEvent:
    """Structured SSE event for the streaming response."""

    def __init__(self, event: str, data: dict | str):
        self.event = event
        self.data = data

    def to_sse(self) -> str:
        data_str = json.dumps(self.data, default=str) if isinstance(self.data, dict) else self.data
        return f"event: {self.event}\ndata: {data_str}\n\n"


class AgentService:
    """Entry point for AI agent interactions.

    Responsibilities:
    - Construct the selected chat model with bound tools
    - Create the LangGraph graph
    - Invoke graph execution with streaming
    - Inject authenticated user context into tool execution

    The graph is compiled **without** a checkpointer. Conversation memory is the
    `conversations`/`messages` tables: `handle_message` reloads the full history from
    Postgres and passes it in on every turn, so a checkpointer adds nothing and actively
    hurts — an in-process `MemorySaver` isn't shared across workers or replicas (so it is
    useless the moment there is more than one), it is unbounded (every thread's history is
    retained for the process lifetime), and because `add_messages` merges by message id
    while the DB-rebuilt messages get fresh ids each turn, the checkpointed thread
    accumulated a duplicate copy of the whole conversation on every request.
    """

    def __init__(self):
        self._model = create_chat_model()
        self._tools = ALL_TOOLS
        self._model_with_tools = self._model.bind_tools(self._tools)
        self._graph = build_graph(self._model_with_tools, self._tools)
        self._compiled = self._graph.compile()

    async def handle_message(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        conversation_service: ConversationService,
    ) -> AsyncIterator[StreamEvent]:
        """Process a user message through the LangGraph agent.

        1. Persist user message to database
        2. Load conversation history from DB
        3. Set authenticated user context for tools
        4. Invoke LangGraph with streaming
        5. Yield stream events (tool_start, tool_end, token, done)
        6. Persist assistant response to database
        """
        # 1. Persist user message
        await conversation_service.add_user_message(conversation_id, content)

        # 2. Load conversation history from DB and build LangChain messages
        db_messages = await conversation_service.get_messages(conversation_id, user_id)
        langchain_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in db_messages:
            if msg.role == "USER":
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "ASSISTANT":
                langchain_messages.append(AIMessage(content=msg.content))

        # 3. Set authenticated user context for tool authorization
        set_current_user_id(user_id)

        # 4. Invoke LangGraph with streaming. No thread_id: without a checkpointer there is no
        # thread to resume, so the ids serve only to correlate this run in traces/logs.
        config = {"metadata": {"conversation_id": str(conversation_id), "user_id": str(user_id)}}
        full_response = ""

        logger.info(
            "agent_invoke_start",
            conversation_id=str(conversation_id),
            user_id=str(user_id),
            message_count=len(langchain_messages),
        )

        try:
            async for event in self._compiled.astream_events(
                {"messages": langchain_messages},
                config=config,
                version="v2",
            ):
                kind = event.get("event", "")

                # Tool start
                if kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    logger.info("tool_start", tool=tool_name)
                    yield StreamEvent(
                        "tool_start",
                        {
                            "tool": tool_name,
                            "args": tool_input,
                        },
                    )

                # Tool end
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    output = event.get("data", {}).get("output", "")
                    # Summarize for SSE (don't send full data)
                    if isinstance(output, str):
                        try:
                            parsed = json.loads(output)
                            summary = _summarize_tool_result(tool_name, parsed)
                        except json.JSONDecodeError:
                            summary = output[:200]
                    else:
                        summary = str(output)[:200]
                    logger.info("tool_end", tool=tool_name)
                    yield StreamEvent(
                        "tool_end",
                        {
                            "tool": tool_name,
                            "result_summary": summary,
                        },
                    )

                # Tool error
                elif kind == "on_tool_error":
                    tool_name = event.get("name", "unknown")
                    error = event.get("data", {}).get("error", "Unknown error")
                    logger.warning("tool_error_event", tool=tool_name, error=str(error))
                    yield StreamEvent(
                        "tool_end",
                        {
                            "tool": tool_name,
                            "result_summary": f"Error: {str(error)}",
                        },
                    )

                # LLM token streaming
                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if (
                        chunk is not None
                        and getattr(chunk, "content", None)
                        and not getattr(chunk, "tool_calls", None)
                        and not getattr(chunk, "tool_call_chunks", None)
                    ):
                        text = _extract_text(chunk.content)
                        if text:
                            full_response += text
                            yield StreamEvent("token", {"content": text})

        except Exception as exc:
            logger.error(
                "agent_invoke_error",
                conversation_id=str(conversation_id),
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", None),
            )
            yield StreamEvent("error", {"message": "An error occurred processing your request."})
            return

        # 5. Persist assistant response
        if full_response:
            await conversation_service.add_assistant_message(conversation_id, full_response)

        logger.info(
            "agent_invoke_end",
            conversation_id=str(conversation_id),
            response_length=len(full_response),
        )

        yield StreamEvent("done", {"message_id": None})


def _extract_text(content: str | list | None) -> str:
    """Flatten a streamed chunk's content into plain answer text.

    Gemini streams ``content`` as a list of blocks rather than a bare string
    (e.g. ``[{"type": "text", "text": "...", "index": 0}]``), and also emits
    non-answer blocks such as empty-text thought signatures.  Only ``text``
    blocks contribute to the visible answer.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type", "text") == "text" and not block.get("thought"):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _summarize_tool_result(tool_name: str, result: dict) -> str:
    """Create a brief summary of a tool result for the SSE stream."""
    if "count" in result:
        return f"Retrieved {result['count']} items"
    if "status" in result:
        return f"Status: {result['status']}"
    if "error" in result:
        return f"Error: {result['error']}"
    return "Completed"
