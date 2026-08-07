from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from flipradar.domain.models.enums import NotificationType


class NotificationResponse(BaseModel):
    id: UUID
    notification_type: NotificationType
    watchlist_item_id: UUID | None
    title: str
    message: str
    payload: dict[str, Any]
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationMarkAllReadResponse(BaseModel):
    updated_count: int


class NotificationPreferenceResponse(BaseModel):
    notification_type: NotificationType
    in_app_enabled: bool
    email_enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None

    def provided_fields(self) -> dict[str, bool]:
        return self.model_dump(exclude_unset=True)
