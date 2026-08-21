import hashlib
import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4

import redis.asyncio as redis
from fastapi import Request
from redis.exceptions import RedisError
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware

from flipradar.api.error_handlers import error_response
from flipradar.core.logging import request_id_context
from flipradar.core.observability import record_http_outcome
from flipradar.core.settings import AppEnvironment

logger = logging.getLogger(__name__)

_RESERVE_RATE_LIMIT = """
local current = redis.call('GET', KEYS[1])
if current and tonumber(current) >= tonumber(ARGV[1]) then
    return {0, redis.call('TTL', KEYS[1])}
end
current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return {1, redis.call('TTL', KEYS[1])}
"""


class RateLimitScope(StrEnum):
    CLIENT = "client"
    CREDENTIAL = "credential"
    GLOBAL = "global"


@dataclass(frozen=True)
class RateLimitPolicy:
    """A fixed-window policy applied before endpoint work starts."""

    name: str
    max_requests: int
    window_seconds: int
    scope: RateLimitScope = RateLimitScope.CLIENT
    requires_llm: bool = False


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class _ProcessLocalFixedWindowLimiter:
    """Small availability fallback; Redis is the production source of truth."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def reserve(self, key: str, policy: RateLimitPolicy) -> RateLimitResult:
        now = time.time()
        hits = self._hits[key]
        cutoff = now - policy.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= policy.max_requests:
            return RateLimitResult(
                allowed=False,
                retry_after_seconds=max(
                    1, int(policy.window_seconds - (now - hits[0]))
                ),
            )
        hits.append(now)
        return RateLimitResult(allowed=True, retry_after_seconds=0)


class RedisRateLimiter:
    """Atomic, shared fixed-window quotas with a bounded local fallback."""

    def __init__(
        self,
        redis_url: str,
        *,
        environment: AppEnvironment,
        namespace: str = "flipradar:rate-limit",
    ) -> None:
        self._client = (
            redis.Redis.from_url(
                redis_url,
                decode_responses=False,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
            if environment is not AppEnvironment.TEST
            else None
        )
        self._environment = environment
        self._namespace = namespace
        self._fallback = _ProcessLocalFixedWindowLimiter()
        self._unavailable_until = 0.0

    async def reserve(self, policy: RateLimitPolicy, identity: str) -> RateLimitResult:
        key = self._key(policy, identity)
        if self._client is not None and time.monotonic() >= self._unavailable_until:
            try:
                raw = await self._client.eval(
                    _RESERVE_RATE_LIMIT,
                    1,
                    key,
                    policy.max_requests,
                    policy.window_seconds,
                )
                allowed, ttl = int(raw[0]), int(raw[1])
                return RateLimitResult(
                    allowed=bool(allowed),
                    retry_after_seconds=max(1, ttl) if not allowed else 0,
                )
            except (RedisError, OSError, TimeoutError) as exc:
                self._unavailable_until = time.monotonic() + 30
                logger.error(
                    "rate limit Redis unavailable policy=%s error_type=%s",
                    policy.name,
                    type(exc).__name__,
                )
                # Keep a bounded process-local fallback for availability. It is
                # deliberately only a fallback: healthy deployments share Redis
                # counters across every API process.
        return self._fallback.reserve(key, policy)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    def _key(self, policy: RateLimitPolicy, identity: str) -> str:
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"{self._namespace}:{policy.name}:{digest}"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        request_id_token = request_id_context.set(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            record_http_outcome(response.status_code)
            logger.info(
                "request completed method=%s path=%s status_code=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - started_at) * 1000,
            )
            return response
        finally:
            request_id_context.reset(request_id_token)


class EndpointRateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed default and endpoint-specific protection for public routes."""

    _EXEMPT_PATHS = frozenset(
        {
            "/health",
            "/health/live",
            "/health/ready",
            "/db-health",
            "/docs",
            "/openapi.json",
        }
    )
    _DEFAULT_POLICY = RateLimitPolicy("api-client", 5000, 24 * 60 * 60)

    # Auth limits intentionally remain independent so a login burst cannot
    # consume password-reset or verification capacity for the same client.
    _EXACT_POLICIES: dict[tuple[str, str], tuple[RateLimitPolicy, ...]] = {
        ("POST", "/auth/register"): (RateLimitPolicy("auth-register", 5, 3600),),
        ("POST", "/auth/login"): (RateLimitPolicy("auth-login", 10, 15 * 60),),
        ("POST", "/auth/mfa/verify"): (
            RateLimitPolicy("auth-mfa-verify", 10, 10 * 60),
        ),
        ("POST", "/auth/mfa/reset/request"): (
            RateLimitPolicy("auth-mfa-reset-request", 3, 3600),
        ),
        ("POST", "/auth/mfa/reset/confirm"): (
            RateLimitPolicy("auth-mfa-reset-confirm", 5, 15 * 60),
        ),
        ("POST", "/auth/verify-email"): (
            RateLimitPolicy("auth-email-verify", 10, 15 * 60),
        ),
        ("POST", "/auth/email-change/confirm"): (
            RateLimitPolicy("auth-email-change-confirm", 5, 15 * 60),
        ),
        ("POST", "/auth/resend-verification"): (
            RateLimitPolicy(
                "auth-resend-verification", 3, 3600, RateLimitScope.CREDENTIAL
            ),
        ),
        ("POST", "/auth/password-reset/request"): (
            RateLimitPolicy("auth-password-reset-request", 3, 3600),
        ),
        ("POST", "/auth/password-reset/confirm"): (
            RateLimitPolicy("auth-password-reset-confirm", 5, 15 * 60),
        ),
        ("POST", "/auth/refresh"): (
            RateLimitPolicy("auth-refresh", 30, 15 * 60, RateLimitScope.CREDENTIAL),
        ),
        ("PUT", "/users/me/mfa"): (
            RateLimitPolicy(
                "account-mfa-settings", 5, 15 * 60, RateLimitScope.CREDENTIAL
            ),
        ),
        ("POST", "/users/me/password"): (
            RateLimitPolicy(
                "account-password-change", 5, 15 * 60, RateLimitScope.CREDENTIAL
            ),
        ),
        ("POST", "/users/me/deletion-request"): (
            RateLimitPolicy("account-deletion", 3, 3600, RateLimitScope.CREDENTIAL),
        ),
        ("POST", "/users/me/email-change/request"): (
            RateLimitPolicy("account-email-change", 3, 3600, RateLimitScope.CREDENTIAL),
        ),
        ("POST", "/listing-evaluations"): (
            RateLimitPolicy("listing-evaluation", 10, 15 * 60),
        ),
        ("POST", "/analyze"): (
            RateLimitPolicy("recommendation-analysis", 20, 10 * 60),
            RateLimitPolicy(
                "llm-global", 100, 60, RateLimitScope.GLOBAL, requires_llm=True
            ),
        ),
        ("POST", "/portfolio/analyze"): (
            RateLimitPolicy(
                "portfolio-analysis", 5, 10 * 60, RateLimitScope.CREDENTIAL
            ),
            RateLimitPolicy(
                "llm-global", 100, 60, RateLimitScope.GLOBAL, requires_llm=True
            ),
        ),
        ("POST", "/portfolio/analytics/refresh"): (
            RateLimitPolicy(
                "portfolio-analytics-refresh", 5, 15 * 60, RateLimitScope.CREDENTIAL
            ),
        ),
        ("POST", "/portfolio/import/preview"): (
            RateLimitPolicy(
                "portfolio-import-preview", 5, 3600, RateLimitScope.CREDENTIAL
            ),
        ),
        ("POST", "/portfolio/import"): (
            RateLimitPolicy("portfolio-import", 5, 3600, RateLimitScope.CREDENTIAL),
        ),
        ("POST", "/watchlist/refresh"): (
            RateLimitPolicy("watchlist-refresh", 5, 15 * 60, RateLimitScope.CREDENTIAL),
        ),
    }

    def __init__(self, app, *, limiter: RedisRateLimiter) -> None:
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path in self._EXEMPT_PATHS:
            return await call_next(request)

        policies = [self._DEFAULT_POLICY, *self._policies_for(request)]
        for policy in policies:
            if policy.requires_llm and not request.app.state.settings.llm.configured:
                continue
            result = await self._limiter.reserve(
                policy, self._identity(request, policy)
            )
            if not result.allowed:
                logger.warning(
                    "request rate limited policy=%s path=%s",
                    policy.name,
                    request.url.path,
                )
                return error_response(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    code="rate_limit_exceeded",
                    message="Request limit exceeded",
                    details={
                        "limit": policy.max_requests,
                        "window_seconds": policy.window_seconds,
                    },
                    request=request,
                    headers={
                        "Retry-After": str(result.retry_after_seconds),
                        "X-RateLimit-Limit": str(policy.max_requests),
                    },
                )
        return await call_next(request)

    def _policies_for(self, request: Request) -> tuple[RateLimitPolicy, ...]:
        exact = self._EXACT_POLICIES.get((request.method, request.url.path))
        if exact:
            return exact
        path = request.url.path
        if request.method == "GET" and path in {"/sets/search", "/parts/search"}:
            return (RateLimitPolicy("catalog-provider-search", 60, 10 * 60),)
        if request.method == "GET" and path.startswith(("/set/", "/sets/")):
            return (RateLimitPolicy("set-detail", 60, 10 * 60),)
        if (
            request.method == "POST"
            and path.startswith("/listings/")
            and path.endswith("/analysis")
        ):
            return (RateLimitPolicy("listing-analysis", 30, 10 * 60),)
        if (
            request.method == "POST"
            and path.startswith("/saved-searches/")
            and path.endswith("/run")
        ):
            return (
                RateLimitPolicy(
                    "saved-search-run", 10, 10 * 60, RateLimitScope.CREDENTIAL
                ),
            )
        if (
            request.method == "GET"
            and path == "/deals"
            and request.query_params.get("refresh") == "true"
        ):
            return (RateLimitPolicy("deal-provider-refresh", 5, 15 * 60),)
        if request.method == "POST" and path.startswith("/marketplace/update/"):
            return (
                RateLimitPolicy("marketplace-refresh", 10, 3600, RateLimitScope.GLOBAL),
            )
        return ()

    @staticmethod
    def _identity(request: Request, policy: RateLimitPolicy) -> str:
        if policy.scope is RateLimitScope.GLOBAL:
            return "global"
        if policy.scope is RateLimitScope.CREDENTIAL:
            authorization = request.headers.get("Authorization", "")
            if authorization.lower().startswith("bearer ") and len(authorization) > 7:
                # A hash avoids retaining credentials in Redis while grouping a
                # legitimate authenticated session independently of its IP.
                return f"credential:{hashlib.sha256(authorization[7:].encode()).hexdigest()}"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"client:{forwarded_for.split(',', 1)[0].strip()}"
        if request.client is not None:
            return f"client:{request.client.host}"
        return "client:unknown"


# Compatibility name retained for callers that used the original middleware.
RollingWindowRateLimitMiddleware = EndpointRateLimitMiddleware
