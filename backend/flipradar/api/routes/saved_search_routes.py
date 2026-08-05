from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchUpdate,
)
from flipradar.services import saved_search_service
from flipradar.services.errors import ServiceError

router = APIRouter(prefix="/saved-searches", tags=["Deals"])


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("", response_model=list[SavedSearchResponse])
async def list_saved_searches(
    current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db_session)
):
    return await saved_search_service.list_saved_searches(db, current_user.id)


@router.post(
    "", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED
)
async def create_saved_search(
    payload: SavedSearchCreate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await saved_search_service.create_saved_search(
            db, current_user.id, payload.name, payload.filter_config
        )
    except ServiceError as exc:
        _raise(exc)


@router.patch("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: UUID,
    payload: SavedSearchUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await saved_search_service.update_saved_search(
            db,
            current_user.id,
            search_id,
            name=payload.name,
            filter_config=payload.filter_config,
        )
    except ServiceError as exc:
        _raise(exc)


@router.post(
    "/{search_id}/duplicate",
    response_model=SavedSearchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_saved_search(
    search_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await saved_search_service.duplicate_saved_search(
            db, current_user.id, search_id
        )
    except ServiceError as exc:
        _raise(exc)


@router.post("/{search_id}/run", response_model=SavedSearchResponse)
async def run_saved_search(
    search_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await saved_search_service.run_saved_search(
            db, current_user.id, search_id
        )
    except ServiceError as exc:
        _raise(exc)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        await saved_search_service.delete_saved_search(db, current_user.id, search_id)
    except ServiceError as exc:
        _raise(exc)
