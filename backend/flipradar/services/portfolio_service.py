from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import PortfolioItemCreate, PortfolioItemUpdate
from flipradar.database.repositories import (
    DEFAULT_PAGE_LIMIT,
    Pagination,
    create_portfolio_item,
    create_portfolio_valuation_snapshot,
    delete_portfolio_item,
    get_all_portfolio_items_for_user,
    get_latest_snapshots_by_set_number,
    get_latest_snapshots_for_set_numbers,
    get_portfolio_item_by_id,
    get_portfolio_items_for_user,
    get_portfolio_valuation_snapshot_for_window,
    get_recent_snapshots_by_set_number,
    get_set_by_number,
    list_portfolio_history,
    update_portfolio_item,
)
from flipradar.domain.engines import portfolio_valuation, price_estimator
from flipradar.services import portfolio_dashboard_cache


def _money(value: Decimal | int) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def add_item_to_portfolio(
    db: AsyncSession, user_id: UUID, payload: PortfolioItemCreate
) -> dict:
    lego_set = await get_set_by_number(db, payload.set_number)
    if lego_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LEGO set not found"
        )

    try:
        async with db.begin_nested():
            item = await create_portfolio_item(
                db,
                user_id,
                payload.model_dump(exclude_none=True),
            )
            await create_user_valuation_snapshot(db, user_id)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid portfolio item"
        ) from exc
    value_map = await _current_unit_value_map(db, [item])
    portfolio_dashboard_cache.invalidate_user(user_id)
    return _portfolio_item_response(item, value_map)


async def list_user_portfolio(db: AsyncSession, user_id: UUID) -> list[dict]:
    return await list_user_portfolio_page(db, user_id)


async def list_user_portfolio_page(
    db: AsyncSession,
    user_id: UUID,
    *,
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    condition: str | None = None,
    theme: str | None = None,
    year: int | None = None,
    performance: str | None = None,
    order: str = "created_at_desc",
) -> list[dict]:
    # Valuation-derived filters and orders must be applied after fair values are
    # calculated. Fetching the matching ownership rows first keeps all DB access
    # user-scoped and preserves independently purchased duplicate holdings.
    valuation_order = order in {"value_asc", "value_desc", "gain_asc", "gain_desc"}
    if performance or valuation_order:
        items = await get_portfolio_items_for_user(
            db,
            user_id,
            condition=condition,
            theme=theme,
            year=year,
            unpaginated=True,
            order="created_at_desc",
        )
        value_map = await _current_unit_value_map(db, items)
        responses = [_portfolio_item_response(item, value_map) for item in items]
        if performance == "gain":
            responses = [
                item
                for item in responses
                if (item["unrealized_gain_loss"] or Decimal("0")) > 0
            ]
        elif performance == "loss":
            responses = [
                item
                for item in responses
                if (item["unrealized_gain_loss"] or Decimal("0")) < 0
            ]
        elif performance == "unvalued":
            responses = [
                item for item in responses if item["current_total_value"] is None
            ]
        if valuation_order:
            field = (
                "current_total_value"
                if order.startswith("value")
                else "unrealized_gain_loss"
            )
            responses.sort(
                key=lambda item: item[field] or Decimal("0"),
                reverse=order.endswith("_desc"),
            )
            responses.sort(key=lambda item: item[field] is None)
        return responses[offset : offset + limit]
    items = await get_portfolio_items_for_user(
        db,
        user_id,
        pagination=Pagination(limit=limit, offset=offset),
        condition=condition,
        theme=theme,
        year=year,
        order=order,
    )
    value_map = await _current_unit_value_map(db, items)
    return [_portfolio_item_response(item, value_map) for item in items]


async def update_user_portfolio_item(
    db: AsyncSession, user_id: UUID, item_id: UUID, payload: PortfolioItemUpdate
) -> dict:
    update_data = payload.model_dump(exclude_unset=True)
    if "set_number" in update_data:
        lego_set = await get_set_by_number(db, update_data["set_number"])
        if lego_set is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="LEGO set not found"
            )

    async with db.begin_nested():
        item = await update_portfolio_item(db, item_id, user_id, update_data)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio item not found",
            )
        await create_user_valuation_snapshot(db, user_id)
    value_map = await _current_unit_value_map(db, [item])
    portfolio_dashboard_cache.invalidate_user(user_id)
    return _portfolio_item_response(item, value_map)


async def get_portfolio_holding_detail(
    db: AsyncSession, user_id: UUID, item_id: UUID
) -> dict:
    """Return one user-owned holding with the market evidence behind its value."""
    item = await get_portfolio_item_by_id(db, item_id, user_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found"
        )

    all_items = await get_all_portfolio_items_for_user(db, user_id)
    value_map = await _current_unit_value_map(db, all_items)
    holding = _portfolio_item_response(item, value_map)
    valuations = [
        portfolio_valuation.calculate_holding_valuation(
            quantity=portfolio_item.quantity,
            purchase_price=portfolio_item.purchase_price,
            unit_market_value=value_map[
                (portfolio_item.set_number, portfolio_item.condition)
            ][0],
        )
        for portfolio_item in all_items
    ]
    portfolio_total = portfolio_valuation.calculate_portfolio_totals(valuations)[
        "total_market_value"
    ]
    holding_value = holding["current_total_value"]
    share = (
        _money((holding_value / portfolio_total) * 100)
        if holding_value is not None and (portfolio_total > 0)
        else None
    )
    valued_holdings = sorted(
        (
            response["current_total_value"]
            for response in (
                _portfolio_item_response(portfolio_item, value_map)
                for portfolio_item in all_items
            )
            if response["current_total_value"] is not None
        ),
        reverse=True,
    )
    rank = (
        valued_holdings.index(holding_value) + 1
        if holding_value is not None and holding_value in valued_holdings
        else None
    )
    risk_level = (
        "high"
        if share is not None and share >= 40
        else "moderate" if share is not None and share >= 20 else "low"
    )
    risk_message = (
        "This holding represents a large share of the portfolio."
        if risk_level == "high"
        else (
            "This holding is a meaningful part of the portfolio."
            if risk_level == "moderate"
            else (
                "This holding has limited concentration impact."
                if share is not None
                else "Concentration will be available when this holding has a market value."
            )
        )
    )

    snapshots = await get_recent_snapshots_by_set_number(db, item.set_number, limit=100)
    fair_value_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.metric_type == "fair_market_value"
    ]
    latest_snapshot_at = max(
        (snapshot.retrieval_time for snapshot in fair_value_snapshots), default=None
    )
    condition_pricing = []
    for condition in ("new", "used_complete", "incomplete"):
        condition_snapshots = [
            snapshot
            for snapshot in fair_value_snapshots
            if snapshot.condition == condition
        ]
        if condition_snapshots:
            estimate = price_estimator.estimate_fair_value(
                condition_snapshots, condition=condition
            )
            estimated_value = _money(estimate["fair_value"])
            confidence = estimate["confidence"]
            condition_latest_at = max(
                snapshot.retrieval_time for snapshot in condition_snapshots
            )
        else:
            estimated_value = None
            confidence = None
            condition_latest_at = None
        condition_pricing.append(
            {
                "condition": "used" if condition == "used_complete" else condition,
                "estimated_unit_value": estimated_value,
                "confidence": confidence,
                "latest_snapshot_at": condition_latest_at,
            }
        )

    return {
        "holding": holding,
        "portfolio_total_value": portfolio_total,
        "portfolio_share_percent": share,
        "concentration_risk": {
            "level": risk_level,
            "message": risk_message,
            "portfolio_share_percent": share,
            "value_rank": rank,
        },
        "market_freshness_at": latest_snapshot_at,
        "market_snapshots": [
            {
                "timestamp": snapshot.retrieval_time,
                "marketplace": snapshot.marketplace.display_name,
                "condition": (
                    "used"
                    if snapshot.condition == "used_complete"
                    else snapshot.condition
                ),
                "metric_type": snapshot.metric_type,
                "value": snapshot.value,
                "sample_size": snapshot.sample_size,
                "currency": snapshot.currency,
            }
            for snapshot in reversed(fair_value_snapshots)
        ],
        "condition_pricing": condition_pricing,
    }


async def delete_user_portfolio_item(
    db: AsyncSession, user_id: UUID, item_id: UUID
) -> None:
    async with db.begin_nested():
        deleted = await delete_portfolio_item(db, item_id, user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio item not found",
            )
        await create_user_valuation_snapshot(db, user_id)
    portfolio_dashboard_cache.invalidate_user(user_id)


async def calculate_portfolio_summary(db: AsyncSession, user_id: UUID) -> dict:
    items = await get_all_portfolio_items_for_user(db, user_id)
    value_map = await _current_unit_value_map(db, items)
    holdings = []
    total_quantity = 0
    holding_valuations = []

    grouped = defaultdict(list)
    for item in items:
        grouped[(item.set_number, item.condition)].append(item)

    for (set_number, condition), grouped_items in grouped.items():
        quantity = sum(item.quantity for item in grouped_items)
        cost_basis = sum(item.purchase_price * item.quantity for item in grouped_items)
        total_quantity += quantity

        unit_value, status, _confidence = value_map[(set_number, condition)]
        set_name = getattr(grouped_items[0].lego_set, "name", None)
        valuations = [
            portfolio_valuation.calculate_holding_valuation(
                quantity=item.quantity,
                purchase_price=item.purchase_price,
                unit_market_value=unit_value,
            )
            for item in grouped_items
        ]
        holding_valuations.extend(valuations)
        current_value = (
            _money(
                sum(
                    valuation.market_value
                    for valuation in valuations
                    if valuation.market_value is not None
                )
            )
            if unit_value is not None
            else None
        )
        gain_loss = (
            _money(
                sum(
                    valuation.unrealized_gain_loss
                    for valuation in valuations
                    if valuation.unrealized_gain_loss is not None
                )
            )
            if unit_value is not None
            else None
        )
        gain_loss_percent = (
            _money((gain_loss / cost_basis) * 100)
            if gain_loss is not None and cost_basis > 0
            else None
        )

        holdings.append(
            {
                "set_number": set_number,
                "set_name": set_name,
                "condition": condition,
                "quantity": quantity,
                "cost_basis": _money(cost_basis),
                "estimated_current_value": current_value,
                "unrealized_gain_loss": gain_loss,
                "unrealized_gain_loss_percent": gain_loss_percent,
                "valuation_status": status,
            }
        )

    totals = portfolio_valuation.calculate_portfolio_totals(holding_valuations)

    return {
        "total_items": len(items),
        "total_sets": len({item.set_number for item in items}),
        "total_quantity": total_quantity,
        "total_cost_basis": totals["total_cost_basis"],
        "estimated_current_value": totals["total_market_value"],
        "unrealized_gain_loss": totals["total_gain_loss"],
        "unrealized_gain_loss_percent": totals["total_gain_loss_percent"],
        "holdings": holdings,
    }


async def get_portfolio_dashboard(
    db: AsyncSession,
    user_id: UUID,
    *,
    limit: int,
    offset: int,
    condition: str | None,
    theme: str | None,
    year: int | None,
    performance: str | None,
    order: str,
    history_range: str,
) -> dict:
    """Serve all dashboard panels from one valuation pass and one bounded cache key."""
    key = (
        user_id,
        limit,
        offset,
        condition,
        theme,
        year,
        performance,
        order,
        history_range,
    )

    async def load() -> dict:
        items = await get_all_portfolio_items_for_user(db, user_id)
        value_map = await _current_unit_value_map(db, items)
        responses = [_portfolio_item_response(item, value_map) for item in items]
        filtered = _filter_and_order_portfolio_responses(
            responses,
            performance=performance,
            order=order,
            condition=condition,
            theme=theme,
            year=year,
            items=items,
        )
        history: dict | None = None
        history_unavailable: str | None = None
        try:
            history = await get_portfolio_valuation_history(db, user_id, history_range)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise
            history_unavailable = str(exc.detail)
        page = filtered[offset : offset + limit + 1]
        return {
            "portfolio": {
                "data": page[:limit],
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "count": len(page[:limit]),
                    "has_more": len(page) > limit,
                },
            },
            "summary": _portfolio_summary_from_items(items, value_map),
            "history": history,
            "history_unavailable": history_unavailable,
        }

    return await portfolio_dashboard_cache.get_or_load(key, load)


def _filter_and_order_portfolio_responses(
    responses: list[dict],
    *,
    performance: str | None,
    order: str,
    condition: str | None,
    theme: str | None,
    year: int | None,
    items: list,
) -> list[dict]:
    by_id = {item.id: item for item in items}
    filtered = [
        response
        for response in responses
        if (condition is None or response["condition"] == condition)
        and (theme is None or response["theme"] == theme)
        and (
            year is None
            or getattr(by_id[response["id"]].lego_set, "release_year", None) == year
        )
    ]
    if performance == "gain":
        filtered = [
            item
            for item in filtered
            if (item["unrealized_gain_loss"] or Decimal("0")) > 0
        ]
    elif performance == "loss":
        filtered = [
            item
            for item in filtered
            if (item["unrealized_gain_loss"] or Decimal("0")) < 0
        ]
    elif performance == "unvalued":
        filtered = [item for item in filtered if item["current_total_value"] is None]
    if order in {"value_asc", "value_desc", "gain_asc", "gain_desc"}:
        field = (
            "current_total_value"
            if order.startswith("value")
            else "unrealized_gain_loss"
        )
        filtered.sort(key=lambda item: item[field] is None)
        filtered.sort(
            key=lambda item: item[field] or Decimal("0"),
            reverse=order.endswith("_desc"),
        )
    elif order.startswith("theme_"):
        filtered.sort(
            key=lambda item: item["theme"] or "", reverse=order.endswith("_desc")
        )
    elif order.startswith("purchase_date_"):
        filtered.sort(
            key=lambda item: item["purchase_date"] or datetime.min.replace(tzinfo=UTC),
            reverse=order.endswith("_desc"),
        )
    else:
        filtered.sort(
            key=lambda item: item["created_at"], reverse=order.endswith("_desc")
        )
    return filtered


def _portfolio_summary_from_items(
    items: list, value_map: dict[tuple[str, str], tuple]
) -> dict:
    valuations = [
        portfolio_valuation.calculate_holding_valuation(
            quantity=item.quantity,
            purchase_price=item.purchase_price,
            unit_market_value=value_map[(item.set_number, item.condition)][0],
        )
        for item in items
    ]
    totals = portfolio_valuation.calculate_portfolio_totals(valuations)
    return {
        "total_items": len(items),
        "total_sets": len({item.set_number for item in items}),
        "total_quantity": sum(item.quantity for item in items),
        "total_cost_basis": totals["total_cost_basis"],
        "estimated_current_value": totals["total_market_value"],
        "unrealized_gain_loss": totals["total_gain_loss"],
        "unrealized_gain_loss_percent": totals["total_gain_loss_percent"],
        "holdings": [],
    }


def _portfolio_item_response(item, value_map: dict[tuple[str, str], tuple]) -> dict:
    unit_value, status, confidence = value_map[(item.set_number, item.condition)]
    valuation = portfolio_valuation.calculate_holding_valuation(
        quantity=item.quantity,
        purchase_price=item.purchase_price,
        unit_market_value=unit_value,
    )
    return {
        "id": item.id,
        "user_id": item.user_id,
        "set_number": item.set_number,
        "quantity": item.quantity,
        "purchase_price": item.purchase_price,
        "condition": item.condition,
        "purchase_date": item.purchase_date,
        "currency": item.currency,
        "notes": item.notes,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "set_name": getattr(item.lego_set, "name", None),
        "theme": getattr(item.lego_set, "theme", None),
        "current_unit_value": unit_value,
        "current_total_value": valuation.market_value,
        "cost_basis": valuation.cost_basis,
        "unrealized_gain_loss": valuation.unrealized_gain_loss,
        "unrealized_gain_loss_percent": valuation.unrealized_gain_loss_percent,
        "valuation_status": status,
        "valuation_confidence": confidence if status == "valued" else None,
    }


async def _current_unit_value(
    db: AsyncSession, set_number: str, condition: str = "unknown"
) -> tuple[Decimal | None, str, str]:
    snapshot_condition = _snapshot_condition(condition)
    if snapshot_condition is None:
        snapshots = await get_latest_snapshots_by_set_number(db, set_number)
    else:
        snapshots = [
            snapshot
            for snapshot in await get_recent_snapshots_by_set_number(
                db, set_number, limit=50
            )
            if snapshot.condition == snapshot_condition
        ]
    if not snapshots:
        return None, "missing_market_data", "missing_market_data"
    estimate = price_estimator.estimate_fair_value(
        snapshots, condition=snapshot_condition
    )
    fair_value = estimate["fair_value"]
    if fair_value <= 0:
        return None, "missing_market_data", "missing_market_data"
    return _money(fair_value), "valued", estimate["confidence"]


async def _current_unit_value_map(
    db: AsyncSession, items: list
) -> dict[tuple[str, str], tuple[Decimal | None, str, str]]:
    keys = {(item.set_number, item.condition) for item in items}
    if not keys:
        return {}

    snapshots_by_set = await get_latest_snapshots_for_set_numbers(
        db, {set_number for set_number, _condition in keys}
    )
    values = {}
    for set_number, condition in keys:
        snapshot_condition = _snapshot_condition(condition)
        snapshots = snapshots_by_set.get(set_number, [])
        if snapshot_condition is not None:
            snapshots = [
                snapshot
                for snapshot in snapshots
                if snapshot.condition == snapshot_condition
            ]
        if not snapshots:
            values[(set_number, condition)] = (
                None,
                "missing_market_data",
                "missing_market_data",
            )
            continue
        estimate = price_estimator.estimate_fair_value(
            snapshots, condition=snapshot_condition
        )
        fair_value = estimate["fair_value"]
        if fair_value <= 0:
            values[(set_number, condition)] = (
                None,
                "missing_market_data",
                "missing_market_data",
            )
        else:
            values[(set_number, condition)] = (
                _money(fair_value),
                "valued",
                estimate["confidence"],
            )
    return values


async def create_user_valuation_snapshot(
    db: AsyncSession, user_id: UUID, *, snapshot_at: datetime | None = None
) -> None:
    """Persist one transactional valuation per user per hourly time window."""
    timestamp = (snapshot_at or datetime.now(UTC)).astimezone(UTC)
    window_start = timestamp.replace(minute=0, second=0, microsecond=0)
    if await get_portfolio_valuation_snapshot_for_window(db, user_id, window_start):
        return

    items = await get_all_portfolio_items_for_user(db, user_id)
    value_map = await _current_unit_value_map(db, items)
    valuations = []
    item_snapshots = []
    for item in items:
        unit_value, _status, confidence = value_map[(item.set_number, item.condition)]
        valuation = portfolio_valuation.calculate_holding_valuation(
            quantity=item.quantity,
            purchase_price=item.purchase_price,
            unit_market_value=unit_value,
        )
        valuations.append(valuation)
        item_snapshots.append(
            {
                "portfolio_item_id": item.id,
                "unit_value": unit_value,
                "total_value": valuation.market_value,
                "confidence": confidence,
                "snapshot_at": timestamp,
            }
        )
    totals = portfolio_valuation.calculate_portfolio_totals(valuations)
    currencies = {item.currency for item in items}
    try:
        async with db.begin_nested():
            await create_portfolio_valuation_snapshot(
                db,
                snapshot_data={
                    "user_id": user_id,
                    "cost_basis": totals["total_cost_basis"],
                    "market_value": totals["total_market_value"],
                    "gain_loss": totals["total_gain_loss"],
                    "currency": currencies.pop() if len(currencies) == 1 else "USD",
                    "window_start": window_start,
                    "snapshot_at": timestamp,
                },
                item_snapshots_data=item_snapshots,
            )
    except IntegrityError:
        # The unique window constraint handles concurrent refreshes without
        # failing the portfolio mutation or creating duplicate history rows.
        return


async def get_portfolio_valuation_history(
    db: AsyncSession, user_id: UUID, history_range: str
) -> dict:
    days_by_range = {
        "1d": 1,
        "1w": 7,
        "1m": 30,
        "3m": 90,
        "180d": 180,
        "1y": 365,
        "all": None,
    }
    days = days_by_range[history_range]
    start = datetime.now(UTC) - timedelta(days=days) if days is not None else None
    snapshots = await list_portfolio_history(db, user_id, start)
    if len(snapshots) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio history is unavailable until at least two valuation snapshots have been recorded.",
        )
    return {
        "range": history_range,
        "points": [
            {
                "timestamp": snapshot.snapshot_at,
                "cost_basis": snapshot.cost_basis,
                "market_value": snapshot.market_value,
                "gain_loss": snapshot.gain_loss,
                "currency": snapshot.currency,
            }
            for snapshot in snapshots
        ],
    }


def _snapshot_condition(condition: str) -> str | None:
    if condition in {"new", "sealed"}:
        return "new"
    if condition == "used":
        return "used_complete"
    return None
