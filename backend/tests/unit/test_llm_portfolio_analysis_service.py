import json
from uuid import uuid4

import pytest

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
                "confidence": "medium",
                "reason_codes": ["strong_profit"],
                "data_quality_flags": [],
            }
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
            "confidence": "medium",
            "reason_codes": ["strong_profit"],
            "data_quality_flags": [],
        }
    }
    assert result["allowed_uncertainty_codes"] == [
        "incomplete_valuation_coverage",
        "insufficient_market_data",
        "stale_valuations",
    ]


def test_portfolio_narrative_cannot_change_deterministic_item_label() -> None:
    payload = portfolio_analysis_payload()
    item_id = str(payload["item_recommendations"][0]["portfolio_item_id"])
    provider = FakeProvider(
        json.dumps(
            {
                "executive_summary": "The calculated portfolio profile calls for deliberate review.",
                "observations": [
                    {
                        "source_metric": "portfolio.concentration",
                        "text": "The calculated concentration profile merits attention.",
                    }
                ],
                "actions": [
                    {
                        "item_key": item_id,
                        "label": "hold",
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
                "observations": [
                    {
                        "source_metric": "portfolio.concentration",
                        "text": "The calculated concentration profile merits attention.",
                    }
                ],
                "actions": [
                    {
                        "item_key": item_id,
                        "label": "consider_selling",
                        "text": "Keep this item under review.",
                    }
                ],
                "uncertainties": [
                    {
                        "code": "stale_valuations",
                        "text": "Some calculated inputs need a freshness review.",
                    }
                ],
            }
        )
    )

    narrative, completion = generate_portfolio_narrative(provider, payload)

    assert completion.model == "claude-test"
    assert narrative.actions[0].label == "consider_selling"
    assert provider.request is not None
    assert provider.request.max_tokens == 900


@pytest.mark.asyncio
async def test_portfolio_analysis_derives_labels_before_calling_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item_id = uuid4()
    analytics = {
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
        ]
    }
    captured: dict = {}

    async def refresh(_db, _user_id):
        return analytics

    async def narrate(analysis, *, user_key):
        captured["analysis"] = analysis
        captured["user_key"] = user_key
        return PortfolioLlmNarrativeResult(status="disabled", narrative=None)

    monkeypatch.setattr(
        portfolio_analysis_service.portfolio_analytics_service,
        "refresh_portfolio_analytics",
        refresh,
    )
    monkeypatch.setattr(
        portfolio_analysis_service, "maybe_generate_portfolio_narrative", narrate
    )

    response = await portfolio_analysis_service.analyze_portfolio(None, item_id)

    assert captured["user_key"] == f"user:{item_id}"
    assert captured["analysis"]["item_recommendations"] == [
        {
            "portfolio_item_id": item_id,
            "set_number": "12345",
            "set_name": "Example Set",
            "label": "watch",
            "confidence": "low",
            "reason_codes": ["valuation_freshness"],
            "data_quality_flags": ["stale_valuation"],
        }
    ]
    assert response["ai_narrative_status"] == "disabled"
