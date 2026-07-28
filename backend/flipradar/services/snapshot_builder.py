"""Build condition-specific, outlier-resistant metric price snapshots."""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean, median, quantiles
from typing import Any

from flipradar.domain.models.enums import PriceMetricType
from flipradar.services.currency_conversion import CurrencyConversionError, convert

IQR_MIN_SAMPLE_SIZE = 4


def build(
    listings: list[dict[str, Any]],
    *,
    retrieval_time: datetime | None = None,
    target_currency: str = "USD",
) -> list[dict[str, Any]]:
    """Return metric rows from converted, condition-specific listing samples.

    Each source listing is retained in ``source_payload`` with its original
    amount and currency. Listings beyond the IQR fences are excluded only when
    there are at least four comparable samples.
    """
    retrieved_at = retrieval_time or datetime.now(UTC)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for listing in listings:
        condition = _pricing_condition(listing)
        if condition is None:
            continue
        try:
            groups[condition].append(_convert_listing(listing, target_currency))
        except CurrencyConversionError:
            # A source currency that cannot be converted must not be mixed into
            # a target-currency valuation. Its original listing remains stored.
            continue

    snapshots = []
    for condition, group in groups.items():
        included, excluded, fences = _exclude_iqr_outliers(group)
        prices = sorted(_listing_total_price(listing) for listing in included)
        #TODO: Fix the bug on line 43
        numeric_prices = [price for price in prices if price is not None]
        if not numeric_prices:
            continue
        values = {
            PriceMetricType.LOW.value: _money(numeric_prices[0]),
            PriceMetricType.MEDIAN.value: _money(median(numeric_prices)),
            PriceMetricType.AVERAGE.value: _money(mean(numeric_prices)),
            PriceMetricType.HIGH.value: _money(numeric_prices[-1]),
            PriceMetricType.FAIR_MARKET_VALUE.value: _money(median(numeric_prices)),
        }
        source_payload = _source_payload(included, excluded, fences)
        for metric_type, value in values.items():
            snapshots.append(
                {
                    "condition": condition,
                    "currency": target_currency.upper(),
                    "metric_type": metric_type,
                    "value": value,
                    "sample_size": len(numeric_prices),
                    "source_payload": source_payload,
                    "retrieval_time": retrieved_at,
                }
            )
    return snapshots


def _convert_listing(listing: dict[str, Any], target_currency: str) -> dict[str, Any]:
    original_currency = _currency(listing)
    original_price = Decimal(str(listing["price"]))
    original_shipping = Decimal(str(listing.get("shipping_price", Decimal("0.00"))))
    return {
        **listing,
        "price": convert(original_price, original_currency, target_currency),
        "shipping_price": convert(
            original_shipping, original_currency, target_currency
        ),
        "currency": target_currency.upper(),
        "original_price": original_price,
        "original_shipping_price": original_shipping,
        "original_currency": original_currency,
    }


def _exclude_iqr_outliers(
    listings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str] | None]:
    prices = [_listing_total_price(listing) for listing in listings]
    numeric_prices = [price for price in prices if price is not None]
    if len(numeric_prices) < IQR_MIN_SAMPLE_SIZE:
        return listings, [], None
    q1, _q2, q3 = quantiles(numeric_prices, n=4, method="inclusive")
    iqr = q3 - q1
    lower, upper = q1 - Decimal("1.5") * iqr, q3 + Decimal("1.5") * iqr
    included, excluded = [], []
    for listing in listings:
        total = _listing_total_price(listing)
        (
            included if total is not None and lower <= total <= upper else excluded
        ).append(listing)
    return (
        included,
        excluded,
        {"lower": str(_money(lower)), "upper": str(_money(upper))},
    )


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


def _source_payload(
    included: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    fences: dict[str, str] | None,
) -> dict[str, Any]:
    return {
        "marketplaces": sorted(
            {
                listing["marketplace"]
                for listing in included
                if listing.get("marketplace")
            }
        ),
        "outlier_handling": {
            "method": "iqr_1.5" if fences else "not_applied_low_sample_size",
            "excluded_count": len(excluded),
            "fences": fences,
        },
        "listings": [_source_listing(listing) for listing in included],
        "excluded_outliers": [_source_listing(listing) for listing in excluded],
    }


def _source_listing(listing: dict[str, Any]) -> dict[str, Any]:
    return {
        "marketplace": listing.get("marketplace"),
        "price": str(listing.get("price")),
        "shipping_price": str(listing.get("shipping_price")),
        "total_price": str(_listing_total_price(listing)),
        "currency": listing.get("currency"),
        "original_price": str(listing.get("original_price")),
        "original_shipping_price": str(listing.get("original_shipping_price")),
        "original_currency": listing.get("original_currency"),
        "condition": listing.get("condition"),
        "is_complete": listing.get("is_complete"),
        "listing_url": listing.get("listing_url"),
    }


def _money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
