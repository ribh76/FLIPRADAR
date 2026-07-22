from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import ListingCreate
from flipradar.api.schemas.validation import MarketplaceName, normalize_set_number
from flipradar.domain.models import LegoSet, Marketplace, MarketplaceListing


async def get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    normalized_name = marketplace_name.lower()
    if normalized_name not in {marketplace.value for marketplace in MarketplaceName}:
        raise ValueError("Unsupported marketplace")
    result = await db.execute(
        select(Marketplace).where(Marketplace.name == normalized_name)
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is not None:
        return marketplace

    marketplace = Marketplace(
        name=normalized_name,
        display_name=normalized_name.title(),
        fee_percent=0,
    )
    db.add(marketplace)
    await db.flush()
    return marketplace


async def create_listing(
    db: AsyncSession, payload: ListingCreate
) -> MarketplaceListing:
    result = await db.execute(
        select(LegoSet).where(LegoSet.set_number == payload.set_number)
    )
    lego_set = result.scalar_one_or_none()
    if lego_set is None:
        raise LookupError("LEGO set not found")

    marketplace = await get_or_create_marketplace(db, payload.marketplace_name)
    listing_data = payload.model_dump(
        exclude={"set_number", "marketplace_name"}, mode="json"
    )
    listing = MarketplaceListing(
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        **listing_data,
    )
    db.add(listing)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ValueError("Marketplace listing already exists") from exc
    await db.refresh(listing)
    return listing


async def list_listings_for_set(
    db: AsyncSession, set_number: str
) -> list[MarketplaceListing]:
    normalized_set_number = normalize_set_number(set_number)
    result = await db.execute(
        select(MarketplaceListing)
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
        .order_by(MarketplaceListing.last_seen_at.desc())
    )
    return list(result.scalars())


async def latest_listing_for_set(
    db: AsyncSession, set_number: str
) -> MarketplaceListing | None:
    normalized_set_number = normalize_set_number(set_number)
    result = await db.execute(
        select(MarketplaceListing)
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
        .order_by(
            MarketplaceListing.last_seen_at.desc(), MarketplaceListing.created_at.desc()
        )
        .limit(1)
    )
    return result.scalar_one_or_none()
