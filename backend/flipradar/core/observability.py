import logging
import re
from collections import deque
from time import monotonic
from typing import Any

logger = logging.getLogger(__name__)
_monitoring_enabled = False
_error_events: deque[tuple[float, bool]] = deque()
_error_rate_alert_active = False
_error_rate_threshold_percent = 5.0
_error_rate_minimum_requests = 20
_error_rate_window_seconds = 300

_SENSITIVE_KEY_PATTERN = re.compile(
    r"password|passwd|secret|token|authorization|api[_-]?key|dsn|email|username|user",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_PATTERNS = (
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*([:=])\s*[^\s,;]+"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)bearer\s+[^\s,;]+"), "Bearer [REDACTED]"),
    (re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE), "[REDACTED_EMAIL]"),
    (re.compile(r"(?i)demo(?:pass\d*!|@flipradar\.com)"), "[REDACTED_DEMO_CREDENTIAL]"),
)


def sanitize_telemetry(value: Any, *, key: str | None = None) -> Any:
    """Remove credentials and account identifiers before telemetry leaves the app."""
    if key and _SENSITIVE_KEY_PATTERN.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): sanitize_telemetry(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list | tuple):
        return [sanitize_telemetry(item) for item in value]
    if not isinstance(value, str):
        return value
    sanitized = value
    for pattern, replacement in _SENSITIVE_VALUE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def record_metric(
    name: str,
    value: int | float = 1,
    *,
    unit: str = "count",
    tags: dict[str, str] | None = None,
) -> None:
    """Emit a structured metric event that can be aggregated by log monitoring."""
    logger.info(
        "metric recorded name=%s value=%s unit=%s", name, value, unit,
        extra={
            "metric": {
                "name": name,
                "value": value,
                "unit": unit,
                "tags": sanitize_telemetry(tags or {}),
            }
        },
    )


def configure_error_rate_alerting(
    *, threshold_percent: float, minimum_requests: int, window_seconds: int
) -> None:
    global _error_rate_threshold_percent
    global _error_rate_minimum_requests
    global _error_rate_window_seconds
    _error_rate_threshold_percent = threshold_percent
    _error_rate_minimum_requests = minimum_requests
    _error_rate_window_seconds = window_seconds


def record_http_outcome(status_code: int) -> None:
    """Emit a threshold-crossing alert for elevated server-error rates."""
    global _error_rate_alert_active
    now = monotonic()
    _error_events.append((now, status_code >= 500))
    cutoff = now - _error_rate_window_seconds
    while _error_events and _error_events[0][0] < cutoff:
        _error_events.popleft()
    request_count = len(_error_events)
    error_count = sum(is_error for _, is_error in _error_events)
    error_rate_percent = 100 * error_count / request_count if request_count else 0
    record_metric(
        "http.request", tags={"outcome": "server_error" if status_code >= 500 else "success"}
    )
    if (
        request_count >= _error_rate_minimum_requests
        and error_rate_percent >= _error_rate_threshold_percent
    ):
        if not _error_rate_alert_active:
            _error_rate_alert_active = True
            _emit_alert(
                "http_error_rate",
                severity="critical",
                tags={
                    "error_rate_percent": f"{error_rate_percent:.2f}",
                    "request_count": str(request_count),
                },
            )
    else:
        _error_rate_alert_active = False


def record_operational_failure(stage: str, error: BaseException) -> None:
    """Emit deploy/migration failure telemetry without exposing exception details."""
    alert_name = "migration_failure" if stage == "migration" else "deployment_failure"
    _emit_alert(alert_name, severity="critical", tags={"stage": stage})
    capture_exception(error, context={"operation_stage": stage})


def _emit_alert(name: str, *, severity: str, tags: dict[str, str]) -> None:
    record_metric("alert.triggered", tags={"alert": name, "severity": severity, **tags})
    logger.error("operational alert triggered alert=%s severity=%s", name, severity)


def configure_exception_monitoring(
    *, dsn: str | None, environment: str, release: str
) -> None:
    """Configure Sentry when a DSN is supplied; local development stays offline."""
    global _monitoring_enabled
    _monitoring_enabled = False
    if not dsn:
        logger.info("exception monitoring disabled reason=no_dsn")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
    except ImportError:
        logger.warning("exception monitoring disabled reason=sdk_not_installed")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
        before_send=lambda event, _: sanitize_telemetry(event),
    )
    _monitoring_enabled = True
    logger.info("exception monitoring configured")


def capture_exception(
    exc: BaseException,
    *,
    request_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Send an unexpected backend exception to Sentry when it is configured."""
    if not _monitoring_enabled:
        return

    try:
        import sentry_sdk
    except ImportError:
        return

    with sentry_sdk.push_scope() as scope:
        if request_id:
            scope.set_tag("request_id", request_id)
        if context:
            scope.set_context("request", sanitize_telemetry(context))
        sentry_sdk.capture_exception(exc)
