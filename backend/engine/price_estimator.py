import logging
from decimal import Decimal, ROUND_HALF_UP

from models import PriceSnapshot

logger = logging.getLogger(__name__)
logger.debug("engine initialized name=price_estimator")


def estimate_fair_value(snapshots: list[PriceSnapshot]) -> dict:
    if not snapshots:
        return {
            "fair_value": Decimal("0.00"),
            "market_low": Decimal("0.00"),
            "market_high": Decimal("0.00"),
            "median_price": Decimal("0.00"),
            "listing_count": 0,
            "confidence": "low",
        }

    values: list[tuple[Decimal, Decimal]] = []
    lows: list[Decimal] = []
    highs: list[Decimal] = []
    listing_count = 0

    for snapshot in snapshots:
        price = _snapshot_price(snapshot)
        if price is None:
            continue

        source_weight = _marketplace_weight(snapshot)
        values.append((price, source_weight))

        if snapshot.low_price is not None:
            lows.append(snapshot.low_price)
        else:
            lows.append(price)

        if snapshot.high_price is not None:
            highs.append(snapshot.high_price)
        else:
            highs.append(price)

        listing_count += snapshot.listing_count or 0

    if not values:
        return {
            "fair_value": Decimal("0.00"),
            "market_low": Decimal("0.00"),
            "market_high": Decimal("0.00"),
            "median_price": Decimal("0.00"),
            "listing_count": listing_count,
            "confidence": _confidence_for_listing_count(listing_count),
        }

    fair_value = _weighted_average(values)
    median_price = _median([price for price, _weight in values])

    return {
        "fair_value": _money(fair_value),
        "market_low": _money(min(lows)),
        "market_high": _money(max(highs)),
        "median_price": _money(median_price),
        "listing_count": listing_count,
        "confidence": _confidence_for_listing_count(listing_count),
    }


def _snapshot_price(snapshot: PriceSnapshot) -> Decimal | None:
    return snapshot.median_price or snapshot.average_price or snapshot.fair_market_value


def _marketplace_weight(snapshot: PriceSnapshot) -> Decimal:
    marketplace = getattr(snapshot, "marketplace", None)
    marketplace_name = (getattr(marketplace, "name", "") or "").lower()
    display_name = (getattr(marketplace, "display_name", "") or "").lower()
    combined_name = f"{marketplace_name} {display_name}"

    if "bricklink" in combined_name:
        return Decimal("1.15")
    if "ebay" in combined_name:
        return Decimal("1.00")
    return Decimal("0.90")


def _weighted_average(values: list[tuple[Decimal, Decimal]]) -> Decimal:
    weighted_total = sum(price * weight for price, weight in values)
    total_weight = sum(weight for _price, weight in values)
    if total_weight == 0:
        return Decimal("0.00")
    return weighted_total / total_weight


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def _confidence_for_listing_count(listing_count: int) -> str:
    if listing_count >= 20:
        return "high"
    if listing_count >= 8:
        return "medium"
    return "low"


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
