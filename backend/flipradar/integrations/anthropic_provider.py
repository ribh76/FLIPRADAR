"""Anthropic Messages API implementation of the LLM provider contract."""

from typing import Any

import requests

from flipradar.core.settings import LlmSettings
from flipradar.integrations.llm_provider import (
    LlmCompletion,
    LlmCompletionRequest,
    LlmProvider,
    LlmProviderConfigurationError,
    LlmProviderError,
    LlmProviderTimeoutError,
    LlmUsage,
)

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicLlmProvider(LlmProvider):
    """Completes prompts through Anthropic's Messages API."""

    def __init__(self, settings: LlmSettings) -> None:
        if not settings.configured or not settings.api_key:
            raise LlmProviderConfigurationError("Anthropic LLM is not configured")
        self._settings = settings

    def complete(self, request: LlmCompletionRequest) -> LlmCompletion:
        payload: dict[str, Any] = {
            "model": request.model or self._settings.model,
            "max_tokens": request.max_tokens or self._settings.max_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        try:
            response = requests.post(
                ANTHROPIC_MESSAGES_URL,
                headers={
                    "x-api-key": self._settings.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=self._settings.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise LlmProviderTimeoutError("Anthropic request timed out") from exc
        except requests.RequestException as exc:
            raise LlmProviderError("Anthropic request failed") from exc

        if response.status_code >= 400:
            raise LlmProviderError("Anthropic returned an error response")

        return _parse_completion(response.json())


def _parse_completion(payload: Any) -> LlmCompletion:
    if not isinstance(payload, dict):
        raise LlmProviderError("Anthropic returned an invalid response")

    content = payload.get("content")
    if not isinstance(content, list):
        raise LlmProviderError("Anthropic returned an invalid response")
    text = "".join(
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    )
    model = payload.get("model")
    if not text or not isinstance(model, str) or not model:
        raise LlmProviderError("Anthropic returned an invalid response")

    usage_payload = payload.get("usage")
    usage = None
    if isinstance(usage_payload, dict):
        input_tokens = usage_payload.get("input_tokens")
        output_tokens = usage_payload.get("output_tokens")
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            usage = LlmUsage(input_tokens=input_tokens, output_tokens=output_tokens)

    stop_reason = payload.get("stop_reason")
    return LlmCompletion(
        text=text,
        model=model,
        stop_reason=stop_reason if isinstance(stop_reason, str) else None,
        usage=usage,
    )
