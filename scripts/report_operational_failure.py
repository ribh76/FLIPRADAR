"""Emit sanitized deploy or migration failure telemetry from startup scripts."""

import sys

from path_setup import ensure_backend_path

ensure_backend_path()

from flipradar.core.logging import setup_logging  # noqa: E402
from flipradar.core.observability import (  # noqa: E402
    configure_exception_monitoring,
    record_operational_failure,
)
from flipradar.core.settings import get_settings  # noqa: E402


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else "deployment"
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
    record_operational_failure(stage, RuntimeError(f"{stage} startup operation failed"))


if __name__ == "__main__":
    main()
