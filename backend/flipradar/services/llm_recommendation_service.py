"""Grounded LLM narration for already-calculated recommendation results."""

import asyncio
import json
import logging
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from flipradar.api.schemas.llm_analysis_schema import (
    LlmFactMetric,
    LlmRecommendationNarrative,
    LlmUncertaintyCode,
)
from flipradar.core.settings import get_settings
from flipradar.integrations.llm_factory import create_llm_provider
from flipradar.integrations.llm_provider import (
    LlmCompletionRequest,
    LlmProvider,
    LlmProviderError,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "recommendation-narrative-v1"
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
    return narrative


async def maybe_generate_recommendation_narrative(
    analysis: Mapping[str, Any],
) -> LlmRecommendationNarrative | None:
    """Return an optional narrative without changing the deterministic result."""

    settings = get_settings().llm
    if not settings.configured:
        return None
    try:
        provider = create_llm_provider(settings)
        return await asyncio.to_thread(
            generate_recommendation_narrative, provider, analysis
        )
    except LlmProviderError as exc:
        logger.warning("LLM narrative unavailable error_type=%s", type(exc).__name__)
        return None


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "value"):
        return value.value
    return value
