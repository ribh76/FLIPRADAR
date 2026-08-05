from decimal import Decimal

import pytest

from flipradar.domain.engines.scoring_engine import score_deal, score_recommendation


def test_scoring_engine_excellent_deal():
    result = score_recommendation(
        Decimal("80.00"), Decimal("100.00"), "high", listing_count=20
    )

    assert result == {
        "score": 90,
        "margin_percent": Decimal("20.0"),
        "deal_band": "excellent",
    }


def test_scoring_engine_strong_deal():
    result = score_recommendation(
        Decimal("550.00"), Decimal("625.00"), "high", listing_count=22
    )

    assert result == {
        "score": 82,
        "margin_percent": Decimal("12.0"),
        "deal_band": "strong",
    }


def test_scoring_engine_deal_bands():
    assert (
        score_recommendation(
            Decimal("95.00"), Decimal("100.00"), "high", listing_count=20
        )["deal_band"]
        == "fair"
    )
    assert (
        score_recommendation(
            Decimal("105.00"), Decimal("100.00"), "high", listing_count=20
        )["deal_band"]
        == "weak"
    )
    assert (
        score_recommendation(
            Decimal("115.00"), Decimal("100.00"), "high", listing_count=20
        )["deal_band"]
        == "bad"
    )


def test_scoring_engine_applies_confidence_penalty():
    result = score_recommendation(
        Decimal("125.00"), Decimal("150.00"), "medium", listing_count=12
    )

    assert result["score"] == 82
    assert result["margin_percent"] == Decimal("16.7")
    assert result["deal_band"] == "strong"


def test_scoring_engine_handles_missing_price_data():
    result = score_recommendation(None, Decimal("0.00"), "low", listing_count=0)

    assert result == {
        "score": 25,
        "margin_percent": Decimal("0.0"),
        "deal_band": "bad",
    }


def test_deal_score_includes_shipping_discount_and_weighted_components():
    result = score_deal(
        asking_price=Decimal("80.00"),
        shipping_price=Decimal("10.00"),
        fair_value=Decimal("120.00"),
        set_quality_score=Decimal("80"),
        valuation_confidence_score=Decimal("90"),
    )

    assert result["total_cost"] == Decimal("90.00")
    assert result["value_difference"] == Decimal("30.00")
    assert result["discount_percent"] == Decimal("25.0")
    assert result["premium_percent"] == Decimal("0.0")
    assert result["score_components"]["value"] == {
        "weight": Decimal("0.30"),
        "raw_score": Decimal("100.0"),
        "weighted_score": Decimal("30.0"),
    }
    assert result["score_components"]["listing_quality"] == {
        "weight": Decimal("0.10"),
        "raw_score": Decimal("80.0"),
        "weighted_score": Decimal("8.0"),
    }
    assert result["score"] == 97
    assert result["confidence_score"] == 96
    assert result["confidence_band"] == "high"
    assert result["deal_band"] == "excellent"


def test_deal_score_reports_a_premium_when_landed_cost_exceeds_fair_value():
    result = score_deal(
        asking_price=Decimal("100.00"),
        shipping_price=Decimal("20.00"),
        fair_value=Decimal("100.00"),
        set_quality_score=Decimal("100"),
        valuation_confidence_score=Decimal("100"),
    )

    assert result["price_vs_fair_value_percent"] == Decimal("-20.0")
    assert result["discount_percent"] == Decimal("0.0")
    assert result["premium_percent"] == Decimal("20.0")
    assert result["score"] == 73
    assert result["deal_band"] == "good"


def test_deal_score_is_unscored_without_fair_value():
    result = score_deal(
        asking_price=Decimal("80.00"),
        shipping_price=Decimal("5.00"),
        fair_value=None,
        set_quality_score=Decimal("80"),
        valuation_confidence_score=Decimal("90"),
    )

    assert result["score"] is None
    assert result["deal_band"] == "unscored"
    assert result["total_cost"] == Decimal("85.00")
    assert result["discount_percent"] is None


def test_deal_score_includes_all_reliability_signals_and_guardrail_penalties():
    result = score_deal(
        asking_price=Decimal("90.00"),
        shipping_price=Decimal("10.00"),
        fair_value=Decimal("150.00"),
        set_quality_score=50,
        product_match_confidence_score=90,
        valuation_confidence_score=80,
        seller_trust_score=70,
        marketplace_trust_score=60,
        condition_score=80,
        is_complete=False,
        is_unclear=True,
        is_suspicious=True,
    )

    assert result["score_components"]["product_match"]["weighted_score"] == Decimal(
        "13.5"
    )
    assert result["score_components"]["seller_trust"]["weighted_score"] == Decimal(
        "7.0"
    )
    assert result["score_components"]["marketplace_trust"]["weighted_score"] == Decimal(
        "6.0"
    )
    assert result["score_components"]["condition_completeness"]["raw_score"] == Decimal(
        "56.0"
    )
    assert result["score_breakdown"]["penalty_total"] == "60"
    assert [
        penalty["reason"] for penalty in result["score_breakdown"]["penalties"]
    ] == [
        "unclear_listing",
        "incomplete_listing",
        "suspicious_listing",
        "low_quality_listing",
    ]
    assert result["score"] == 19
    assert result["deal_band"] == "poor"
    assert result["confidence_score"] == 13
    assert result["confidence_band"] == "low"
    assert "Penalty applied: suspicious listing" in result["explanation"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"asking_price": -1, "fair_value": 100}, "asking_price"),
        ({"asking_price": 1, "fair_value": 0}, "fair_value"),
        (
            {"asking_price": 1, "fair_value": 100, "set_quality_score": 101},
            "set_quality_score",
        ),
    ],
)
def test_deal_score_rejects_invalid_inputs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        score_deal(**kwargs)
