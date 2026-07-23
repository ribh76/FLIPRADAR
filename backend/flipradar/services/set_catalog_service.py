from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import LegoSetCreate
from flipradar.database import repositories
from flipradar.database.repositories import Pagination
from flipradar.domain.models import LegoSet
from flipradar.services.errors import ServiceConflictError


async def create_lego_set(db: AsyncSession, payload: LegoSetCreate) -> LegoSet:
    try:
        return await repositories.create_set(db, payload.model_dump())
    except repositories.DuplicateRecordError as exc:
        raise ServiceConflictError(str(exc)) from exc


async def list_lego_sets(
    db: AsyncSession,
    *,
    limit: int = repositories.DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    theme: str | None = None,
    query: str | None = None,
    order: str = "set_number",
) -> list[LegoSet]:
    return await repositories.list_sets(
        db,
        pagination=Pagination(limit=limit, offset=offset),
        theme=theme,
        query=query,
        order=order,
    )
