from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas.notification_schema import (
    NotificationMarkAllReadResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from flipradar.domain.models.enums import NotificationType
from flipradar.services import notification_service
from flipradar.services.errors import ServiceError

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await notification_service.list_notifications(
        db,
        current_user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def get_unread_count(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await notification_service.unread_count(db, current_user.id)


@router.get("/preferences", response_model=list[NotificationPreferenceResponse])
async def list_notification_preferences(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await notification_service.list_preferences(db, current_user.id)


@router.patch(
    "/preferences/{notification_type}", response_model=NotificationPreferenceResponse
)
async def update_notification_preference(
    notification_type: NotificationType,
    payload: NotificationPreferenceUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await notification_service.update_preference(
        db, current_user.id, notification_type, payload.provided_fields()
    )


@router.post("/mark-all-read", response_model=NotificationMarkAllReadResponse)
async def mark_all_notifications_read(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await notification_service.mark_all_read(db, current_user.id)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await notification_service.mark_read(
            db, current_user.id, notification_id
        )
    except ServiceError as exc:
        _raise(exc)
