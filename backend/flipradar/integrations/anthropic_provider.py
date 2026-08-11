"""Anthropic Messages API implementation of the LLM provider contract."""

from time import perf_counter
from typing import Any

import requests

from flipradar.core.observability import record_metric
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
        api_key = settings.api_key
        if not settings.configured or not api_key:
            raise LlmProviderConfigurationError("Anthropic LLM is not configured")
        self._settings = settings
        self._api_key = api_key

    def complete(self, request: LlmCompletionRequest) -> LlmCompletion:
        started_at = perf_counter()
        model = request.model or self._settings.model
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": min(
                request.max_tokens or self._settings.max_tokens,
                self._settings.max_tokens,
            ),
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        try:
            try:
                response = requests.post(
                    ANTHROPIC_MESSAGES_URL,
                    headers={
                        "x-api-key": self._api_key,
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
            try:
                response_payload = response.json()
            except ValueError as exc:
                raise LlmProviderError("Anthropic returned an invalid response") from exc
            completion = _parse_completion(response_payload)
        except LlmProviderError as exc:
            _record_llm_metrics(
                model=model,
                started_at=started_at,
                outcome="failure",
                error_type=type(exc).__name__,
                input_cost_per_million_tokens=(
                    self._settings.input_cost_per_million_tokens
                ),
                output_cost_per_million_tokens=(
                    self._settings.output_cost_per_million_tokens
                ),
            )
            raise

        _record_llm_metrics(
            model=completion.model,
            started_at=started_at,
            outcome="success",
            usage=completion.usage,
            input_cost_per_million_tokens=self._settings.input_cost_per_million_tokens,
            output_cost_per_million_tokens=(
                self._settings.output_cost_per_million_tokens
            ),
        )
        return completion


def _record_llm_metrics(
    *,
    model: str,
    started_at: float,
    outcome: str,
    usage: LlmUsage | None = None,
    error_type: str | None = None,
    input_cost_per_million_tokens: float,
    output_cost_per_million_tokens: float,
) -> None:
    tags = {"provider": "anthropic", "model": model, "outcome": outcome}
    if error_type:
        tags["error_type"] = error_type
    record_metric("llm.request", tags=tags)
    record_metric(
        "llm.latency", (perf_counter() - started_at) * 1000, unit="ms", tags=tags
    )
    if usage is None:
        return
    record_metric("llm.input_tokens", usage.input_tokens, tags=tags)
    record_metric("llm.output_tokens", usage.output_tokens, tags=tags)
    estimated_cost = (
        usage.input_tokens * input_cost_per_million_tokens
        + usage.output_tokens * output_cost_per_million_tokens
    ) / 1_000_000
    record_metric("provider.cost", estimated_cost, unit="usd", tags=tags)


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
