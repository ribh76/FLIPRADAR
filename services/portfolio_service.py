from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import PortfolioItemCreate
from database.repositories import (
    create_portfolio_item,
    delete_portfolio_item,
    get_latest_snapshots_by_set_number,
    get_portfolio_items_for_user,
    get_set_by_number,
)
from engine import price_estimator


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
    return await _portfolio_item_response(db, item)


async def list_user_portfolio(db: AsyncSession, user_id: UUID) -> list[dict]:
    items = await get_portfolio_items_for_user(db, user_id)
    return [await _portfolio_item_response(db, item) for item in items]


async def delete_user_portfolio_item(
    db: AsyncSession, user_id: UUID, item_id: UUID
) -> None:
    deleted = await delete_portfolio_item(db, item_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found"
        )


async def calculate_portfolio_summary(db: AsyncSession, user_id: UUID) -> dict:
    items = await get_portfolio_items_for_user(db, user_id)
    holdings = []
    total_quantity = 0
    total_cost_basis = Decimal("0.00")
    estimated_current_value = Decimal("0.00")

    grouped = defaultdict(list)
    for item in items:
        grouped[item.set_number].append(item)

    for set_number, grouped_items in grouped.items():
        quantity = sum(item.quantity for item in grouped_items)
        cost_basis = sum(item.purchase_price * item.quantity for item in grouped_items)
        total_quantity += quantity
        total_cost_basis += cost_basis

        unit_value, status = await _current_unit_value(db, set_number)
        set_name = getattr(grouped_items[0].lego_set, "name", None)
        if unit_value is None:
            current_value = None
            gain_loss = None
        else:
            current_value = _money(unit_value * quantity)
            gain_loss = _money(current_value - cost_basis)
            estimated_current_value += current_value

        holdings.append(
            {
                "set_number": set_number,
                "set_name": set_name,
                "quantity": quantity,
                "cost_basis": _money(cost_basis),
                "estimated_current_value": current_value,
                "unrealized_gain_loss": gain_loss,
                "valuation_status": status,
            }
        )

    gain_loss_total = _money(estimated_current_value - total_cost_basis)
    gain_loss_percent = None
    if total_cost_basis > 0:
        gain_loss_percent = _money((gain_loss_total / total_cost_basis) * 100)

    return {
        "total_items": len(items),
        "total_sets": len(grouped),
        "total_quantity": total_quantity,
        "total_cost_basis": _money(total_cost_basis),
        "estimated_current_value": _money(estimated_current_value),
        "unrealized_gain_loss": gain_loss_total,
        "unrealized_gain_loss_percent": gain_loss_percent,
        "holdings": holdings,
    }


async def _portfolio_item_response(db: AsyncSession, item) -> dict:
    unit_value, status = await _current_unit_value(db, item.set_number)
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
        "acquired_at": item.acquired_at,
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
    db: AsyncSession, set_number: str
) -> tuple[Decimal | None, str]:
    snapshots = await get_latest_snapshots_by_set_number(db, set_number)
    if not snapshots:
        return None, "missing_market_data"
    estimate = price_estimator.estimate_fair_value(snapshots)
    fair_value = estimate["fair_value"]
    if fair_value <= 0:
        return None, "missing_market_data"
    return _money(fair_value), "valued"
