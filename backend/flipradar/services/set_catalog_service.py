from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import LegoSetCreate
from flipradar.domain.models import LegoSet


async def create_lego_set(db: AsyncSession, payload: LegoSetCreate) -> LegoSet:
    lego_set = LegoSet(**payload.model_dump())
    db.add(lego_set)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ValueError("LEGO set already exists") from exc
    await db.refresh(lego_set)
    return lego_set


async def list_lego_sets(db: AsyncSession) -> list[LegoSet]:
    result = await db.execute(select(LegoSet).order_by(LegoSet.set_number))
    return list(result.scalars())
