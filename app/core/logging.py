import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(
    log_level: str = "INFO",
    *,
    sqlalchemy_level: str = "WARNING",
    uvicorn_access_level: str = "INFO",
) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Quiet down noisy third-party libraries
    logging.getLogger("sqlalchemy.engine").setLevel(
        getattr(logging, sqlalchemy_level.upper(), logging.WARNING)
    )
    logging.getLogger("uvicorn.access").setLevel(
        getattr(logging, uvicorn_access_level.upper(), logging.INFO)
    )
