"""Schemas for an authenticated, deterministic portfolio analysis run."""

import re
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flipradar.api.schemas.llm_analysis_schema import LlmNarrativeStatus
from flipradar.api.schemas.portfolio_schema import PortfolioAnalyticsResponse

PORTFOLIO_ANALYSIS_PROMPT_VERSION = "portfolio-analysis-v1"

type PortfolioRecommendationLabel = Literal[
    "hold", "watch", "consider_selling", "insufficient_data"
]
PORTFOLIO_RECOMMENDATION_LABELS: frozenset[PortfolioRecommendationLabel] = frozenset(
    {"hold", "watch", "consider_selling", "insufficient_data"}
)


def portfolio_recommendation_label(value: str) -> PortfolioRecommendationLabel:
    """Narrow a rule-engine category to the public recommendation label type."""

    if value not in PORTFOLIO_RECOMMENDATION_LABELS:
        raise ValueError(f"Unsupported portfolio recommendation label: {value}")
    return cast(PortfolioRecommendationLabel, value)


_UNSUPPORTED_OUTPUT_PATTERN = re.compile(
    r"(?:[$€£]|\b(?:usd|dollars?|eur|euros?|gbp|pounds?)\b|"
    r"\b(?:ebay|bricklink|amazon|facebook|mercari|whatnot)\b|"
    r"\b(?:listings?|sales?|sellers?|availability)\b|\d)",
    flags=re.IGNORECASE,
)


class PortfolioItemRecommendation(BaseModel):
    """Rule-derived label and supporting inputs for one owned holding."""

    portfolio_item_id: UUID
    set_number: str
    set_name: str | None
    label: PortfolioRecommendationLabel
    priority: int = Field(..., ge=1)
    confidence: str
    reason_codes: list[str]
    data_quality_flags: list[str]


class PortfolioConfidenceSummary(BaseModel):
    overall: Literal["low", "medium", "high"]
    item_counts: dict[str, int]


class PortfolioDataQualityWarning(BaseModel):
    code: str
    affected_holding_count: int = Field(..., ge=1)
    message: str


class LlmPortfolioObservation(BaseModel):
    source_metric: str = Field(..., min_length=1, max_length=160)
    text: str = Field(..., min_length=1, max_length=320)

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def reject_unsupported_claims(cls, value: str) -> str:
        if _UNSUPPORTED_OUTPUT_PATTERN.search(value):
            raise ValueError(
                "portfolio observations cannot contain numeric market claims"
            )
        return value


class LlmPortfolioAction(BaseModel):
    item_key: str = Field(..., min_length=1, max_length=160)
    label: PortfolioRecommendationLabel
    priority: int = Field(..., ge=1)
    text: str = Field(..., min_length=1, max_length=320)

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def reject_unsupported_claims(cls, value: str) -> str:
        if _UNSUPPORTED_OUTPUT_PATTERN.search(value):
            raise ValueError("portfolio actions cannot contain numeric market claims")
        return value


class LlmPortfolioUncertainty(BaseModel):
    code: str = Field(..., min_length=1, max_length=80)
    text: str = Field(..., min_length=1, max_length=320)

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def reject_unsupported_claims(cls, value: str) -> str:
        if _UNSUPPORTED_OUTPUT_PATTERN.search(value):
            raise ValueError(
                "portfolio uncertainties cannot contain numeric market claims"
            )
        return value


class LlmPortfolioNarrative(BaseModel):
    """Bounded prose over calculated portfolio metrics and item labels."""

    executive_summary: str = Field(..., min_length=1, max_length=500)
    diversification_observations: list[LlmPortfolioObservation] = Field(
        default_factory=list, max_length=6
    )
    concentration_observations: list[LlmPortfolioObservation] = Field(
        default_factory=list, max_length=6
    )
    prioritized_actions: list[LlmPortfolioAction] = Field(
        default_factory=list, max_length=10
    )
    uncertainties: list[LlmPortfolioUncertainty] = Field(
        default_factory=list, max_length=6
    )
    prompt_version: Literal[PORTFOLIO_ANALYSIS_PROMPT_VERSION] = (
        PORTFOLIO_ANALYSIS_PROMPT_VERSION
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("executive_summary")
    @classmethod
    def reject_unsupported_claims(cls, value: str) -> str:
        if _UNSUPPORTED_OUTPUT_PATTERN.search(value):
            raise ValueError("portfolio summary cannot contain numeric market claims")
        return value


class PortfolioAnalysisResponse(BaseModel):
    """A refreshed portfolio snapshot plus deterministic labels and optional prose."""

    id: UUID
    generated_at: datetime
    analytics: PortfolioAnalyticsResponse
    item_recommendations: list[PortfolioItemRecommendation]
    confidence_summary: PortfolioConfidenceSummary
    data_quality_warnings: list[PortfolioDataQualityWarning]
    ai_narrative: LlmPortfolioNarrative | None = None
    ai_narrative_status: LlmNarrativeStatus = "disabled"


class PortfolioAnalysisHistoryEntry(BaseModel):
    """Immutable analysis metadata and context available for historical comparison."""

    id: UUID
    generated_at: datetime
    method_version: str
    prompt_version: str
    ai_narrative_status: LlmNarrativeStatus
    portfolio_context: dict
    item_recommendations: list[PortfolioItemRecommendation]
    confidence_summary: PortfolioConfidenceSummary
    data_quality_warnings: list[PortfolioDataQualityWarning]


class PortfolioRecommendationChange(BaseModel):
    set_number: str
    set_name: str | None
    previous_label: PortfolioRecommendationLabel | None
    current_label: PortfolioRecommendationLabel | None
    previous_confidence: str | None
    current_confidence: str | None
    change_type: Literal["added", "removed", "changed", "unchanged"]
    is_reversal: bool


class PortfolioAnalysisComparisonResponse(BaseModel):
    previous_analysis_id: UUID
    current_analysis_id: UUID
    previous_generated_at: datetime
    current_generated_at: datetime
    changes: list[PortfolioRecommendationChange]
