import time
from collections import defaultdict, deque
from collections.abc import Callable
from uuid import uuid4

from fastapi import Request
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware

from flipradar.api.error_handlers import error_response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RollingWindowRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        max_requests: int = 5000,
        window_seconds: int = 86400,
        exempt_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths or {
            "/health",
            "/health/live",
            "/health/ready",
            "/db-health",
            "/docs",
            "/openapi.json",
        }
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        key = self._client_key(request)
        now = time.time()
        hits = self._hits[key]
        cutoff = now - self.window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()

        if len(hits) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - hits[0])))
            return error_response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="rate_limit_exceeded",
                message="Request limit exceeded",
                details={
                    "limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                },
                request=request,
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)

    def _client_key(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        if request.client is not None:
            return request.client.host
        return "unknown"
