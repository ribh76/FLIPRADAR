"""Grounded LLM narration for deterministic portfolio analyses."""

import asyncio
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic, sleep
from typing import Any

from pydantic import ValidationError

from flipradar.api.schemas.portfolio_analysis_schema import (
    PORTFOLIO_ANALYSIS_PROMPT_VERSION,
    LlmPortfolioNarrative,
)
from flipradar.core.settings import get_settings
from flipradar.integrations.llm_factory import create_llm_provider
from flipradar.integrations.llm_provider import (
    LlmCompletion,
    LlmCompletionRequest,
    LlmProvider,
    LlmProviderError,
    LlmProviderTimeoutError,
)
from flipradar.services.llm_recommendation_service import (
    LlmExecutionPolicy,
    LlmRateLimiter,
    LlmStructuredOutputError,
    _rate_limiter_for,
    _track_usage,
    _usage_tracker,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = PORTFOLIO_ANALYSIS_PROMPT_VERSION
NARRATIVE_MAX_TOKENS = 900

SYSTEM_PROMPT = """You write a short portfolio narrative for calculated FlipRadar data.
Return JSON only, with exactly this shape:
{
  "executive_summary": "string",
  "observations": [{"source_metric": "allowed metric id", "text": "string"}],
  "actions": [{"item_key": "allowed item key", "label": "matching deterministic label", "text": "string"}],
  "uncertainties": [{"code": "allowed uncertainty code", "text": "string"}]
}

The deterministic system, not you, calculates all metrics and item labels.
Use only the supplied calculated metrics. Every observation must reference an
allowed metric id. Every action must use an allowed item key and its exact,
already-calculated label. Uncertainties must use only a supplied uncertainty
code. Never invent, estimate, repeat, compare, or imply prices, percentages,
listing counts, sales, sellers, availability, or marketplace facts. Never name a
marketplace. Text fields must contain no digits, currency symbols, or currency
names. Do not provide financial advice or guarantees."""


@dataclass(frozen=True)
class PortfolioLlmNarrativeResult:
    status: str
    narrative: LlmPortfolioNarrative | None


class PortfolioPromptMetrics:
    """Small, explicitly whitelisted view of a deterministic analysis result."""

    def __init__(
        self,
        *,
        values: dict[str, Any],
        item_metrics: dict[str, dict[str, Any]],
        item_labels: dict[str, str],
        uncertainty_codes: set[str],
    ) -> None:
        self.values = values
        self.item_metrics = item_metrics
        self.item_labels = item_labels
        self.uncertainty_codes = uncertainty_codes

    @classmethod
    def from_analysis(cls, analysis: Mapping[str, Any]) -> PortfolioPromptMetrics:
        analytics = analysis["analytics"]
        summary = analytics["summary_metrics"]
        attention = summary["valuation_attention"]
        values = {
            "portfolio.holding_count": analytics["holding_count"],
            "portfolio.valued_holding_count": analytics["valued_holding_count"],
            "portfolio.total_cost_basis": analytics["total_cost_basis"],
            "portfolio.total_market_value": analytics["total_market_value"],
            "portfolio.concentration": summary["concentration"],
            "portfolio.diversification": summary["diversification"],
            "portfolio.signal_counts": summary["signals"],
            "portfolio.valuation_attention": {
                "stale_count": len(attention["stale"]),
                "low_confidence_count": len(attention["low_confidence"]),
                "insufficient_data_count": len(attention["insufficient_data"]),
            },
        }
        item_metrics = {
            str(item["portfolio_item_id"]): {
                "label": item["label"],
                "confidence": item["confidence"],
                "reason_codes": item["reason_codes"],
                "data_quality_flags": item["data_quality_flags"],
            }
            for item in analysis["item_recommendations"]
        }
        item_labels = {
            item_key: item_metrics[item_key]["label"] for item_key in item_metrics
        }
        uncertainty_codes: set[str] = set()
        if analytics["holding_count"] != analytics["valued_holding_count"]:
            uncertainty_codes.add("incomplete_valuation_coverage")
        if attention["stale"]:
            uncertainty_codes.add("stale_valuations")
        if attention["low_confidence"]:
            uncertainty_codes.add("low_confidence_valuations")
        if attention["insufficient_data"]:
            uncertainty_codes.add("insufficient_market_data")
        return cls(
            values=values,
            item_metrics=item_metrics,
            item_labels=item_labels,
            uncertainty_codes=uncertainty_codes,
        )

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "prompt_version": PROMPT_VERSION,
            "calculated_metrics": _json_value(self.values),
            "item_metrics": self.item_metrics,
            "allowed_observation_metric_ids": sorted(self.values),
            "allowed_item_keys": sorted(self.item_labels),
            "allowed_uncertainty_codes": sorted(self.uncertainty_codes),
        }


def build_portfolio_analysis_prompt(metrics: PortfolioPromptMetrics) -> str:
    """Serialize only the calculated values allowed into the LLM request."""

    return json.dumps(metrics.prompt_payload(), separators=(",", ":"), sort_keys=True)


def generate_portfolio_narrative(
    provider: LlmProvider, analysis: Mapping[str, Any]
) -> tuple[LlmPortfolioNarrative, LlmCompletion]:
    metrics = PortfolioPromptMetrics.from_analysis(analysis)
    completion = provider.complete(
        LlmCompletionRequest(
            prompt=build_portfolio_analysis_prompt(metrics),
            system_prompt=SYSTEM_PROMPT,
            max_tokens=NARRATIVE_MAX_TOKENS,
        )
    )
    try:
        narrative = LlmPortfolioNarrative.model_validate_json(completion.text)
    except (ValidationError, ValueError) as exc:
        raise LlmStructuredOutputError(
            "LLM returned an invalid portfolio analysis response"
        ) from exc

    if any(
        observation.source_metric not in metrics.values
        for observation in narrative.observations
    ):
        raise LlmStructuredOutputError("LLM referenced an unavailable portfolio metric")
    if any(
        action.item_key not in metrics.item_labels
        or action.label != metrics.item_labels[action.item_key]
        for action in narrative.actions
    ):
        raise LlmStructuredOutputError("LLM changed or invented an item label")
    if any(
        uncertainty.code not in metrics.uncertainty_codes
        for uncertainty in narrative.uncertainties
    ):
        raise LlmStructuredOutputError("LLM referenced an unavailable uncertainty")
    return narrative, completion


async def maybe_generate_portfolio_narrative(
    analysis: Mapping[str, Any], *, user_key: str
) -> PortfolioLlmNarrativeResult:
    """Generate bounded prose; a failure never changes deterministic analysis."""

    settings = get_settings().llm
    if not settings.configured:
        return PortfolioLlmNarrativeResult(status="disabled", narrative=None)
    try:
        provider = create_llm_provider(settings)
    except LlmProviderError as exc:
        logger.warning("portfolio LLM unavailable error_type=%s", type(exc).__name__)
        return PortfolioLlmNarrativeResult(status="failed", narrative=None)

    policy = LlmExecutionPolicy.from_settings(settings)
    return await asyncio.to_thread(
        _generate_with_guardrails,
        provider,
        analysis,
        user_key,
        policy,
    )


def _generate_with_guardrails(
    provider: LlmProvider,
    analysis: Mapping[str, Any],
    user_key: str,
    policy: LlmExecutionPolicy,
) -> PortfolioLlmNarrativeResult:
    limiter: LlmRateLimiter = _rate_limiter_for(policy)
    if limiter.acquire(user_key) is not None:
        logger.warning("portfolio LLM rate limited")
        return PortfolioLlmNarrativeResult(status="rate_limited", narrative=None)

    started_at = monotonic()
    max_attempts = policy.max_retries + 1
    for attempt in range(1, max_attempts + 1):
        try:
            narrative, completion = generate_portfolio_narrative(provider, analysis)
            _track_usage(
                _usage_tracker,
                completion,
                policy,
                latency_ms=int((monotonic() - started_at) * 1000),
                attempts=attempt,
            )
            return PortfolioLlmNarrativeResult(status="available", narrative=narrative)
        except LlmProviderTimeoutError:
            if attempt == max_attempts:
                return PortfolioLlmNarrativeResult(status="timed_out", narrative=None)
        except LlmStructuredOutputError:
            return PortfolioLlmNarrativeResult(
                status="invalid_response", narrative=None
            )
        except LlmProviderError as exc:
            logger.warning("portfolio LLM failure error_type=%s", type(exc).__name__)
            if attempt == max_attempts:
                return PortfolioLlmNarrativeResult(status="failed", narrative=None)
        except Exception:
            logger.exception("portfolio LLM unexpected failure")
            return PortfolioLlmNarrativeResult(status="failed", narrative=None)

        logger.info("portfolio LLM retry attempt=%s/%s", attempt + 1, max_attempts)
        sleep(policy.retry_backoff_seconds * attempt)

    return PortfolioLlmNarrativeResult(status="failed", narrative=None)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
