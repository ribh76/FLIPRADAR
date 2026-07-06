import logging
from typing import Any
from uuid import UUID

from sqlalchemy import delete, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import LegoSet, PortfolioItem, PriceSnapshot, Recommendation, User
from app.schemas.validation import normalize_set_number

logger = logging.getLogger(__name__)


async def get_set_by_number(db: AsyncSession, set_number: str) -> LegoSet | None:
    normalized_set_number = normalize_set_number(set_number)
    try:
        result = await db.execute(
            select(LegoSet).where(LegoSet.set_number == normalized_set_number)
        )
        lego_set = result.scalar_one_or_none()
    except SQLAlchemyError:
        logger.exception(
            "unexpected DB failure while fetching set set_number=%s", set_number
        )
        raise
    if lego_set is None:
        logger.info("important missing data set not found set_number=%s", set_number)
    return lego_set


async def get_latest_snapshots_by_set_number(
    db: AsyncSession, set_number: str
) -> list[PriceSnapshot]:
    normalized_set_number = normalize_set_number(set_number)
    recent_snapshots = await get_recent_snapshots_by_set_number(
        db, normalized_set_number, limit=50
    )
    latest_by_marketplace = {}
    for snapshot in recent_snapshots:
        latest_by_marketplace.setdefault(snapshot.marketplace_id, snapshot)
    snapshots = list(latest_by_marketplace.values())
    if not snapshots:
        logger.info(
            "important missing data no snapshots set_number=%s snapshot_count=0",
            set_number,
        )
    return snapshots


async def get_recent_snapshots_by_set_number(
    db: AsyncSession, set_number: str, limit: int = 10
) -> list[PriceSnapshot]:
    normalized_set_number = normalize_set_number(set_number)
    statement = (
        select(PriceSnapshot)
        .options(selectinload(PriceSnapshot.marketplace))
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
        .order_by(PriceSnapshot.snapshot_at.desc(), PriceSnapshot.created_at.desc())
        .limit(limit)
    )
    try:
        result = await db.execute(statement)
    except SQLAlchemyError:
        logger.exception(
            "unexpected DB failure while fetching snapshots set_number=%s", set_number
        )
        raise
    return list(result.scalars())


async def create_recommendation(
    db: AsyncSession, recommendation_data: dict[str, Any]
) -> Recommendation:
    recommendation = Recommendation(**recommendation_data)
    db.add(recommendation)
    try:
        await db.flush()
        await db.refresh(recommendation)
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating recommendation")
        raise
    return recommendation


async def get_user_by_username_or_email(
    db: AsyncSession, identifier: str
) -> User | None:
    normalized = identifier.strip().lower()
    result = await db.execute(
        select(User).where(or_(User.username == normalized, User.email == normalized))
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_data: dict[str, Any]) -> User:
    user = User(**user_data)
    db.add(user)
    try:
        await db.flush()
        await db.refresh(user)
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating user")
        raise
    return user


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def create_portfolio_item(
    db: AsyncSession, user_id: UUID, item_data: dict[str, Any]
) -> PortfolioItem:
    item = PortfolioItem(user_id=user_id, **item_data)
    db.add(item)
    try:
        await db.flush()
        await db.refresh(item)
        await db.refresh(item, attribute_names=["lego_set"])
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating portfolio item")
        raise
    return item


async def get_portfolio_items_for_user(
    db: AsyncSession, user_id: UUID
) -> list[PortfolioItem]:
    result = await db.execute(
        select(PortfolioItem)
        .options(selectinload(PortfolioItem.lego_set))
        .where(PortfolioItem.user_id == user_id)
        .order_by(PortfolioItem.created_at.desc())
    )
    return list(result.scalars())


async def get_portfolio_item_by_id(
    db: AsyncSession, item_id: UUID, user_id: UUID
) -> PortfolioItem | None:
    result = await db.execute(
        select(PortfolioItem)
        .options(selectinload(PortfolioItem.lego_set))
        .where(PortfolioItem.id == item_id, PortfolioItem.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_portfolio_item(
    db: AsyncSession, item_id: UUID, user_id: UUID, item_data: dict[str, Any]
) -> PortfolioItem | None:
    item = await get_portfolio_item_by_id(db, item_id, user_id)
    if item is None:
        return None

    for field_name, value in item_data.items():
        setattr(item, field_name, value)

    try:
        await db.flush()
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while updating portfolio item")
        raise
    return await get_portfolio_item_by_id(db, item_id, user_id)


async def delete_portfolio_item(db: AsyncSession, item_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        delete(PortfolioItem).where(
            PortfolioItem.id == item_id, PortfolioItem.user_id == user_id
        )
    )
    return bool(result.rowcount)
