import logging

from flipradar.core.settings import Settings

logger = logging.getLogger(__name__)


def report_startup_configuration(settings: Settings) -> None:
    logger.info(
        "runtime environment app_env=%s debug=%s frontend_url=%s",
        settings.application.environment.value,
        settings.application.debug,
        settings.application.frontend_url,
    )

    marketplace = settings.marketplace
    if not marketplace.ebay.usable:
        logger.warning(
            "optional integration disabled provider=ebay configured=%s enabled=%s",
            marketplace.ebay.configured,
            marketplace.ebay.enabled,
        )
    if not marketplace.bricklink.usable:
        logger.warning(
            "optional integration disabled provider=bricklink configured=%s enabled=%s",
            marketplace.bricklink.configured,
            marketplace.bricklink.enabled,
        )
    if not settings.email.configured:
        logger.warning(
            "optional integration disabled provider=email configured=%s enabled=%s",
            settings.email.configured,
            settings.email.enabled,
        )
    if not settings.llm.configured:
        logger.warning(
            "optional integration disabled provider=%s configured=%s enabled=%s",
            settings.llm.provider,
            settings.llm.configured,
            settings.llm.enabled,
        )
