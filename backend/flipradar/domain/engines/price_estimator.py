"""Robust, auditable market valuation from condition-specific price snapshots."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from statistics import quantiles
from typing import Any

from flipradar.domain.models import PriceSnapshot
from flipradar.domain.models.enums import PriceMetricType, SnapshotCondition

ESTIMATION_METHODOLOGY_VERSION = "7-28v1"
SUPPORTED_VALUATION_CONDITIONS = frozenset(
    condition.value for condition in SnapshotCondition
)
DEFAULT_FRESHNESS_HOURS = 24
AUTOMATED_PRICING_MIN_CONFIDENCE = Decimal("80")
SOLD_LISTING_WEIGHT = Decimal("1.50")
ACTIVE_LISTING_WEIGHT = Decimal("1.00")
IQR_MIN_SAMPLE_SIZE = 4


def select_eligible_snapshots(
    snapshots: Sequence[PriceSnapshot] | Sequence[Any],
    *,
    condition: str | None = None,
    set_number: str | None = None,
    lego_set_id: Any | None = None,
    now: datetime | None = None,
    freshness_hours: int | None = DEFAULT_FRESHNESS_HOURS,
    min_confidence: Decimal | float | int = AUTOMATED_PRICING_MIN_CONFIDENCE,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Return pricing rows eligible for valuation and auditable exclusions.

    Snapshots without listing-level confidence or a retrieval time are accepted
    for compatibility with imported/manual historical snapshots. Freshly-built
    snapshots, however, are held to the requested freshness and confidence
    thresholds.
    """
    requested_condition = condition or _default_condition(snapshots)
    cutoff = None
    if freshness_hours is not None:
        reference_time = now or datetime.now(UTC)
        cutoff = reference_time - timedelta(hours=freshness_hours)
    threshold = Decimal(str(min_confidence))
    eligible, excluded = [], []
    for snapshot in snapshots:
        reason = _ineligibility_reason(
            snapshot,
            condition=requested_condition,
            set_number=set_number,
            lego_set_id=lego_set_id,
            cutoff=cutoff,
            min_confidence=threshold,
        )
        if reason is None:
            eligible.append(snapshot)
        else:
            excluded.append({"snapshot_id": _snapshot_id(snapshot), "reason": reason})
    return eligible, excluded


def estimate_fair_value(
    snapshots: Sequence[PriceSnapshot] | Sequence[Any],
    *,
    condition: str | None = None,
    set_number: str | None = None,
    lego_set_id: Any | None = None,
    now: datetime | None = None,
    freshness_hours: int | None = DEFAULT_FRESHNESS_HOURS,
    min_confidence: Decimal | float | int = AUTOMATED_PRICING_MIN_CONFIDENCE,
) -> dict[str, Any]:
    """Estimate a condition-specific market value from eligible metric rows.

    One marketplace/retrieval contributes one observation. Its weight combines
    marketplace reliability, a capped square-root sample-size factor, and the
    sold-versus-active evidence mix. Tukey IQR filtering removes inconsistent
    marketplace observations before calculating the weighted expected value.
    """
    eligible, exclusions = select_eligible_snapshots(
        snapshots,
        condition=condition,
        set_number=set_number,
        lego_set_id=lego_set_id,
        now=now,
        freshness_hours=freshness_hours,
        min_confidence=min_confidence,
    )
    groups = _metric_groups(eligible)
    observations: list[dict[str, Any]] = []
    for metrics in groups.values():
        representative = _representative(metrics)
        price = _value(representative)
        if price is None:
            continue
        sample_size = _sample_size(representative)
        sold_count, active_count = _evidence_counts(representative)
        observations.append(
            {
                "price": price,
                "low": _value(metrics.get(PriceMetricType.LOW.value)) or price,
                "high": _value(metrics.get(PriceMetricType.HIGH.value)) or price,
                "sample_size": sample_size,
                "sold_count": sold_count,
                "active_count": active_count,
                "weight": _observation_weight(
                    representative, sample_size, sold_count, active_count
                ),
                "input": _input_record(
                    representative, sample_size, sold_count, active_count
                ),
            }
        )

    included, outliers = _exclude_iqr_outliers(observations)
    exclusions.extend(outliers)
    listing_count = sum(item["sample_size"] for item in included)
    if not included:
        return _empty_estimate(listing_count, exclusions)

    expected = _weighted_average([(item["price"], item["weight"]) for item in included])
    median_price = _median([item["price"] for item in included])
    low = min(item["low"] for item in included)
    high = max(item["high"] for item in included)
    confidence_score = _confidence_score(included, now=now)
    confidence = _confidence_band(confidence_score)
    return {
        # Existing consumer contract.
        "fair_value": _money(expected),
        "market_low": _money(low),
        "market_high": _money(high),
        "median_price": _money(median_price),
        "listing_count": listing_count,
        "confidence": confidence,
        # Phase-20 valuation contract.
        "low_value": _money(low),
        "expected_value": _money(expected),
        "high_value": _money(high),
        "confidence_score": confidence_score,
        "condition": condition or _default_condition(snapshots),
        "methodology_version": ESTIMATION_METHODOLOGY_VERSION,
        "inputs_used": [item["input"] for item in included],
        "excluded_inputs": exclusions,
    }


def _metric_groups(
    snapshots: Sequence[Any],
) -> dict[tuple[Any, Any, Any], dict[str, Any]]:
    groups: dict[tuple[Any, Any, Any], dict[str, Any]] = defaultdict(dict)
    for snapshot in snapshots:
        metric_type = getattr(snapshot, "metric_type", None)
        if metric_type is None:
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
    return groups


def _ineligibility_reason(
    snapshot: Any,
    *,
    condition: str | None,
    set_number: str | None,
    lego_set_id: Any | None,
    cutoff: datetime | None,
    min_confidence: Decimal,
) -> str | None:
    snapshot_condition = getattr(snapshot, "condition", condition)
    # The former wide snapshot shape had no condition field. Preserve it as a
    # trusted compatibility input when callers do not request a condition.
    if snapshot_condition is None and getattr(snapshot, "metric_type", None) is None:
        snapshot_condition = condition
    if (
        snapshot_condition not in SUPPORTED_VALUATION_CONDITIONS
        and snapshot_condition is not None
    ):
        return "unsupported_condition"
    if condition is not None and snapshot_condition != condition:
        return "condition_mismatch"
    if set_number is not None and _set_number(snapshot) != set_number.upper():
        return "set_mismatch"
    if (
        lego_set_id is not None
        and getattr(snapshot, "lego_set_id", None) != lego_set_id
    ):
        return "set_mismatch"
    retrieval_time = getattr(snapshot, "retrieval_time", None)
    if (
        cutoff is not None
        and retrieval_time is not None
        and _as_utc(retrieval_time) < cutoff
    ):
        return "stale"
    confidence = _snapshot_confidence(snapshot)
    if confidence is not None and confidence < min_confidence:
        return "below_confidence_threshold"
    return None


def _default_condition(snapshots: Sequence[Any]) -> str | None:
    present = {getattr(snapshot, "condition", None) for snapshot in snapshots}
    for preferred in ("new", "used_complete", "incomplete"):
        if preferred in present:
            return preferred
    return None


def _add_legacy_snapshot(groups: dict, snapshot: Any) -> None:
    key = (id(snapshot), None, None)
    for metric, field in (
        ("low", "low_price"),
        ("median", "median_price"),
        ("average", "average_price"),
        ("high", "high_price"),
        ("fair_market_value", "fair_market_value"),
    ):
        value = getattr(snapshot, field, None)
        if value is not None:
            groups[key][metric] = (
                snapshot if metric == "median" else _MetricValue(snapshot, value)
            )


class _MetricValue:
    def __init__(self, snapshot: Any, value: Decimal):
        self.value = value
        self.marketplace = getattr(snapshot, "marketplace", None)
        self.sample_size = getattr(snapshot, "listing_count", 0)
        self.source_payload = getattr(snapshot, "source_payload", None)


def _representative(metrics: dict[str, Any]) -> Any | None:
    return (
        metrics.get(PriceMetricType.FAIR_MARKET_VALUE.value)
        or metrics.get(PriceMetricType.MEDIAN.value)
        or metrics.get(PriceMetricType.AVERAGE.value)
    )


def _value(snapshot: Any | None) -> Decimal | None:
    if snapshot is None:
        return None
    value = getattr(snapshot, "value", None)
    if value is not None:
        return Decimal(str(value))
    value = getattr(snapshot, "median_price", None)
    return Decimal(str(value)) if value is not None else None


def _sample_size(snapshot: Any) -> int:
    return int(
        getattr(snapshot, "sample_size", getattr(snapshot, "listing_count", 0)) or 0
    )


def _evidence_counts(snapshot: Any) -> tuple[int, int]:
    payload = getattr(snapshot, "source_payload", None) or {}
    evidence = payload.get("evidence_counts", {})
    sold = int(evidence.get("sold", 0) or 0)
    active = int(evidence.get("active", 0) or 0)
    if not (sold or active):
        for listing in payload.get("listings", []):
            status = str(
                listing.get("listing_status", listing.get("status", ""))
            ).lower()
            sold += status == "sold"
            active += status == "active"
    return sold, active


def _observation_weight(
    snapshot: Any, sample_size: int, sold: int, active: int
) -> Decimal:
    evidence_total = sold + active
    evidence_weight = (
        (Decimal(sold) * SOLD_LISTING_WEIGHT + Decimal(active) * ACTIVE_LISTING_WEIGHT)
        / evidence_total
        if evidence_total
        else Decimal("1")
    )
    # More observations help, but cannot let one marketplace overwhelm the market.
    sample_weight = Decimal(max(1, min(sample_size, 100))).sqrt()
    return _marketplace_weight(snapshot) * sample_weight * evidence_weight


def _marketplace_weight(snapshot: Any) -> Decimal:
    marketplace = getattr(snapshot, "marketplace", None)
    combined_name = f"{getattr(marketplace, 'name', '') or ''} {getattr(marketplace, 'display_name', '') or ''}".lower()
    if "bricklink" in combined_name:
        return Decimal("1.15")
    if "ebay" in combined_name:
        return Decimal("1.00")
    return Decimal("0.90")


def _exclude_iqr_outliers(
    observations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(observations) < IQR_MIN_SAMPLE_SIZE:
        return observations, []
    prices = sorted(item["price"] for item in observations)
    q1, _q2, q3 = quantiles(prices, n=4, method="inclusive")
    iqr = q3 - q1
    lower, upper = q1 - Decimal("1.5") * iqr, q3 + Decimal("1.5") * iqr
    included, excluded = [], []
    for item in observations:
        if lower <= item["price"] <= upper:
            included.append(item)
        else:
            excluded.append(
                {
                    "snapshot_id": item["input"]["snapshot_id"],
                    "reason": "iqr_outlier",
                    "price": str(_money(item["price"])),
                }
            )
    return included, excluded

##TODO: Fix weighed average function type issue
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


def _confidence_score(
    observations: list[dict[str, Any]], *, now: datetime | None
) -> int:
    sample_size = sum(item["sample_size"] for item in observations)
    sample_score = min(50, sample_size * 2)
    marketplace_score = min(20, len(observations) * 10)
    sold = sum(item["sold_count"] for item in observations)
    active = sum(item["active_count"] for item in observations)
    evidence_score = min(10, sold * 2) if sold + active else 5
    prices = [item["price"] for item in observations]
    spread = (
        (max(prices) - min(prices)) / _median(prices)
        if len(prices) > 1 and _median(prices)
        else Decimal("0")
    )
    consistency_score = max(0, 15 - min(15, int(spread * 100)))
    freshness_score = (
        5 if all(_is_fresh_input(item["input"], now) for item in observations) else 0
    )
    return min(
        100,
        sample_score
        + marketplace_score
        + evidence_score
        + consistency_score
        + freshness_score,
    )


def _confidence_band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _is_fresh_input(input_record: dict[str, Any], now: datetime | None) -> bool:
    retrieval = input_record.get("retrieval_time")
    if retrieval is None:
        return False
    return _as_utc(_datetime_value(retrieval)) >= (
        now or datetime.now(UTC)
    ) - timedelta(hours=DEFAULT_FRESHNESS_HOURS)


def _input_record(
    snapshot: Any, sample_size: int, sold: int, active: int
) -> dict[str, Any]:
    marketplace = getattr(snapshot, "marketplace", None)
    return {
        "snapshot_id": _snapshot_id(snapshot),
        "marketplace": getattr(marketplace, "name", None),
        "condition": getattr(snapshot, "condition", None),
        "retrieval_time": _serialized_datetime(
            getattr(snapshot, "retrieval_time", None)
        ),
        "sample_size": sample_size,
        "sold_count": sold,
        "active_count": active,
    }


def _snapshot_confidence(snapshot: Any) -> Decimal | None:
    direct = getattr(snapshot, "confidence_score", None)
    if direct is not None:
        return Decimal(str(direct))
    payload = getattr(snapshot, "source_payload", None) or {}
    values = [
        item.get("match_confidence", item.get("confidence"))
        for item in payload.get("listings", [])
    ]
    values = [Decimal(str(value)) for value in values if value is not None]
    return min(values) if values else None


def _set_number(snapshot: Any) -> str | None:
    value = getattr(snapshot, "set_number", None) or getattr(
        getattr(snapshot, "lego_set", None), "set_number", None
    )
    return str(value).upper() if value is not None else None


def _snapshot_id(snapshot: Any) -> str | None:
    value = getattr(snapshot, "id", None)
    return str(value) if value is not None else None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _datetime_value(value: datetime | str) -> datetime:
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def _serialized_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _empty_estimate(
    sample_size: int, exclusions: list[dict[str, Any]]
) -> dict[str, Any]:
    zero = Decimal("0.00")
    return {
        "fair_value": zero,
        "market_low": zero,
        "market_high": zero,
        "median_price": zero,
        "listing_count": sample_size,
        "confidence": "low",
        "low_value": zero,
        "expected_value": zero,
        "high_value": zero,
        "confidence_score": 0,
        "condition": None,
        "methodology_version": ESTIMATION_METHODOLOGY_VERSION,
        "inputs_used": [],
        "excluded_inputs": exclusions,
    }


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
