"""search_documents tool — STUB for Phase 4.

Only the tool contract/interface is implemented.  The actual RAG
pipeline (PDF parsing, embeddings, pgvector retrieval, citations) is
deferred to Phase 5.

In Phase 4 this tool returns a controlled "not yet available" result.
It does NOT pretend documents were searched.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.ai.tools.schemas import SearchDocumentsInput


@tool(args_schema=SearchDocumentsInput)
async def search_documents(
    query: str,
    document_id: int | None = None,
    **kwargs,
) -> dict:
    """Search uploaded financial documents for relevant information.

    Currently not available — document search will be enabled in a future
    update.  Do not claim that documents were searched.
    """
    return {
        "query": query,
        "results": [],
        "count": 0,
        "status": "UNAVAILABLE",
        "message": ("Document search is not yet available.  This feature will be enabled when document upload and RAG are implemented."),
    }
