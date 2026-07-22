import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flipradar.core.logging import setup_logging  # noqa: E402

setup_logging("INFO")
logger = logging.getLogger(__name__)
logger.info("test logging configured")
