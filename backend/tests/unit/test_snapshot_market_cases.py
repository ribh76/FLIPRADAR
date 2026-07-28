from decimal import Decimal

import pytest

from flipradar.services.snapshot_builder import build


def _listing(price: str) -> dict:
    return {
        "marketplace": "ebay",
        "condition": "new",
        "currency": "USD",
        "price": Decimal(price),
        "shipping_price": Decimal("0.00"),
        "listing_url": "https://example.test/listing",
    }


@pytest.mark.parametrize(
    (
        "case_name",
        "prices",
        "expected_snapshot_count",
        "expected_sample_size",
        "expected_outliers",
    ),
    [
        ("empty market", [], 0, None, None),
        ("low-volume market", ["100.00", "105.00", "110.00"], 5, 3, 0),
        (
            "outlier-heavy market",
            ["95.00", "100.00", "105.00", "110.00", "1000.00"],
            5,
            4,
            1,
        ),
    ],
)
def test_snapshot_generation_market_cases(
    case_name: str,
    prices: list[str],
    expected_snapshot_count: int,
    expected_sample_size: int | None,
    expected_outliers: int | None,
):
    snapshots = build([_listing(price) for price in prices])

    assert len(snapshots) == expected_snapshot_count, case_name
    if not snapshots:
        return
    assert {snapshot["sample_size"] for snapshot in snapshots} == {expected_sample_size}
    assert {
        snapshot["source_payload"]["outlier_handling"]["excluded_count"]
        for snapshot in snapshots
    } == {expected_outliers}
