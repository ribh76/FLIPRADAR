"""Persisted portfolio-level analytics built from owned holdings and market data."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.database.repositories import (
    create_portfolio_analytics_snapshot,
    get_active_listing_supply_for_set_numbers,
    get_all_portfolio_items_for_user,
    get_latest_portfolio_analytics_snapshot,
    get_price_snapshots_for_set_numbers,
)
from flipradar.domain.engines import hold_sell_engine
from flipradar.services.portfolio_service import (
    _current_unit_value_map,
    _snapshot_condition,
)

ANALYTICS_SCHEMA_VERSION = 1
PRICE_TREND_WINDOW_DAYS = 90
VALUATION_STALE_AFTER_DAYS = 14
SUPPLY_STALE_AFTER_DAYS = 14
MIN_RELIABLE_SUPPLY_LISTINGS = 3


def _money(value: Decimal | int | float) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _current_time() -> datetime:
    """Small clock seam used by deterministic analytics refreshes and tests."""
    return datetime.now(UTC)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _latest_by_metric(snapshots: list, condition: str | None) -> dict[str, Any]:
    candidates = [
        snapshot
        for snapshot in snapshots
        if condition is None or snapshot.condition == condition
    ]
    latest: dict[str, Any] = {}
    for snapshot in sorted(
        candidates,
        key=lambda snapshot: _as_utc(snapshot.retrieval_time),
        reverse=True,
    ):
        latest.setdefault(snapshot.metric_type, snapshot)
    return latest


def _trend_from_snapshots(snapshots: list, condition: str | None) -> dict[str, Any]:
    fair_values_by_day: dict[datetime.date, list[Decimal]] = defaultdict(list)
    for snapshot in snapshots:
        if snapshot.metric_type != "fair_market_value":
            continue
        if condition is not None and snapshot.condition != condition:
            continue
        fair_values_by_day[_as_utc(snapshot.retrieval_time).date()].append(
            Decimal(snapshot.value)
        )
    points = [
        {"date": day, "value": _money(median(values))}
        for day, values in sorted(fair_values_by_day.items())
    ]
    if len(points) < 2 or points[0]["value"] <= 0:
        return {
            "label": "insufficient_data",
            "percent": None,
            "points": points,
        }
    change_percent = _money(
        ((points[-1]["value"] - points[0]["value"]) / points[0]["value"]) * 100
    )
    label = (
        "rising"
        if change_percent >= Decimal("8.00")
        else "falling" if change_percent <= Decimal("-8.00") else "flat"
    )
    return {"label": label, "percent": change_percent, "points": points}


def _demand_signal(snapshots: list, condition: str | None) -> str | None:
    """Infer demand only when a latest pricing payload contains evidence counts."""
    latest_fair = _latest_by_metric(snapshots, condition).get("fair_market_value")
    evidence = (getattr(latest_fair, "source_payload", None) or {}).get(
        "evidence_counts", {}
    )
    sold = int(evidence.get("sold", 0) or 0)
    active = int(evidence.get("active", 0) or 0)
    if not (sold or active):
        return None
    if sold >= max(3, active):
        return "strong"
    if active >= max(3, sold * 3):
        return "weak"
    return "moderate"


def _allocation(holdings: list[dict], field: str, total_value: Decimal) -> list[dict]:
    grouped: dict[str, dict] = {}
    for holding in holdings:
        key = str(holding[field] if holding[field] is not None else "Unknown")
        bucket = grouped.setdefault(
            key,
            {
                "key": key,
                "holding_count": 0,
                "quantity": 0,
                "market_value": Decimal("0"),
                "unvalued_holding_count": 0,
            },
        )
        bucket["holding_count"] += 1
        bucket["quantity"] += holding["quantity"]
        if holding["current_total_value"] is None:
            bucket["unvalued_holding_count"] += 1
        else:
            bucket["market_value"] += holding["current_total_value"]
    return [
        {
            **bucket,
            "portfolio_value_percent": (
                _money((bucket["market_value"] / total_value) * 100)
                if total_value > 0
                else Decimal("0.00")
            ),
        }
        for bucket in sorted(
            grouped.values(), key=lambda item: item["market_value"], reverse=True
        )
    ]


def _concentration(holdings: list[dict], total_value: Decimal) -> dict:
    valued = [item for item in holdings if item["current_total_value"] is not None]
    ranked = sorted(valued, key=lambda item: item["current_total_value"], reverse=True)
    shares = [
        (holding["current_total_value"] / total_value) * 100
        for holding in ranked
        if total_value > 0
    ]
    hhi = _money(sum(share * share for share in shares)) if shares else Decimal("0.00")
    largest_share = _money(shares[0]) if shares else Decimal("0.00")
    top_three_share = _money(sum(shares[:3])) if shares else Decimal("0.00")
    level = (
        "high"
        if largest_share >= Decimal("40") or hhi >= Decimal("2500")
        else (
            "moderate"
            if largest_share >= Decimal("20") or hhi >= Decimal("1500")
            else "low"
        )
    )
    return {
        "level": level,
        "hhi": hhi,
        "effective_holding_count": (
            _money(Decimal("10000") / hhi) if hhi > 0 else Decimal("0.00")
        ),
        "largest_holding_percent": largest_share,
        "top_three_percent": top_three_share,
        "largest_holding": (
            _holding_reference(ranked[0], total_value) if ranked else None
        ),
    }


def _holding_reference(holding: dict, total_value: Decimal) -> dict:
    return {
        "portfolio_item_id": holding["portfolio_item_id"],
        "set_number": holding["set_number"],
        "set_name": holding["set_name"],
        "current_total_value": holding["current_total_value"],
        "portfolio_value_percent": (
            _money((holding["current_total_value"] / total_value) * 100)
            if total_value > 0 and holding["current_total_value"] is not None
            else None
        ),
    }


def _performance_reference(holding: dict) -> dict:
    return {
        "portfolio_item_id": holding["portfolio_item_id"],
        "set_number": holding["set_number"],
        "set_name": holding["set_name"],
        "performance_percent": holding["performance_percent"],
        "unrealized_gain_loss": holding["unrealized_gain_loss"],
        "current_total_value": holding["current_total_value"],
    }


async def refresh_portfolio_analytics(
    db: AsyncSession,
    user_id: UUID,
    *,
    portfolio_id: UUID | None = None,
    analysis_at: datetime | None = None,
) -> dict:
    """Calculate and persist a complete point-in-time portfolio analysis."""
    now = _as_utc(analysis_at) if analysis_at is not None else _current_time()
    items = await get_all_portfolio_items_for_user(db, user_id, portfolio_id)
    value_map = await _current_unit_value_map(db, items)
    set_numbers = {item.set_number for item in items}
    historical_snapshots, listings_by_set = await _market_evidence(db, set_numbers, now)
    total_market_value = _money(
        sum(
            unit_value * item.quantity
            for item in items
            if (unit_value := value_map[(item.set_number, item.condition)][0])
            is not None
        )
    )

    holdings: list[dict] = []
    persisted_holdings: list[dict] = []
    for item in items:
        holding, persisted = _analyze_holding(
            item=item,
            unit_value_data=value_map[(item.set_number, item.condition)],
            price_snapshots=historical_snapshots.get(item.set_number, []),
            listings=listings_by_set.get(item.set_number, []),
            portfolio_total_value=total_market_value,
            now=now,
        )
        holdings.append(holding)
        persisted_holdings.append(persisted)

    total_cost_basis = _money(sum(item["cost_basis"] for item in holdings))
    summary_metrics = _summary_metrics(holdings, total_market_value)
    currencies = {item.currency for item in items}
    snapshot = await create_portfolio_analytics_snapshot(
        db,
        snapshot_data={
            "user_id": user_id,
            "portfolio_id": portfolio_id,
            "generated_at": now,
            "currency": currencies.pop() if len(currencies) == 1 else "USD",
            "schema_version": ANALYTICS_SCHEMA_VERSION,
            "holding_count": len(holdings),
            "valued_holding_count": sum(
                holding["current_total_value"] is not None for holding in holdings
            ),
            "total_cost_basis": total_cost_basis,
            "total_market_value": total_market_value,
            "summary_metrics": _json_value(summary_metrics),
        },
        holding_metrics_data=persisted_holdings,
    )
    return _snapshot_response(snapshot)


async def get_latest_portfolio_analytics(
    db: AsyncSession, user_id: UUID, portfolio_id: UUID | None = None
) -> dict:
    snapshot = await get_latest_portfolio_analytics_snapshot(db, user_id, portfolio_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio analytics are unavailable until an analysis is refreshed.",
        )
    return _snapshot_response(snapshot)


async def _market_evidence(
    db: AsyncSession, set_numbers: set[str], now: datetime
) -> tuple[dict, dict]:
    snapshots = await get_price_snapshots_for_set_numbers(
        db,
        set_numbers,
        since=now - timedelta(days=PRICE_TREND_WINDOW_DAYS),
    )
    listings = await get_active_listing_supply_for_set_numbers(db, set_numbers)
    return snapshots, listings


def _analyze_holding(
    *,
    item,
    unit_value_data: tuple,
    price_snapshots: list,
    listings: list,
    portfolio_total_value: Decimal,
    now: datetime,
) -> tuple[dict, dict]:
    unit_value, valuation_status, confidence = unit_value_data
    confidence = confidence if valuation_status == "valued" else "missing_market_data"
    unit_value = Decimal(unit_value) if unit_value is not None else None
    cost_basis = _money(item.purchase_price * item.quantity)
    current_total_value = (
        _money(unit_value * item.quantity) if unit_value is not None else None
    )
    gain_loss = (
        _money(current_total_value - cost_basis)
        if current_total_value is not None
        else None
    )
    performance_percent = (
        _money((gain_loss / cost_basis) * 100)
        if gain_loss is not None and cost_basis > 0
        else None
    )
    holding_start = item.purchase_date or item.created_at
    holding_days = (
        max(0, (now - _as_utc(holding_start)).days) if holding_start else None
    )
    snapshot_condition = _snapshot_condition(item.condition)
    latest_metrics = _latest_by_metric(price_snapshots, snapshot_condition)
    latest_fair = latest_metrics.get("fair_market_value")
    latest_valuation_at = (
        _as_utc(latest_fair.retrieval_time) if latest_fair is not None else None
    )
    valuation_stale = (
        latest_valuation_at is None
        or latest_valuation_at < now - timedelta(days=VALUATION_STALE_AFTER_DAYS)
    )
    valuation_age_days = (
        max(0, (now - latest_valuation_at).days)
        if latest_valuation_at is not None
        else None
    )
    trend = _trend_from_snapshots(price_snapshots, snapshot_condition)
    recent_fair_values = [float(point["value"]) for point in trend["points"]]
    fresh_listings = [
        listing
        for listing in listings
        if _as_utc(listing.last_seen_at)
        >= now - timedelta(days=SUPPLY_STALE_AFTER_DAYS)
    ]
    supply_reliable = len(fresh_listings) >= MIN_RELIABLE_SUPPLY_LISTINGS
    marketplace_supply = len(fresh_listings) if supply_reliable else None
    concentration_percent = (
        _money((current_total_value / portfolio_total_value) * 100)
        if current_total_value is not None and portfolio_total_value > 0
        else None
    )
    signal_input = hold_sell_engine.decide_sell_or_hold(
        set_number=item.set_number,
        fair_value=float(unit_value) if unit_value is not None else None,
        market_low=(
            float(latest_metrics["low"].value)
            if latest_metrics.get("low") is not None
            else None
        ),
        market_high=(
            float(latest_metrics["high"].value)
            if latest_metrics.get("high") is not None
            else None
        ),
        listing_count=len(fresh_listings) if supply_reliable else 0,
        confidence=confidence if confidence in {"high", "medium", "low"} else "low",
        purchase_price=float(item.purchase_price),
        quantity=item.quantity,
        condition=item.condition,
        recent_fair_values=recent_fair_values,
        concentration_percent=(
            float(concentration_percent) if concentration_percent is not None else None
        ),
        marketplace_supply=marketplace_supply,
        supply_reliable=supply_reliable,
        demand_signal=_demand_signal(price_snapshots, snapshot_condition),
        valuation_age_days=valuation_age_days,
    )
    signal = (
        "sell_consideration"
        if signal_input["verdict"] == "SELL"
        else signal_input["verdict"].lower()
    )
    flags: list[str] = []
    if current_total_value is None:
        flags.append("insufficient_market_data")
    if confidence in {"low", "missing_market_data"}:
        flags.append("low_confidence_valuation")
    if valuation_stale:
        flags.append("stale_valuation")
    if not supply_reliable:
        flags.append("marketplace_supply_unreliable")
    if trend["label"] == "insufficient_data":
        flags.append("insufficient_price_trend_data")
    holding = {
        "portfolio_item_id": item.id,
        "set_number": item.set_number,
        "set_name": item.lego_set.name,
        "theme": item.lego_set.theme,
        "release_year": item.lego_set.release_year,
        "condition": item.condition,
        "quantity": item.quantity,
        "cost_basis": cost_basis,
        "current_unit_value": unit_value,
        "current_total_value": current_total_value,
        "unrealized_gain_loss": gain_loss,
        "performance_percent": performance_percent,
        "holding_days": holding_days,
        "holding_period_source": (
            "purchase_date"
            if item.purchase_date is not None
            else "portfolio_created_at"
        ),
        "valuation_status": valuation_status,
        "valuation_confidence": confidence,
        "valuation_as_of": latest_valuation_at,
        "valuation_age_days": valuation_age_days,
        "valuation_stale": valuation_stale,
        "price_trend": {
            "label": trend["label"],
            "percent": trend["percent"],
            "window_days": PRICE_TREND_WINDOW_DAYS,
            "point_count": len(trend["points"]),
        },
        "marketplace_supply": {
            "active_verified_listings": len(fresh_listings),
            "reliable": supply_reliable,
            "reported_supply": marketplace_supply,
            "as_of": max(
                (_as_utc(listing.last_seen_at) for listing in fresh_listings),
                default=None,
            ),
        },
        "signal": {
            "action": signal,
            "category": signal_input["category"],
            "score": signal_input["score"],
            "confidence": signal_input["recommendation_confidence"],
            "reason_codes": signal_input["reason_codes"],
            "reasoning": signal_input["reasoning"],
            "reasons": signal_input["reasons"],
            "warnings": signal_input["warnings"],
            "weighted_inputs": signal_input["weighted_inputs"],
        },
        "flags": flags,
    }
    persisted = {
        "portfolio_item_id": item.id,
        "set_number": item.set_number,
        "condition": item.condition,
        "quantity": item.quantity,
        "cost_basis": cost_basis,
        "current_total_value": current_total_value,
        "performance_percent": performance_percent,
        "holding_days": holding_days,
        "valuation_confidence": confidence,
        "valuation_stale": valuation_stale,
        "trend_label": trend["label"],
        "trend_percent": trend["percent"],
        "marketplace_supply": marketplace_supply,
        "supply_reliable": supply_reliable,
        "signal": signal,
        "signal_score": signal_input["score"],
        "flags": flags,
        "metrics": _json_value(holding),
    }
    return holding, persisted


def _summary_metrics(holdings: list[dict], total_market_value: Decimal) -> dict:
    performers = [
        holding for holding in holdings if holding["performance_percent"] is not None
    ]
    top = sorted(
        performers, key=lambda item: item["performance_percent"], reverse=True
    )[:3]
    bottom = sorted(performers, key=lambda item: item["performance_percent"])[:3]
    allocations = {
        "set": _allocation(holdings, "set_number", total_market_value),
        "theme": _allocation(holdings, "theme", total_market_value),
        "condition": _allocation(holdings, "condition", total_market_value),
        "release_year": _allocation(holdings, "release_year", total_market_value),
    }
    theme_allocation = allocations["theme"]
    theme_hhi = _money(
        sum(bucket["portfolio_value_percent"] ** 2 for bucket in theme_allocation)
    )
    signal_counts = {"hold": 0, "watch": 0, "sell_consideration": 0}
    for holding in holdings:
        signal_counts[holding["signal"]["action"]] += 1
    insufficient = [
        _holding_reference(item, total_market_value)
        for item in holdings
        if "insufficient_market_data" in item["flags"]
    ]
    stale = [
        _holding_reference(item, total_market_value)
        for item in holdings
        if "stale_valuation" in item["flags"]
    ]
    low_confidence = [
        _holding_reference(item, total_market_value)
        for item in holdings
        if "low_confidence_valuation" in item["flags"]
    ]
    return {
        "allocation": allocations,
        "concentration": _concentration(holdings, total_market_value),
        "diversification": {
            "distinct_sets": len({item["set_number"] for item in holdings}),
            "distinct_themes": len(
                {item["theme"] for item in holdings if item["theme"] is not None}
            ),
            "distinct_conditions": len({item["condition"] for item in holdings}),
            "distinct_release_years": len(
                {
                    item["release_year"]
                    for item in holdings
                    if item["release_year"] is not None
                }
            ),
            "theme_hhi": theme_hhi,
            "value_coverage_percent": (
                _money(
                    (
                        sum(
                            item["current_total_value"] is not None for item in holdings
                        )
                        / len(holdings)
                    )
                    * 100
                )
                if holdings
                else Decimal("0.00")
            ),
        },
        "top_performers": [_performance_reference(item) for item in top],
        "bottom_performers": [_performance_reference(item) for item in bottom],
        "valuation_attention": {
            "stale": stale,
            "low_confidence": low_confidence,
            "insufficient_data": insufficient,
        },
        "signals": signal_counts,
    }


def _snapshot_response(snapshot) -> dict:
    return {
        "id": snapshot.id,
        "generated_at": snapshot.generated_at,
        "currency": snapshot.currency,
        "schema_version": snapshot.schema_version,
        "holding_count": snapshot.holding_count,
        "valued_holding_count": snapshot.valued_holding_count,
        "total_cost_basis": snapshot.total_cost_basis,
        "total_market_value": snapshot.total_market_value,
        "summary_metrics": snapshot.summary_metrics,
        "holdings": [
            {
                "portfolio_item_id": holding.portfolio_item_id,
                "set_number": holding.set_number,
                "condition": holding.condition,
                "quantity": holding.quantity,
                "cost_basis": holding.cost_basis,
                "current_total_value": holding.current_total_value,
                "performance_percent": holding.performance_percent,
                "holding_days": holding.holding_days,
                "valuation_confidence": holding.valuation_confidence,
                "valuation_stale": holding.valuation_stale,
                "trend_label": holding.trend_label,
                "trend_percent": holding.trend_percent,
                "marketplace_supply": holding.marketplace_supply,
                "supply_reliable": holding.supply_reliable,
                "signal": holding.signal,
                "signal_score": holding.signal_score,
                "flags": holding.flags,
                "metrics": holding.metrics,
            }
            for holding in snapshot.holding_metrics
        ],
    }
