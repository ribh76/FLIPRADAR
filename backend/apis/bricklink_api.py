import logging

from config import get_settings

logger = logging.getLogger(__name__)


class BricklinkApiNotConfiguredError(RuntimeError):
    """Raised until BrickLink API credentials and client configuration are added."""


async def fetch_price_snapshots(set_number: str) -> list[dict]:
    settings = get_settings()
    if not settings.bricklink_api_configured:
        logger.warning(
            "to-be-implemented API call skipped provider=bricklink set_number=%s",
            set_number,
        )
        raise BricklinkApiNotConfiguredError(
            "BrickLink API configuration has not been added."
        )
    logger.info(
        "to-be-implemented API call provider=bricklink set_number=%s", set_number
    )
    return []
