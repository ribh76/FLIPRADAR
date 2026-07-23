from decimal import ROUND_HALF_UP, Decimal
from statistics import mean, median
from typing import Any


def build(listings: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [
        price
        for price in (_listing_total_price(listing) for listing in listings)
        if price is not None
    ]
    prices = sorted(prices)

    if not prices:
        return {
            "condition": "unknown",
            "currency": "USD",
            "low_price": None,
            "median_price": None,
            "average_price": None,
            "high_price": None,
            "fair_market_value": None,
            "listing_count": 0,
            "source_payload": {"listings": []},
        }

    median_price = _money(median(prices))
    average_price = _money(mean(prices))

    return {
        "condition": _snapshot_condition(listings),
        "currency": _snapshot_currency(listings),
        "low_price": _money(prices[0]),
        "median_price": median_price,
        "average_price": average_price,
        "high_price": _money(prices[-1]),
        "fair_market_value": median_price,
        "listing_count": len(prices),
        "source_payload": {
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
                    "listing_url": listing.get("listing_url"),
                }
                for listing in listings
            ],
        },
    }


def _listing_total_price(listing: dict[str, Any]) -> Decimal | None:
    price = listing.get("price")
    shipping_price = listing.get("shipping_price", Decimal("0.00"))
    if price is None:
        return None
    return _money(price + shipping_price)


def _snapshot_condition(listings: list[dict[str, Any]]) -> str:
    conditions = {listing.get("condition") for listing in listings}
    conditions.discard(None)
    conditions.discard("unknown")
    if len(conditions) == 1:
        return str(conditions.pop())
    if len(conditions) > 1:
        return "mixed"
    return "unknown"


def _snapshot_currency(listings: list[dict[str, Any]]) -> str:
    currencies = [
        listing.get("currency") for listing in listings if listing.get("currency")
    ]
    if not currencies:
        return "USD"
    first_currency = currencies[0]
    if all(currency == first_currency for currency in currencies):
        return str(first_currency)
    return "USD"


def _money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
