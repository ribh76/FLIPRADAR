from celery import Celery

from flipradar.core.settings import get_settings

settings = get_settings()
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
        }
    },
)
