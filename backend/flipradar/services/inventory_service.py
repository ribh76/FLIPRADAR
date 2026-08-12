"""Inventory and missing-parts checklist calculations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flipradar.domain.models import (
    ChecklistAdjustment,
    Element,
    InventoryItem,
    LegoSet,
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
            }
        )
    return {
        "set_number": lego_set.set_number,
        "set_name": lego_set.name,
        "required_parts": sum(line["adjusted_quantity"] for line in lines),
        "owned_parts": sum(
            min(line["adjusted_quantity"], line["owned_quantity"]) for line in lines
        ),
        "missing_parts": sum(line["missing_quantity"] for line in lines),
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
