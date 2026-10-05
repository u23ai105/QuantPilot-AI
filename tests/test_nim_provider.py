"""Tests for the NIM provider additions: factory selection, model-registry
rejection, tool-call path through the LangGraph agent, and streaming chunk
normalization in AgentService.

All tests use mocked LLM clients — no live Gemini or NVIDIA API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.ai.model_registry import NIM_MODELS, LLMConfigurationError, resolve_model
from app.ai.service import _extract_text

# ---------------------------------------------------------------------------
# 1. Factory selection
# ---------------------------------------------------------------------------


class TestCreateChatModel:
    """create_chat_model selects the right backend based on provider."""

    def test_gemini_provider_returns_gemini_model(self):
        """When provider='gemini' and GEMINI_API_KEY is set, a Gemini model is returned."""
        fake_model = MagicMock()
        fake_adapter = MagicMock()
        fake_adapter.model = fake_model

        with (
            patch("app.ai.llm_factory.settings") as mock_settings,
            patch("app.ai.llm_factory.GeminiLLMAdapter", return_value=fake_adapter) as MockAdapter,
        ):
            mock_settings.llm_provider = "gemini"
            mock_settings.llm_model = None
            mock_settings.gemini_api_key = "test-key"
            mock_settings.gemini_model = "gemini-3.6-flash"
            mock_settings.gemini_temperature = 0.0
            mock_settings.gemini_max_output_tokens = 4096
            mock_settings.nvidia_api_key.get_secret_value.return_value = ""

            from app.ai.llm_factory import create_chat_model

            result = create_chat_model(provider="gemini", model="gemini-3.6-flash")

        MockAdapter.assert_called_once_with(model_name="gemini-3.6-flash")
        assert result is fake_model

    def test_nim_provider_returns_nim_wrapper(self):
        """When provider='nim' and NVIDIA_API_KEY is set, a _NIMRateLimitRetry is returned."""
        from app.ai.llm_factory import _NIMRateLimitRetry, create_chat_model

        with (
            patch("app.ai.llm_factory.settings") as mock_settings,
            patch("app.ai.llm_factory._make_nim_client") as mock_make,
        ):
            mock_settings.llm_provider = "nim"
            mock_settings.llm_model = None
            mock_settings.gemini_model = "gemini-3.6-flash"
            mock_settings.gemini_temperature = 0.0
            mock_settings.gemini_max_output_tokens = 4096

            secret = MagicMock()
            secret.get_secret_value.return_value = "nvapi-test-key"
            mock_settings.nvidia_api_key = secret
            mock_settings.nvidia_base_url = "https://integrate.api.nvidia.com/v1"

            fake_inner = MagicMock()
            mock_make.return_value = fake_inner

            result = create_chat_model(provider="nim", model=NIM_MODELS[0])

        mock_make.assert_called_once_with(NIM_MODELS[0])
        assert isinstance(result, _NIMRateLimitRetry)

    def test_nim_missing_key_raises_configuration_error(self):
        """If NVIDIA_API_KEY is empty for nim provider, LLMConfigurationError is raised."""
        with patch("app.ai.llm_factory.settings") as mock_settings:
            mock_settings.llm_provider = "nim"
            mock_settings.llm_model = None
            mock_settings.gemini_model = "gemini-3.6-flash"
            mock_settings.gemini_temperature = 0.0
            mock_settings.gemini_max_output_tokens = 4096

            secret = MagicMock()
            secret.get_secret_value.return_value = ""
            mock_settings.nvidia_api_key = secret
            mock_settings.nvidia_base_url = "https://integrate.api.nvidia.com/v1"

            from app.ai.llm_factory import create_chat_model

            with pytest.raises(LLMConfigurationError, match="NVIDIA_API_KEY"):
                create_chat_model(provider="nim", model=NIM_MODELS[0])

    def test_gemini_missing_key_raises_configuration_error(self):
        """If GEMINI_API_KEY is empty for gemini provider, LLMConfigurationError is raised."""
        with patch("app.ai.llm_factory.settings") as mock_settings:
            mock_settings.llm_provider = "gemini"
            mock_settings.llm_model = None
            mock_settings.gemini_api_key = ""
            mock_settings.gemini_model = "gemini-3.6-flash"

            from app.ai.llm_factory import create_chat_model

            with pytest.raises(LLMConfigurationError, match="GEMINI_API_KEY"):
                create_chat_model(provider="gemini", model="gemini-3.6-flash")


# ---------------------------------------------------------------------------
# 2. Unknown-model rejection
# ---------------------------------------------------------------------------


class TestResolveModel:
    """resolve_model rejects unknown providers and models with clear errors."""

    def test_unknown_provider_raises(self):
        with pytest.raises(LLMConfigurationError, match="Unknown LLM provider 'anthropic'"):
            resolve_model("anthropic")

    def test_unknown_nim_model_raises(self):
        with pytest.raises(LLMConfigurationError, match="Unknown model 'fake/model-42'"):
            resolve_model("nim", "fake/model-42")

    def test_unknown_gemini_model_raises(self):
        """A model not matching settings.gemini_model is rejected."""
        with patch("app.ai.model_registry.settings") as mock_settings:
            mock_settings.gemini_model = "gemini-3.6-flash"
            with pytest.raises(LLMConfigurationError, match="Unknown model 'gemini-0.1-fake'"):
                resolve_model("gemini", "gemini-0.1-fake")

    def test_gemini_default_resolves_to_settings_model(self):
        """Passing no model for gemini resolves to settings.gemini_model."""
        with patch("app.ai.model_registry.settings") as mock_settings:
            mock_settings.gemini_model = "gemini-3.6-flash"
            result = resolve_model("gemini")
        assert result == "gemini-3.6-flash"

    def test_nim_default_resolves_to_first_allowed(self):
        """Passing no model for nim resolves to the first entry in NIM_MODELS."""
        result = resolve_model("nim")
        assert result == NIM_MODELS[0]

    def test_all_nim_models_are_accepted(self):
        """The verified model in the NIM_MODELS allowlist passes resolve_model without error."""
        assert len(NIM_MODELS) == 1
        for model_id in NIM_MODELS:
            resolved = resolve_model("nim", model_id)
            assert resolved == model_id


# ---------------------------------------------------------------------------
# 3. Tool-call path (LangGraph agent wiring)
# ---------------------------------------------------------------------------


class TestToolCallPath:
    """The agent correctly routes through tools and returns a final answer."""

    @pytest.mark.asyncio
    async def test_agent_yields_tool_start_and_done_events(self):
        """When the mocked LLM returns a tool-call followed by a plain reply,
        AgentService emits tool_start, tool_end, token and done events."""
        from app.ai.service import AgentService

        call_count = 0

        async def fake_astream_events(inputs, config, version):
            nonlocal call_count
            call_count += 1
            # Simulate on_tool_start
            yield {"event": "on_tool_start", "name": "get_market_data", "data": {"input": {"symbol": "AAPL"}}}
            # Simulate tool output
            yield {
                "event": "on_tool_end",
                "name": "get_market_data",
                "data": {"output": '{"count": 21, "symbol": "AAPL"}'},
            }
            # Simulate LLM token stream
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessage(content="AAPL traded ")}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessage(content="between $180 and $195.")}}

        with (
            patch("app.ai.service.create_chat_model") as mock_factory,
            patch("app.ai.service.ConversationService") as _,
        ):
            mock_model = MagicMock()
            mock_model.bind_tools.return_value = mock_model
            mock_factory.return_value = mock_model

            service = AgentService()
            # Replace the compiled graph's astream_events
            service._compiled.astream_events = fake_astream_events

            # Minimal mock ConversationService
            mock_conv_svc = AsyncMock()
            mock_conv_svc.add_user_message = AsyncMock()
            mock_conv_svc.add_assistant_message = AsyncMock()
            mock_conv_svc.get_messages = AsyncMock(return_value=[])

            import uuid

            events = []
            async for ev in service.handle_message(
                conversation_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                content="What did AAPL do in January 2024?",
                conversation_service=mock_conv_svc,
            ):
                events.append(ev)

        event_names = [e.event for e in events]
        assert "tool_start" in event_names
        assert "tool_end" in event_names
        assert "token" in event_names
        assert event_names[-1] == "done"


# ---------------------------------------------------------------------------
# 4. Streaming normalization (_extract_text)
# ---------------------------------------------------------------------------


class TestExtractText:
    """_extract_text correctly normalises both Gemini and OpenAI chunk formats."""

    # --- Gemini formats ---

    def test_plain_string_is_returned_as_is(self):
        assert _extract_text("hello") == "hello"

    def test_empty_string_returns_empty(self):
        assert _extract_text("") == ""

    def test_none_returns_empty(self):
        assert _extract_text(None) == ""

    def test_list_of_text_blocks_concatenated(self):
        """Gemini streams content as a list of {"type": "text", "text": "..."} dicts."""
        content = [{"type": "text", "text": "Hello "}, {"type": "text", "text": "world"}]
        assert _extract_text(content) == "Hello world"

    def test_thought_blocks_excluded(self):
        """Gemini thought-signature blocks (thought=True) must not appear in output."""
        content = [
            {"type": "text", "text": "<think>internal reasoning</think>", "thought": True},
            {"type": "text", "text": "Visible answer."},
        ]
        assert _extract_text(content) == "Visible answer."

    def test_non_text_block_types_excluded(self):
        """Blocks with type != 'text' (e.g. tool-call blocks) are ignored."""
        content = [
            {"type": "tool_use", "id": "tc_1", "name": "get_market_data"},
            {"type": "text", "text": "Done."},
        ]
        assert _extract_text(content) == "Done."

    def test_empty_list_returns_empty(self):
        assert _extract_text([]) == ""

    def test_list_of_bare_strings_concatenated(self):
        """Some providers stream a list of plain strings instead of dicts."""
        assert _extract_text(["foo", " ", "bar"]) == "foo bar"

    # --- OpenAI / NIM format ---

    def test_openai_plain_string_chunk(self):
        """NIM / OpenAI streams plain strings; _extract_text must pass them through."""
        assert _extract_text("partial token") == "partial token"

    def test_mixed_list_dicts_and_strings(self):
        """A list mixing plain strings and text-dicts is handled correctly."""
        content = ["Hello ", {"type": "text", "text": "world"}]
        assert _extract_text(content) == "Hello world"

    def test_tool_call_chunk_skipped_via_chunk_guard(self):
        """service.py guards against tool_call_chunks before calling _extract_text,
        but _extract_text itself must also skip non-text content gracefully."""
        content = [{"type": "tool_use", "name": "calculate_indicators"}]
        assert _extract_text(content) == ""

    def test_text_block_with_none_text_skipped(self):
        """A text block with text=None (malformed chunk) does not crash."""
        content = [{"type": "text", "text": None}, {"type": "text", "text": "ok"}]
        assert _extract_text(content) == "ok"
