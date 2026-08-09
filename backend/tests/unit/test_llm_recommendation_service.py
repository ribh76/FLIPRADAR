import json

import pytest

from flipradar.integrations.llm_provider import LlmCompletion, LlmCompletionRequest
from flipradar.services.llm_recommendation_service import (
    SYSTEM_PROMPT,
    LlmStructuredOutputError,
    RecommendationPromptMetrics,
    build_recommendation_prompt,
    generate_recommendation_narrative,
)


class FakeProvider:
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


def analysis_payload() -> dict:
    return {
        "recommendation": "BUY",
        "confidence": "low",
        "score": 82,
        "valuation_source": "market",
        "fair_value": 200.0,
        "market_low": 175.0,
        "market_high": 225.0,
        "listing_count": 2,
        "all_in_price": 150.0,
        "discount_pct": 25.0,
        "condition": "new",
        # Deliberately untrusted/raw fields that must never enter the prompt.
        "listing_title": "Rare eBay deal from a private seller",
        "raw_payload": {"seller": "Example Seller", "price": "999.99"},
    }


def test_prompt_contains_only_whitelisted_calculated_metrics() -> None:
    prompt = build_recommendation_prompt(
        RecommendationPromptMetrics.from_analysis(analysis_payload())
    )
    payload = json.loads(prompt)

    assert "listing_title" not in prompt
    assert "raw_payload" not in prompt
    assert "Example Seller" not in prompt
    assert payload["calculated_metrics"] == {
        "all_in_price": 150.0,
        "confidence": "low",
        "decision": "BUY",
        "discount_percent": 25.0,
        "fair_value": 200.0,
        "listing_count": 2,
        "market_range": {"high": 225.0, "low": 175.0},
        "score": 82,
        "valuation_source": "market",
    }
    assert payload["allowed_uncertainty_codes"] == [
        "limited_listing_evidence",
        "low_confidence",
    ]
    assert "Never invent" in SYSTEM_PROMPT
    assert "Never name a marketplace" in SYSTEM_PROMPT


def test_validated_narrative_links_facts_and_uncertainty_to_allowed_inputs() -> None:
    provider = FakeProvider(
        json.dumps(
            {
                "summary": "The deterministic recommendation has a favorable calculated spread.",
                "facts": [
                    {
                        "source_metric": "discount_percent",
                        "text": "The deterministic spread supports the recommendation.",
                    }
                ],
                "uncertainties": [
                    {
                        "code": "low_confidence",
                        "text": "Use the result carefully because the evidence is limited.",
                    }
                ],
            }
        )
    )

    narrative = generate_recommendation_narrative(provider, analysis_payload())

    assert narrative.facts[0].source_metric == "discount_percent"
    assert narrative.uncertainties[0].code == "low_confidence"
    assert provider.request is not None
    assert provider.request.max_tokens == 600


@pytest.mark.parametrize(
    "text",
    [
        "The value is $999.",
        "eBay activity supports this recommendation.",
        "The evidence includes two listings.",
    ],
)
def test_narrative_rejects_prices_marketplaces_and_numeric_claims(text: str) -> None:
    provider = FakeProvider(
        json.dumps({"summary": text, "facts": [], "uncertainties": []})
    )

    with pytest.raises(LlmStructuredOutputError):
        generate_recommendation_narrative(provider, analysis_payload())


def test_narrative_rejects_unavailable_metric_and_unknown_fields() -> None:
    provider = FakeProvider(
        json.dumps(
            {
                "summary": "The result reflects deterministic calculations.",
                "facts": [
                    {
                        "source_metric": "trend_percent",
                        "text": "The calculated direction informs the result.",
                    }
                ],
                "uncertainties": [],
                "invented_field": "not allowed",
            }
        )
    )

    with pytest.raises(LlmStructuredOutputError):
        generate_recommendation_narrative(provider, analysis_payload())
