"""Agent state definition for the LangGraph graph.

Intentionally minimal — LangGraph's ``add_messages`` reducer handles
message accumulation automatically.  No custom memory architecture.
"""

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State flowing through the QuantPilot agent graph.

    Attributes:
        messages: The conversation message history.  The ``add_messages``
            reducer appends new messages rather than replacing the list.
    """

    messages: Annotated[list, add_messages]
