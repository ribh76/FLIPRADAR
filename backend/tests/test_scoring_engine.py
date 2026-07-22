from decimal import Decimal

from engine.scoring_engine import score_recommendation


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
