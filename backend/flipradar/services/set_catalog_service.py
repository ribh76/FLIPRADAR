from collections.abc import Callable
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import LegoSetCreate
from flipradar.api.schemas.validation import normalize_set_number
from flipradar.database import repositories
from flipradar.database.repositories import Pagination
from flipradar.domain.models import LegoSet
from flipradar.integrations import bricklink_mock_client
from flipradar.services.errors import (
    ServiceConflictError,
    ServiceIncompleteDataError,
    ServiceNotFoundError,
    ServiceValidationError,
)


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


_CATALOG_REQUIRED_FIELDS = (
    "set_number",
    "name",
    "theme",
    "release_year",
    "piece_count",
)


def _missing_catalog_fields(record: dict | LegoSet) -> list[str]:
    if isinstance(record, dict):
        return [
            field
            for field in _CATALOG_REQUIRED_FIELDS
            if record.get(field) in (None, "")
        ]
    return [
        field for field in _CATALOG_REQUIRED_FIELDS if getattr(record, field) is None
    ]


def _provider_metadata(set_number: str, provider: str) -> tuple[dict, str]:
    if provider != "bricklink":
        raise ServiceValidationError(f"Unsupported catalog provider: {provider}")
    try:
        return (
            bricklink_mock_client.fetch_set_metadata(set_number),
            "https://www.bricklink.com/v2/catalog/catalogitem.page?S="
            f"{set_number}#T=S",
        )
    except bricklink_mock_client.MockBricklinkSetNotFoundError as exc:
        raise ServiceNotFoundError(
            f"LEGO set '{set_number}' was not found in the local catalog or {provider}"
        ) from exc


def _normalize_provider_set(
    record: dict, provider: str, source_url: str
) -> LegoSetCreate:
    missing_fields = _missing_catalog_fields(record)
    if missing_fields:
        raise ServiceIncompleteDataError(
            f"{provider} returned incomplete set data; missing: {', '.join(missing_fields)}"
        )
    payload = {
        "set_number": normalize_set_number(record["set_number"]),
        "name": str(record["name"]).strip(),
        "theme": str(record["theme"]).strip(),
        "subtheme": record.get("subtheme"),
        "release_year": record["release_year"],
        "retirement_year": record.get("retirement_year"),
        "piece_count": record["piece_count"],
        "minifig_count": record.get("minifig_count"),
        "source_name": f"{provider.title()} catalog",
        "source_url": source_url,
        "data_quality_flag": True,
        "completeness_flag": True,
    }
    try:
        return LegoSetCreate(**payload)
    except ValidationError as exc:
        raise ServiceIncompleteDataError(
            f"{provider} returned invalid set data: {exc.errors()[0]['msg']}"
        ) from exc


async def search_lego_sets(
    db: AsyncSession,
    query: str,
    *,
    provider: str = "bricklink",
    limit: int = 25,
) -> dict:
    """Search local catalog first, then fetch and cache an exact provider miss."""
    normalized_query = normalize_set_number(query)
    normalized_provider = provider.strip().lower()
    local_results = await list_lego_sets(
        db, limit=limit, query=normalized_query, order="set_number"
    )
    exact_set = next(
        (
            lego_set
            for lego_set in local_results
            if lego_set.set_number == normalized_query
        ),
        None,
    )
    if local_results and (exact_set is None or not _missing_catalog_fields(exact_set)):
        return {
            "query": normalized_query,
            "provider": None,
            "source": "local",
            "exact_match": exact_set is not None,
            "results": local_results,
        }

    try:
        record, source_url = _provider_metadata(normalized_query, normalized_provider)
    except ServiceNotFoundError as exc:
        if exact_set is None:
            raise
        missing_fields = ", ".join(_missing_catalog_fields(exact_set))
        raise ServiceIncompleteDataError(
            f"Local LEGO set '{normalized_query}' is incomplete; missing: {missing_fields}. "
            f"{normalized_provider} could not supply the missing data."
        ) from exc
    payload = _normalize_provider_set(record, normalized_provider, source_url)
    lego_set = await upsert_lego_set(db, payload)
    return {
        "query": normalized_query,
        "provider": normalized_provider,
        "source": "provider",
        "exact_match": lego_set.set_number == normalized_query,
        "results": [lego_set],
    }


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
