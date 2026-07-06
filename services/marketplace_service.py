import logging
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.validation import MarketplaceName, normalize_set_number
from database.session import SessionLocal
from models import LegoSet, Marketplace, MarketplaceListing, PriceSnapshot
from services import bricklink_client, ebay_client, listing_normalizer, snapshot_builder

logger = logging.getLogger(__name__)


async def update_marketplace_data(
    set_number: str, db: AsyncSession | None = None
) -> PriceSnapshot:
    normalized_set_number = normalize_set_number(set_number)
    if db is None:
        async with SessionLocal() as session:
            try:
                snapshot = await _update_marketplace_data(session, normalized_set_number)
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

    await _save_listings(db, lego_set, normalized_listings)
    snapshots = await _save_snapshots_by_marketplace(db, lego_set, normalized_listings)
    if not snapshots:
        raise LookupError("No valid marketplace listings found")
    return snapshots[0]


def _with_marketplace(marketplace_name: str, listings: list[dict]) -> list[dict]:
    return [{**listing, "marketplace": marketplace_name} for listing in listings]


async def _get_lego_set(db: AsyncSession, set_number: str) -> LegoSet | None:
    normalized_set_number = normalize_set_number(set_number)
    result = await db.execute(
        select(LegoSet).where(LegoSet.set_number == normalized_set_number)
    )
    return result.scalar_one_or_none()


async def _get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    normalized_name = marketplace_name.lower()
    allowed_marketplaces = {marketplace.value for marketplace in MarketplaceName}
    if normalized_name not in allowed_marketplaces:
        raise ValueError("Unsupported marketplace")

    result = await db.execute(
        select(Marketplace).where(Marketplace.name == normalized_name)
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is not None:
        return marketplace

    marketplace = Marketplace(
        name=normalized_name,
        display_name=marketplace_name.title(),
        base_url=_marketplace_base_url(normalized_name),
        fee_percent=Decimal("0.00"),
    )
    db.add(marketplace)
    await db.flush()
    return marketplace


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
        marketplace = marketplace_cache[marketplace_name]
        existing_listing = await _get_existing_listing(
            db, marketplace.id, listing_data["external_listing_id"]
        )
        if existing_listing is not None:
            logger.info(
                "duplicate marketplace listing skipped marketplace=%s external_listing_id=%s",
                marketplace_name,
                listing_data["external_listing_id"],
            )
            continue

        listing = MarketplaceListing(
            lego_set_id=lego_set.id,
            marketplace_id=marketplace.id,
            external_listing_id=listing_data["external_listing_id"],
            title=listing_data["title"],
            url=listing_data["listing_url"],
            price=listing_data["price"],
            shipping_price=listing_data["shipping_price"],
            total_price=listing_data["price"] + listing_data["shipping_price"],
            currency=listing_data["currency"],
            condition=listing_data["condition"],
            listing_status="active",
            seller_name=listing_data["seller"],
            raw_payload=listing_data["raw_payload"],
        )
        db.add(listing)
        await db.flush()
        saved_listings.append(listing)

    return saved_listings


async def _save_snapshots_by_marketplace(
    db: AsyncSession, lego_set: LegoSet, listings: list[dict]
) -> list[PriceSnapshot]:
    listings_by_marketplace = defaultdict(list)
    for listing in listings:
        listings_by_marketplace[listing["marketplace"]].append(listing)

    snapshots = []
    for marketplace_name in sorted(listings_by_marketplace):
        marketplace = await _get_or_create_marketplace(db, marketplace_name)
        snapshot_data = snapshot_builder.build(listings_by_marketplace[marketplace_name])
        snapshot = await _save_snapshot(db, lego_set, marketplace, snapshot_data)
        snapshots.append(snapshot)
    return snapshots


async def _save_snapshot(
    db: AsyncSession,
    lego_set: LegoSet,
    marketplace: Marketplace,
    snapshot_data: dict,
) -> PriceSnapshot:
    snapshot = PriceSnapshot(
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        **snapshot_data,
    )
    db.add(snapshot)
    await db.flush()
    await db.refresh(snapshot)
    return snapshot


def _marketplace_base_url(marketplace_name: str) -> str | None:
    if marketplace_name == MarketplaceName.EBAY.value:
        return "https://www.ebay.com"
    if marketplace_name == MarketplaceName.BRICKLINK.value:
        return "https://www.bricklink.com"
    return None


async def _get_existing_listing(
    db: AsyncSession, marketplace_id, external_listing_id: str
) -> MarketplaceListing | None:
    result = await db.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.marketplace_id == marketplace_id,
            MarketplaceListing.external_listing_id == external_listing_id,
        )
    )
    return result.scalar_one_or_none()
