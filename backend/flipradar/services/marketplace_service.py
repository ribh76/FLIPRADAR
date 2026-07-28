import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas.validation import MarketplaceName, normalize_set_number
from flipradar.core.settings import get_settings
from flipradar.database import repositories
from flipradar.database.session import SessionLocal
from flipradar.domain.models import (
    LegoSet,
    Marketplace,
    MarketplaceListing,
    PriceSnapshot,
)
from flipradar.integrations.bricklink_mock_client import adapter as bricklink_adapter
from flipradar.integrations.ebay_mock_client import adapter as ebay_adapter
from flipradar.integrations.marketplace_adapter import MarketplaceAdapter
from flipradar.services import (
    listing_normalizer,
    product_matching_engine,
    snapshot_builder,
)
from flipradar.services.errors import (
    ServiceConflictError,
    ServiceProviderError,
    ServiceProviderTimeoutError,
)

logger = logging.getLogger(__name__)

MARKETPLACE_ADAPTERS: tuple[MarketplaceAdapter, ...] = (
    ebay_adapter,
    bricklink_adapter,
)
PROVIDER_MAX_ATTEMPTS = 3
PROVIDER_TIMEOUT_SECONDS = 10
STALE_LISTING_DAYS = 90


async def update_marketplace_data(
    set_number: str, db: AsyncSession | None = None
) -> PriceSnapshot:
    normalized_set_number = normalize_set_number(set_number)
    if db is None:
        async with SessionLocal() as session:
            try:
                snapshot = await _update_marketplace_data(
                    session, normalized_set_number
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            return snapshot

    return await _update_marketplace_data(db, normalized_set_number)


async def refresh_marketplace_data(
    set_number: str, *, force: bool = False, db: AsyncSession | None = None
) -> PriceSnapshot | None:
    """Refresh only stale data, making repeated refresh invocations idempotent."""
    normalized_set_number = normalize_set_number(set_number)
    if db is None:
        async with SessionLocal() as session:
            try:
                snapshot = await _refresh_marketplace_data(
                    session, normalized_set_number, force=force
                )
                await session.commit()
                return snapshot
            except Exception:
                await session.rollback()
                raise
    return await _refresh_marketplace_data(db, normalized_set_number, force=force)


async def _refresh_marketplace_data(
    db: AsyncSession, set_number: str, *, force: bool
) -> PriceSnapshot | None:
    freshness_hours = get_settings().pricing_freshness_hours
    latest_retrieval = await repositories.latest_price_snapshot_retrieval_time(
        db, set_number
    )
    if not force and latest_retrieval is not None:
        cutoff = datetime.now(UTC) - timedelta(hours=freshness_hours)
        if latest_retrieval >= cutoff:
            logger.info(
                "marketplace refresh skipped fresh_snapshot set_number=%s retrieval_time=%s",
                set_number,
                latest_retrieval,
            )
            return None
    return await _update_marketplace_data(db, set_number)


async def _update_marketplace_data(db: AsyncSession, set_number: str) -> PriceSnapshot:
    lego_set = await _get_lego_set(db, set_number)
    if lego_set is None:
        raise LookupError("LEGO set not found")

    raw_listings = []
    for adapter in MARKETPLACE_ADAPTERS:
        raw_listings.extend(await _fetch_adapter_listings(adapter, lego_set.set_number))

    normalized_listings = listing_normalizer.normalize(raw_listings)
    matched_listings = _match_listings_to_set(normalized_listings, lego_set)
    normalized_listings = matched_listings[:50]
    if len(normalized_listings) < 10:
        logger.warning(
            "major marketplace data shortage set_number=%s listing_count=%s",
            lego_set.set_number,
            len(normalized_listings),
        )

    async with db.begin_nested():
        await _save_listings(db, lego_set, normalized_listings)
        snapshots = await _save_snapshots_by_marketplace(
            db, lego_set, normalized_listings
        )
        stale_count = await _mark_stale_listings(db, lego_set)
    if stale_count:
        logger.info(
            "stale marketplace listings marked removed set_number=%s count=%s",
            lego_set.set_number,
            stale_count,
        )
    if not snapshots:
        raise LookupError("No valid marketplace listings found")
    return snapshots[0]


def _match_listings_to_set(listings: list[dict], lego_set: LegoSet) -> list[dict]:
    """Keep only listings that match the requested catalog set."""
    matched_listings = []
    for listing in listings:
        match = product_matching_engine.match_listing_to_set(
            listing["title"], set_number=lego_set.set_number, set_name=lego_set.name
        )
        if not match.is_match:
            logger.info(
                "marketplace listing rejected set_number=%s candidates=%s explanation=%s title=%r",
                lego_set.set_number,
                match.candidate_set_numbers,
                match.explanation,
                listing["title"],
            )
            continue
        matched_listings.append(
            {
                **listing,
                "detected_set_number": match.detected_set_number,
                "match_confidence": match.confidence,
                "match_reasons": list(match.match_reasons),
                "exclusion_flags": list(match.exclusion_reasons),
            }
        )
    return matched_listings


async def _fetch_adapter_listings(
    adapter: MarketplaceAdapter,
    set_number: str,
    *,
    max_attempts: int = PROVIDER_MAX_ATTEMPTS,
    timeout_seconds: float = PROVIDER_TIMEOUT_SECONDS,
) -> list[dict]:
    """Fetch provider data with bounded retries and a per-attempt timeout."""
    for attempt in range(1, max_attempts + 1):
        try:
            listings = await asyncio.wait_for(
                asyncio.to_thread(adapter.fetch_listings, set_number),
                timeout=timeout_seconds,
            )
            if not isinstance(listings, list):
                raise TypeError("provider response must be a list")
            return listings
        except TimeoutError as exc:
            if attempt == max_attempts:
                raise ServiceProviderTimeoutError(
                    f"{adapter.marketplace} timed out after {max_attempts} attempts"
                ) from exc
            logger.warning(
                "marketplace provider timeout provider=%s attempt=%s/%s",
                adapter.marketplace,
                attempt,
                max_attempts,
            )
        except Exception as exc:
            if attempt == max_attempts:
                raise ServiceProviderError(
                    f"{adapter.marketplace} failed after {max_attempts} attempts"
                ) from exc
            logger.warning(
                "marketplace provider failure provider=%s attempt=%s/%s error=%s",
                adapter.marketplace,
                attempt,
                max_attempts,
                type(exc).__name__,
            )
        await asyncio.sleep(0)
    raise AssertionError("unreachable")


async def _mark_stale_listings(db: AsyncSession, lego_set: LegoSet) -> int:
    stale_before = datetime.now(UTC) - timedelta(days=STALE_LISTING_DAYS)
    return await repositories.mark_stale_marketplace_listings(
        db, lego_set_id=lego_set.id, stale_before=stale_before
    )


async def _get_lego_set(db: AsyncSession, set_number: str) -> LegoSet | None:
    return await repositories.get_set_by_number(db, normalize_set_number(set_number))


async def _get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    normalized_name = marketplace_name.lower()
    allowed_marketplaces = {marketplace.value for marketplace in MarketplaceName}
    if normalized_name not in allowed_marketplaces:
        raise ValueError("Unsupported marketplace")
    try:
        return await repositories.get_or_create_marketplace(db, normalized_name)
    except repositories.DuplicateRecordError as exc:
        raise ServiceConflictError(str(exc)) from exc


async def _save_listings(
    db: AsyncSession, lego_set: LegoSet, listings: list[dict]
) -> list[MarketplaceListing]:
    saved_listings = []
    marketplace_cache: dict[str, Marketplace] = {}

    for listing_data in listings:
        marketplace_name = listing_data["marketplace"]
        if marketplace_name not in marketplace_cache:
            marketplace_cache[marketplace_name] = await _get_or_create_marketplace(
                db, marketplace_name
            )

    listings_by_marketplace = defaultdict(list)
    for listing_data in listings:
        listings_by_marketplace[listing_data["marketplace"]].append(
            {
                "external_listing_id": listing_data["external_listing_id"],
                "detected_set_number": listing_data["detected_set_number"],
                "title": listing_data["title"],
                "url": listing_data["listing_url"],
                "price": listing_data["price"],
                "shipping_price": listing_data["shipping_price"],
                "total_price": listing_data["price"] + listing_data["shipping_price"],
                "currency": listing_data["currency"],
                "condition": listing_data["condition"],
                "is_complete": listing_data["is_complete"],
                "is_sealed": listing_data["is_sealed"],
                "listing_status": "active",
                "seller_name": listing_data["seller"],
                "match_confidence": listing_data["match_confidence"],
                "match_reasons": listing_data["match_reasons"],
                "exclusion_flags": listing_data["exclusion_flags"],
                "raw_payload": listing_data["raw_payload"],
            }
        )

    for marketplace_name, marketplace_listings in listings_by_marketplace.items():
        marketplace = marketplace_cache[marketplace_name]
        new_listings = await repositories.bulk_create_marketplace_listings(
            db,
            lego_set_id=lego_set.id,
            marketplace_id=marketplace.id,
            listings_data=marketplace_listings,
            skip_duplicates=True,
        )
        duplicate_count = len(marketplace_listings) - len(new_listings)
        if duplicate_count:
            logger.info(
                "duplicate marketplace listings skipped marketplace=%s duplicate_count=%s",
                marketplace_name,
                duplicate_count,
            )
        saved_listings.extend(new_listings)

    return saved_listings


async def _save_snapshots_by_marketplace(
    db: AsyncSession, lego_set: LegoSet, listings: list[dict]
) -> list[PriceSnapshot]:
    pricing_listings = _listings_for_automated_pricing(listings)
    listings_by_marketplace = defaultdict(list)
    for listing in pricing_listings:
        listings_by_marketplace[listing["marketplace"]].append(listing)

    snapshots = []
    snapshot_rows = []
    for marketplace_name in sorted(listings_by_marketplace):
        marketplace = await _get_or_create_marketplace(db, marketplace_name)
        snapshot_data = snapshot_builder.build(
            listings_by_marketplace[marketplace_name],
            target_currency=get_settings().pricing_currency,
        )
        snapshot_rows.extend(
            {
                "lego_set_id": lego_set.id,
                "marketplace_id": marketplace.id,
                **metric_snapshot,
            }
            for metric_snapshot in snapshot_data
        )
    snapshots.extend(await repositories.bulk_create_price_snapshots(db, snapshot_rows))
    return snapshots


def _listings_for_automated_pricing(listings: list[dict]) -> list[dict]:
    """Exclude uncertain title-only matches from automated market valuations."""
    return [
        listing
        for listing in listings
        if listing.get("match_confidence", 0)
        >= product_matching_engine.AUTOMATED_PRICING_MIN_CONFIDENCE
    ]


async def _save_snapshot(
    db: AsyncSession,
    lego_set: LegoSet,
    marketplace: Marketplace,
    snapshot_data: dict,
) -> PriceSnapshot:
    return await repositories.create_price_snapshot(
        db,
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        snapshot_data=snapshot_data,
    )


def _marketplace_base_url(marketplace_name: str) -> str | None:
    if marketplace_name == MarketplaceName.EBAY.value:
        return "https://www.ebay.com"
    if marketplace_name == MarketplaceName.BRICKLINK.value:
        return "https://www.bricklink.com"
    return None


async def _get_existing_listing(
    db: AsyncSession, marketplace_id, external_listing_id: str
) -> MarketplaceListing | None:
    return await repositories.get_existing_listing(
        db, marketplace_id, external_listing_id
    )
