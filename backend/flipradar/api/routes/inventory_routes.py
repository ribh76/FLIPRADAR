from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.route_classification import RouteClassification, route_metadata
from flipradar.api.schemas.inventory_schema import (
    ChecklistAdjustmentUpdate,
    InventoryItemResponse,
    InventoryQuantityUpdate,
    MissingPartsChecklistResponse,
    PurchaseItemUpdate,
)
from flipradar.services import inventory_service
from flipradar.services.errors import ServiceError

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get(
    "",
    response_model=list[InventoryItemResponse],
    **route_metadata(RouteClassification.PUBLIC, "List the authenticated user's inventory."),
)
async def get_inventory(
    current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db_session)
) -> list[dict]:
    return await inventory_service.list_inventory(db, current_user.id)


@router.put(
    "/items/{element_id}",
    response_model=InventoryItemResponse,
    **route_metadata(RouteClassification.PUBLIC, "Set an owned inventory item's quantity."),
)
async def update_inventory_item(
    element_id: UUID,
    payload: InventoryQuantityUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        return await inventory_service.set_inventory_quantity(
            db, current_user.id, element_id, payload.quantity
        )
    except ServiceError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/checklists/{set_number}",
    response_model=MissingPartsChecklistResponse,
    **route_metadata(RouteClassification.PUBLIC, "Build the authenticated user's missing-parts checklist."),
)
async def get_checklist(
    set_number: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        return await inventory_service.checklist(db, current_user.id, set_number)
    except ServiceError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.patch(
    "/checklists/{set_number}/requirements/{requirement_id}",
    response_model=MissingPartsChecklistResponse,
    **route_metadata(RouteClassification.PUBLIC, "Update an authenticated user's checklist adjustment."),
)
async def adjust_checklist(
    requirement_id: UUID,
    set_number: str,
    payload: ChecklistAdjustmentUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        return await inventory_service.update_adjustment(
            db,
            current_user.id,
            set_number,
            requirement_id,
            payload.manual_adjustment,
            payload.substitute_element_id,
        )
    except ServiceError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/checklists/{set_number}/purchase-list",
    response_model=MissingPartsChecklistResponse,
    **route_metadata(RouteClassification.PUBLIC, "Add an authenticated user's missing parts to a purchase list."),
)
async def create_replacement_purchase_list(
    set_number: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        return await inventory_service.add_missing_parts_to_purchase_list(
            db, current_user.id, set_number
        )
    except ServiceError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.patch(
    "/purchase-list/{purchase_item_id}",
    response_model=MissingPartsChecklistResponse,
    **route_metadata(RouteClassification.PUBLIC, "Update an authenticated user's purchase-list item."),
)
async def update_replacement_purchase(
    purchase_item_id: UUID,
    payload: PurchaseItemUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        return await inventory_service.update_purchase_item(
            db,
            current_user.id,
            purchase_item_id,
            payload.purchased,
            payload.actual_unit_cost,
        )
    except ServiceError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
