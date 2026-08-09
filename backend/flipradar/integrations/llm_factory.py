"""Construct the configured LLM provider without exposing credentials."""

from flipradar.core.settings import LlmProviderName, LlmSettings
from flipradar.integrations.anthropic_provider import AnthropicLlmProvider
from flipradar.integrations.llm_provider import LlmProvider


def create_llm_provider(settings: LlmSettings) -> LlmProvider:
    if settings.provider == LlmProviderName.ANTHROPIC:
        return AnthropicLlmProvider(settings)
    raise ValueError(f"Unsupported LLM provider: {settings.provider}")
