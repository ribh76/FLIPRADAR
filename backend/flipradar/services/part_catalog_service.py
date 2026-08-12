"""Part catalog search and provider synchronization use cases."""

import asyncio
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.database.repositories import Pagination, PartCatalogRepository
from flipradar.domain.models import Part
from flipradar.integrations import bricklink_mock_client
from flipradar.services.errors import ServiceNotFoundError, ServiceValidationError
from flipradar.services.part_catalog_normalizer import normalize_part_catalog_record

RepositoryFactory = Callable[[AsyncSession], PartCatalogRepository]


class PartCatalogService:
    def __init__(
        self, repository_factory: RepositoryFactory = PartCatalogRepository
    ) -> None:
        self._repository_factory = repository_factory
        self._sync_locks: dict[tuple[str, str], asyncio.Lock] = {}

    async def synchronize(
        self, db: AsyncSession, query: str, *, provider: str = "bricklink"
    ) -> list[Part]:
        provider = _provider(provider)
        normalized_query = query.strip().lower()
        if not normalized_query:
            raise ServiceValidationError("Part search query is required")
        lock = self._sync_locks.setdefault((provider, normalized_query), asyncio.Lock())
        async with lock:
            raw_records = _provider_records(provider, normalized_query)
            repository = self._repository_factory(db)
            parts: dict[str, Part] = {}
            for raw_record in raw_records:
                record = normalize_part_catalog_record(raw_record, provider=provider)
                part = await repository.upsert_record(record)
                parts[part.canonical_identifier] = part
            # Re-read after the batch so previously eager-loaded collections
            # include every element/color added by this synchronization.
            refreshed = await repository.search(
                normalized_query, pagination=Pagination(limit=100, offset=0)
            )
            return refreshed or list(parts.values())

    async def search(
        self,
        db: AsyncSession,
        query: str,
        *,
        provider: str = "bricklink",
        limit: int = 25,
    ) -> dict:
        repository = self._repository_factory(db)
        local_results = await repository.search(
            query, pagination=Pagination(limit=limit, offset=0)
        )
        if local_results:
            return {"query": query.strip(), "source": "local", "results": local_results}
        results = await self.synchronize(db, query, provider=provider)
        return {
            "query": query.strip(),
            "source": "provider",
            "results": results[:limit],
        }


def _provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized != "bricklink":
        raise ServiceValidationError(f"Unsupported catalog provider: {provider}")
    return normalized


def _provider_records(provider: str, query: str) -> list[dict]:
    if provider == "bricklink":
        records = bricklink_mock_client.fetch_part_catalog_records(query)
        if records:
            return records
    raise ServiceNotFoundError(
        f"LEGO part '{query}' was not found in the local catalog or {provider}"
    )


part_catalog_service = PartCatalogService()


async def search_parts(
    db: AsyncSession, query: str, *, provider: str = "bricklink", limit: int = 25
) -> dict:
    return await part_catalog_service.search(db, query, provider=provider, limit=limit)


async def synchronize_parts(
    db: AsyncSession, query: str, *, provider: str = "bricklink"
) -> list[Part]:
    return await part_catalog_service.synchronize(db, query, provider=provider)
