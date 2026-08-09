from flipradar.domain.engines.hold_sell_engine import (
    RECOMMENDATION_CATEGORY_DEFINITIONS,
    WEIGHTED_INPUTS,
    RecommendationCategory,
    _category_for_score,
    decide_sell_or_hold,
)


def test_category_score_boundaries_are_explicit_and_stable():
    assert _category_for_score(44) is RecommendationCategory.HOLD
    assert _category_for_score(45) is RecommendationCategory.WATCH
    assert _category_for_score(64) is RecommendationCategory.WATCH
    assert _category_for_score(65) is RecommendationCategory.CONSIDER_SELLING


def test_consider_selling_uses_all_weighted_inputs_with_high_confidence():
    result = decide_sell_or_hold(
        set_number="75192",
        fair_value=200.00,
        listing_count=24,
        confidence="high",
        purchase_price=100.00,
        recent_fair_values=[180.00, 170.00, 140.00],
        concentration_percent=50.0,
        marketplace_supply=24,
        supply_reliable=True,
        demand_signal="strong",
        valuation_age_days=1,
    )

    assert result["verdict"] == "SELL"
    assert result["category"] == RecommendationCategory.CONSIDER_SELLING
    assert result["score"] == 84
    assert result["recommendation_confidence"] == "high"
    assert result["trend_label"] == "falling"
    assert result["profit_pct"] == 74.0
    assert [input_["factor"] for input_ in result["weighted_inputs"]] == list(
        WEIGHTED_INPUTS
    )
    assert sum(input_["weight"] for input_ in result["weighted_inputs"]) == 100
    assert result["weighted_inputs"][0]["contribution"] == 14.0
    assert any(reason["code"] == "supply_and_demand" for reason in result["reasons"])
    assert "not financial advice" in result["warnings"][0]


def test_watch_category_is_used_when_freshness_and_confidence_are_weak():
    result = decide_sell_or_hold(
        set_number="75313",
        fair_value=100.00,
        confidence="low",
        purchase_price=70.00,
        recent_fair_values=[100.00, 101.00, 100.00],
        marketplace_supply=2,
        supply_reliable=False,
        valuation_age_days=21,
    )

    assert result["verdict"] == "WATCH"
    assert result["category"] == RecommendationCategory.WATCH
    assert result["recommendation_confidence"] == "low"
    assert result["trend_label"] == "flat"
    assert "valuation_confidence_low" in result["reason_codes"]
    assert "Marketplace supply is not reliable" in " ".join(result["warnings"])
    freshness = next(
        input_
        for input_ in result["weighted_inputs"]
        if input_["factor"] == "freshness"
    )
    assert freshness["contribution"] == -2.5


def test_insufficient_data_category_is_returned_without_a_valuation():
    result = decide_sell_or_hold(set_number="00000", fair_value=None)

    assert result["verdict"] == "HOLD"
    assert result["category"] == RecommendationCategory.INSUFFICIENT_DATA
    assert result["recommendation_confidence"] == "low"
    assert result["reason_codes"] == ["missing_fair_value"]
    assert result["weighted_inputs"] == []
    assert (
        result["reasoning"]
        == RECOMMENDATION_CATEGORY_DEFINITIONS[RecommendationCategory.INSUFFICIENT_DATA]
    )


def test_low_confidence_prevents_a_sell_category_at_the_rule_boundary():
    result = decide_sell_or_hold(
        set_number="low-confidence-boundary",
        fair_value=200.00,
        confidence="low",
        purchase_price=80.00,
        recent_fair_values=[200.00, 180.00, 140.00],
        concentration_percent=50.0,
        marketplace_supply=20,
        supply_reliable=True,
        demand_signal="strong",
        valuation_age_days=1,
    )

    assert result["score"] >= 65
    assert result["recommendation_confidence"] == "low"
    assert result["verdict"] == "WATCH"
    assert result["category"] == RecommendationCategory.WATCH
    assert "consideration_downgraded_low_confidence" in result["reason_codes"]


def test_freshness_boundary_changes_the_weighted_contribution():
    base_inputs = {
        "set_number": "freshness-boundary",
        "fair_value": 100.00,
        "confidence": "high",
        "purchase_price": 100.00,
        "recent_fair_values": [100.00, 100.00, 100.00],
    }
    within_window = decide_sell_or_hold(**base_inputs, valuation_age_days=14)
    stale = decide_sell_or_hold(**base_inputs, valuation_age_days=15)

    fresh_weight = next(
        input_
        for input_ in within_window["weighted_inputs"]
        if input_["factor"] == "freshness"
    )
    stale_weight = next(
        input_ for input_ in stale["weighted_inputs"] if input_["factor"] == "freshness"
    )
    assert fresh_weight["contribution"] == 0.0
    assert stale_weight["contribution"] == -2.5
    assert stale["score"] == within_window["score"] - 2


def test_reasoning_and_structured_messages_avoid_guaranteed_claims():
    result = decide_sell_or_hold(
        set_number="safe-language",
        fair_value=150.00,
        confidence="high",
        purchase_price=100.00,
        recent_fair_values=[180.00, 160.00, 150.00],
        valuation_age_days=1,
    )

    messages = [
        result["reasoning"],
        *result["warnings"],
        *(reason["statement"] for reason in result["reasons"]),
    ]
    assert not any("guarantee" in message.lower() for message in messages)
    assert not any("will profit" in message.lower() for message in messages)
