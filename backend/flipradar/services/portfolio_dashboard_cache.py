"""Small, bounded single-flight cache for expensive portfolio dashboard reads."""

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import TypeVar


T = TypeVar("T")
_TTL = timedelta(seconds=5)
_MAX_ENTRIES = 256
_cache: dict[tuple, tuple[datetime, object]] = {}
_locks: dict[tuple, asyncio.Lock] = {}


async def get_or_load(key: tuple, loader: Callable[[], Awaitable[T]]) -> T:
    """Coalesce identical in-flight reads and keep a very short result cache."""
    now = datetime.now(UTC)
    cached = _cache.get(key)
    if cached and cached[0] > now:
        return deepcopy(cached[1])  # type: ignore[return-value]

    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        now = datetime.now(UTC)
        cached = _cache.get(key)
        if cached and cached[0] > now:
            return deepcopy(cached[1])  # type: ignore[return-value]
        result = await loader()
        if len(_cache) >= _MAX_ENTRIES:
            expired = [cache_key for cache_key, value in _cache.items() if value[0] <= now]
            for cache_key in expired or [next(iter(_cache))]:
                _cache.pop(cache_key, None)
                _locks.pop(cache_key, None)
        _cache[key] = (now + _TTL, deepcopy(result))
        return result


def invalidate_user(user_id: object) -> None:
    """Ensure mutations are immediately visible without waiting for the TTL."""
    for key in [key for key in _cache if key and key[0] == user_id]:
        _cache.pop(key, None)
        _locks.pop(key, None)


def clear() -> None:
    """Test helper for isolating cache behavior."""
    _cache.clear()
    _locks.clear()
