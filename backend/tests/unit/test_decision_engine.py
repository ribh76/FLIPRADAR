from decimal import Decimal

from flipradar.api.schemas import RecommendationDecision, UserGoal
from flipradar.domain.engines.decision_engine import decide


def score(score_value: int, deal_band: str = "strong") -> dict:
    return {
        "score": score_value,
        "margin_percent": Decimal("12.0"),
        "deal_band": deal_band,
    }


def test_decision_engine_buy_goal_thresholds():
    assert (
        decide(
            score(75), UserGoal.BUY, Decimal("90.00"), Decimal("100.00")
        ).recommendation
        == RecommendationDecision.BUY
    )
    assert (
        decide(
            score(55), UserGoal.BUY, Decimal("98.00"), Decimal("100.00")
        ).recommendation
        == RecommendationDecision.WATCH
    )
    assert (
        decide(
            score(54), UserGoal.BUY, Decimal("115.00"), Decimal("100.00")
        ).recommendation
        == RecommendationDecision.PASS
    )


def test_decision_engine_buy_or_pass_matches_buy():
    result = decide(
        score(82),
        UserGoal.BUY_VS_PASS,
        Decimal("550.00"),
        Decimal("625.00"),
    )

    assert result.recommendation == RecommendationDecision.BUY


def test_decision_engine_sell_goal_uses_fair_value():
    assert (
        decide(
            score(70), UserGoal.SELL, Decimal("100.00"), Decimal("100.00")
        ).recommendation
        == RecommendationDecision.SELL
    )
    assert (
        decide(
            score(70), UserGoal.SELL, Decimal("90.00"), Decimal("100.00")
        ).recommendation
        == RecommendationDecision.HOLD
    )


def test_decision_engine_hold_or_sell_uses_trend():
    assert (
        decide(
            score(80),
            UserGoal.HOLD_OR_SELL,
            Decimal("100.00"),
            Decimal("100.00"),
            trend="upward",
        ).recommendation
        == RecommendationDecision.HOLD
    )
    assert (
        decide(
            score(80, "strong"),
            UserGoal.HOLD_OR_SELL,
            Decimal("100.00"),
            Decimal("100.00"),
            trend="flat",
        ).recommendation
        == RecommendationDecision.SELL
    )


def test_decision_engine_hold_or_sell_holds_when_value_is_not_favorable():
    result = decide(
        score(45, "bad"),
        UserGoal.HOLD_OR_SELL,
        Decimal("115.00"),
        Decimal("100.00"),
        trend="down",
    )

    assert result.recommendation == RecommendationDecision.HOLD
    assert (
        result.reasoning
        == "Market trend is flat/down, but current value is not favorable enough."
    )


def test_decision_engine_no_snapshots_watches():
    result = decide(
        score(25, "bad"),
        UserGoal.BUY,
        Decimal("100.00"),
        Decimal("0.00"),
        has_snapshots=False,
    )

    assert result.recommendation == RecommendationDecision.WATCH
    assert result.reasoning == "No price snapshots found for this set."
