from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flipradar.api.middleware import (
    EndpointRateLimitMiddleware,
    RateLimitPolicy,
    RateLimitScope,
    RedisRateLimiter,
    RequestContextMiddleware,
)
from flipradar.core.settings import AppEnvironment


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.closed = False

    async def eval(self, _script, _keys, key, limit, _window):
        current = self.values.get(key, 0)
        if current >= int(limit):
            return [0, 42]
        self.values[key] = current + 1
        return [1, 42]

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_redis_rate_limiter_enforces_shared_policy(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_redis = FakeRedis()
    monkeypatch.setattr(
        "flipradar.api.middleware.redis.Redis.from_url",
        lambda *_args, **_kwargs: fake_redis,
    )
    limiter = RedisRateLimiter("redis://test", environment=AppEnvironment.DEVELOPMENT)
    policy = RateLimitPolicy("test", 2, 60, RateLimitScope.CLIENT)

    assert (await limiter.reserve(policy, "client:one")).allowed is True
    assert (await limiter.reserve(policy, "client:one")).allowed is True
    denied = await limiter.reserve(policy, "client:one")

    assert denied.allowed is False
    assert denied.retry_after_seconds == 42
    await limiter.close()
    assert fake_redis.closed is True


def test_auth_login_has_a_strict_endpoint_limit_without_redis():
    app = FastAPI()
    app.state.settings = SimpleNamespace(llm=SimpleNamespace(configured=False))
    limiter = RedisRateLimiter("redis://test", environment=AppEnvironment.TEST)
    app.add_middleware(EndpointRateLimitMiddleware, limiter=limiter)
    app.add_middleware(RequestContextMiddleware)

    @app.post("/auth/login")
    async def login():
        return {"ok": True}

    with TestClient(app) as client:
        for _ in range(10):
            assert client.post("/auth/login").status_code == 200
        limited = client.post("/auth/login")

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limit_exceeded"
    assert limited.headers["retry-after"]
    assert limited.headers["x-ratelimit-limit"] == "10"
