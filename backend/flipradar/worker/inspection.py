"""Read-only Celery inspection helpers for watchlist worker operations."""

from __future__ import annotations

import logging
from typing import Any

from flipradar.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def inspect_watchlist_workers() -> dict[str, Any]:
    """Inspect active, reserved, scheduled jobs and worker stats without mutation."""
    try:
        inspector = celery_app.control.inspect()
        return {
            "available": True,
            "active": inspector.active() or {},
            "reserved": inspector.reserved() or {},
            "scheduled": inspector.scheduled() or {},
            "stats": inspector.stats() or {},
        }
    except Exception:
        logger.exception("watchlist worker inspection failed")
        return {
            "available": False,
            "active": {},
            "reserved": {},
            "scheduled": {},
            "stats": {},
        }
