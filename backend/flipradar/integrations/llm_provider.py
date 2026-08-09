"""Provider-agnostic contracts for bounded LLM completions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LlmProviderError(Exception):
    """Raised when an LLM provider cannot complete a valid request."""


class LlmProviderConfigurationError(LlmProviderError):
    """Raised when an LLM provider has not been enabled or configured."""


class LlmProviderTimeoutError(LlmProviderError):
    """Raised when an LLM provider request exceeds its configured timeout."""


@dataclass(frozen=True)
class LlmCompletionRequest:
    """A single user prompt, optionally governed by a system instruction."""

    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class LlmUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class LlmCompletion:
    text: str
    model: str
    stop_reason: str | None
    usage: LlmUsage | None


class LlmProvider(ABC):
    """Interface implemented by all backend LLM providers."""

    @abstractmethod
    def complete(self, request: LlmCompletionRequest) -> LlmCompletion:
        """Return a text completion or raise a typed provider error."""
