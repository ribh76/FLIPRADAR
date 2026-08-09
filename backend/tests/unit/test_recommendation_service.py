import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from flipradar.api.schemas.recommendation_schema import (
    AnalyzeRequest,
    ManualValuationOverride,
    UserGoal,
)
from flipradar.core.settings import LlmProviderName, LlmSettings
from flipradar.integrations.llm_provider import LlmCompletion, LlmUsage
from flipradar.services import llm_recommendation_service, recommendation_service
from flipradar.services.llm_recommendation_service import LlmNarrativeResult


async def _empty_snapshots(_db, _set_number):
    return []


@pytest.mark.asyncio
async def test_analyze_returns_insufficient_data_error_without_market_or_override(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        recommendation_service, "_get_lego_set", lambda _db, _set_number: _lego_set()
    )
    monkeypatch.setattr(
        recommendation_service, "get_latest_snapshots_by_set_number", _empty_snapshots
    )

    with pytest.raises(
        recommendation_service.InsufficientValuationDataError,
        match="Insufficient data",
    ):
        await recommendation_service.analyze_set(
            object(),
            AnalyzeRequest(
                set_number="75192",
                user_goal=UserGoal.BUY_VS_PASS,
                asking_price=Decimal("100.00"),
                condition="new",
            ),
        )


@pytest.mark.asyncio
async def test_analyze_uses_documented_manual_override_when_market_data_is_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        recommendation_service, "_get_lego_set", lambda _db, _set_number: _lego_set()
    )
    monkeypatch.setattr(
        recommendation_service, "get_latest_snapshots_by_set_number", _empty_snapshots
    )
    monkeypatch.setattr(recommendation_service, "_save_recommendation", _save_nothing)

    response = await recommendation_service.analyze_set(
        object(),
        AnalyzeRequest(
            set_number="75192",
            user_goal=UserGoal.BUY_VS_PASS,
            asking_price=Decimal("100.00"),
            condition="new",
            manual_valuation_override=ManualValuationOverride(
                expected_value=Decimal("200.00"),
                reason="Verified collector sale.",
            ),
        ),
    )

    assert response["fair_value"] == 200.0
    assert response["valuation_source"] == "manual_override"


@pytest.mark.asyncio
async def test_analyze_keeps_deterministic_result_when_llm_output_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        recommendation_service, "_get_lego_set", lambda _db, _set_number: _lego_set()
    )
    monkeypatch.setattr(
        recommendation_service, "get_latest_snapshots_by_set_number", _empty_snapshots
    )
    monkeypatch.setattr(recommendation_service, "_save_recommendation", _save_nothing)

    async def invalid_narrative(*_args, **_kwargs):
        return LlmNarrativeResult(status="invalid_response", narrative=None)

    monkeypatch.setattr(
        recommendation_service,
        "maybe_generate_recommendation_narrative",
        invalid_narrative,
    )

    response = await recommendation_service.analyze_set(
        object(),
        AnalyzeRequest(
            set_number="75192",
            user_goal=UserGoal.BUY_VS_PASS,
            asking_price=Decimal("100.00"),
            condition="new",
            manual_valuation_override=ManualValuationOverride(
                expected_value=Decimal("200.00"),
                reason="Verified collector sale.",
            ),
        ),
    )

    assert response["recommendation"] == "BUY"
    assert response["fair_value"] == 200.0
    assert response["ai_narrative"] is None
    assert response["ai_narrative_status"] == "invalid_response"


@pytest.mark.asyncio
async def test_analyze_returns_validated_mocked_llm_narrative(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        recommendation_service, "_get_lego_set", lambda _db, _set_number: _lego_set()
    )
    monkeypatch.setattr(
        recommendation_service, "get_latest_snapshots_by_set_number", _empty_snapshots
    )
    monkeypatch.setattr(recommendation_service, "_save_recommendation", _save_nothing)
    settings = LlmSettings(
        enabled=True,
        provider=LlmProviderName.ANTHROPIC,
        api_key="test-key",
        model="claude-test",
        timeout_seconds=1,
        max_tokens=100,
        max_retries=0,
        retry_backoff_seconds=0,
        user_rate_limit=10,
        global_rate_limit=100,
        rate_limit_window_seconds=60,
        input_cost_per_million_tokens=3.0,
        output_cost_per_million_tokens=15.0,
    )

    class Provider:
        def complete(self, _request):
            return LlmCompletion(
                text=json.dumps(
                    {
                        "summary": "The deterministic recommendation has a favorable calculated spread.",
                        "facts": [
                            {
                                "source_metric": "fair_value",
                                "text": "The calculated valuation supports the deterministic result.",
                            }
                        ],
                        "uncertainties": [
                            {
                                "code": "manual_valuation",
                                "text": "The valuation depends on documented manual evidence.",
                            }
                        ],
                    }
                ),
                model="claude-test",
                stop_reason="end_turn",
                usage=LlmUsage(input_tokens=10, output_tokens=5),
            )

    monkeypatch.setattr(
        llm_recommendation_service,
        "get_settings",
        lambda: SimpleNamespace(llm=settings),
    )
    monkeypatch.setattr(
        llm_recommendation_service, "create_llm_provider", lambda _settings: Provider()
    )

    response = await recommendation_service.analyze_set(
        object(),
        AnalyzeRequest(
            set_number="75192",
            user_goal=UserGoal.BUY_VS_PASS,
            asking_price=Decimal("100.00"),
            condition="new",
            manual_valuation_override=ManualValuationOverride(
                expected_value=Decimal("200.00"),
                reason="Verified collector sale.",
            ),
        ),
    )

    assert response["recommendation"] == "BUY"
    assert response["ai_narrative_status"] == "available"
    assert response["ai_narrative"].prompt_version == "recommendation-narrative-v1"


async def _save_nothing(*_args, **_kwargs):
    return None


async def _lego_set():
    return SimpleNamespace(id="set-id")
