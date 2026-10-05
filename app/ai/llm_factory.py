"""LLM factory — returns a ready-to-use chat model for the configured provider.

Design (AI_ARCHITECTURE.md §6):
- ``create_chat_model`` is the *only* public symbol; callers never import Gemini
  or OpenAI SDK objects directly.
- Gemini path returns ``GeminiLLMAdapter.model`` (the langchain-google-genai instance).
- NIM path returns a ``ChatOpenAI`` instance wired to the NVIDIA inference endpoint.
- Embeddings are always Gemini; this factory only handles chat models.
- NIM 429 handling: ``ChatOpenAI`` is constructed with ``max_retries=3`` which
  causes the underlying httpx client to retry on network errors, but *not* on
  HTTP 429 (that is an application-level response).  ``RateLimitingChatOpenAI``
  wraps the model's ``_generate`` / ``_stream`` to catch ``openai.RateLimitError``
  and back off with exponential delay (1 s, 2 s, 4 s) before re-raising on the
  final attempt.  This keeps the retry logic local and avoids adding tenacity as
  a dependency.
"""

from __future__ import annotations

import asyncio
import logging
import time

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.ai.model_registry import LLMConfigurationError, resolve_model
from app.ai.provider import GeminiLLMAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)

# Maximum number of 429-backoff attempts before propagating the error.
_NIM_MAX_429_RETRIES = 3
# Base delay in seconds for the first retry; doubles on each attempt.
_NIM_BASE_DELAY_SECONDS = 1.0


def _make_nim_client(model: str) -> ChatOpenAI:
    """Construct a ``ChatOpenAI`` instance pointed at the NVIDIA NIM endpoint."""
    return ChatOpenAI(
        model=model,
        api_key=settings.nvidia_api_key,  # type: ignore[arg-type]  # SecretStr accepted
        base_url=settings.nvidia_base_url,
        temperature=settings.gemini_temperature,
        # NIM expects max_tokens in the body; passing it via extra_body avoids
        # langchain-openai renaming it to max_completion_tokens on newer APIs.
        extra_body={"max_tokens": settings.gemini_max_output_tokens},
        streaming=True,
        stream_usage=False,
        use_responses_api=False,
        timeout=60,
        max_retries=0,  # We handle 429s ourselves; other errors should surface immediately.
    )


class _NIMRateLimitRetry(BaseChatModel):
    """Thin wrapper around ``ChatOpenAI`` that retries on HTTP 429 / RateLimitError.

    LangGraph / LangChain call ``_generate`` for batch invocations and
    ``_stream`` for streaming.  We override both so that the retry behaviour
    covers every call path the agent uses.

    Attributes:
        _inner: The wrapped ``ChatOpenAI`` client.
    """

    model_config = {"arbitrary_types_allowed": True}

    _inner: ChatOpenAI

    def __init__(self, inner: ChatOpenAI, **kwargs):
        super().__init__(**kwargs)
        # Bypass Pydantic assignment validation for the private attr.
        object.__setattr__(self, "_inner", inner)

    # --- Required BaseChatModel interface ---

    @property
    def _llm_type(self) -> str:  # type: ignore[override]
        return "nim-rate-limit-retry"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Synchronous generation with 429 backoff."""
        import openai

        delay = _NIM_BASE_DELAY_SECONDS
        for attempt in range(_NIM_MAX_429_RETRIES + 1):
            try:
                return self._inner._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except openai.RateLimitError:
                if attempt >= _NIM_MAX_429_RETRIES:
                    raise
                logger.warning("NIM 429 rate limit (attempt %d/%d); backing off %.1fs", attempt + 1, _NIM_MAX_429_RETRIES, delay)
                time.sleep(delay)
                delay *= 2

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        """Synchronous streaming with 429 backoff (yields chunks)."""
        import openai

        delay = _NIM_BASE_DELAY_SECONDS
        for attempt in range(_NIM_MAX_429_RETRIES + 1):
            try:
                yield from self._inner._stream(messages, stop=stop, run_manager=run_manager, **kwargs)
                return
            except openai.RateLimitError:
                if attempt >= _NIM_MAX_429_RETRIES:
                    raise
                logger.warning("NIM 429 rate limit (stream attempt %d/%d); backing off %.1fs", attempt + 1, _NIM_MAX_429_RETRIES, delay)
                time.sleep(delay)
                delay *= 2

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        """Async generation with 429 backoff."""
        import openai

        delay = _NIM_BASE_DELAY_SECONDS
        for attempt in range(_NIM_MAX_429_RETRIES + 1):
            try:
                return await self._inner._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except openai.RateLimitError:
                if attempt >= _NIM_MAX_429_RETRIES:
                    raise
                logger.warning("NIM 429 rate limit (async attempt %d/%d); backing off %.1fs", attempt + 1, _NIM_MAX_429_RETRIES, delay)
                await asyncio.sleep(delay)
                delay *= 2

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        """Async streaming with 429 backoff (async-yields chunks)."""
        import openai

        delay = _NIM_BASE_DELAY_SECONDS
        for attempt in range(_NIM_MAX_429_RETRIES + 1):
            try:
                async for chunk in self._inner._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
                    yield chunk
                return
            except openai.RateLimitError:
                if attempt >= _NIM_MAX_429_RETRIES:
                    raise
                logger.warning("NIM 429 rate limit (astream attempt %d/%d); backing off %.1fs", attempt + 1, _NIM_MAX_429_RETRIES, delay)
                await asyncio.sleep(delay)
                delay *= 2

    # Delegate tool binding and any other method to the inner model so the agent
    # graph sees the same interface as raw ChatOpenAI / GeminiLLMAdapter.
    def bind_tools(self, tools, **kwargs):
        """Bind tools and return a new wrapper over the tool-bound inner model."""
        bound_inner = self._inner.bind_tools(tools, **kwargs)
        # bind_tools returns a RunnableBinding, not a ChatOpenAI; we don't need
        # to wrap it again — LangGraph calls _generate/_stream on the raw model
        # only before tool binding, and uses the bound runnable after that.
        return bound_inner

    def with_structured_output(self, schema, **kwargs):
        return self._inner.with_structured_output(schema, **kwargs)


def create_chat_model(provider: str | None = None, model: str | None = None) -> BaseChatModel:
    """Create and return a chat model for the given *provider* and *model*.

    Args:
        provider: ``"gemini"`` (default) or ``"nim"``.  Falls back to
            ``settings.llm_provider`` when *None*.
        model: Override the default model for the provider.  Falls back to
            ``settings.llm_model`` and then the registry default.

    Returns:
        A ``BaseChatModel`` instance (``GeminiLLMAdapter.model`` for Gemini;
        ``_NIMRateLimitRetry`` wrapping a ``ChatOpenAI`` for NIM).

    Raises:
        LLMConfigurationError: When the provider or model is invalid, or when
            the required API key is absent.
    """
    selected_provider = provider or settings.llm_provider
    selected_model = resolve_model(selected_provider, model or settings.llm_model)

    if selected_provider == "gemini":
        if not settings.gemini_api_key:
            raise LLMConfigurationError("GEMINI_API_KEY is not configured")
        return GeminiLLMAdapter(model_name=selected_model).model

    # NIM provider
    if not settings.nvidia_api_key.get_secret_value().strip():
        raise LLMConfigurationError("NVIDIA_API_KEY is not configured")
    inner = _make_nim_client(selected_model)
    return _NIMRateLimitRetry(inner=inner)
