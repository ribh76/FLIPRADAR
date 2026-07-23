import logging
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_DEBUG", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-for-tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://testserver")

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flipradar.core.logging import setup_logging  # noqa: E402
from flipradar.core.settings import Settings, clear_settings_cache  # noqa: E402

setup_logging("INFO")
logger = logging.getLogger(__name__)
logger.info("test logging configured")


def pytest_configure():
    clear_settings_cache()


def pytest_unconfigure():
    clear_settings_cache()


@pytest.fixture
def test_settings() -> Settings:
    clear_settings_cache()
    return Settings()
