"""Grounded LLM narration for already-calculated recommendation results."""

import asyncio
import json
import logging
from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from threading import Lock
from time import monotonic, sleep
from typing import Any

from pydantic import ValidationError

from flipradar.api.schemas.llm_analysis_schema import (
    RECOMMENDATION_NARRATIVE_PROMPT_VERSION,
    LlmFactMetric,
    LlmNarrativeStatus,
    LlmRecommendationNarrative,
    LlmUncertaintyCode,
)
from flipradar.core.settings import LlmSettings, get_settings
from flipradar.integrations.llm_factory import create_llm_provider
from flipradar.integrations.llm_provider import (
    LlmCompletion,
    LlmCompletionRequest,
    LlmProvider,
    LlmProviderError,
    LlmProviderTimeoutError,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = RECOMMENDATION_NARRATIVE_PROMPT_VERSION
NARRATIVE_MAX_TOKENS = 600

SYSTEM_PROMPT = """You write a short explanation for a deterministic FlipRadar recommendation.
Return JSON only, with exactly this shape:
{
  "summary": "string",
  "facts": [{"source_metric": "allowed metric id", "text": "string"}],
  "uncertainties": [{"code": "allowed uncertainty code", "text": "string"}]
}

The deterministic system, not you, calculates all values and recommendations.
Use only the supplied calculated metrics. Every fact must reference one supplied
metric id. Uncertainties must use only a supplied uncertainty code. Never invent,
estimate, repeat, compare, or imply prices, percentages, listing counts, sales,
sellers, availability, or marketplace facts. Never name a marketplace. Text
fields must contain no digits, currency symbols, or currency names. If no supplied
uncertainty applies, return an empty uncertainties array. Do not provide financial
advice or guarantees."""


class LlmStructuredOutputError(LlmProviderError):
    """Raised when an LLM response does not satisfy the grounded card schema."""


@dataclass(frozen=True)
class LlmExecutionPolicy:
    max_retries: int
    retry_backoff_seconds: float
    user_rate_limit: int
    global_rate_limit: int
    rate_limit_window_seconds: int
    input_cost_per_million_tokens: float
    output_cost_per_million_tokens: float

    @classmethod
    def from_settings(cls, settings: LlmSettings) -> LlmExecutionPolicy:
        return cls(
            max_retries=settings.max_retries,
            retry_backoff_seconds=settings.retry_backoff_seconds,
            user_rate_limit=settings.user_rate_limit,
            global_rate_limit=settings.global_rate_limit,
            rate_limit_window_seconds=settings.rate_limit_window_seconds,
            input_cost_per_million_tokens=settings.input_cost_per_million_tokens,
            output_cost_per_million_tokens=settings.output_cost_per_million_tokens,
        )


@dataclass(frozen=True)
class LlmUsageRecord:
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    attempts: int


@dataclass(frozen=True)
class LlmNarrativeResult:
    status: LlmNarrativeStatus
    narrative: LlmRecommendationNarrative | None


class LlmRateLimiter:
    """Thread-safe rolling-window quota for one optional LLM capability."""

    def __init__(
        self, policy: LlmExecutionPolicy, *, clock: Callable[[], float] = monotonic
    ) -> None:
        self._policy = policy
        self._clock = clock
        self._global_hits: deque[float] = deque()
        self._user_hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def acquire(self, user_key: str) -> str | None:
        with self._lock:
            now = self._clock()
            self._prune(self._global_hits, now)
            user_hits = self._user_hits[user_key]
            self._prune(user_hits, now)
            if len(self._global_hits) >= self._policy.global_rate_limit:
                return "global"
            if len(user_hits) >= self._policy.user_rate_limit:
                return "user"
            self._global_hits.append(now)
            user_hits.append(now)
            return None

    def _prune(self, hits: deque[float], now: float) -> None:
        cutoff = now - self._policy.rate_limit_window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()


class LlmUsageTracker:
    """Retains process-local usage records and emits no prompt or secret data."""

    def __init__(self) -> None:
        self._records: list[LlmUsageRecord] = []
        self._lock = Lock()

    def record(self, record: LlmUsageRecord) -> None:
        with self._lock:
            self._records.append(record)

    def snapshot(self) -> list[LlmUsageRecord]:
        with self._lock:
            return list(self._records)


_usage_tracker = LlmUsageTracker()
_rate_limiters: dict[LlmExecutionPolicy, LlmRateLimiter] = {}
_rate_limiter_lock = Lock()


class RecommendationPromptMetrics:
    """Whitelisted deterministic metrics exposed to the LLM prompt."""

    def __init__(
        self,
        values: dict[LlmFactMetric, Any],
        uncertainty_codes: set[LlmUncertaintyCode],
    ) -> None:
        self.values = values
        self.uncertainty_codes = uncertainty_codes

    @classmethod
    def from_analysis(cls, analysis: Mapping[str, Any]) -> RecommendationPromptMetrics:
        values: dict[LlmFactMetric, Any] = {}
        required_metrics = {
            LlmFactMetric.DECISION: analysis.get("recommendation"),
            LlmFactMetric.CONFIDENCE: analysis.get("confidence"),
            LlmFactMetric.SCORE: analysis.get("score"),
            LlmFactMetric.VALUATION_SOURCE: analysis.get("valuation_source"),
            LlmFactMetric.FAIR_VALUE: analysis.get("fair_value"),
        }
        for metric, value in required_metrics.items():
            if value is not None:
                values[metric] = _json_value(value)

        optional_metrics = {
            LlmFactMetric.ALL_IN_PRICE: analysis.get("all_in_price"),
            LlmFactMetric.DISCOUNT_PERCENT: analysis.get("discount_pct"),
            LlmFactMetric.ESTIMATED_PROFIT: analysis.get("estimated_profit"),
            LlmFactMetric.ESTIMATED_ROI_PERCENT: analysis.get("estimated_roi_pct"),
            LlmFactMetric.TREND_PERCENT: analysis.get("trend_pct"),
            LlmFactMetric.TARGET_SELL_PRICE: analysis.get("target_sell_price"),
            LlmFactMetric.CONCENTRATION_PERCENT: analysis.get("concentration_percent"),
            LlmFactMetric.VALUATION_AGE_DAYS: analysis.get("valuation_age_days"),
        }
        for metric, value in optional_metrics.items():
            if value is not None:
                values[metric] = _json_value(value)

        low, high = analysis.get("market_low"), analysis.get("market_high")
        if low is not None and high is not None:
            values[LlmFactMetric.MARKET_RANGE] = {
                "low": _json_value(low),
                "high": _json_value(high),
            }
        if analysis.get("listing_count") is not None:
            values[LlmFactMetric.LISTING_COUNT] = _json_value(analysis["listing_count"])

        uncertainty_codes: set[LlmUncertaintyCode] = set()
        if analysis.get("confidence") == "low":
            uncertainty_codes.add(LlmUncertaintyCode.LOW_CONFIDENCE)
        if (
            isinstance(analysis.get("listing_count"), int)
            and analysis["listing_count"] < 3
        ):
            uncertainty_codes.add(LlmUncertaintyCode.LIMITED_LISTING_EVIDENCE)
        if analysis.get("valuation_source") == "manual_override":
            uncertainty_codes.add(LlmUncertaintyCode.MANUAL_VALUATION)
        if (
            isinstance(analysis.get("valuation_age_days"), int)
            and analysis["valuation_age_days"] > 7
        ):
            uncertainty_codes.add(LlmUncertaintyCode.STALE_VALUATION)
        if analysis.get("condition") == "unknown":
            uncertainty_codes.add(LlmUncertaintyCode.UNKNOWN_CONDITION)
        if analysis.get("warnings"):
            uncertainty_codes.add(LlmUncertaintyCode.DETERMINISTIC_WARNING)

        return cls(values=values, uncertainty_codes=uncertainty_codes)

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "prompt_version": PROMPT_VERSION,
            "calculated_metrics": {
                metric.value: value for metric, value in self.values.items()
            },
            "allowed_fact_metric_ids": [metric.value for metric in self.values],
            "allowed_uncertainty_codes": sorted(
                code.value for code in self.uncertainty_codes
            ),
        }


def build_recommendation_prompt(metrics: RecommendationPromptMetrics) -> str:
    """Serialize only controlled calculated values for the provider request."""

    return json.dumps(metrics.prompt_payload(), separators=(",", ":"), sort_keys=True)


def generate_recommendation_narrative(
    provider: LlmProvider, analysis: Mapping[str, Any]
) -> LlmRecommendationNarrative:
    """Generate and validate card content without exposing raw marketplace data."""

    return _generate_recommendation_narrative(provider, analysis)[0]


def _generate_recommendation_narrative(
    provider: LlmProvider, analysis: Mapping[str, Any]
) -> tuple[LlmRecommendationNarrative, LlmCompletion]:
    metrics = RecommendationPromptMetrics.from_analysis(analysis)
    completion = provider.complete(
        LlmCompletionRequest(
            prompt=build_recommendation_prompt(metrics),
            system_prompt=SYSTEM_PROMPT,
            max_tokens=NARRATIVE_MAX_TOKENS,
        )
    )
    try:
        narrative = LlmRecommendationNarrative.model_validate_json(completion.text)
    except (ValidationError, ValueError) as exc:
        raise LlmStructuredOutputError(
            "LLM returned an invalid structured response"
        ) from exc

    available_metrics = set(metrics.values)
    if any(card.source_metric not in available_metrics for card in narrative.facts):
        raise LlmStructuredOutputError(
            "LLM referenced an unavailable calculated metric"
        )
    if any(
        card.code not in metrics.uncertainty_codes for card in narrative.uncertainties
    ):
        raise LlmStructuredOutputError("LLM referenced an unavailable uncertainty")
    return narrative, completion


async def maybe_generate_recommendation_narrative(
    analysis: Mapping[str, Any],
    *,
    user_key: str = "anonymous",
) -> LlmNarrativeResult:
    """Return an optional narrative without changing the deterministic result."""

    settings = get_settings().llm
    if not settings.configured:
        return LlmNarrativeResult(status="disabled", narrative=None)
    policy = LlmExecutionPolicy.from_settings(settings)
    try:
        provider = create_llm_provider(settings)
    except LlmProviderError as exc:
        logger.warning("LLM narrative unavailable error_type=%s", type(exc).__name__)
        return LlmNarrativeResult(status="failed", narrative=None)
    return await asyncio.to_thread(
        generate_narrative_with_guardrails,
        provider,
        analysis,
        user_key=user_key,
        policy=policy,
    )


def generate_narrative_with_guardrails(
    provider: LlmProvider,
    analysis: Mapping[str, Any],
    *,
    user_key: str,
    policy: LlmExecutionPolicy,
    limiter: LlmRateLimiter | None = None,
    usage_tracker: LlmUsageTracker | None = None,
    sleep_fn: Callable[[float], None] = sleep,
    clock: Callable[[], float] = monotonic,
) -> LlmNarrativeResult:
    """Apply quotas, bounded retries, validation, and usage instrumentation."""

    limiter = limiter or _rate_limiter_for(policy)
    usage_tracker = usage_tracker or _usage_tracker
    blocked_scope = limiter.acquire(user_key)
    if blocked_scope is not None:
        logger.warning("LLM narrative rate limited scope=%s", blocked_scope)
        return LlmNarrativeResult(status="rate_limited", narrative=None)

    started_at = clock()
    max_attempts = policy.max_retries + 1
    for attempt in range(1, max_attempts + 1):
        try:
            narrative, completion = _generate_recommendation_narrative(
                provider, analysis
            )
            _track_usage(
                usage_tracker,
                completion,
                policy,
                latency_ms=int((clock() - started_at) * 1000),
                attempts=attempt,
            )
            return LlmNarrativeResult(status="available", narrative=narrative)
        except LlmProviderTimeoutError:
            logger.warning("LLM narrative timeout attempt=%s/%s", attempt, max_attempts)
            if attempt == max_attempts:
                return LlmNarrativeResult(status="timed_out", narrative=None)
        except LlmStructuredOutputError:
            logger.warning("LLM narrative invalid_response attempt=%s", attempt)
            return LlmNarrativeResult(status="invalid_response", narrative=None)
        except LlmProviderError as exc:
            logger.warning(
                "LLM narrative failure attempt=%s/%s error_type=%s",
                attempt,
                max_attempts,
                type(exc).__name__,
            )
            if attempt == max_attempts:
                return LlmNarrativeResult(status="failed", narrative=None)

        logger.info("LLM narrative retry attempt=%s/%s", attempt + 1, max_attempts)
        sleep_fn(policy.retry_backoff_seconds * attempt)
    raise AssertionError("unreachable")


def _track_usage(
    usage_tracker: LlmUsageTracker,
    completion: LlmCompletion,
    policy: LlmExecutionPolicy,
    *,
    latency_ms: int,
    attempts: int,
) -> None:
    if completion.usage is None:
        logger.warning(
            "LLM narrative completed without usage model=%s prompt_version=%s",
            completion.model,
            PROMPT_VERSION,
        )
        return
    estimated_cost_usd = (
        completion.usage.input_tokens * policy.input_cost_per_million_tokens
        + completion.usage.output_tokens * policy.output_cost_per_million_tokens
    ) / 1_000_000
    record = LlmUsageRecord(
        model=completion.model,
        prompt_version=PROMPT_VERSION,
        input_tokens=completion.usage.input_tokens,
        output_tokens=completion.usage.output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        latency_ms=latency_ms,
        attempts=attempts,
    )
    usage_tracker.record(record)
    logger.info(
        "LLM narrative completed model=%s prompt_version=%s input_tokens=%s output_tokens=%s estimated_cost_usd=%.6f latency_ms=%s attempts=%s",
        record.model,
        record.prompt_version,
        record.input_tokens,
        record.output_tokens,
        record.estimated_cost_usd,
        record.latency_ms,
        record.attempts,
    )


def _rate_limiter_for(policy: LlmExecutionPolicy) -> LlmRateLimiter:
    with _rate_limiter_lock:
        limiter = _rate_limiters.get(policy)
        if limiter is None:
            limiter = LlmRateLimiter(policy)
            _rate_limiters[policy] = limiter
        return limiter


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "value"):
        return value.value
    return value
