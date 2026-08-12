from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas.inventory_schema import (
    ChecklistAdjustmentUpdate,
    InventoryItemResponse,
    InventoryQuantityUpdate,
    MissingPartsChecklistResponse,
)
from flipradar.services import inventory_service
from flipradar.services.errors import ServiceError

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=list[InventoryItemResponse])
async def get_inventory(
    current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db_session)
) -> list[dict]:
    return await inventory_service.list_inventory(db, current_user.id)


@router.put("/items/{element_id}", response_model=InventoryItemResponse)
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


@router.get("/checklists/{set_number}", response_model=MissingPartsChecklistResponse)
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
