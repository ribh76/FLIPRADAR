from flipradar.domain.engines.hold_sell_engine import decide_sell_or_hold


def test_hold_sell_engine_strong_profit_can_sell_despite_rising_trend():
    result = decide_sell_or_hold(
        set_number="75192",
        fair_value=200.00,
        market_low=150.00,
        market_high=210.00,
        listing_count=24,
        confidence="high",
        purchase_price=80.00,
        quantity=2,
        recent_fair_values=[150.00, 160.00, 200.00],
    )

    assert result["verdict"] == "SELL"
    assert result["score"] == 83
    assert result["total_estimated_net_value"] == 348.00
    assert result["cost_basis"] == 160.00
    assert result["profit"] == 188.00
    assert result["profit_pct"] == 117.5
    assert result["trend_label"] == "rising"
    assert "very_strong_profit" in result["reason_codes"]
    assert "hold_due_to_upward_trend" in result["reason_codes"]


def test_hold_sell_engine_missing_fair_value_holds():
    result = decide_sell_or_hold(
        set_number="00000",
        fair_value=None,
    )

    assert result == {
        "verdict": "HOLD",
        "score": 40,
        "confidence": "low",
        "reasoning": (
            "Not enough market data is available to estimate current resale value."
        ),
        "reason_codes": ["missing_fair_value"],
    }


def test_hold_sell_engine_missing_purchase_price_watches_on_market_signal():
    result = decide_sell_or_hold(
        set_number="10316",
        fair_value=100.00,
        listing_count=10,
        confidence="medium",
    )

    assert result["verdict"] == "WATCH"
    assert result["score"] == 53
    assert result["cost_basis"] is None
    assert result["profit"] is None
    assert result["profit_pct"] is None
    assert "missing_purchase_price" in result["reason_codes"]
    assert "insufficient_trend_data" in result["reason_codes"]
    assert "moderate_market_depth" in result["reason_codes"]


def test_hold_sell_engine_low_confidence_downgrades_sell():
    result = decide_sell_or_hold(
        set_number="75313",
        fair_value=100.00,
        market_high=100.00,
        listing_count=20,
        confidence="low",
        purchase_price=66.00,
        recent_fair_values=[120.00, 115.00, 100.00],
    )

    assert result["score"] == 84
    assert result["verdict"] == "WATCH"
    assert "sell_downgraded_due_to_low_confidence" in result["reason_codes"]


def test_hold_sell_engine_invalid_quantity_holds():
    result = decide_sell_or_hold(
        set_number="75313",
        fair_value=100.00,
        quantity=0,
    )

    assert result == {
        "verdict": "HOLD",
        "score": 0,
        "confidence": "low",
        "reasoning": "Quantity must be greater than zero.",
        "reason_codes": ["invalid_quantity"],
    }
