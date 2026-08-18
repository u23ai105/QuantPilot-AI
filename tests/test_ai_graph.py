"""Tests for the LangGraph agent graph routing logic.

Uses mocked LLM responses — no live Gemini API required.
"""

from langchain_core.messages import AIMessage, HumanMessage

from app.ai.graph import should_continue


def test_should_continue_with_tool_calls():
    """When the last message has tool_calls, route to tool_node."""
    msg = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": "get_market_data", "args": {"symbol": "AAPL"}}],
    )
    state = {"messages": [HumanMessage(content="hi"), msg]}
    assert should_continue(state) == "tool_node"


def test_should_continue_without_tool_calls():
    """When the last message has no tool_calls, route to END."""
    msg = AIMessage(content="Here is the answer.")
    state = {"messages": [HumanMessage(content="hi"), msg]}
    result = should_continue(state)
    assert result == "__end__"


def test_should_continue_empty_tool_calls():
    """Empty tool_calls list should route to END."""
    msg = AIMessage(content="Answer", tool_calls=[])
    state = {"messages": [HumanMessage(content="hi"), msg]}
    result = should_continue(state)
    assert result == "__end__"
