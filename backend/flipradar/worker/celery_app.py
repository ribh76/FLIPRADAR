from time import perf_counter

from celery import Celery
from celery.signals import task_failure, task_prerun, task_retry, task_success

from flipradar.core.logging import setup_logging
from flipradar.core.observability import configure_exception_monitoring, record_metric
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
        "clear-mfa-token-blacklist-daily": {
            "task": "flipradar.auth.clear_mfa_token_blacklist",
            "schedule": 24 * 60 * 60,
        },
    },
)

_task_started_at: dict[str, float] = {}


def _task_tags(task_name: str, *, outcome: str) -> dict[str, str]:
    return {"task": task_name, "outcome": outcome}


def _record_task_outcome(task_id: str, task_name: str, outcome: str) -> None:
    started_at = _task_started_at.pop(task_id, perf_counter())
    tags = _task_tags(task_name, outcome=outcome)
    record_metric("worker.job", tags=tags)
    record_metric(
        "worker.job.latency", (perf_counter() - started_at) * 1000, unit="ms", tags=tags
    )


@task_prerun.connect
def _record_task_start(task_id: str, task: object, **_: object) -> None:
    _task_started_at[task_id] = perf_counter()
    record_metric("worker.job", tags=_task_tags(task.name, outcome="started"))


@task_success.connect
def _record_task_success(result: object, sender: object, **_: object) -> None:
    del result
    _record_task_outcome(sender.request.id, sender.name, "success")


@task_failure.connect
def _record_task_failure(task_id: str, sender: object, **_: object) -> None:
    _record_task_outcome(task_id, sender.name, "failure")


@task_retry.connect
def _record_task_retry(request: object, sender: object, **_: object) -> None:
    _record_task_outcome(request.id, sender.name, "retry")
