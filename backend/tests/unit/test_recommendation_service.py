from decimal import Decimal
from types import SimpleNamespace

import pytest

from flipradar.api.schemas.recommendation_schema import (
    AnalyzeRequest,
    ManualValuationOverride,
    UserGoal,
)
from flipradar.services import recommendation_service


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


async def _save_nothing(*_args, **_kwargs):
    return None


async def _lego_set():
    return SimpleNamespace(id="set-id")
