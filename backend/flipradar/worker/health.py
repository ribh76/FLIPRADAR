"""Redis-backed, low-cost operational metrics for watchlist worker jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Final

import redis

from flipradar.core.settings import get_settings

logger = logging.getLogger(__name__)

METRIC_EVENTS: Final = (
    "attempted",
    "completed",
    "failed",
    "retried",
    "duplicate_skipped",
    "rate_limited",
)
METRIC_TTL_SECONDS: Final = 48 * 60 * 60


def _metric_key(event: str, provider: str, bucket: str) -> str:
    return f"flipradar:watchlist-job-metric:{bucket}:{provider}:{event}"


def record_job_metric(event: str, provider: str) -> None:
    """Increment an hourly metric without making worker execution depend on Redis."""
    if event not in METRIC_EVENTS:
        raise ValueError(f"Unknown watchlist job metric: {event}")
    bucket = datetime.now(UTC).strftime("%Y%m%d%H")
    try:
        client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        key = _metric_key(event, provider, bucket)
        value = client.incr(key)
        if value == 1:
            client.expire(key, METRIC_TTL_SECONDS)
    except redis.RedisError:
        logger.exception(
            "watchlist job metric unavailable event=%s provider=%s", event, provider
        )


def get_job_health_metrics(provider: str, *, hours: int = 24) -> dict[str, int]:
    """Return recent aggregate health counters for a provider's watchlist jobs."""
    if hours < 1:
        raise ValueError("hours must be at least one")
    now = datetime.now(UTC)
    buckets = [
        (now.replace(minute=0, second=0, microsecond=0)).timestamp() - 3600 * offset
        for offset in range(hours)
    ]
    keys = [
        _metric_key(
            event, provider, datetime.fromtimestamp(bucket, UTC).strftime("%Y%m%d%H")
        )
        for event in METRIC_EVENTS
        for bucket in buckets
    ]
    totals: dict[str, int] = dict.fromkeys(METRIC_EVENTS, 0)
    try:
        client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        values = client.mget(keys)
    except redis.RedisError:
        logger.exception("watchlist job health unavailable provider=%s", provider)
        return totals
    for index, value in enumerate(values):
        if value is not None:
            totals[METRIC_EVENTS[index // hours]] += int(value)
    return totals
