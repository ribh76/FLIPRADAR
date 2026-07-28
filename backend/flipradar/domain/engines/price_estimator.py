import logging
from collections import defaultdict
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from flipradar.domain.models import PriceSnapshot
from flipradar.domain.models.enums import PriceMetricType

logger = logging.getLogger(__name__)


def estimate_fair_value(
    snapshots: Sequence[PriceSnapshot] | Sequence[Any], *, condition: str | None = None
) -> dict:
    """Estimate a value from metric rows, without mixing pricing conditions.

    The repository supplies all metric rows from the newest retrieval for each
    marketplace/condition. A marketplace contributes one sample size, rather
    than one per metric, so adding metrics cannot inflate confidence.
    """
    if condition is None:
        condition = _default_condition(snapshots)
    groups: dict[tuple[Any, Any, Any], dict[str, Any]] = defaultdict(dict)
    for snapshot in snapshots:
        if (
            condition is not None
            and getattr(snapshot, "condition", condition) != condition
        ):
            continue
        metric_type = getattr(snapshot, "metric_type", None)
        if metric_type is None:
            # Compatibility for callers still passing the former wide shape.
            _add_legacy_snapshot(groups, snapshot)
            continue
        key = (
            getattr(
                snapshot,
                "marketplace_id",
                id(getattr(snapshot, "marketplace", snapshot)),
            ),
            getattr(snapshot, "condition", None),
            getattr(snapshot, "retrieval_time", None),
        )
        groups[key][str(metric_type)] = snapshot

    values: list[tuple[Decimal, Decimal]] = []
    lows: list[Decimal] = []
    highs: list[Decimal] = []
    sample_size = 0
    for metrics in groups.values():
        representative = (
            metrics.get(PriceMetricType.FAIR_MARKET_VALUE.value)
            or metrics.get(PriceMetricType.MEDIAN.value)
            or metrics.get(PriceMetricType.AVERAGE.value)
        )
        if representative is None:
            continue
        price = _value(representative)
        if price is None:
            continue
        values.append((price, _marketplace_weight(representative)))
        sample_size += int(
            getattr(
                representative,
                "sample_size",
                getattr(representative, "listing_count", 0),
            )
            or 0
        )
        low = _value(metrics.get(PriceMetricType.LOW.value))
        high = _value(metrics.get(PriceMetricType.HIGH.value))
        lows.append(low if low is not None else price)
        highs.append(high if high is not None else price)

    if not values:
        return _empty_estimate(sample_size)

    fair_value = _weighted_average(values)
    median_price = _median([price for price, _weight in values])
    return {
        "fair_value": _money(fair_value),
        "market_low": _money(min(lows)),
        "market_high": _money(max(highs)),
        "median_price": _money(median_price),
        "listing_count": sample_size,
        "confidence": _confidence_for_listing_count(sample_size),
    }


def _default_condition(snapshots: Sequence[Any]) -> str | None:
    present = {getattr(snapshot, "condition", None) for snapshot in snapshots}
    for preferred in ("new", "used_complete", "incomplete"):
        if preferred in present:
            return preferred
    return None


def _add_legacy_snapshot(groups: dict, snapshot: Any) -> None:
    key = (id(snapshot), None, None)
    for metric, field in (
        (PriceMetricType.LOW.value, "low_price"),
        (PriceMetricType.MEDIAN.value, "median_price"),
        (PriceMetricType.AVERAGE.value, "average_price"),
        (PriceMetricType.HIGH.value, "high_price"),
        (PriceMetricType.FAIR_MARKET_VALUE.value, "fair_market_value"),
    ):
        value = getattr(snapshot, field, None)
        if value is not None:
            groups[key][metric] = (
                snapshot
                if metric == PriceMetricType.MEDIAN.value
                else _MetricValue(snapshot, value)
            )


class _MetricValue:
    def __init__(self, snapshot: Any, value: Decimal):
        self.value = value
        self.marketplace = getattr(snapshot, "marketplace", None)
        self.sample_size = getattr(snapshot, "listing_count", 0)


def _value(snapshot: Any | None) -> Decimal | None:
    if snapshot is None:
        return None
    value = getattr(snapshot, "value", None)
    if value is not None:
        return Decimal(str(value))
    return getattr(snapshot, "median_price", None)


def _empty_estimate(sample_size: int) -> dict:
    return {
        "fair_value": Decimal("0.00"),
        "market_low": Decimal("0.00"),
        "market_high": Decimal("0.00"),
        "median_price": Decimal("0.00"),
        "listing_count": sample_size,
        "confidence": _confidence_for_listing_count(sample_size),
    }


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


#TODO: Fix RTE fatal type error without removing type hint
def _weighted_average(values: list[tuple[Decimal, Decimal]]) -> Decimal: 
    return sum(price * weight for price, weight in values) / sum(
        weight for _, weight in values
    )


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    return (
        ordered[midpoint]
        if len(ordered) % 2
        else (ordered[midpoint - 1] + ordered[midpoint]) / 2
    )


def _confidence_for_listing_count(listing_count: int) -> str:
    if listing_count >= 20:
        return "high"
    if listing_count >= 8:
        return "medium"
    return "low"


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
