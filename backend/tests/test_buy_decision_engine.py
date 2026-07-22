from engine.buy_decision_engine import decide_buy_or_pass


def test_buy_decision_engine_deep_discount_buy():
    result = decide_buy_or_pass(
        set_number="75192",
        asking_price=450.00,
        fair_value=625.00,
        market_low=590.00,
        market_high=700.00,
        listing_count=22,
        confidence="high",
    )

    assert result["verdict"] == "BUY"
    assert result["score"] == 100
    assert result["all_in_price"] == 450.00
    assert result["discount_pct"] == 28.0
    assert "deep_discount" in result["reason_codes"]
    assert "meets_target_roi" in result["reason_codes"]
    assert "high_confidence_data" in result["reason_codes"]
    assert "strong_market_depth" in result["reason_codes"]


def test_buy_decision_engine_low_confidence_downgrades_buy():
    result = decide_buy_or_pass(
        set_number="10316",
        asking_price=70.00,
        fair_value=100.00,
        listing_count=10,
        confidence="low",
    )

    assert result["score"] == 93
    assert result["verdict"] == "WATCH"
    assert "buy_downgraded_due_to_low_confidence" in result["reason_codes"]


def test_buy_decision_engine_missing_fair_value_watches():
    result = decide_buy_or_pass(
        set_number="00000",
        asking_price=100.00,
        fair_value=None,
    )

    assert result == {
        "verdict": "WATCH",
        "score": 40,
        "confidence": "low",
        "reasoning": "Not enough market data is available to estimate fair value.",
        "reason_codes": ["missing_fair_value"],
    }


def test_buy_decision_engine_invalid_asking_price_passes():
    result = decide_buy_or_pass(
        set_number="00000",
        asking_price=0,
        fair_value=100.00,
    )

    assert result == {
        "verdict": "PASS",
        "score": 0,
        "confidence": "low",
        "reasoning": "Asking price must be greater than zero.",
        "reason_codes": ["invalid_asking_price"],
    }


def test_buy_decision_engine_shipping_and_market_high_penalize_score():
    result = decide_buy_or_pass(
        set_number="75313",
        asking_price=185.00,
        shipping_price=15.00,
        fair_value=190.00,
        market_low=150.00,
        market_high=200.00,
        listing_count=3,
        confidence="medium",
    )

    assert result["verdict"] == "PASS"
    assert result["all_in_price"] == 200.00
    assert result["discount_pct"] == -5.26
    assert "above_fair_value" in result["reason_codes"]
    assert "negative_estimated_roi" in result["reason_codes"]
    assert "near_or_above_market_high" in result["reason_codes"]
    assert "thin_market_data" in result["reason_codes"]
