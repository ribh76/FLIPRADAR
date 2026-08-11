from celery import Celery

from flipradar.core.logging import setup_logging
from flipradar.core.observability import configure_exception_monitoring
from flipradar.core.settings import get_settings

settings = get_settings()
setup_logging(
    settings.logging.level,
    sqlalchemy_level=settings.logging.sqlalchemy_level,
    uvicorn_access_level=settings.logging.uvicorn_access_level,
    environment=settings.application.environment.value,
    release=settings.observability.release,
)
configure_exception_monitoring(
    dsn=settings.observability.sentry_dsn,
    environment=settings.application.environment.value,
    release=settings.observability.release,
)
celery_app = Celery(
    "flipradar",
    broker=settings.resolved_celery_broker_url,
    backend=settings.resolved_celery_result_backend,
    include=["flipradar.worker.tasks"],
)
celery_app.conf.update(
    timezone="UTC",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    beat_schedule={
        "refresh-watchlists-daily": {
            "task": "flipradar.watchlist.dispatch_daily_refresh",
            "schedule": 24 * 60 * 60,
        },
        "deliver-watchlist-notification-digests-hourly": {
            "task": "flipradar.notifications.deliver_email_digests",
            "schedule": 60 * 60,
        },
    },
)
