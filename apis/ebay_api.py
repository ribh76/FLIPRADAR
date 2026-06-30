import logging

from config import get_settings

logger = logging.getLogger(__name__)


class EbayApiNotConfiguredError(RuntimeError):
    """Raised until eBay API credentials and client configuration are added."""


async def fetch_marketplace_listings(set_number: str) -> list[dict]:
    settings = get_settings()
    if not settings.ebay_api_configured:
        logger.warning(
            "to-be-implemented API call skipped provider=ebay set_number=%s", set_number
        )
        raise EbayApiNotConfiguredError("eBay API configuration has not been added.")
    logger.info("to-be-implemented API call provider=ebay set_number=%s", set_number)
    return []
