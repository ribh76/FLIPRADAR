import json
from types import SimpleNamespace

import pytest

from flipradar.integrations.llm_provider import (
    LlmCompletion,
    LlmCompletionRequest,
    LlmProvider,
    LlmProviderTimeoutError,
    LlmUsage,
)
from flipradar.services import llm_recommendation_service
from flipradar.services.llm_recommendation_service import (
    SYSTEM_PROMPT,
    LlmExecutionPolicy,
    LlmRateLimiter,
    LlmStructuredOutputError,
    LlmUsageTracker,
    RecommendationPromptMetrics,
    build_recommendation_prompt,
    generate_narrative_with_guardrails,
    generate_recommendation_narrative,
    maybe_generate_recommendation_narrative,
)


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


class SequenceProvider(LlmProvider):
    def __init__(self, outcomes: list[Exception | str]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def complete(self, _request: LlmCompletionRequest) -> LlmCompletion:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return LlmCompletion(
            text=outcome,
            model="claude-test",
            stop_reason="end_turn",
            usage=LlmUsage(input_tokens=10, output_tokens=4),
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


def valid_narrative_json() -> str:
    return json.dumps(
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


def execution_policy(**overrides: object) -> LlmExecutionPolicy:
    values = {
        "max_retries": 1,
        "retry_backoff_seconds": 0.1,
        "user_rate_limit": 2,
        "global_rate_limit": 3,
        "rate_limit_window_seconds": 60,
        "input_cost_per_million_tokens": 3.0,
        "output_cost_per_million_tokens": 15.0,
    }
    values.update(overrides)
    return LlmExecutionPolicy(**values)


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
    assert narrative.prompt_version == "recommendation-narrative-v1"


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


def test_guarded_workflow_retries_timeout_and_tracks_usage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = execution_policy()
    provider = SequenceProvider(
        [LlmProviderTimeoutError("timeout"), valid_narrative_json()]
    )
    usage_tracker = LlmUsageTracker()
    delays: list[float] = []

    result = generate_narrative_with_guardrails(
        provider,
        analysis_payload(),
        user_key="user:one",
        policy=policy,
        limiter=LlmRateLimiter(policy),
        usage_tracker=usage_tracker,
        sleep_fn=delays.append,
    )

    assert result.status == "available"
    assert result.narrative is not None
    assert provider.calls == 2
    assert delays == [0.1]
    record = usage_tracker.snapshot()[0]
    assert record.prompt_version == "recommendation-narrative-v1"
    assert record.input_tokens == 10
    assert record.output_tokens == 4
    assert record.estimated_cost_usd == pytest.approx(0.00009)
    assert "timeout attempt=1/2" in caplog.text
    assert "retry attempt=2/2" in caplog.text


def test_guarded_workflow_enforces_user_and_global_quotas() -> None:
    policy = execution_policy(user_rate_limit=1, global_rate_limit=2)
    limiter = LlmRateLimiter(policy)
    provider = SequenceProvider([valid_narrative_json(), valid_narrative_json()])

    first = generate_narrative_with_guardrails(
        provider,
        analysis_payload(),
        user_key="user:one",
        policy=policy,
        limiter=limiter,
    )
    per_user = generate_narrative_with_guardrails(
        provider,
        analysis_payload(),
        user_key="user:one",
        policy=policy,
        limiter=limiter,
    )
    second = generate_narrative_with_guardrails(
        provider,
        analysis_payload(),
        user_key="user:two",
        policy=policy,
        limiter=limiter,
    )
    global_limit = generate_narrative_with_guardrails(
        provider,
        analysis_payload(),
        user_key="user:three",
        policy=policy,
        limiter=limiter,
    )

    assert first.status == "available"
    assert per_user.status == "rate_limited"
    assert second.status == "available"
    assert global_limit.status == "rate_limited"
    assert provider.calls == 2


def test_guarded_workflow_falls_back_on_invalid_model_output() -> None:
    policy = execution_policy()
    provider = SequenceProvider(
        [
            json.dumps(
                {"summary": "The value is $999.", "facts": [], "uncertainties": []}
            )
        ]
    )

    result = generate_narrative_with_guardrails(
        provider,
        analysis_payload(),
        user_key="user:one",
        policy=policy,
        limiter=LlmRateLimiter(policy),
    )

    assert result.status == "invalid_response"
    assert result.narrative is None


@pytest.mark.asyncio
async def test_optional_workflow_falls_back_on_unexpected_provider_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = execution_policy()
    configured_llm = SimpleNamespace(configured=True, **policy.__dict__)

    class BrokenProvider(LlmProvider):
        def complete(self, _request: LlmCompletionRequest) -> LlmCompletion:
            raise RuntimeError("unexpected provider failure")

    monkeypatch.setattr(
        llm_recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(llm=configured_llm),
    )
    monkeypatch.setattr(
        llm_recommendation_service,
        "create_llm_provider",
        lambda _settings: BrokenProvider(),
    )

    result = await maybe_generate_recommendation_narrative(analysis_payload())

    assert result.status == "failed"
    assert result.narrative is None
