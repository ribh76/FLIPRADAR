"""Build metric-level price snapshots from confidently matched listings."""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean, median
from typing import Any

from flipradar.domain.models.enums import PriceMetricType


def build(
    listings: list[dict[str, Any]], *, retrieval_time: datetime | None = None
) -> list[dict[str, Any]]:
    """Return one row for every supported metric, condition, and currency.

    Unknown-condition listings are intentionally omitted: folding them into a
    condition bucket would make a condition-specific valuation misleading.
    """
    retrieved_at = retrieval_time or datetime.now(UTC)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for listing in listings:
        condition = _pricing_condition(listing)
        price = _listing_total_price(listing)
        if condition is not None and price is not None:
            groups[(condition, _currency(listing))].append(listing)

    snapshots = []
    for (condition, currency), group in groups.items():
        prices = sorted(_listing_total_price(listing) for listing in group)
        # The guard above ensures every total is present.
        numeric_prices = [price for price in prices if price is not None]
        values = {
            PriceMetricType.LOW.value: _money(numeric_prices[0]),
            PriceMetricType.MEDIAN.value: _money(median(numeric_prices)),
            PriceMetricType.AVERAGE.value: _money(mean(numeric_prices)),
            PriceMetricType.HIGH.value: _money(numeric_prices[-1]),
            PriceMetricType.FAIR_MARKET_VALUE.value: _money(median(numeric_prices)),
        }
        source_payload = _source_payload(group)
        for metric_type, value in values.items():
            snapshots.append(
                {
                    "condition": condition,
                    "currency": currency,
                    "metric_type": metric_type,
                    "value": value,
                    "sample_size": len(numeric_prices),
                    "source_payload": source_payload,
                    "retrieval_time": retrieved_at,
                }
            )
    return snapshots


def _pricing_condition(listing: dict[str, Any]) -> str | None:
    if listing.get("condition") == "new" or listing.get("is_sealed") is True:
        return "new"
    if listing.get("is_complete") is True:
        return "used_complete"
    if listing.get("is_complete") is False:
        return "incomplete"
    return None


def _listing_total_price(listing: dict[str, Any]) -> Decimal | None:
    price = listing.get("price")
    shipping_price = listing.get("shipping_price", Decimal("0.00"))
    if price is None:
        return None
    return _money(Decimal(str(price)) + Decimal(str(shipping_price)))


def _currency(listing: dict[str, Any]) -> str:
    return str(listing.get("currency") or "USD").upper()


def _source_payload(listings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "marketplaces": sorted(
            {
                listing["marketplace"]
                for listing in listings
                if listing.get("marketplace")
            }
        ),
        "listings": [
            {
                "marketplace": listing.get("marketplace"),
                "price": str(listing.get("price")),
                "shipping_price": str(listing.get("shipping_price")),
                "total_price": str(_listing_total_price(listing)),
                "condition": listing.get("condition"),
                "is_complete": listing.get("is_complete"),
                "listing_url": listing.get("listing_url"),
            }
            for listing in listings
        ],
    }


def _money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
