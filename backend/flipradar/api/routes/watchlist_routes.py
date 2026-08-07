from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    WatchlistHistoryPoint,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistItemUpdate,
    WatchlistMonitoringPreferenceResponse,
    WatchlistMonitoringPreferenceUpdate,
    WatchlistMoveToPortfolio,
    WatchlistReplacementResponse,
    WatchlistSummaryResponse,
)
from flipradar.services import watchlist_service
from flipradar.services.errors import ServiceError

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("", response_model=list[WatchlistItemResponse])
async def list_watchlist_items(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await watchlist_service.list_watchlist_items(
        db, current_user.id, limit=limit, offset=offset
    )


@router.post(
    "", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED
)
async def create_watchlist_item(
    payload: WatchlistItemCreate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await watchlist_service.create_watchlist_item(
            db, current_user.id, payload
        )
    except ServiceError as exc:
        _raise(exc)


@router.post("/refresh", response_model=list[WatchlistItemResponse])
async def refresh_watchlist_items(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await watchlist_service.refresh_watchlist_items(db, current_user.id)


@router.get("/summary", response_model=WatchlistSummaryResponse)
async def get_watchlist_summary(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await watchlist_service.get_watchlist_summary(db, current_user.id)


@router.get(
    "/monitoring-preferences", response_model=WatchlistMonitoringPreferenceResponse
)
async def get_watchlist_monitoring_preferences(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await watchlist_service.get_watchlist_monitoring_preference(
        db, current_user.id
    )


@router.patch(
    "/monitoring-preferences", response_model=WatchlistMonitoringPreferenceResponse
)
async def update_watchlist_monitoring_preferences(
    payload: WatchlistMonitoringPreferenceUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await watchlist_service.update_watchlist_monitoring_preference(
        db, current_user.id, payload
    )


@router.get("/{item_id}/history", response_model=list[WatchlistHistoryPoint])
async def get_watchlist_history(
    item_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await watchlist_service.get_watchlist_history(
            db, current_user.id, item_id
        )
    except ServiceError as exc:
        _raise(exc)


@router.get(
    "/{item_id}/replacements", response_model=list[WatchlistReplacementResponse]
)
async def find_watchlist_replacements(
    item_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await watchlist_service.find_replacements(db, current_user.id, item_id)
    except ServiceError as exc:
        _raise(exc)


@router.post("/{item_id}/move-to-portfolio")
async def move_watchlist_item_to_portfolio(
    item_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    payload: WatchlistMoveToPortfolio = Body(default_factory=WatchlistMoveToPortfolio),
):
    try:
        return await watchlist_service.move_watchlist_item_to_portfolio(
            db, current_user.id, item_id, payload
        )
    except ServiceError as exc:
        _raise(exc)


@router.get("/{item_id}", response_model=WatchlistItemResponse)
async def get_watchlist_item(
    item_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await watchlist_service.get_watchlist_item(db, current_user.id, item_id)
    except ServiceError as exc:
        _raise(exc)


@router.patch("/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item(
    item_id: UUID,
    payload: WatchlistItemUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await watchlist_service.update_watchlist_item(
            db, current_user.id, item_id, payload
        )
    except ServiceError as exc:
        _raise(exc)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    item_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    try:
        await watchlist_service.delete_watchlist_item(db, current_user.id, item_id)
    except ServiceError as exc:
        _raise(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
