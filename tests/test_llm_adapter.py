"""
Unit tests for LLMAdapter and Anthropic Claude integration.
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from verisight.config import LLMConfig, set_config, VeriSightConfig
from verisight.agents.base_agent import LLMAdapter


class TestLLMConfigProvider:
    """Tests for provider resolution and auto-detection in LLMConfig."""

    def test_default_gemini_config(self):
        with patch.dict(os.environ, {}, clear=True):
            config = LLMConfig()
            assert config.provider == "gemini"
            assert config.model_name == "gemini-2.0-flash"

    def test_explicit_anthropic_provider(self):
        config = LLMConfig(provider="anthropic")
        assert config.provider == "anthropic"
        assert config.model_name == "claude-sonnet-4-20250514"

    def test_explicit_claude_provider_alias(self):
        config = LLMConfig(provider="claude")
        assert config.provider == "claude"
        assert config.model_name == "claude-sonnet-4-20250514"

    def test_model_name_auto_detects_anthropic(self):
        config = LLMConfig(model_name="claude-3-7-sonnet-20250219")
        assert config.provider == "anthropic"
        assert config.model_name == "claude-3-7-sonnet-20250219"

    def test_env_var_auto_detects_anthropic(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test12345",
        }
        with patch.dict(os.environ, env, clear=True):
            config = LLMConfig()
            assert config.provider == "anthropic"
            assert config.api_key == "sk-ant-test12345"
            assert config.model_name == "claude-sonnet-4-20250514"


class TestLLMAdapterAnthropic:
    """Tests for LLMAdapter with Anthropic provider."""

    def test_missing_anthropic_key_raises_error(self):
        config = VeriSightConfig(llm=LLMConfig(provider="anthropic", api_key=""))
        set_config(config)
        adapter = LLMAdapter()
        with pytest.raises(RuntimeError) as exc_info:
            adapter.generate("Hello")
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)

    @patch("anthropic.Anthropic")
    def test_anthropic_generate_success(self, mock_anthropic_cls):
        # Setup mock Anthropic client
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"result": "success"}')]
        mock_client.messages.create.return_value = mock_response

        config = VeriSightConfig(
            llm=LLMConfig(provider="anthropic", api_key="sk-ant-test", model_name="claude-sonnet-4-20250514")
        )
        set_config(config)

        adapter = LLMAdapter()
        res = adapter.generate(prompt="Analyze log", system_prompt="You are a helper")

        assert res == '{"result": "success"}'
        mock_client.messages.create.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            temperature=0.1,
            messages=[{"role": "user", "content": "Analyze log"}],
            system="You are a helper",
        )
