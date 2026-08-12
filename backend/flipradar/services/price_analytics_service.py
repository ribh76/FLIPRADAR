"""Transparent, descriptive price analytics built from stored observations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import sqrt

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def calculate_price_analytics(
    snapshots: Iterable,
    rollups: Iterable,
    *,
    now: datetime | None = None,
) -> dict:
    """Calculate descriptive metrics; this deliberately makes no price forecast."""
    raw = list(snapshots)
    compacted = list(rollups)
    points = _daily_points(raw, compacted)
    current_at = now or datetime.now(UTC)
    latest_by_marketplace = _latest_by_marketplace(raw)
    latest_values = [
        Decimal(snapshot.value) for snapshot in latest_by_marketplace.values()
    ]
    latest_samples = sum(
        snapshot.sample_size for snapshot in latest_by_marketplace.values()
    )

    rolling = {
        f"{days}d": _rolling_average(points, current_at.date(), days)
        for days in (7, 30, 90)
    }
    returns = _returns(points)
    record_high = max((point[1] for point in points), default=None)
    latest_value = points[-1][1] if points else None
    drawdown = (
        _percentage(latest_value - record_high, record_high)
        if latest_value is not None and record_high
        else None
    )
    period_start = current_at.date() - timedelta(days=30)
    observations_30d = sum(1 for point_date, _ in points if point_date >= period_start)
    liquidity_score = min(
        100,
        len(latest_by_marketplace) * 25
        + min(25, latest_samples)
        + min(25, observations_30d * 5),
    )

    return {
        "observation_count": len(raw)
        + sum(item.observation_count for item in compacted if item.period == "monthly"),
        "series_point_count": len(points),
        "latest_value": latest_value,
        "rolling_averages": rolling,
        "volatility": {
            "return_standard_deviation_percent": _volatility(returns),
            "return_count": len(returns),
        },
        "marketplace_spread": {
            "marketplace_count": len(latest_values),
            "low_value": min(latest_values) if latest_values else None,
            "high_value": max(latest_values) if latest_values else None,
            "absolute_spread": (
                max(latest_values) - min(latest_values) if latest_values else None
            ),
            "spread_percent_of_low": (
                _percentage(max(latest_values) - min(latest_values), min(latest_values))
                if latest_values and min(latest_values) > ZERO
                else None
            ),
        },
        "liquidity": {
            "latest_marketplace_count": len(latest_by_marketplace),
            "latest_sample_size": latest_samples,
            "observations_30d": observations_30d,
            "proxy_score": liquidity_score,
        },
        "drawdown": {
            "recorded_high": record_high,
            "latest_value": latest_value,
            "drawdown_percent": drawdown,
        },
    }


def _daily_points(snapshots: list, rollups: list) -> list[tuple[date, Decimal]]:
    by_date: dict[date, list[Decimal]] = defaultdict(list)
    for snapshot in snapshots:
        by_date[_utc_date(snapshot.retrieval_time)].append(Decimal(snapshot.value))
    # Monthly compaction is the canonical long-term series. Weekly rows are exposed
    # for charting, but not combined here so a period is never counted twice.
    for rollup in rollups:
        if rollup.period == "monthly":
            by_date[rollup.period_start].append(Decimal(rollup.average_value))
    return [
        (point_date, _mean(values)) for point_date, values in sorted(by_date.items())
    ]


def _utc_date(observed_at: datetime) -> date:
    if observed_at.tzinfo is None:
        return observed_at.replace(tzinfo=UTC).date()
    return observed_at.astimezone(UTC).date()


def _latest_by_marketplace(snapshots: list) -> dict:
    latest = {}
    for snapshot in snapshots:
        existing = latest.get(snapshot.marketplace_id)
        if existing is None or snapshot.retrieval_time > existing.retrieval_time:
            latest[snapshot.marketplace_id] = snapshot
    return latest


def _rolling_average(
    points: list[tuple[date, Decimal]], today: date, days: int
) -> Decimal | None:
    values = [
        value
        for point_date, value in points
        if point_date >= today - timedelta(days=days - 1)
    ]
    return _mean(values) if values else None


def _returns(points: list[tuple[date, Decimal]]) -> list[Decimal]:
    return [
        (current - previous) / previous
        for (_, previous), (_, current) in zip(points, points[1:], strict=False)
        if previous > ZERO
    ]


def _volatility(returns: list[Decimal]) -> Decimal | None:
    if len(returns) < 2:
        return None
    average = _mean(returns)
    variance = sum((item - average) ** 2 for item in returns) / len(returns)
    return (Decimal(str(sqrt(float(variance)))) * HUNDRED).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _mean(values: list[Decimal]) -> Decimal:
    return (sum(values) / len(values)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _percentage(numerator: Decimal, denominator: Decimal) -> Decimal:
    return ((numerator / denominator) * HUNDRED).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
