from collections.abc import Callable
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import LegoSetCreate
from flipradar.database import repositories
from flipradar.database.repositories import Pagination
from flipradar.domain.models import LegoSet
from flipradar.services.errors import ServiceConflictError


class LegoSetCache(Protocol):
    def get(self, set_number: str) -> LegoSet | None: ...

    def set(self, lego_set: LegoSet) -> None: ...

    def invalidate(self, set_number: str) -> None: ...


class InMemoryLegoSetCache:
    """Small injectable cache suitable for request-local or process-local use."""

    def __init__(self) -> None:
        self._items: dict[str, LegoSet] = {}

    def get(self, set_number: str) -> LegoSet | None:
        return self._items.get(set_number.strip().upper())

    def set(self, lego_set: LegoSet) -> None:
        self._items[lego_set.set_number] = lego_set

    def invalidate(self, set_number: str) -> None:
        self._items.pop(set_number.strip().upper(), None)


RepositoryFactory = Callable[[AsyncSession], repositories.LegoSetCatalogRepository]


class LegoSetCatalogService:
    """Catalog use cases with injectable persistence and cache dependencies."""

    def __init__(
        self,
        repository_factory: RepositoryFactory = repositories.LegoSetCatalogRepository,
        cache: LegoSetCache | None = None,
    ) -> None:
        self._repository_factory = repository_factory
        self._cache = cache

    async def get(self, db: AsyncSession, set_number: str) -> LegoSet | None:
        normalized = set_number.strip().upper()
        if self._cache is not None:
            cached = self._cache.get(normalized)
            if cached is not None:
                return cached
        lego_set = await self._repository_factory(db).get_by_number(normalized)
        if lego_set is not None and self._cache is not None:
            self._cache.set(lego_set)
        return lego_set

    async def upsert(self, db: AsyncSession, payload: LegoSetCreate) -> LegoSet:
        lego_set = await self._repository_factory(db).upsert(payload.model_dump())
        if self._cache is not None:
            self._cache.set(lego_set)
        return lego_set


catalog_service = LegoSetCatalogService(cache=InMemoryLegoSetCache())


async def get_cached_lego_set(db: AsyncSession, set_number: str) -> LegoSet | None:
    return await catalog_service.get(db, set_number)


async def get_lego_set(db: AsyncSession, set_number: str) -> LegoSet | None:
    """Get one catalog set through the configured cache and repository."""
    return await get_cached_lego_set(db, set_number)


async def upsert_lego_set(db: AsyncSession, payload: LegoSetCreate) -> LegoSet:
    return await catalog_service.upsert(db, payload)


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
