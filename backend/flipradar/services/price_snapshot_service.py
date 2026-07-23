import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import PriceSnapshotCreate
from flipradar.database import repositories
from flipradar.database.repositories import Pagination
from flipradar.domain.models import Marketplace, PriceSnapshot
from flipradar.services.errors import (
    ServiceConflictError,
    ServiceNotFoundError,
    ServiceValidationError,
)

logger = logging.getLogger(__name__)


async def get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    try:
        return await repositories.get_or_create_marketplace(db, marketplace_name)
    except ValueError as exc:
        raise ServiceValidationError(str(exc)) from exc
    except repositories.DuplicateRecordError as exc:
        raise ServiceConflictError(str(exc)) from exc


async def create_price_snapshot(
    db: AsyncSession, payload: PriceSnapshotCreate
) -> PriceSnapshot:
    lego_set = await repositories.get_set_by_number(db, payload.set_number)
    if lego_set is None:
        raise ServiceNotFoundError("LEGO set not found")

    marketplace = await get_or_create_marketplace(db, payload.marketplace_name)
    snapshot_data = payload.model_dump(
        exclude={"set_number", "marketplace_name"}, exclude_none=True
    )
    try:
        async with db.begin_nested():
            return await repositories.create_price_snapshot(
                db,
                lego_set_id=lego_set.id,
                marketplace_id=marketplace.id,
                snapshot_data=snapshot_data,
            )
    except repositories.DuplicateRecordError as exc:
        raise ServiceConflictError(str(exc)) from exc


async def list_price_snapshots_for_set(
    db: AsyncSession,
    set_number: str,
    *,
    limit: int = repositories.DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    condition: str | None = None,
    marketplace_name: str | None = None,
    order: str = "snapshot_desc",
) -> list[PriceSnapshot]:
    return await repositories.list_price_snapshots_for_set(
        db,
        set_number,
        pagination=Pagination(limit=limit, offset=offset),
        condition=condition,
        marketplace_name=marketplace_name,
        order=order,
    )


async def get_latest_price_snapshot_by_set_number(
    db: AsyncSession, set_number: str
) -> PriceSnapshot | None:
    try:
        snapshot = await repositories.get_latest_price_snapshot_by_set_number(
            db, set_number
        )
    except SQLAlchemyError:
        logger.exception(
            "unexpected DB failure while fetching latest snapshot set_number=%s",
            set_number,
        )
        raise
    return snapshot
