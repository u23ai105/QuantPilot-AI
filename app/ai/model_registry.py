"""LLM model registry — allowlist of chat models for each provider.

Design rationale (AI_ARCHITECTURE.md §6):
- Gemini model name is read from settings.gemini_model, never hard-coded here.
- NIM models are an explicit allowlist from the nim_probe.py pass/fail table.
  Only models that passed plain + tool + stream checks are listed.
- Unknown provider or model raises LLMConfigurationError (→ 502 at the API layer).
"""

from app.core.config import settings

# Candidates seen in NVIDIA's catalog but NOT verified (probe timed out or not probed).
# Move one into NIM_MODELS only after it passes scripts/nim_probe.py:
# z-ai/glm-5.3-flash, moonshotai/kimi-k3, deepseek-ai/deepseek-v4.1-flash
NIM_MODELS = ("nvidia/nemotron-3-ultra-550b-a55b",)


class LLMConfigurationError(ValueError):
    """Raised when the provider or model configuration is invalid.

    Caught at the API layer (conversations.py) and surfaced as a 502 so the
    caller knows the AI subsystem is mis-configured rather than experiencing a
    transient failure.
    """


def resolve_model(provider: str, model: str | None = None) -> str:
    """Validate and return the canonical model ID for *provider*.

    Args:
        provider: ``"gemini"`` or ``"nim"``
        model:    Explicit model override; defaults to the first allowed model.

    Returns:
        The validated model ID string.

    Raises:
        LLMConfigurationError: If *provider* is unknown or *model* is not
            on the allowlist for that provider.
    """
    if provider == "gemini":
        allowed = (settings.gemini_model,)
    elif provider == "nim":
        allowed = NIM_MODELS
    else:
        raise LLMConfigurationError(f"Unknown LLM provider '{provider}'. Choose 'gemini' or 'nim'.")

    selected = model or allowed[0]
    if selected not in allowed:
        raise LLMConfigurationError(f"Unknown model '{selected}' for provider '{provider}'. Allowed models: {', '.join(allowed)}.")
    return selected
