"""Strict, card-oriented schema for grounded LLM recommendation narratives."""

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RECOMMENDATION_NARRATIVE_PROMPT_VERSION = "recommendation-narrative-v1"

LlmNarrativeStatus = Literal[
    "available", "disabled", "rate_limited", "timed_out", "failed", "invalid_response"
]


class LlmFactMetric(StrEnum):
    DECISION = "decision"
    CONFIDENCE = "confidence"
    SCORE = "score"
    VALUATION_SOURCE = "valuation_source"
    FAIR_VALUE = "fair_value"
    MARKET_RANGE = "market_range"
    LISTING_COUNT = "listing_count"
    ALL_IN_PRICE = "all_in_price"
    DISCOUNT_PERCENT = "discount_percent"
    ESTIMATED_PROFIT = "estimated_profit"
    ESTIMATED_ROI_PERCENT = "estimated_roi_percent"
    TREND_PERCENT = "trend_percent"
    TARGET_SELL_PRICE = "target_sell_price"
    CONCENTRATION_PERCENT = "concentration_percent"
    VALUATION_AGE_DAYS = "valuation_age_days"


class LlmUncertaintyCode(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    LIMITED_LISTING_EVIDENCE = "limited_listing_evidence"
    STALE_VALUATION = "stale_valuation"
    MANUAL_VALUATION = "manual_valuation"
    UNKNOWN_CONDITION = "unknown_condition"
    DETERMINISTIC_WARNING = "deterministic_warning"


_UNSUPPORTED_OUTPUT_PATTERN = re.compile(
    r"(?:[$€£]|\b(?:usd|dollars?|eur|euros?|gbp|pounds?)\b|\b(?:ebay|bricklink|amazon|facebook|mercari|whatnot)\b|\b(?:listings?|sales?|sellers?|availability)\b|\d)",
    flags=re.IGNORECASE,
)


class LlmFactCard(BaseModel):
    """A model interpretation tied to one calculated metric card."""

    source_metric: LlmFactMetric
    text: str = Field(..., min_length=1, max_length=320)

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def reject_unattributed_market_claims(cls, value: str) -> str:
        if _UNSUPPORTED_OUTPUT_PATTERN.search(value):
            raise ValueError(
                "LLM fact card text cannot contain prices, numeric claims, or marketplace names"
            )
        return value


class LlmUncertaintyCard(BaseModel):
    """A known limitation that keeps the model's interpretation bounded."""

    code: LlmUncertaintyCode
    text: str = Field(..., min_length=1, max_length=320)

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def reject_unattributed_market_claims(cls, value: str) -> str:
        if _UNSUPPORTED_OUTPUT_PATTERN.search(value):
            raise ValueError(
                "LLM uncertainty text cannot contain prices, numeric claims, or marketplace names"
            )
        return value


class LlmRecommendationNarrative(BaseModel):
    """Validated AI explanation rendered as fact and uncertainty cards."""

    summary: str = Field(..., min_length=1, max_length=500)
    facts: list[LlmFactCard] = Field(default_factory=list, max_length=6)
    uncertainties: list[LlmUncertaintyCard] = Field(default_factory=list, max_length=6)
    prompt_version: Literal["recommendation-narrative-v1"] = (
        RECOMMENDATION_NARRATIVE_PROMPT_VERSION
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("summary")
    @classmethod
    def reject_unattributed_market_claims(cls, value: str) -> str:
        if _UNSUPPORTED_OUTPUT_PATTERN.search(value):
            raise ValueError(
                "LLM summary cannot contain prices, numeric claims, or marketplace names"
            )
        return value
