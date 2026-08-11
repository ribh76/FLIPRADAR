import logging
from typing import Any

logger = logging.getLogger(__name__)
_monitoring_enabled = False


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
            scope.set_context("request", context)
        sentry_sdk.capture_exception(exc)
