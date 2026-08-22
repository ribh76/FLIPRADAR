import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas.portfolio_analysis_schema import (
    portfolio_recommendation_label,
)
from flipradar.integrations.llm_provider import (
    LlmCompletion,
    LlmCompletionRequest,
    LlmProvider,
)
from flipradar.services import portfolio_analysis_service
from flipradar.services.llm_portfolio_analysis_service import (
    PortfolioLlmNarrativeResult,
    PortfolioPromptMetrics,
    build_portfolio_analysis_prompt,
    generate_portfolio_narrative,
)
from flipradar.services.llm_recommendation_service import LlmStructuredOutputError


class FakeProvider(LlmProvider):
    def __init__(self, text: str) -> None:
        self.text = text
        self.request: LlmCompletionRequest | None = None

    def complete(self, request: LlmCompletionRequest) -> LlmCompletion:
        self.request = request
        return LlmCompletion(
            text=self.text,
            model="claude-test",
            stop_reason="end_turn",
            usage=None,
        )


def test_portfolio_recommendation_label_narrows_only_supported_categories() -> None:
    assert portfolio_recommendation_label("watch") == "watch"
    with pytest.raises(ValueError, match="Unsupported portfolio recommendation label"):
        portfolio_recommendation_label("sell_consideration")


def portfolio_analysis_payload() -> dict:
    item_id = uuid4()
    return {
        "analytics": {
            "holding_count": 2,
            "valued_holding_count": 1,
            "total_cost_basis": 300,
            "total_market_value": 250,
            "summary_metrics": {
                "concentration": {"level": "high", "largest_holding_percent": 75},
                "diversification": {"distinct_sets": 2, "value_coverage_percent": 50},
                "signals": {"hold": 1, "watch": 0, "sell_consideration": 1},
                "valuation_attention": {
                    "stale": [{"set_number": "12345"}],
                    "low_confidence": [],
                    "insufficient_data": [{"set_number": "67890"}],
                },
            },
        },
        "item_recommendations": [
            {
                "portfolio_item_id": item_id,
                "set_number": "12345",
                "set_name": "Untrusted catalog name",
                "label": "consider_selling",
                "priority": 1,
                "confidence": "medium",
                "reason_codes": ["strong_profit"],
                "data_quality_flags": [],
            }
        ],
        "confidence_summary": {
            "overall": "medium",
            "item_counts": {"high": 0, "medium": 1, "low": 0},
        },
        "data_quality_warnings": [
            {
                "code": "stale_valuation",
                "affected_holding_count": 1,
                "message": "Some holdings use valuation evidence that needs refreshing.",
            },
            {
                "code": "insufficient_market_data",
                "affected_holding_count": 1,
                "message": "Some holdings do not have enough market data for a current valuation.",
            },
        ],
    }


def test_portfolio_prompt_exposes_only_whitelisted_metrics_and_labels() -> None:
    payload = portfolio_analysis_payload()
    prompt = build_portfolio_analysis_prompt(
        PortfolioPromptMetrics.from_analysis(payload)
    )
    result = json.loads(prompt)

    assert "Untrusted catalog name" not in prompt
    assert result["calculated_metrics"]["portfolio.signal_counts"] == {
        "hold": 1,
        "watch": 0,
        "sell_consideration": 1,
    }
    assert result["item_metrics"] == {
        str(payload["item_recommendations"][0]["portfolio_item_id"]): {
            "label": "consider_selling",
            "priority": 1,
            "confidence": "medium",
            "reason_codes": ["strong_profit"],
            "data_quality_flags": [],
        }
    }
    assert result["allowed_uncertainty_codes"] == [
        "insufficient_market_data",
        "stale_valuation",
    ]


def test_portfolio_narrative_cannot_change_deterministic_item_label() -> None:
    payload = portfolio_analysis_payload()
    item_id = str(payload["item_recommendations"][0]["portfolio_item_id"])
    provider = FakeProvider(
        json.dumps(
            {
                "executive_summary": "The calculated portfolio profile calls for deliberate review.",
                "diversification_observations": [],
                "concentration_observations": [
                    {
                        "source_metric": "portfolio.concentration",
                        "text": "The calculated concentration profile merits attention.",
                    }
                ],
                "prioritized_actions": [
                    {
                        "item_key": item_id,
                        "label": "hold",
                        "priority": 1,
                        "text": "Keep this item under review.",
                    }
                ],
                "uncertainties": [],
            }
        )
    )

    with pytest.raises(LlmStructuredOutputError):
        generate_portfolio_narrative(provider, payload)


def test_portfolio_narrative_accepts_calculated_metric_and_matching_label() -> None:
    payload = portfolio_analysis_payload()
    item_id = str(payload["item_recommendations"][0]["portfolio_item_id"])
    provider = FakeProvider(
        json.dumps(
            {
                "executive_summary": "The calculated portfolio profile calls for deliberate review.",
                "diversification_observations": [
                    {
                        "source_metric": "portfolio.diversification",
                        "text": "The calculated mix has room for further review.",
                    }
                ],
                "concentration_observations": [
                    {
                        "source_metric": "portfolio.concentration",
                        "text": "The calculated concentration profile merits attention.",
                    }
                ],
                "prioritized_actions": [
                    {
                        "item_key": item_id,
                        "label": "consider_selling",
                        "priority": 1,
                        "text": "Keep this item under review.",
                    }
                ],
                "uncertainties": [
                    {
                        "code": "stale_valuation",
                        "text": "Some calculated inputs need a freshness review.",
                    }
                ],
            }
        )
    )

    narrative, completion = generate_portfolio_narrative(provider, payload)

    assert completion.model == "claude-test"
    assert narrative.prioritized_actions[0].label == "consider_selling"
    assert provider.request is not None
    assert provider.request.max_tokens == 900


@pytest.mark.asyncio
async def test_portfolio_analysis_derives_labels_before_calling_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item_id = uuid4()
    analytics = {
        "id": item_id,
        "generated_at": "2026-08-09T12:00:00Z",
        "holdings": [
            {
                "portfolio_item_id": item_id,
                "set_number": "12345",
                "flags": ["stale_valuation"],
                "metrics": {
                    "set_name": "Example Set",
                    "signal": {
                        "category": "watch",
                        "confidence": "low",
                        "reason_codes": ["valuation_freshness"],
                    },
                },
            }
        ],
    }
    captured: dict = {}

    async def refresh(_db, _user_id, *, portfolio_id=None):
        del portfolio_id
        return analytics

    async def narrate(analysis, *, user_key):
        captured["analysis"] = analysis
        captured["user_key"] = user_key
        return PortfolioLlmNarrativeResult(status="disabled", narrative=None)

    async def store(_db, *, analysis_data):
        captured["stored"] = analysis_data
        return type(
            "Stored", (), {"id": item_id, "generated_at": analytics["generated_at"]}
        )()

    monkeypatch.setattr(
        portfolio_analysis_service.portfolio_analytics_service,
        "refresh_portfolio_analytics",
        refresh,
    )
    monkeypatch.setattr(
        portfolio_analysis_service, "maybe_generate_portfolio_narrative", narrate
    )
    monkeypatch.setattr(portfolio_analysis_service, "create_portfolio_analysis", store)

    db_session = AsyncMock(spec=AsyncSession)
    response = await portfolio_analysis_service.analyze_portfolio(db_session, item_id)

    assert captured["user_key"] == f"user:{item_id}"
    assert captured["analysis"]["item_recommendations"] == [
        {
            "portfolio_item_id": item_id,
            "set_number": "12345",
            "set_name": "Example Set",
            "label": "watch",
            "priority": 2,
            "confidence": "low",
            "reason_codes": ["valuation_freshness"],
            "data_quality_flags": ["stale_valuation"],
        }
    ]
    assert captured["analysis"]["confidence_summary"] == {
        "overall": "low",
        "item_counts": {"high": 0, "medium": 0, "low": 1},
    }
    assert captured["analysis"]["data_quality_warnings"] == [
        {
            "code": "stale_valuation",
            "affected_holding_count": 1,
            "message": "Some holdings use valuation evidence that needs refreshing.",
        }
    ]
    assert captured["stored"]["ai_narrative_status"] == "disabled"
    assert response["ai_narrative_status"] == "disabled"
