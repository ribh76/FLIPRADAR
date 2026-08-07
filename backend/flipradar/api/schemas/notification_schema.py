from __future__ import annotations

from datetime import datetime, time
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, model_validator

from flipradar.domain.models.enums import NotificationType


class NotificationResponse(BaseModel):
    id: UUID
    notification_type: NotificationType
    watchlist_item_id: UUID | None
    title: str
    message: str
    action_url: str
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


class NotificationSettingsResponse(BaseModel):
    email_enabled: bool
    timezone: str
    quiet_hours_start: time | None
    quiet_hours_end: time | None


class NotificationSettingsUpdate(BaseModel):
    email_enabled: bool | None = None
    timezone: str | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None

    @model_validator(mode="after")
    def validate_quiet_hours(self) -> NotificationSettingsUpdate:
        start_provided = "quiet_hours_start" in self.model_fields_set
        end_provided = "quiet_hours_end" in self.model_fields_set
        if start_provided != end_provided:
            raise ValueError("Provide both quiet-hours start and end, or neither")
        if (
            start_provided
            and self.quiet_hours_start is not None
            and self.quiet_hours_start == self.quiet_hours_end
        ):
            raise ValueError("Quiet-hours start and end must differ")
        if self.timezone is not None:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("timezone must be a valid IANA timezone") from exc
        return self

    def provided_fields(self) -> dict[str, bool | str | time | None]:
        return self.model_dump(exclude_unset=True)
