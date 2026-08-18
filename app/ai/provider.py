"""Gemini LLM adapter — isolates Google Generative AI SDK from application code."""

import structlog
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings

logger = structlog.get_logger(__name__)


class GeminiLLMAdapter:
    """Concrete Gemini implementation.

    This is NOT a multi-provider abstraction.  It is a single adapter that
    keeps Gemini SDK imports out of domain/service code so that application
    services never ``import google.generativeai`` directly.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ):
        self._api_key = api_key or settings.gemini_api_key
        self._model_name = model_name or settings.gemini_model
        self._temperature = temperature if temperature is not None else settings.gemini_temperature
        self._max_output_tokens = max_output_tokens or settings.gemini_max_output_tokens

        if not self._api_key:
            logger.warning("gemini_api_key_missing", hint="Set GEMINI_API_KEY in .env")

        self._model = ChatGoogleGenerativeAI(
            model=self._model_name,
            google_api_key=self._api_key,
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
        )

    @property
    def model(self) -> ChatGoogleGenerativeAI:
        """Return the raw LangChain chat model (unbound)."""
        return self._model

    def bind_tools(self, tools: list) -> ChatGoogleGenerativeAI:
        """Return a copy of the model with tool schemas bound for function calling."""
        return self._model.bind_tools(tools)
