from types import SimpleNamespace

from flipradar.worker import celery_app as worker_app
from flipradar.worker import tasks


class FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.expirations: list[tuple[str, int]] = []

    def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expirations.append((key, seconds))


def test_celery_configures_daily_watchlist_dispatch():
    schedule = worker_app.celery_app.conf.beat_schedule["refresh-watchlists-daily"]
    assert schedule["task"] == "flipradar.watchlist.dispatch_daily_refresh"
    assert schedule["schedule"] == 24 * 60 * 60


def test_provider_rate_limiter_allows_only_hourly_limit(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(
        tasks.redis.Redis,
        "from_url",
        lambda *args, **kwargs: fake_redis,
    )
    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: SimpleNamespace(
            redis_url="redis://test", watchlist_provider_hourly_limit=2
        ),
    )

    assert tasks._reserve_provider_refresh("ebay") is True
    assert tasks._reserve_provider_refresh("ebay") is True
    assert tasks._reserve_provider_refresh("ebay") is False
    assert fake_redis.expirations[0][1] == 60 * 60
