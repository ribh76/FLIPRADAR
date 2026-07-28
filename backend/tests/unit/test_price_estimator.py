from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from flipradar.domain.engines.price_estimator import estimate_fair_value


def assert_legacy_summary(result: dict, expected: dict) -> None:
    assert {key: result[key] for key in expected} == expected


def make_snapshot(
    marketplace_name: str,
    *,
    median_price: Decimal | None,
    average_price: Decimal | None,
    low_price: Decimal | None,
    high_price: Decimal | None,
    listing_count: int,
) -> SimpleNamespace:
    return SimpleNamespace(
        marketplace=SimpleNamespace(
            name=marketplace_name,
            display_name=marketplace_name.title(),
        ),
        median_price=median_price,
        average_price=average_price,
        fair_market_value=None,
        low_price=low_price,
        high_price=high_price,
        listing_count=listing_count,
    )


def metric_snapshot(
    marketplace_name: str,
    value: str,
    *,
    condition: str = "new",
    sample_size: int = 10,
    retrieval_time: datetime | None = None,
    listings: list[dict] | None = None,
    set_number: str = "75192",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{marketplace_name}-{value}",
        marketplace_id=marketplace_name,
        marketplace=SimpleNamespace(
            name=marketplace_name, display_name=marketplace_name
        ),
        set_number=set_number,
        condition=condition,
        metric_type="fair_market_value",
        value=Decimal(value),
        sample_size=sample_size,
        retrieval_time=retrieval_time or datetime.now(UTC),
        source_payload={"listings": listings or []},
    )


def test_price_estimator_returns_market_summary_dict():
    snapshots = [
        make_snapshot(
            "ebay",
            median_price=Decimal("625.00"),
            average_price=Decimal("640.00"),
            low_price=Decimal("590.00"),
            high_price=Decimal("680.00"),
            listing_count=10,
        ),
        make_snapshot(
            "bricklink",
            median_price=Decimal("625.00"),
            average_price=Decimal("650.00"),
            low_price=Decimal("600.00"),
            high_price=Decimal("700.00"),
            listing_count=12,
        ),
    ]

    result = estimate_fair_value(snapshots)
    assert_legacy_summary(
        result,
        {
            "fair_value": Decimal("625.00"),
            "market_low": Decimal("590.00"),
            "market_high": Decimal("700.00"),
            "median_price": Decimal("625.00"),
            "listing_count": 22,
            "confidence": "high",
        },
    )
    assert result["expected_value"] == Decimal("625.00")
    assert result["confidence_score"] == 84
    assert len(result["inputs_used"]) == 2


def test_price_estimator_prefers_median_over_average():
    snapshot = make_snapshot(
        "ebay",
        median_price=Decimal("150.00"),
        average_price=Decimal("175.00"),
        low_price=None,
        high_price=None,
        listing_count=8,
    )

    result = estimate_fair_value([snapshot])

    assert result["fair_value"] == Decimal("150.00")
    assert result["median_price"] == Decimal("150.00")
    assert result["confidence"] == "medium"


def test_price_estimator_weights_bricklink_slightly_higher():
    snapshots = [
        make_snapshot(
            "ebay",
            median_price=Decimal("600.00"),
            average_price=None,
            low_price=Decimal("590.00"),
            high_price=Decimal("620.00"),
            listing_count=10,
        ),
        make_snapshot(
            "bricklink",
            median_price=Decimal("700.00"),
            average_price=None,
            low_price=Decimal("680.00"),
            high_price=Decimal("720.00"),
            listing_count=10,
        ),
    ]

    result = estimate_fair_value(snapshots)

    assert result["fair_value"] == Decimal("653.49")
    assert result["fair_value"] > Decimal("650.00")


def test_price_estimator_handles_missing_marketplace_data():
    snapshot = make_snapshot(
        "",
        median_price=None,
        average_price=Decimal("125.00"),
        low_price=None,
        high_price=None,
        listing_count=3,
    )

    assert_legacy_summary(
        estimate_fair_value([snapshot]),
        {
            "fair_value": Decimal("125.00"),
            "market_low": Decimal("125.00"),
            "market_high": Decimal("125.00"),
            "median_price": Decimal("125.00"),
            "listing_count": 3,
            "confidence": "low",
        },
    )


def test_price_estimator_handles_snapshots_without_usable_prices():
    snapshot = make_snapshot(
        "ebay",
        median_price=None,
        average_price=None,
        low_price=Decimal("90.00"),
        high_price=Decimal("140.00"),
        listing_count=6,
    )

    assert_legacy_summary(
        estimate_fair_value([snapshot]),
        {
            "fair_value": Decimal("0.00"),
            "market_low": Decimal("0.00"),
            "market_high": Decimal("0.00"),
            "median_price": Decimal("0.00"),
            "listing_count": 0,
            "confidence": "low",
        },
    )


def test_price_estimator_handles_no_snapshots():
    result = estimate_fair_value([])
    assert_legacy_summary(
        result,
        {
            "fair_value": Decimal("0.00"),
            "market_low": Decimal("0.00"),
            "market_high": Decimal("0.00"),
            "median_price": Decimal("0.00"),
            "listing_count": 0,
            "confidence": "low",
        },
    )
    assert result["valuation_status"] == "insufficient_data"
    assert result["error"] == {
        "code": "insufficient_data",
        "message": "Insufficient data to produce a reliable market valuation.",
    }


def test_price_estimator_manual_override_is_auditable_and_precedes_market_data():
    result = estimate_fair_value(
        [metric_snapshot("ebay", "100")],
        condition="new",
        manual_value=Decimal("240.00"),
        manual_low=Decimal("220.00"),
        manual_high=Decimal("260.00"),
        manual_reason="Verified local sale and collector appraisal.",
    )

    assert result["fair_value"] == Decimal("240.00")
    assert result["market_low"] == Decimal("220.00")
    assert result["market_high"] == Decimal("260.00")
    assert result["valuation_source"] == "manual_override"
    assert result["inputs_used"] == [
        {
            "source": "manual_override",
            "expected_value": "240.00",
            "low_value": "220.00",
            "high_value": "260.00",
            "reason": "Verified local sale and collector appraisal.",
        }
    ]


def test_price_estimator_rejects_manual_override_without_reason_or_valid_range():
    with pytest.raises(ValueError, match="reason is required"):
        estimate_fair_value([], manual_value=100)
    with pytest.raises(ValueError, match="low <= expected <= high"):
        estimate_fair_value([], manual_value=100, manual_low=110, manual_reason="test")


def test_price_estimator_filters_stale_wrong_condition_and_low_confidence_inputs():
    now = datetime(2026, 7, 28, tzinfo=UTC)
    valid = metric_snapshot("ebay", "100", retrieval_time=now)
    stale = metric_snapshot(
        "bricklink", "500", retrieval_time=now - timedelta(hours=25)
    )
    used = metric_snapshot(
        "bricklink", "600", condition="used_complete", retrieval_time=now
    )
    other_set = metric_snapshot(
        "other-set", "650", set_number="10316", retrieval_time=now
    )
    low_confidence = metric_snapshot(
        "other",
        "700",
        retrieval_time=now,
        listings=[{"match_confidence": 79}],
    )

    result = estimate_fair_value(
        [valid, stale, used, other_set, low_confidence],
        condition="new",
        set_number="75192",
        now=now,
    )

    assert result["fair_value"] == Decimal("100.00")
    assert [entry["reason"] for entry in result["excluded_inputs"]] == [
        "stale",
        "condition_mismatch",
        "set_mismatch",
        "below_confidence_threshold",
    ]


def test_price_estimator_weights_sold_evidence_above_active_listings():
    active = metric_snapshot(
        "ebay", "100", listings=[{"listing_status": "active"}] * 10
    )
    sold = metric_snapshot(
        "bricklink", "200", listings=[{"listing_status": "sold"}] * 10
    )

    result = estimate_fair_value([active, sold])

    assert result["fair_value"] > Decimal("155.00")
    assert result["inputs_used"][1]["sold_count"] == 10


def test_price_estimator_discards_iqr_outlier_marketplace_observation():
    snapshots = [
        metric_snapshot("market-a", "100"),
        metric_snapshot("market-b", "102"),
        metric_snapshot("market-c", "105"),
        metric_snapshot("market-d", "110"),
        metric_snapshot("market-e", "1000"),
    ]

    result = estimate_fair_value(snapshots)

    assert result["fair_value"] < Decimal("110.00")
    assert result["excluded_inputs"][-1]["reason"] == "iqr_outlier"
