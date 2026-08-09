"""Schemas for an authenticated, deterministic portfolio analysis run."""

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flipradar.api.schemas.llm_analysis_schema import LlmNarrativeStatus
from flipradar.api.schemas.portfolio_schema import PortfolioAnalyticsResponse

PORTFOLIO_ANALYSIS_PROMPT_VERSION = "portfolio-analysis-v1"

PortfolioRecommendationLabel = Literal[
    "hold", "watch", "consider_selling", "insufficient_data"
]

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
    confidence: str
    reason_codes: list[str]
    data_quality_flags: list[str]


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
    observations: list[LlmPortfolioObservation] = Field(
        default_factory=list, max_length=6
    )
    actions: list[LlmPortfolioAction] = Field(default_factory=list, max_length=10)
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

    analytics: PortfolioAnalyticsResponse
    item_recommendations: list[PortfolioItemRecommendation]
    ai_narrative: LlmPortfolioNarrative | None = None
    ai_narrative_status: LlmNarrativeStatus = "disabled"
