"""Scheduled, provider-batched watchlist monitoring tasks."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

import redis

from flipradar.core.settings import get_settings
from flipradar.database import repositories
from flipradar.database.session import SessionLocal
from flipradar.services import marketplace_service, watchlist_service
from flipradar.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


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
            return False
        return True
    except redis.RedisError:
        logger.exception(
            "watchlist refresh rate limiter unavailable provider=%s", provider
        )
        return False


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
    batches: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for item in entries:
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


@celery_app.task(name="flipradar.watchlist.refresh_provider_batch")
def refresh_provider_batch(
    provider: str, set_users: dict[str, list[str]]
) -> dict[str, int]:
    return asyncio.run(_refresh_provider_batch(provider, set_users))


async def _refresh_provider_batch(
    provider: str, set_users: dict[str, list[str]]
) -> dict[str, int]:
    logger.info(
        "watchlist refresh batch started provider=%s set_count=%s",
        provider,
        len(set_users),
    )
    successful_sets = 0
    affected_users: set[UUID] = set()
    async with SessionLocal() as db:
        for set_number, user_ids in set_users.items():
            logger.info(
                "watchlist refresh attempt provider=%s set_number=%s",
                provider,
                set_number,
            )
            if not _reserve_provider_refresh(provider):
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
            except Exception:
                logger.exception(
                    "watchlist refresh failed provider=%s set_number=%s",
                    provider,
                    set_number,
                )
        for user_id in affected_users:
            await watchlist_service.capture_watchlist_intelligence(db, user_id)
        await db.commit()
    logger.info(
        "watchlist refresh batch finished provider=%s successful_sets=%s affected_users=%s",
        provider,
        successful_sets,
        len(affected_users),
    )
    return {"successful_sets": successful_sets, "affected_users": len(affected_users)}
