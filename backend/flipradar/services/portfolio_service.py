from collections import defaultdict
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
    delete_portfolio_item,
    get_all_portfolio_items_for_user,
    get_latest_snapshots_by_set_number,
    get_latest_snapshots_for_set_numbers,
    get_portfolio_items_for_user,
    get_recent_snapshots_by_set_number,
    get_set_by_number,
    update_portfolio_item,
)
from flipradar.domain.engines import price_estimator


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
        item = await create_portfolio_item(
            db,
            user_id,
            payload.model_dump(exclude_none=True),
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid portfolio item"
        ) from exc
    value_map = await _current_unit_value_map(db, [item])
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

    item = await update_portfolio_item(db, item_id, user_id, update_data)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found"
        )
    value_map = await _current_unit_value_map(db, [item])
    return _portfolio_item_response(item, value_map)


async def delete_user_portfolio_item(
    db: AsyncSession, user_id: UUID, item_id: UUID
) -> None:
    deleted = await delete_portfolio_item(db, item_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found"
        )


async def calculate_portfolio_summary(db: AsyncSession, user_id: UUID) -> dict:
    items = await get_all_portfolio_items_for_user(db, user_id)
    value_map = await _current_unit_value_map(db, items)
    holdings = []
    total_quantity = 0
    total_cost_basis = Decimal("0.00")
    valued_cost_basis = Decimal("0.00")
    estimated_current_value = Decimal("0.00")
    unrealized_gain_loss = Decimal("0.00")

    grouped = defaultdict(list)
    for item in items:
        grouped[(item.set_number, item.condition)].append(item)

    for (set_number, condition), grouped_items in grouped.items():
        quantity = sum(item.quantity for item in grouped_items)
        cost_basis = sum(item.purchase_price * item.quantity for item in grouped_items)
        total_quantity += quantity
        total_cost_basis += cost_basis

        unit_value, status = value_map[(set_number, condition)]
        set_name = getattr(grouped_items[0].lego_set, "name", None)
        if unit_value is None:
            current_value = None
            gain_loss = None
        else:
            current_value = _money(unit_value * quantity)
            gain_loss = _money(current_value - cost_basis)
            estimated_current_value += current_value
            valued_cost_basis += cost_basis
            unrealized_gain_loss += gain_loss

        holdings.append(
            {
                "set_number": set_number,
                "set_name": set_name,
                "condition": condition,
                "quantity": quantity,
                "cost_basis": _money(cost_basis),
                "estimated_current_value": current_value,
                "unrealized_gain_loss": gain_loss,
                "valuation_status": status,
            }
        )

    gain_loss_percent = None
    if valued_cost_basis > 0:
        gain_loss_percent = _money((unrealized_gain_loss / valued_cost_basis) * 100)

    return {
        "total_items": len(items),
        "total_sets": len({item.set_number for item in items}),
        "total_quantity": total_quantity,
        "total_cost_basis": _money(total_cost_basis),
        "estimated_current_value": _money(estimated_current_value),
        "unrealized_gain_loss": _money(unrealized_gain_loss),
        "unrealized_gain_loss_percent": gain_loss_percent,
        "holdings": holdings,
    }


def _portfolio_item_response(item, value_map: dict[tuple[str, str], tuple]) -> dict:
    unit_value, status = value_map[(item.set_number, item.condition)]
    cost_basis = _money(item.purchase_price * item.quantity)
    current_total_value = _money(unit_value * item.quantity) if unit_value else None
    gain_loss = (
        _money(current_total_value - cost_basis)
        if current_total_value is not None
        else None
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
        "current_unit_value": unit_value,
        "current_total_value": current_total_value,
        "cost_basis": cost_basis,
        "unrealized_gain_loss": gain_loss,
        "valuation_status": status,
    }


async def _current_unit_value(
    db: AsyncSession, set_number: str, condition: str = "unknown"
) -> tuple[Decimal | None, str]:
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
        return None, "missing_market_data"
    estimate = price_estimator.estimate_fair_value(
        snapshots, condition=snapshot_condition
    )
    fair_value = estimate["fair_value"]
    if fair_value <= 0:
        return None, "missing_market_data"
    return _money(fair_value), "valued"


async def _current_unit_value_map(
    db: AsyncSession, items: list
) -> dict[tuple[str, str], tuple]:
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
            values[(set_number, condition)] = (None, "missing_market_data")
            continue
        estimate = price_estimator.estimate_fair_value(
            snapshots, condition=snapshot_condition
        )
        fair_value = estimate["fair_value"]
        if fair_value <= 0:
            values[(set_number, condition)] = (None, "missing_market_data")
        else:
            values[(set_number, condition)] = (_money(fair_value), "valued")
    return values


def _snapshot_condition(condition: str) -> str | None:
    if condition in {"new", "sealed"}:
        return "new"
    if condition == "used":
        return "used_complete"
    return None
