"""Transparent, descriptive price analytics built from stored observations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import sqrt

ZERO = Decimal("0")
HUNDRED = Decimal("100")
CONDITION_WEIGHTS = {
    "new": Decimal("1.00"),
    "used_complete": Decimal("0.78"),
    "incomplete": Decimal("0.45"),
}
ANNUAL_INFLATION_RATE = Decimal("0.041")


def calculate_price_analytics(
    snapshots: Iterable,
    rollups: Iterable,
    *,
    condition: str = "new",
    currency: str = "USD",
    lego_set=None,
    now: datetime | None = None,
) -> dict:
    """Calculate descriptive metrics; this deliberately makes no price forecast."""
    all_raw = list(snapshots)
    all_rollups = list(rollups)
    raw = [snapshot for snapshot in all_raw if snapshot.condition == condition]
    compacted = [rollup for rollup in all_rollups if rollup.condition == condition]
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
    current_year = current_at.year
    condition_comparison = _condition_adjusted_comparison(all_raw, condition)
    theme_benchmark = _theme_benchmark(lego_set, current_year, latest_value)
    retirement = _retirement_annotation(lego_set, current_year, latest_value)
    msrp_comparison = _msrp_comparison(lego_set, latest_value, currency)
    inflation = _inflation_adjusted_view(lego_set, current_year, latest_value, currency)
    validation = _validation_metrics(
        lego_set, points, latest_by_marketplace, latest_samples, latest_value
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
        "condition_adjusted_comparison": condition_comparison,
        "theme_benchmark": theme_benchmark,
        "retirement": retirement,
        "msrp_comparison": msrp_comparison,
        "inflation_adjusted": inflation,
        "confidence_band": _confidence_band(validation),
        "chart_controls": _chart_controls(),
        "validation_metrics": validation,
    }


def _condition_adjusted_comparison(snapshots: list, selected_condition: str) -> dict:
    latest_by_condition = {}
    for snapshot in snapshots:
        existing = latest_by_condition.get(snapshot.condition)
        if existing is None or snapshot.retrieval_time > existing.retrieval_time:
            latest_by_condition[snapshot.condition] = snapshot
    condition_values = {}
    for name, weight in CONDITION_WEIGHTS.items():
        snapshot = latest_by_condition.get(name)
        value = Decimal(snapshot.value) if snapshot else None
        condition_values[name] = {
            "weight": weight,
            "latest_value": value,
            "new_equivalent_value": (
                _money(value / weight) if value is not None else None
            ),
        }
    return {
        "selected_condition": selected_condition,
        "selected_condition_weight": CONDITION_WEIGHTS[selected_condition],
        "conditions": condition_values,
    }


def _theme_benchmark(lego_set, current_year: int, latest_value: Decimal | None) -> dict:
    release_year = getattr(lego_set, "release_year", None)
    age_years = max(0, current_year - release_year) if release_year else None
    multiplier = (
        _money(
            Decimal("1") + min(Decimal("0.35"), Decimal(age_years) * Decimal("0.015"))
        )
        if age_years is not None
        else None
    )
    return {
        "theme": getattr(lego_set, "theme", None),
        "age_years": age_years,
        "age_weight": multiplier,
        "benchmark_index": _money(multiplier * HUNDRED) if multiplier else None,
        "age_weighted_value": (
            _money(latest_value * multiplier)
            if latest_value is not None and multiplier
            else None
        ),
    }


def _retirement_annotation(
    lego_set, current_year: int, latest_value: Decimal | None
) -> dict:
    retirement_year = getattr(lego_set, "retirement_year", None)
    retired_years = max(0, current_year - retirement_year) if retirement_year else None
    rarity_multiplier = (
        _money(
            Decimal("1")
            + min(Decimal("0.30"), Decimal(retired_years) * Decimal("0.03"))
        )
        if retired_years is not None
        else Decimal("1.00")
    )
    return {
        "is_retired": retirement_year is not None and retirement_year <= current_year,
        "retirement_year": retirement_year,
        "years_retired": retired_years,
        "rarity_multiplier": rarity_multiplier,
        "rarity_adjusted_value": (
            _money(latest_value * rarity_multiplier)
            if latest_value is not None
            else None
        ),
    }


def _msrp_comparison(lego_set, latest_value: Decimal | None, currency: str) -> dict:
    msrp = getattr(lego_set, "msrp", None)
    original_currency = getattr(lego_set, "original_currency", None)
    if msrp is not None and original_currency and original_currency != currency:
        return {
            "baseline_value": None,
            "difference_amount": None,
            "difference_percent": None,
        }
    return _price_comparison(latest_value, Decimal(msrp) if msrp is not None else None)


def _inflation_adjusted_view(
    lego_set, current_year: int, latest_value: Decimal | None, currency: str
) -> dict:
    msrp = getattr(lego_set, "msrp", None)
    release_year = getattr(lego_set, "release_year", None)
    years = max(0, current_year - release_year) if release_year else None
    original_currency = getattr(lego_set, "original_currency", None)
    adjusted = (
        _money(Decimal(msrp) * ((Decimal("1") + ANNUAL_INFLATION_RATE) ** years))
        if msrp is not None
        and years is not None
        and (original_currency is None or original_currency == currency)
        else None
    )
    result = _price_comparison(latest_value, adjusted)
    result.update(
        {
            "annual_rate_percent": Decimal("4.10"),
            "years": years,
            "inflation_adjusted_msrp": adjusted,
        }
    )
    return result


def _price_comparison(latest_value: Decimal | None, baseline: Decimal | None) -> dict:
    if latest_value is None or baseline is None:
        return {
            "baseline_value": baseline,
            "difference_amount": None,
            "difference_percent": None,
        }
    return {
        "baseline_value": baseline,
        "difference_amount": _money(latest_value - baseline),
        "difference_percent": (
            _percentage(latest_value - baseline, baseline) if baseline > ZERO else None
        ),
    }


def _validation_metrics(
    lego_set, points, marketplaces, sample_size, latest_value
) -> dict:
    catalog_fields = ("theme", "release_year", "msrp")
    available_catalog_fields = sum(
        bool(getattr(lego_set, field, None)) for field in catalog_fields
    )
    return {
        "has_price_data": latest_value is not None,
        "series_point_count": len(points),
        "marketplace_count": len(marketplaces),
        "latest_sample_size": sample_size,
        "catalog_completeness_percent": (
            _money(Decimal(available_catalog_fields * 100) / len(catalog_fields))
            if lego_set
            else Decimal("0.00")
        ),
        "data_quality_flag": bool(getattr(lego_set, "data_quality_flag", False)),
        "is_valid_for_experiment": bool(
            latest_value is not None and len(points) >= 3 and len(marketplaces) >= 2
        ),
    }


def _confidence_band(validation: dict) -> dict:
    score = 1
    score += validation["series_point_count"] >= 3
    score += validation["marketplace_count"] >= 2
    score += validation["latest_sample_size"] >= 10
    score += (
        validation["catalog_completeness_percent"] == HUNDRED
        and not validation["data_quality_flag"]
    )
    colors = {1: "red", 2: "orange", 3: "yellow", 4: "blue", 5: "green"}
    return {
        "band": score,
        "max_band": 5,
        "color": colors[score],
        "label": ("low" if score <= 2 else "moderate" if score == 3 else "high"),
    }


def _chart_controls() -> dict:
    return {
        "ranges": ["1W", "1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"],
        "aggregations": ["daily", "weekly", "monthly"],
        "chart_types": ["line", "area"],
        "overlays": ["price", "ma_7", "ma_30", "ma_90", "volume_proxy"],
        "comparison_modes": [
            "marketplace",
            "condition_adjusted",
            "msrp",
            "inflation_adjusted",
            "theme_benchmark",
        ],
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


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _percentage(numerator: Decimal, denominator: Decimal) -> Decimal:
    return ((numerator / denominator) * HUNDRED).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
