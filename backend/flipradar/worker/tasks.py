"""Scheduled, provider-batched watchlist monitoring tasks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import redis

from flipradar.core.settings import get_settings
from flipradar.database import repositories
from flipradar.database.session import SessionLocal
from flipradar.services import (
    marketplace_service,
    notification_service,
    watchlist_service,
)
from flipradar.worker.celery_app import celery_app
from flipradar.worker.health import record_job_metric

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 60 * 60
JOB_LOCK_TTL_SECONDS = 24 * 60 * 60
EXPIRED_LISTING_STATUSES = {"ended", "removed", "sold"}


def _reserve_provider_refresh(provider: str) -> bool:
    """Allow a bounded number of provider refreshes in each rolling hour."""
    settings = get_settings()
    bucket = datetime.now(UTC).strftime("%Y%m%d%H")
    key = f"flipradar:watchlist-refresh:{provider}:{bucket}"
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        current = int(client.incr(key))
        if current == 1:
            client.expire(key, 60 * 60)
        if current > settings.watchlist_provider_hourly_limit:
            logger.warning(
                "watchlist refresh rate limited provider=%s count=%s limit=%s",
                provider,
                current,
                settings.watchlist_provider_hourly_limit,
            )
            record_job_metric("rate_limited", provider)
            return False
        return True
    except redis.RedisError:
        logger.exception(
            "watchlist refresh rate limiter unavailable provider=%s", provider
        )
        return False


def _job_lock_key(provider: str, set_users: dict[str, list[str]]) -> str:
    payload = json.dumps(
        {
            set_number: sorted(user_ids)
            for set_number, user_ids in sorted(set_users.items())
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"flipradar:watchlist-job-lock:{provider}:{digest}"


def _acquire_job_lock(provider: str, set_users: dict[str, list[str]]) -> str | None:
    """Atomically reserve a provider batch so duplicate Celery delivery is harmless."""
    key = _job_lock_key(provider, set_users)
    try:
        client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        acquired = client.set(key, "1", nx=True, ex=JOB_LOCK_TTL_SECONDS)
    except redis.RedisError:
        logger.exception("watchlist job lock unavailable provider=%s", provider)
        return None
    return key if acquired else ""


def _release_job_lock(key: str) -> None:
    try:
        redis.Redis.from_url(get_settings().redis_url, decode_responses=True).delete(
            key
        )
    except redis.RedisError:
        logger.exception("watchlist job lock release failed key=%s", key)


def _retry_provider_batch(
    task: Any,
    provider: str,
    failed_set_users: dict[str, list[str]],
    exc: Exception,
) -> Any:
    record_job_metric("retried", provider)
    logger.warning(
        "watchlist refresh batch retry scheduled provider=%s failed_sets=%s delay_seconds=%s",
        provider,
        len(failed_set_users),
        RETRY_DELAY_SECONDS,
    )
    return task.retry(
        exc=exc,
        args=[provider, failed_set_users],
        countdown=RETRY_DELAY_SECONDS,
    )


@celery_app.task(name="flipradar.watchlist.dispatch_daily_refresh")
def dispatch_daily_refresh() -> dict[str, int]:
    """Batch current watchlist entries by marketplace before scheduling work."""
    return asyncio.run(_dispatch_daily_refresh())


async def _dispatch_daily_refresh() -> dict[str, int]:
    if not get_settings().watchlist_worker_enabled:
        logger.info("watchlist refresh dispatcher skipped reason=worker_disabled")
        return {}
    async with SessionLocal() as db:
        entries = await repositories.list_watchlist_items_for_background_refresh(db)
        preferences = await repositories.list_watchlist_monitoring_preferences(db)
    batches: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for item in entries:
        preference = preferences.get(item.user_id)
        if preference is not None and not preference.is_enabled:
            continue
        lego_set = item.lego_set or (item.listing.lego_set if item.listing else None)
        if lego_set is None:
            continue
        provider = item.listing.marketplace.name if item.listing else "catalog"
        batches[provider][lego_set.set_number].add(str(item.user_id))
    for provider, set_users in batches.items():
        refresh_provider_batch.delay(
            provider,
            {
                set_number: sorted(user_ids)
                for set_number, user_ids in set_users.items()
            },
        )
        logger.info(
            "watchlist refresh job queued provider=%s set_count=%s",
            provider,
            len(set_users),
        )
    return {provider: len(set_users) for provider, set_users in batches.items()}


@celery_app.task(name="flipradar.notifications.deliver_email_digests")
def deliver_notification_email_digests() -> dict[str, int]:
    """Send each opted-in user at most one digest of pending watchlist changes."""
    return asyncio.run(_deliver_notification_email_digests())


async def _deliver_notification_email_digests() -> dict[str, int]:
    async with SessionLocal() as db:
        result = await notification_service.deliver_pending_email_digests(db)
        await db.commit()
    logger.info(
        "watchlist notification digests complete users=%s pending=%s delivered=%s",
        result["users"],
        result["pending"],
        result["delivered"],
    )
    return result


@celery_app.task(
    name="flipradar.watchlist.refresh_provider_batch", bind=True, max_retries=None
)
def refresh_provider_batch(
    self: Any, provider: str, set_users: dict[str, list[str]]
) -> dict[str, Any]:
    lock_key = _acquire_job_lock(provider, set_users)
    if lock_key is None:
        record_job_metric("failed", provider)
        raise _retry_provider_batch(
            self,
            provider,
            set_users,
            RuntimeError("watchlist job lock is unavailable"),
        )
    if not lock_key:
        logger.info(
            "watchlist refresh batch skipped reason=duplicate provider=%s", provider
        )
        record_job_metric("duplicate_skipped", provider)
        return {"successful_sets": 0, "affected_users": 0, "duplicate": True}
    try:
        result = asyncio.run(_refresh_provider_batch(provider, set_users))
    except Exception as exc:
        record_job_metric("failed", provider)
        raise _retry_provider_batch(self, provider, set_users, exc) from exc
    finally:
        _release_job_lock(lock_key)
    if result["failed_set_users"]:
        raise _retry_provider_batch(
            self,
            provider,
            result["failed_set_users"],
            RuntimeError("one or more watchlist refreshes failed"),
        )
    return {
        "successful_sets": result["successful_sets"],
        "affected_users": result["affected_users"],
    }


async def _refresh_provider_batch(
    provider: str, set_users: dict[str, list[str]]
) -> dict[str, Any]:
    logger.info(
        "watchlist refresh batch started provider=%s set_count=%s",
        provider,
        len(set_users),
    )
    successful_sets = 0
    affected_users: set[UUID] = set()
    failed_set_users: dict[str, list[str]] = {}
    async with SessionLocal() as db:
        for set_number, user_ids in set_users.items():
            logger.info(
                "watchlist refresh attempt provider=%s set_number=%s",
                provider,
                set_number,
            )
            record_job_metric("attempted", provider)
            if not _reserve_provider_refresh(provider):
                failed_set_users[set_number] = user_ids
                continue
            try:
                await marketplace_service.refresh_marketplace_data(
                    set_number, force=True, db=db
                )
                successful_sets += 1
                affected_users.update(UUID(user_id) for user_id in user_ids)
                logger.info(
                    "watchlist refresh complete provider=%s set_number=%s",
                    provider,
                    set_number,
                )
                record_job_metric("completed", provider)
            except Exception:
                failed_set_users[set_number] = user_ids
                record_job_metric("failed", provider)
                logger.exception(
                    "watchlist refresh failed provider=%s set_number=%s",
                    provider,
                    set_number,
                )
        for user_id in affected_users:
            await watchlist_service.capture_watchlist_intelligence(db, user_id)
            await _log_watchlist_guardrails(db, user_id)
        await db.commit()
    logger.info(
        "watchlist refresh batch finished provider=%s successful_sets=%s affected_users=%s",
        provider,
        successful_sets,
        len(affected_users),
    )
    return {
        "successful_sets": successful_sets,
        "affected_users": len(affected_users),
        "failed_set_users": failed_set_users,
    }


def _guardrail_events(
    previous: Any,
    current: Any,
    *,
    material_price_change_percent: Decimal,
    monitor_listing_expiration: bool,
) -> list[str]:
    """Return guardrail identifiers for consecutive persisted price observations."""
    events: list[str] = []
    if previous.listing_price and current.listing_price is not None:
        percent_change = (
            abs(current.listing_price - previous.listing_price)
            / previous.listing_price
            * Decimal("100")
        )
        if percent_change >= material_price_change_percent:
            events.append("material_price_change")
    if previous.target_price != current.target_price:
        events.append("target_price_change")
    if (
        monitor_listing_expiration
        and previous.listing_status not in EXPIRED_LISTING_STATUSES
        and current.listing_status in EXPIRED_LISTING_STATUSES
    ):
        events.append("listing_expiration")
    return events


async def _log_watchlist_guardrails(db: Any, user_id: UUID) -> None:
    preferences = await repositories.list_watchlist_monitoring_preferences(db)
    preference = preferences.get(user_id)
    if preference is not None and not preference.is_enabled:
        return
    threshold = (
        preference.material_price_change_percent
        if preference is not None
        else Decimal("10")
    )
    monitor_expiration = (
        preference.monitor_listing_expiration if preference is not None else True
    )
    items = await repositories.list_watchlist_items_for_user(db, user_id)
    histories = await repositories.list_watchlist_price_history(
        db, [item.id for item in items]
    )
    per_item: dict[UUID, list[Any]] = defaultdict(list)
    for history in histories:
        per_item[history.watchlist_item_id].append(history)
    items_by_id = {item.id: item for item in items}
    for item_id, observations in per_item.items():
        if len(observations) < 2:
            continue
        events = _guardrail_events(
            observations[1],
            observations[0],
            material_price_change_percent=threshold,
            monitor_listing_expiration=monitor_expiration,
        )
        for event in events:
            logger.warning(
                "watchlist guardrail detected event=%s user_id=%s watchlist_item_id=%s",
                event,
                user_id,
                item_id,
            )
        created = await notification_service.emit_watchlist_notifications(
            db,
            user_id=user_id,
            item=items_by_id[item_id],
            previous=observations[1],
            current=observations[0],
            material_price_change_percent=threshold,
        )
        if created:
            logger.info(
                "watchlist notifications created user_id=%s watchlist_item_id=%s count=%s",
                user_id,
                item_id,
                len(created),
            )
