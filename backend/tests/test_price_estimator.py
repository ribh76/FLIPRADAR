from decimal import Decimal
from types import SimpleNamespace

from flipradar.domain.engines.price_estimator import estimate_fair_value


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

    assert estimate_fair_value(snapshots) == {
        "fair_value": Decimal("625.00"),
        "market_low": Decimal("590.00"),
        "market_high": Decimal("700.00"),
        "median_price": Decimal("625.00"),
        "listing_count": 22,
        "confidence": "high",
    }


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

    assert estimate_fair_value([snapshot]) == {
        "fair_value": Decimal("125.00"),
        "market_low": Decimal("125.00"),
        "market_high": Decimal("125.00"),
        "median_price": Decimal("125.00"),
        "listing_count": 3,
        "confidence": "low",
    }


def test_price_estimator_handles_snapshots_without_usable_prices():
    snapshot = make_snapshot(
        "ebay",
        median_price=None,
        average_price=None,
        low_price=Decimal("90.00"),
        high_price=Decimal("140.00"),
        listing_count=6,
    )

    assert estimate_fair_value([snapshot]) == {
        "fair_value": Decimal("0.00"),
        "market_low": Decimal("0.00"),
        "market_high": Decimal("0.00"),
        "median_price": Decimal("0.00"),
        "listing_count": 0,
        "confidence": "low",
    }


def test_price_estimator_handles_no_snapshots():
    assert estimate_fair_value([]) == {
        "fair_value": Decimal("0.00"),
        "market_low": Decimal("0.00"),
        "market_high": Decimal("0.00"),
        "median_price": Decimal("0.00"),
        "listing_count": 0,
        "confidence": "low",
    }
