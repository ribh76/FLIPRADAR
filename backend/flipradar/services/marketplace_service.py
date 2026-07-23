import logging
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas.validation import MarketplaceName, normalize_set_number
from flipradar.database import repositories
from flipradar.database.session import SessionLocal
from flipradar.domain.models import (
    LegoSet,
    Marketplace,
    MarketplaceListing,
    PriceSnapshot,
)
from flipradar.integrations import bricklink_mock_client as bricklink_client
from flipradar.integrations import ebay_mock_client as ebay_client
from flipradar.services import listing_normalizer, snapshot_builder
from flipradar.services.errors import ServiceConflictError

logger = logging.getLogger(__name__)


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


async def _update_marketplace_data(db: AsyncSession, set_number: str) -> PriceSnapshot:
    lego_set = await _get_lego_set(db, set_number)
    if lego_set is None:
        raise LookupError("LEGO set not found")

    raw_listings = []
    raw_listings.extend(
        _with_marketplace("ebay", ebay_client.fetch(lego_set.set_number))
    )
    raw_listings.extend(
        _with_marketplace("bricklink", bricklink_client.fetch(lego_set.set_number))
    )

    normalized_listings = listing_normalizer.normalize(raw_listings)[:50]
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
    if not snapshots:
        raise LookupError("No valid marketplace listings found")
    return snapshots[0]


def _with_marketplace(marketplace_name: str, listings: list[dict]) -> list[dict]:
    return [{**listing, "marketplace": marketplace_name} for listing in listings]


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
                "title": listing_data["title"],
                "url": listing_data["listing_url"],
                "price": listing_data["price"],
                "shipping_price": listing_data["shipping_price"],
                "total_price": listing_data["price"] + listing_data["shipping_price"],
                "currency": listing_data["currency"],
                "condition": listing_data["condition"],
                "listing_status": "active",
                "seller_name": listing_data["seller"],
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
    listings_by_marketplace = defaultdict(list)
    for listing in listings:
        listings_by_marketplace[listing["marketplace"]].append(listing)

    snapshots = []
    snapshot_rows = []
    for marketplace_name in sorted(listings_by_marketplace):
        marketplace = await _get_or_create_marketplace(db, marketplace_name)
        snapshot_data = snapshot_builder.build(
            listings_by_marketplace[marketplace_name]
        )
        snapshot_rows.append(
            {
                "lego_set_id": lego_set.id,
                "marketplace_id": marketplace.id,
                **snapshot_data,
            }
        )
    snapshots.extend(await repositories.bulk_create_price_snapshots(db, snapshot_rows))
    return snapshots


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
