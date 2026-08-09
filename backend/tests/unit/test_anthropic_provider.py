from unittest.mock import Mock, patch

import pytest
import requests

from flipradar.core.settings import LlmProviderName, LlmSettings
from flipradar.integrations.anthropic_provider import AnthropicLlmProvider
from flipradar.integrations.llm_provider import (
    LlmCompletionRequest,
    LlmProviderConfigurationError,
    LlmProviderError,
    LlmProviderTimeoutError,
)


def configured_settings() -> LlmSettings:
    return LlmSettings(
        enabled=True,
        provider=LlmProviderName.ANTHROPIC,
        api_key="test-api-key",
        model="claude-test",
        timeout_seconds=12,
        max_tokens=123,
        max_retries=2,
        retry_backoff_seconds=0.1,
        user_rate_limit=10,
        global_rate_limit=100,
        rate_limit_window_seconds=60,
        input_cost_per_million_tokens=3.0,
        output_cost_per_million_tokens=15.0,
    )


@patch("flipradar.integrations.anthropic_provider.requests.post")
def test_anthropic_provider_sends_a_bounded_messages_request(post: Mock) -> None:
    post.return_value = Mock(
        status_code=200,
        json=lambda: {
            "model": "claude-test",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "A useful response."}],
            "usage": {"input_tokens": 10, "output_tokens": 8},
        },
    )
    provider = AnthropicLlmProvider(configured_settings())

    completion = provider.complete(
        LlmCompletionRequest(prompt="Hello", system_prompt="Be concise.")
    )

    assert completion.text == "A useful response."
    assert completion.usage is not None
    assert completion.usage.input_tokens == 10
    post.assert_called_once_with(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": "test-api-key",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-test",
            "max_tokens": 123,
            "messages": [{"role": "user", "content": "Hello"}],
            "system": "Be concise.",
        },
        timeout=12,
    )


def test_anthropic_provider_requires_enabled_configuration() -> None:
    with pytest.raises(LlmProviderConfigurationError):
        AnthropicLlmProvider(
            configured_settings().model_copy(update={"enabled": False})
        )


@patch("flipradar.integrations.anthropic_provider.requests.post")
def test_anthropic_provider_caps_request_tokens_at_configured_limit(post: Mock) -> None:
    post.return_value = Mock(
        status_code=200,
        json=lambda: {
            "model": "claude-test",
            "content": [{"type": "text", "text": "Response."}],
        },
    )
    provider = AnthropicLlmProvider(configured_settings())

    provider.complete(LlmCompletionRequest(prompt="Hello", max_tokens=600))

    assert post.call_args.kwargs["json"]["max_tokens"] == 123


@patch("flipradar.integrations.anthropic_provider.requests.post")
def test_anthropic_provider_maps_timeouts(post: Mock) -> None:
    post.side_effect = requests.Timeout()
    provider = AnthropicLlmProvider(configured_settings())

    with pytest.raises(LlmProviderTimeoutError):
        provider.complete(LlmCompletionRequest(prompt="Hello"))


@patch("flipradar.integrations.anthropic_provider.requests.post")
def test_anthropic_provider_rejects_invalid_response(post: Mock) -> None:
    post.return_value = Mock(status_code=200, json=lambda: {"content": []})
    provider = AnthropicLlmProvider(configured_settings())

    with pytest.raises(LlmProviderError):
        provider.complete(LlmCompletionRequest(prompt="Hello"))


@patch("flipradar.integrations.anthropic_provider.requests.post")
def test_anthropic_provider_maps_invalid_json_to_provider_error(post: Mock) -> None:
    post.return_value = Mock(status_code=200, json=Mock(side_effect=ValueError()))
    provider = AnthropicLlmProvider(configured_settings())

    with pytest.raises(LlmProviderError):
        provider.complete(LlmCompletionRequest(prompt="Hello"))
