from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.ai.tools._context import _current_user_id, get_db_session_for_tool
from app.ai.tools.schemas import SearchDocumentsInput
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


@tool(args_schema=SearchDocumentsInput)
async def search_documents(
    query: str,
    document_id: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search uploaded financial documents for relevant information.

    Uses semantic search to find chunks of text matching the query.
    Always use this tool when answering questions about specific documents.
    """
    user_id = _current_user_id.get()
    if not user_id:
        return {"error": "Authentication required to search documents."}

    session = await get_db_session_for_tool()
    if not session:
        return {"error": "Database session not available."}

    service = RetrievalService(session)

    try:
        results = await service.search(
            user_id=user_id,
            query=query,
            limit=5,
            document_id=document_id,
        )

        if not results:
            return {
                "query": query,
                "results": [],
                "count": 0,
                "status": "UNAVAILABLE",
                "message": "No relevant information found in the available documents.",
            }

        return {
            "query": query,
            "results": [r.model_dump() for r in results],
            "count": len(results),
            "status": "SUCCESS",
        }

    except Exception as e:
        logger.error(f"Error in search_documents tool: {e}")
        return {"query": query, "results": [], "count": 0, "status": "ERROR", "message": f"An error occurred while searching documents: {str(e)}"}
    finally:
        await session.close()
