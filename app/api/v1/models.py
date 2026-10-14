"""Model listing and discovery endpoints.

GET /models — List available chat and embedding models.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.ai.model_registry import NIM_MODELS
from app.core.config import settings

router = APIRouter(prefix="/models", tags=["models"])


class ChatModelInfo(BaseModel):
    provider: str
    model: str
    display_name: str
    description: str
    is_default: bool


class EmbeddingModelInfo(BaseModel):
    provider: str
    model: str
    display_name: str
    description: str
    dimensions: int
    is_default: bool


class ModelsListResponse(BaseModel):
    chat_models: list[ChatModelInfo]
    embedding_models: list[EmbeddingModelInfo]
    current_chat_provider: str
    current_chat_model: str
    current_embedding_provider: str


@router.get(
    "",
    response_model=ModelsListResponse,
    summary="List available AI models",
    description="Returns the available chat LLMs (Gemini, NVIDIA NIM) and embedding models (Local FastEmbed, Gemini Embedding 2), "
    "indicating their capabilities and the active defaults.",
)
async def list_models() -> dict[str, Any]:
    nim_models_info = [
        ChatModelInfo(
            provider="nim",
            model=m,
            display_name=f"NVIDIA Nemotron ({m.split('/')[-1]})" if "nemotron" in m else m,
            description="Ultra 550B MoE model hosted on NVIDIA NIM with tool calling support",
            is_default=(settings.llm_provider == "nim" and (settings.llm_model == m or not settings.llm_model)),
        )
        for m in NIM_MODELS
    ]

    chat_models = [
        ChatModelInfo(
            provider="gemini",
            model=settings.gemini_model,
            display_name="Google Gemini (gemini-3.6-flash)",
            description="Fast Google multimodal LLM with streaming tool calling",
            is_default=(settings.llm_provider == "gemini"),
        ),
        *nim_models_info,
    ]

    embedding_models = [
        EmbeddingModelInfo(
            provider="local",
            model="BAAI/bge-base-en-v1.5",
            display_name="Local FastEmbed (BGE-base-en-v1.5)",
            description="Local CPU ONNX embeddings, 768-dim, unlimited usage, no rate limits",
            dimensions=768,
            is_default=(settings.embedding_provider == "local"),
        ),
        EmbeddingModelInfo(
            provider="gemini",
            model=settings.gemini_embedding_model,
            display_name="Google Gemini Embedding 2",
            description="Google cloud embeddings with Matryoshka reduction to 768-dim",
            dimensions=768,
            is_default=(settings.embedding_provider == "gemini"),
        ),
    ]

    return {
        "chat_models": chat_models,
        "embedding_models": embedding_models,
        "current_chat_provider": settings.llm_provider,
        "current_chat_model": settings.llm_model or settings.gemini_model,
        "current_embedding_provider": settings.embedding_provider,
    }
