"""LangGraph agent graph construction.

Implements the approved graph structure:

    START → agent_node → tool_calls? → tool_node → agent_node → … → END

The graph supports zero, one, or multiple sequential tool calls and
recovers gracefully from tool errors.
"""

from __future__ import annotations

import json

import structlog
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, StateGraph

from app.ai.state import AgentState

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def should_continue(state: AgentState) -> str:
    """Decide whether to route to tool_node or END.

    Per AI_ARCHITECTURE.md §2.4 — if the last message contains tool_calls
    we route to the tool node; otherwise the conversation is complete.
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tool_node"
    return END


# ---------------------------------------------------------------------------
# Safe tool node wrapper
# ---------------------------------------------------------------------------


def create_safe_tool_node(tools: list):
    """Create a tool node that catches exceptions and returns safe error messages.

    Per AI_ARCHITECTURE.md §5.1 — tool failures are formatted as ToolMessage
    with error content so the agent can recover gracefully.
    """
    # Map tool names to tool objects for direct invocation
    tool_map = {tool.name: tool for tool in tools}

    async def safe_tool_node(state: AgentState) -> dict:
        last_message = state["messages"][-1]
        results = []

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call["id"]

            logger.info(
                "tool_call_start",
                tool=tool_name,
                args=tool_args,
            )

            tool = tool_map.get(tool_name)
            if not tool:
                results.append(
                    ToolMessage(
                        content=f"Error: Unknown tool '{tool_name}'.",
                        tool_call_id=tool_call_id,
                    )
                )
                continue

            try:
                result = await tool.ainvoke(tool_args)
                # If result is a dict or list, serialize to JSON string
                if isinstance(result, (dict, list)):
                    content = json.dumps(result, default=str)
                else:
                    content = str(result)
                results.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=tool_call_id,
                    )
                )
                logger.info("tool_call_end", tool=tool_name, success=True)
            except Exception as exc:
                error_msg = f"Error: {exc}"
                results.append(
                    ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_call_id,
                    )
                )
                logger.warning(
                    "tool_call_error",
                    tool=tool_name,
                    error=str(exc),
                )

        return {"messages": results}

    return safe_tool_node


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(model_with_tools, tools: list) -> StateGraph:
    """Construct the compiled LangGraph agent graph.

    Args:
        model_with_tools: The Gemini model with tool schemas bound.
        tools: List of LangChain tool objects.

    Returns:
        A compiled StateGraph ready for invocation.
    """

    async def agent_node(state: AgentState) -> dict:
        """Invoke the LLM with the current message history."""
        response = await model_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent_node", agent_node)
    graph.add_node("tool_node", create_safe_tool_node(tools))

    graph.set_entry_point("agent_node")
    graph.add_conditional_edges(
        "agent_node",
        should_continue,
        {
            "tool_node": "tool_node",
            END: END,
        },
    )
    graph.add_edge("tool_node", "agent_node")

    return graph
