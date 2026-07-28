from datetime import UTC, datetime
from decimal import Decimal

from flipradar.services.snapshot_builder import build


def _listing(*, condition: str, complete: bool | None, price: str) -> dict:
    return {
        "marketplace": "ebay",
        "condition": condition,
        "is_complete": complete,
        "currency": "USD",
        "price": Decimal(price),
        "shipping_price": Decimal("5.00"),
        "listing_url": "https://example.test/listing",
    }


def test_build_emits_every_supported_metric_per_pricing_condition():
    retrieved_at = datetime(2026, 7, 28, tzinfo=UTC)
    snapshots = build(
        [
            _listing(condition="new", complete=None, price="100.00"),
            _listing(condition="used", complete=True, price="75.00"),
            _listing(condition="used", complete=False, price="50.00"),
            _listing(condition="unknown", complete=None, price="25.00"),
        ],
        retrieval_time=retrieved_at,
    )

    assert len(snapshots) == 15
    assert {snapshot["condition"] for snapshot in snapshots} == {
        "new",
        "used_complete",
        "incomplete",
    }
    assert {snapshot["metric_type"] for snapshot in snapshots} == {
        "low",
        "median",
        "average",
        "high",
        "fair_market_value",
    }
    new_median = next(
        snapshot
        for snapshot in snapshots
        if snapshot["condition"] == "new" and snapshot["metric_type"] == "median"
    )
    assert new_median["value"] == Decimal("105.00")
    assert new_median["sample_size"] == 1
    assert new_median["retrieval_time"] == retrieved_at


def test_build_excludes_iqr_outliers_from_snapshot_metrics():
    snapshots = build(
        [
            _listing(condition="new", complete=None, price="95.00"),
            _listing(condition="new", complete=None, price="100.00"),
            _listing(condition="new", complete=None, price="105.00"),
            _listing(condition="new", complete=None, price="110.00"),
            _listing(condition="new", complete=None, price="1000.00"),
        ]
    )

    fair_value = next(
        snapshot
        for snapshot in snapshots
        if snapshot["metric_type"] == "fair_market_value"
    )
    assert fair_value["value"] == Decimal("107.50")
    assert fair_value["sample_size"] == 4
    assert fair_value["source_payload"]["outlier_handling"]["excluded_count"] == 1
    assert len(fair_value["source_payload"]["excluded_outliers"]) == 1


def test_build_ignores_listings_without_a_usable_price():
    listing = _listing(condition="new", complete=None, price="100.00")
    listing["price"] = None

    assert build([listing]) == []
