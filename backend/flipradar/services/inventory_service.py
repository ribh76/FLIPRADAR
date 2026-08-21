"""Inventory and missing-parts checklist calculations."""

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flipradar.domain.models import (
    ChecklistAdjustment,
    Element,
    InventoryItem,
    LegoSet,
    PortfolioItem,
    PriceSnapshot,
    ReplacementPurchaseItem,
    SetPartRequirement,
)
from flipradar.services.errors import ServiceError


def _element_response(element: Element) -> dict:
    return {
        "id": element.id,
        "element_number": element.canonical_identifier,
        "part_number": element.part.canonical_identifier,
        "part_name": element.part.name,
        "color": element.color.name,
        "image_url": (
            element.image_urls[0]
            if element.image_urls
            else (element.part.image_urls[0] if element.part.image_urls else None)
        ),
        "estimated_unit_cost": (
            element.part.market_price
            if element.part.market_price is not None
            else None
        ),
    }


async def list_inventory(db: AsyncSession, user_id: UUID) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(InventoryItem)
                .where(InventoryItem.user_id == user_id, InventoryItem.quantity > 0)
                .options(
                    selectinload(InventoryItem.element).selectinload(Element.part),
                    selectinload(InventoryItem.element).selectinload(Element.color),
                )
                .order_by(InventoryItem.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "quantity": item.quantity,
            "element": _element_response(item.element),
        }
        for item in rows
    ]


async def set_inventory_quantity(
    db: AsyncSession, user_id: UUID, element_id: UUID, quantity: int
) -> dict:
    element = (
        await db.execute(
            select(Element)
            .where(Element.id == element_id)
            .options(selectinload(Element.part), selectinload(Element.color))
        )
    ).scalar_one_or_none()
    if element is None:
        raise ServiceError("Part/color element was not found", status_code=404)
    item = (
        await db.execute(
            select(InventoryItem).where(
                InventoryItem.user_id == user_id, InventoryItem.element_id == element_id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        item = InventoryItem(user_id=user_id, element_id=element_id, quantity=quantity)
        db.add(item)
    else:
        item.quantity = quantity
    await db.commit()
    await db.refresh(item)
    return {
        "id": item.id,
        "quantity": item.quantity,
        "element": _element_response(element),
    }


async def checklist(db: AsyncSession, user_id: UUID, set_number: str) -> dict:
    lego_set = (
        await db.execute(
            select(LegoSet).where(LegoSet.set_number == set_number.upper())
        )
    ).scalar_one_or_none()
    if lego_set is None:
        raise ServiceError("Set was not found", status_code=404)
    requirements = (
        (
            await db.execute(
                select(SetPartRequirement)
                .where(SetPartRequirement.lego_set_id == lego_set.id)
                .options(
                    selectinload(SetPartRequirement.element).selectinload(Element.part),
                    selectinload(SetPartRequirement.element).selectinload(
                        Element.color
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    adjustments = (
        (
            await db.execute(
                select(ChecklistAdjustment).where(
                    ChecklistAdjustment.user_id == user_id,
                    ChecklistAdjustment.requirement_id.in_(
                        [r.id for r in requirements]
                    ),
                )
            )
        )
        .scalars()
        .all()
        if requirements
        else []
    )
    by_requirement = {
        adjustment.requirement_id: adjustment for adjustment in adjustments
    }
    inventory = (
        await db.execute(
            select(InventoryItem.element_id, InventoryItem.quantity).where(
                InventoryItem.user_id == user_id
            )
        )
    ).all()
    owned = {element_id: quantity for element_id, quantity in inventory}
    purchases = (
        (
            await db.execute(
                select(ReplacementPurchaseItem).where(
                    ReplacementPurchaseItem.user_id == user_id,
                    ReplacementPurchaseItem.requirement_id.in_(
                        [requirement.id for requirement in requirements]
                    ),
                )
            )
        )
        .scalars()
        .all()
        if requirements
        else []
    )
    purchases_by_requirement = {item.requirement_id: item for item in purchases}
    lines = []
    for requirement in requirements:
        adjustment = by_requirement.get(requirement.id)
        adjusted = max(
            0,
            requirement.quantity + (adjustment.manual_adjustment if adjustment else 0),
        )
        substitute = None
        if adjustment and adjustment.substitute_element_id:
            substitute = (
                await db.execute(
                    select(Element)
                    .where(Element.id == adjustment.substitute_element_id)
                    .options(selectinload(Element.part), selectinload(Element.color))
                )
            ).scalar_one_or_none()
        available = owned.get(
            substitute.id if substitute else requirement.element_id, 0
        )
        candidates = (
            (
                await db.execute(
                    select(Element)
                    .where(
                        Element.part_id == requirement.element.part_id,
                        Element.id != requirement.element_id,
                    )
                    .options(selectinload(Element.part), selectinload(Element.color))
                )
            )
            .scalars()
            .all()
        )
        lines.append(
            {
                "requirement_id": requirement.id,
                "element": _element_response(requirement.element),
                "required_quantity": requirement.quantity,
                "adjusted_quantity": adjusted,
                "owned_quantity": available,
                "missing_quantity": max(0, adjusted - available),
                "substitute_element": (
                    _element_response(substitute) if substitute else None
                ),
                "substitution_candidates": [
                    _element_response(candidate) for candidate in candidates
                ],
                "purchase_item_id": (
                    purchases_by_requirement[requirement.id].id
                    if requirement.id in purchases_by_requirement
                    else None
                ),
                "purchased": (
                    purchases_by_requirement[requirement.id].purchased
                    if requirement.id in purchases_by_requirement
                    else False
                ),
                "actual_unit_cost": (
                    purchases_by_requirement[requirement.id].actual_unit_cost
                    if requirement.id in purchases_by_requirement
                    else None
                ),
            }
        )
    completed_snapshot = (
        await db.execute(
            select(PriceSnapshot.value)
            .where(
                PriceSnapshot.lego_set_id == lego_set.id,
                PriceSnapshot.metric_type == "fair_market_value",
            )
            .order_by(PriceSnapshot.retrieval_time.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    purchase_price = (
        await db.execute(
            select(PortfolioItem.purchase_price)
            .where(
                PortfolioItem.user_id == user_id,
                PortfolioItem.lego_set_id == lego_set.id,
            )
            .order_by(PortfolioItem.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    required_parts = sum(line["adjusted_quantity"] for line in lines)
    owned_parts = sum(
        min(line["adjusted_quantity"], line["owned_quantity"]) for line in lines
    )
    completeness_percent = (
        (Decimal(owned_parts) / Decimal(required_parts) * Decimal("100")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        if required_parts
        else Decimal("0.0")
    )
    estimated_replacement_cost = sum(
        (
            line["missing_quantity"]
            * (line["substitute_element"] or line["element"])["estimated_unit_cost"]
            for line in lines
            if (line["substitute_element"] or line["element"])["estimated_unit_cost"]
            is not None
        ),
        Decimal("0.00"),
    )
    estimated_replacement_cost = estimated_replacement_cost.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    completed_set_value = (
        Decimal(completed_snapshot) if completed_snapshot is not None else None
    )
    completeness_adjusted_value = (
        (completed_set_value * completeness_percent / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if completed_set_value is not None
        else None
    )
    return {
        "set_number": lego_set.set_number,
        "set_name": lego_set.name,
        "required_parts": required_parts,
        "owned_parts": owned_parts,
        "missing_parts": sum(line["missing_quantity"] for line in lines),
        "completeness_percent": completeness_percent,
        "estimated_replacement_cost": estimated_replacement_cost,
        "completed_set_value": completed_set_value,
        "completeness_adjusted_value": completeness_adjusted_value,
        "purchase_price": Decimal(purchase_price) if purchase_price is not None else None,
        "projected_net_value": (
            (
                completed_set_value
                - estimated_replacement_cost
                - Decimal(purchase_price)
            ).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if completed_set_value is not None and purchase_price is not None
            else None
        ),
        "lines": lines,
    }


async def update_adjustment(
    db: AsyncSession,
    user_id: UUID,
    set_number: str,
    requirement_id: UUID,
    manual_adjustment: int,
    substitute_element_id: UUID | None,
) -> dict:
    requirement = (
        await db.execute(
            select(SetPartRequirement)
            .join(LegoSet)
            .where(
                SetPartRequirement.id == requirement_id,
                LegoSet.set_number == set_number.upper(),
            )
        )
    ).scalar_one_or_none()
    if requirement is None:
        raise ServiceError("Set requirement was not found", status_code=404)
    if substitute_element_id:
        substitute = (
            await db.execute(select(Element).where(Element.id == substitute_element_id))
        ).scalar_one_or_none()
        if substitute is None:
            raise ServiceError("Substitute element was not found", status_code=404)
    adjustment = (
        await db.execute(
            select(ChecklistAdjustment).where(
                ChecklistAdjustment.user_id == user_id,
                ChecklistAdjustment.requirement_id == requirement_id,
            )
        )
    ).scalar_one_or_none()
    if adjustment is None:
        adjustment = ChecklistAdjustment(user_id=user_id, requirement_id=requirement_id)
        db.add(adjustment)
    adjustment.manual_adjustment = manual_adjustment
    adjustment.substitute_element_id = substitute_element_id
    await db.commit()
    return await checklist(db, user_id, set_number)


async def add_missing_parts_to_purchase_list(
    db: AsyncSession, user_id: UUID, set_number: str
) -> dict:
    """Create or refresh unpurchased replacement orders from a checklist."""
    data = await checklist(db, user_id, set_number)
    for line in data["lines"]:
        if not line["missing_quantity"]:
            continue
        element = line["substitute_element"] or line["element"]
        item = (
            await db.execute(
                select(ReplacementPurchaseItem).where(
                    ReplacementPurchaseItem.user_id == user_id,
                    ReplacementPurchaseItem.requirement_id == line["requirement_id"],
                )
            )
        ).scalar_one_or_none()
        if item is None:
            db.add(
                ReplacementPurchaseItem(
                    user_id=user_id,
                    requirement_id=line["requirement_id"],
                    element_id=element["id"],
                    quantity=line["missing_quantity"],
                    estimated_unit_cost=element["estimated_unit_cost"] or Decimal("0.00"),
                )
            )
        elif not item.purchased:
            item.element_id = element["id"]
            item.quantity = line["missing_quantity"]
            item.estimated_unit_cost = element["estimated_unit_cost"] or Decimal("0.00")
    await db.commit()
    return await checklist(db, user_id, set_number)


async def update_purchase_item(
    db: AsyncSession,
    user_id: UUID,
    purchase_item_id: UUID,
    purchased: bool,
    actual_unit_cost: Decimal | None,
) -> dict:
    item = (
        await db.execute(
            select(ReplacementPurchaseItem).where(
                ReplacementPurchaseItem.id == purchase_item_id,
                ReplacementPurchaseItem.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise ServiceError("Purchase-list item was not found", status_code=404)
    item.purchased = purchased
    item.actual_unit_cost = actual_unit_cost
    set_number = (
        await db.execute(
            select(LegoSet.set_number)
            .join(
                SetPartRequirement,
                SetPartRequirement.lego_set_id == LegoSet.id,
            )
            .where(SetPartRequirement.id == item.requirement_id)
        )
    ).scalar_one()
    await db.commit()
    return await checklist(db, user_id, set_number)
