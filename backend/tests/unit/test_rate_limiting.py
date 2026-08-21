from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from flipradar.api.middleware import (
    EndpointRateLimitMiddleware,
    RateLimitPolicy,
    RateLimitScope,
    RedisRateLimiter,
    RequestContextMiddleware,
    TrustedProxyClientIpResolver,
)
from flipradar.core.settings import AppEnvironment, Settings


class FakeRedis:
    def __init__(self) -> None:
        self.now = 0
        self.values: dict[str, tuple[int, int]] = {}
        self.closed = False

    async def eval(self, _script, _keys, key, limit, window):
        count, expires_at = self.values.get(key, (0, 0))
        if expires_at <= self.now:
            count, expires_at = 0, self.now + int(window)
        if count >= int(limit):
            return [0, max(1, expires_at - self.now)]
        self.values[key] = (count + 1, expires_at)
        return [1, max(1, expires_at - self.now)]

    def advance(self, seconds: int) -> None:
        self.now += seconds

    async def aclose(self) -> None:
        self.closed = True


def _redis_limiter(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[FakeRedis, RedisRateLimiter]:
    fake_redis = FakeRedis()
    monkeypatch.setattr(
        "flipradar.api.middleware.redis.Redis.from_url",
        lambda *_args, **_kwargs: fake_redis,
    )
    return fake_redis, RedisRateLimiter(
        "redis://test", environment=AppEnvironment.DEVELOPMENT
    )


@pytest.mark.asyncio
async def test_redis_rate_limiter_enforces_a_shared_limit_across_instances(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_redis, first_limiter = _redis_limiter(monkeypatch)
    second_limiter = RedisRateLimiter(
        "redis://test", environment=AppEnvironment.DEVELOPMENT
    )
    policy = RateLimitPolicy("test", 2, 60, RateLimitScope.CLIENT)

    assert (await first_limiter.reserve(policy, "client:one")).allowed is True
    assert (await second_limiter.reserve(policy, "client:one")).allowed is True
    denied = await first_limiter.reserve(policy, "client:one")

    assert denied.allowed is False
    assert denied.retry_after_seconds == 60
    await first_limiter.close()
    await second_limiter.close()
    assert fake_redis.closed is True


@pytest.mark.asyncio
async def test_redis_rate_limiter_allows_requests_after_window_expiration(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_redis, limiter = _redis_limiter(monkeypatch)
    policy = RateLimitPolicy("expires", 1, 60)

    assert (await limiter.reserve(policy, "client:one")).allowed is True
    assert (await limiter.reserve(policy, "client:one")).allowed is False
    fake_redis.advance(60)

    assert (await limiter.reserve(policy, "client:one")).allowed is True


def test_untrusted_direct_peer_cannot_spoof_client_identity_with_forwarded_for():
    resolver = TrustedProxyClientIpResolver(("10.0.0.0/8",))
    request = _request("198.51.100.50", "203.0.113.9")

    assert resolver.resolve(request) == "198.51.100.50"


def test_trusted_proxy_chain_uses_the_rightmost_non_proxy_client_address():
    resolver = TrustedProxyClientIpResolver(("10.0.0.0/8", "fd00::/8"))
    request = _request("10.0.0.8", "203.0.113.9, 198.51.100.50, fd00::7")

    assert resolver.resolve(request) == "198.51.100.50"


def test_malformed_forwarded_for_from_trusted_proxy_falls_back_to_peer_address():
    resolver = TrustedProxyClientIpResolver(("10.0.0.0/8",))
    request = _request("10.0.0.8", "not-an-address")

    assert resolver.resolve(request) == "10.0.0.8"


def test_trusted_proxy_cidrs_must_be_valid_networks():
    settings = Settings(trusted_proxy_cidrs="10.0.0.0/8, fd00::/8")

    assert settings.trusted_proxy_networks == ("10.0.0.0/8", "fd00::/8")
    with pytest.raises(ValueError, match="TRUSTED_PROXY_CIDRS"):
        Settings(trusted_proxy_cidrs="not-a-network")


def test_auth_login_has_a_strict_endpoint_limit_without_redis():
    app = _rate_limited_app()

    with TestClient(app) as client:
        for _ in range(10):
            assert client.post("/auth/login").status_code == 200
        limited = client.post("/auth/login")

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limit_exceeded"
    assert limited.headers["retry-after"]
    assert limited.headers["x-ratelimit-limit"] == "10"


def test_normal_user_activity_stays_below_auth_and_expensive_operation_limits():
    app = _rate_limited_app()
    normal_actions = (
        "/auth/register",
        "/auth/login",
        "/auth/password-reset/request",
        "/auth/verify-email",
        "/auth/mfa/verify",
        "/listing-evaluations",
        "/analyze",
        "/portfolio/analyze",
        "/portfolio/analytics/refresh",
        "/watchlist/refresh",
    )

    with TestClient(app) as client:
        for path in normal_actions:
            assert (
                client.post(
                    path, headers={"Authorization": "Bearer normal-user"}
                ).status_code
                == 200
            )


def _request(peer_address: str, forwarded_for: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/auth/login",
            "headers": [(b"x-forwarded-for", forwarded_for.encode())],
            "client": (peer_address, 443),
            "server": ("api.flipradar.example", 443),
        }
    )


def _rate_limited_app() -> FastAPI:
    app = FastAPI()
    app.state.settings = SimpleNamespace(llm=SimpleNamespace(configured=False))
    limiter = RedisRateLimiter("redis://test", environment=AppEnvironment.TEST)
    app.add_middleware(EndpointRateLimitMiddleware, limiter=limiter)
    app.add_middleware(RequestContextMiddleware)

    async def ok():
        return {"ok": True}

    for path in (
        "/auth/register",
        "/auth/login",
        "/auth/password-reset/request",
        "/auth/verify-email",
        "/auth/mfa/verify",
        "/listing-evaluations",
        "/analyze",
        "/portfolio/analyze",
        "/portfolio/analytics/refresh",
        "/watchlist/refresh",
    ):
        app.add_api_route(path, ok, methods=["POST"])
    return app
