"""Watchlist notification creation, user inbox behavior, and digest delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.core.settings import get_settings as get_app_settings
from flipradar.database import repositories
from flipradar.database.repositories import Pagination
from flipradar.domain.models import Notification, WatchlistItem
from flipradar.domain.models.enums import NotificationType
from flipradar.services.email_service import get_email_service
from flipradar.services.errors import ServiceNotFoundError

BUY_DEAL_SCORE = Decimal("70")
INACTIVE_LISTING_STATUSES = {"ended", "removed", "sold"}


def _preference_values(preference: Any | None) -> tuple[bool, bool]:
    if preference is None:
        return True, False
    return preference.in_app_enabled, preference.email_enabled


def _item_label(item: WatchlistItem) -> str:
    lego_set = item.lego_set or (item.listing.lego_set if item.listing else None)
    return lego_set.set_number if lego_set else "this listing"


def _item_action_url(item: WatchlistItem) -> str:
    return f"{get_app_settings().frontend_url.rstrip('/')}/watchlist?item_id={item.id}"


def _quiet_hours_active(settings: Any, now: datetime) -> bool:
    if settings is None or settings.quiet_hours_start is None:
        return False
    try:
        local_time = now.astimezone(ZoneInfo(settings.timezone)).time()
    except ZoneInfoNotFoundError:
        local_time = now.astimezone(UTC).time()
    start = settings.quiet_hours_start
    end = settings.quiet_hours_end
    if start < end:
        return start <= local_time < end
    return local_time >= start or local_time < end


async def emit_watchlist_notifications(
    db: AsyncSession,
    *,
    user_id: UUID,
    item: WatchlistItem,
    previous: Any,
    current: Any,
    material_price_change_percent: Decimal,
) -> list[Notification]:
    """Emit deduplicated notifications for a fresh watchlist observation."""
    preferences = await repositories.list_notification_preferences(db, user_id)
    settings = await repositories.get_user_notification_settings(db, user_id)
    label = _item_label(item)
    action_url = _item_action_url(item)
    created: list[Notification] = []

    async def emit(
        notification_type: NotificationType,
        title: str,
        message: str,
        payload: dict[str, Any],
        **specific_fields: Any,
    ) -> None:
        in_app_enabled, email_enabled = _preference_values(
            preferences.get(notification_type.value)
        )
        email_enabled = email_enabled and (settings is None or settings.email_enabled)
        if not in_app_enabled and not email_enabled:
            return
        dedupe_key = f"{item.id}:{notification_type.value}:{payload}"
        if await repositories.get_latest_notification_by_dedupe_key(
            db, user_id, dedupe_key
        ):
            await repositories.create_notification_audit_log(
                db,
                user_id=user_id,
                event="suppressed_duplicate",
                channel="notification",
                detail=dedupe_key,
            )
            return
        notification = await repositories.create_notification(
            db,
            {
                "user_id": user_id,
                "watchlist_item_id": item.id,
                "notification_type": notification_type.value,
                "event_key": f"{current.id}:{notification_type.value}",
                "dedupe_key": dedupe_key,
                "title": title,
                "message": message,
                "action_url": action_url,
                "payload": {**payload, "action_url": action_url},
                "is_in_app": in_app_enabled,
                "email_eligible": email_enabled,
                **specific_fields,
            },
        )
        if notification is not None:
            created.append(notification)
            await repositories.create_notification_audit_log(
                db,
                user_id=user_id,
                notification_id=notification.id,
                event="created",
                channel="in_app",
            )

    if previous.listing_price and current.listing_price is not None:
        drop_percent = (
            (previous.listing_price - current.listing_price)
            / previous.listing_price
            * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if drop_percent >= material_price_change_percent:
            await emit(
                NotificationType.PRICE_DROP,
                f"Price drop for {label}",
                f"Price fell from ${previous.listing_price} to ${current.listing_price}.",
                {
                    "previous_price": str(previous.listing_price),
                    "current_price": str(current.listing_price),
                },
                previous_price=previous.listing_price,
                current_price=current.listing_price,
                drop_percent=drop_percent,
            )
    if (
        current.target_price is not None
        and current.listing_price is not None
        and current.listing_price <= current.target_price
        and (
            previous.listing_price is None
            or previous.target_price is None
            or previous.listing_price > previous.target_price
        )
    ):
        await emit(
            NotificationType.TARGET_REACHED,
            f"Target price reached for {label}",
            f"Current price ${current.listing_price} meets your ${current.target_price} target.",
            {
                "target_price": str(current.target_price),
                "current_price": str(current.listing_price),
            },
            target_price=current.target_price,
            current_price=current.listing_price,
        )
    if (
        previous.listing_status not in INACTIVE_LISTING_STATUSES
        and current.listing_status in INACTIVE_LISTING_STATUSES
    ):
        await emit(
            NotificationType.ENDED_LISTING,
            f"Listing ended for {label}",
            f"The watched listing is now {current.listing_status}.",
            {"listing_status": current.listing_status},
            listing_status=current.listing_status,
        )
    if (
        current.deal_score is not None
        and current.deal_score >= BUY_DEAL_SCORE
        and (previous.deal_score is None or previous.deal_score < BUY_DEAL_SCORE)
    ):
        await emit(
            NotificationType.DEAL_SCORE,
            f"New high-scoring deal for {label}",
            f"Deal score improved to {current.deal_score}.",
            {
                "previous_score": (
                    str(previous.deal_score)
                    if previous.deal_score is not None
                    else None
                ),
                "current_score": str(current.deal_score),
            },
            previous_score=previous.deal_score,
            current_score=current.deal_score,
        )
    return created


async def list_notifications(
    db: AsyncSession,
    user_id: UUID,
    *,
    unread_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    notifications = await repositories.list_notifications_for_user(
        db,
        user_id,
        unread_only=unread_only,
        pagination=Pagination(limit=limit, offset=offset),
    )
    return [_response(notification) for notification in notifications]


async def unread_count(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    return {"unread_count": await repositories.unread_notification_count(db, user_id)}


async def mark_read(
    db: AsyncSession, user_id: UUID, notification_id: UUID
) -> dict[str, Any]:
    notification = await repositories.get_notification_for_user(
        db, notification_id, user_id
    )
    if notification is None:
        raise ServiceNotFoundError("Notification not found")
    if not notification.is_read:
        await repositories.mark_notification_read(
            db, notification, read_at=datetime.now(UTC)
        )
    return _response(notification)


async def mark_all_read(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    count = await repositories.mark_all_notifications_read(
        db, user_id, read_at=datetime.now(UTC)
    )
    return {"updated_count": count}


async def list_preferences(db: AsyncSession, user_id: UUID) -> list[dict[str, Any]]:
    preferences = await repositories.list_notification_preferences(db, user_id)
    return [
        {
            "notification_type": notification_type.value,
            "in_app_enabled": _preference_values(
                preferences.get(notification_type.value)
            )[0],
            "email_enabled": _preference_values(
                preferences.get(notification_type.value)
            )[1],
        }
        for notification_type in NotificationType
    ]


async def update_preference(
    db: AsyncSession,
    user_id: UUID,
    notification_type: NotificationType,
    data: dict[str, Any],
) -> dict[str, Any]:
    preference = await repositories.upsert_notification_preference(
        db, user_id, notification_type.value, data
    )
    if data.get("email_enabled") is False:
        await repositories.disable_pending_notification_emails(
            db, user_id, notification_type.value
        )
    return {
        "notification_type": preference.notification_type,
        "in_app_enabled": preference.in_app_enabled,
        "email_enabled": preference.email_enabled,
    }


async def get_notification_settings(db: AsyncSession, user_id: UUID) -> dict[str, Any]:
    settings = await repositories.get_user_notification_settings(db, user_id)
    return _settings_response(settings)


async def update_notification_settings(
    db: AsyncSession, user_id: UUID, data: dict[str, Any]
) -> dict[str, Any]:
    settings = await repositories.upsert_user_notification_settings(db, user_id, data)
    if data.get("email_enabled") is False:
        await repositories.disable_pending_notification_emails(db, user_id)
    return _settings_response(settings)


async def unsubscribe_email(db: AsyncSession, user_id: UUID) -> dict[str, Any]:
    settings = await repositories.upsert_user_notification_settings(
        db, user_id, {"email_enabled": False}
    )
    await repositories.disable_pending_notification_emails(db, user_id)
    await repositories.create_notification_audit_log(
        db, user_id=user_id, event="email_unsubscribed", channel="email"
    )
    return _settings_response(settings)


async def deliver_pending_email_digests(db: AsyncSession) -> dict[str, int]:
    """Send at most one watchlist digest per user, then mark its entries sent."""
    users = await repositories.list_users_with_pending_notification_emails(db)
    delivered = 0
    pending_count = 0
    for user in users:
        notifications = await repositories.list_pending_notification_emails(db, user.id)
        if not notifications:
            continue
        pending_count += len(notifications)
        settings = await repositories.get_user_notification_settings(db, user.id)
        if settings is not None and not settings.email_enabled:
            await repositories.disable_pending_notification_emails(db, user.id)
            continue
        if _quiet_hours_active(settings, datetime.now(UTC)):
            continue
        html_items = "".join(
            f"<li><strong>{notification.title}</strong>: {notification.message} "
            f'<a href="{notification.action_url}">View item</a></li>'
            for notification in notifications
        )
        lines = "\n".join(
            f"- {notification.title}: {notification.message}\n  View: {notification.action_url}"
            for notification in notifications
        )
        unsubscribe_url = f"{get_app_settings().frontend_url.rstrip('/')}/notifications?unsubscribe=email"
        try:
            result = await get_email_service().send(
                to_address=user.email,
                subject=f"FlipRadar watchlist update ({len(notifications)})",
                text_body=(
                    f"Hi {user.username},\n\nYour watchlist updates:\n{lines}\n\n"
                    f"Manage or unsubscribe from email alerts: {unsubscribe_url}"
                ),
                html_body=(
                    f"<p>Hi {user.username},</p><p>Your watchlist updates:</p>"
                    f'<ul>{html_items}</ul><p><a href="{unsubscribe_url}">'
                    "Manage or unsubscribe from email alerts</a></p>"
                ),
            )
        except Exception as exc:
            for notification in notifications:
                await repositories.create_notification_audit_log(
                    db,
                    user_id=user.id,
                    notification_id=notification.id,
                    event="delivery_failed",
                    channel="email",
                    detail=str(exc),
                )
            continue
        if result.sent:
            await repositories.mark_notification_emails_sent(
                db,
                [notification.id for notification in notifications],
                sent_at=datetime.now(UTC),
            )
            for notification in notifications:
                await repositories.create_notification_audit_log(
                    db,
                    user_id=user.id,
                    notification_id=notification.id,
                    event="delivered",
                    channel="email",
                )
            delivered += len(notifications)
        else:
            event = "delivery_failed" if result.attempted else "delivery_deferred"
            for notification in notifications:
                await repositories.create_notification_audit_log(
                    db,
                    user_id=user.id,
                    notification_id=notification.id,
                    event=event,
                    channel="email",
                    detail=result.reason,
                )
    return {"users": len(users), "pending": pending_count, "delivered": delivered}


def _response(notification: Notification) -> dict[str, Any]:
    return {
        "id": notification.id,
        "notification_type": notification.notification_type,
        "watchlist_item_id": notification.watchlist_item_id,
        "title": notification.title,
        "message": notification.message,
        "action_url": notification.action_url,
        "payload": notification.payload,
        "is_read": notification.is_read,
        "created_at": notification.created_at,
        "read_at": notification.read_at,
    }


def _settings_response(settings: Any | None) -> dict[str, Any]:
    return {
        "email_enabled": settings.email_enabled if settings is not None else True,
        "timezone": settings.timezone if settings is not None else "UTC",
        "quiet_hours_start": (
            settings.quiet_hours_start if settings is not None else None
        ),
        "quiet_hours_end": settings.quiet_hours_end if settings is not None else None,
    }
