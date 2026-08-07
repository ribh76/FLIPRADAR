from decimal import Decimal
from types import SimpleNamespace

from flipradar.worker import celery_app as worker_app
from flipradar.worker import health, inspection, tasks


class FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.expirations: list[tuple[str, int]] = []

    def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expirations.append((key, seconds))

    def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        if nx and key in self.counts:
            return False
        self.counts[key] = 1
        self.expirations.append((key, ex))
        return True

    def delete(self, key: str) -> int:
        return int(self.counts.pop(key, None) is not None)

    def mget(self, keys: list[str]) -> list[str | None]:
        return [str(self.counts[key]) if key in self.counts else None for key in keys]


class FakeRetryTask:
    def __init__(self):
        self.kwargs = None

    def retry(self, **kwargs):
        self.kwargs = kwargs
        return "retried"


def _settings():
    return SimpleNamespace(redis_url="redis://test", watchlist_provider_hourly_limit=2)


def test_celery_configures_daily_watchlist_dispatch():
    schedule = worker_app.celery_app.conf.beat_schedule["refresh-watchlists-daily"]
    assert schedule["task"] == "flipradar.watchlist.dispatch_daily_refresh"
    assert schedule["schedule"] == 24 * 60 * 60
    assert tasks.refresh_provider_batch.max_retries is None
    digest = worker_app.celery_app.conf.beat_schedule[
        "deliver-watchlist-notification-digests-hourly"
    ]
    assert digest["task"] == "flipradar.notifications.deliver_email_digests"
    assert digest["schedule"] == 60 * 60


def test_provider_rate_limiter_allows_only_hourly_limit(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(
        tasks.redis.Redis, "from_url", lambda *args, **kwargs: fake_redis
    )
    monkeypatch.setattr(tasks, "get_settings", _settings)

    assert tasks._reserve_provider_refresh("ebay") is True
    assert tasks._reserve_provider_refresh("ebay") is True
    assert tasks._reserve_provider_refresh("ebay") is False
    assert fake_redis.expirations[0][1] == 60 * 60


def test_job_lock_prevents_duplicate_concurrent_batches(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(
        tasks.redis.Redis, "from_url", lambda *args, **kwargs: fake_redis
    )
    monkeypatch.setattr(tasks, "get_settings", _settings)
    batch = {"10316-1": ["00000000-0000-0000-0000-000000000001"]}

    lock_key = tasks._acquire_job_lock("ebay", batch)
    assert lock_key
    assert tasks._acquire_job_lock("ebay", batch) == ""
    tasks._release_job_lock(lock_key)
    assert tasks._acquire_job_lock("ebay", batch)


def test_failed_batches_retry_after_one_hour(monkeypatch):
    task = FakeRetryTask()
    monkeypatch.setattr(tasks, "record_job_metric", lambda *args: None)

    assert (
        tasks._retry_provider_batch(task, "ebay", {"10316-1": []}, RuntimeError())
        == "retried"
    )
    assert task.kwargs["countdown"] == 60 * 60
    assert task.kwargs["args"] == ["ebay", {"10316-1": []}]


def test_guardrails_identify_material_target_and_expiration_changes():
    previous = SimpleNamespace(
        listing_price=Decimal("100"),
        target_price=Decimal("90"),
        listing_status="active",
    )
    current = SimpleNamespace(
        listing_price=Decimal("80"), target_price=Decimal("75"), listing_status="ended"
    )

    assert tasks._guardrail_events(
        previous,
        current,
        material_price_change_percent=Decimal("10"),
        monitor_listing_expiration=True,
    ) == ["material_price_change", "target_price_change", "listing_expiration"]


def test_job_health_metrics_aggregate_recent_worker_events(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(
        health.redis.Redis, "from_url", lambda *args, **kwargs: fake_redis
    )
    monkeypatch.setattr(health, "get_settings", _settings)

    health.record_job_metric("attempted", "ebay")
    health.record_job_metric("completed", "ebay")

    metrics = health.get_job_health_metrics("ebay", hours=1)
    assert metrics["attempted"] == 1
    assert metrics["completed"] == 1
    assert metrics["failed"] == 0


def test_worker_inspection_returns_read_only_celery_state(monkeypatch):
    inspector = SimpleNamespace(
        active=lambda: {"worker": []},
        reserved=lambda: {"worker": []},
        scheduled=lambda: {"worker": []},
        stats=lambda: {"worker": {"pid": 1}},
    )
    monkeypatch.setattr(inspection.celery_app.control, "inspect", lambda: inspector)

    result = inspection.inspect_watchlist_workers()
    assert result["available"] is True
    assert result["stats"]["worker"]["pid"] == 1
