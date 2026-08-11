import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from flipradar.core.observability import sanitize_telemetry

request_id_context: ContextVar[str | None] = ContextVar(
    "request_id", default=None
)


class JsonFormatter(logging.Formatter):
    """Render application logs as one JSON object per line for log aggregation."""

    def __init__(self, *, environment: str, release: str) -> None:
        super().__init__()
        self.environment = environment
        self.release = release

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_telemetry(record.getMessage()),
            "environment": self.environment,
            "release": self.release,
        }
        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = sanitize_telemetry(
                self.formatException(record.exc_info)
            )
        metric = getattr(record, "metric", None)
        if metric is not None:
            payload["metric"] = sanitize_telemetry(metric)
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(
    log_level: str = "INFO",
    *,
    sqlalchemy_level: str = "WARNING",
    uvicorn_access_level: str = "INFO",
    environment: str = "development",
    release: str = "unknown",
) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(environment=environment, release=release))
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        handlers=[handler],
    )

    # Quiet down noisy third-party libraries
    logging.getLogger("sqlalchemy.engine").setLevel(
        getattr(logging, sqlalchemy_level.upper(), logging.WARNING)
    )
    logging.getLogger("uvicorn.access").setLevel(
        getattr(logging, uvicorn_access_level.upper(), logging.INFO)
    )
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
