"""Part catalog search and provider synchronization use cases."""

import asyncio
from collections.abc import Callable
from copy import copy

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.database.repositories import (
    Pagination,
    PartCatalogRepository,
    PartCatalogSearchPage,
)
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
        offset: int = 0,
        color: str | None = None,
        category: str | None = None,
        year: int | None = None,
    ) -> dict:
        normalized_query = query.strip()
        if not normalized_query:
            raise ServiceValidationError("Part search query is required")
        filters = {"color": color, "category": category, "year": year}
        repository = self._repository_factory(db)
        local_page = await repository.search_page(
            normalized_query,
            pagination=Pagination(limit=limit, offset=offset),
            **filters,
        )
        if local_page.matches or local_page.total:
            return _search_response(
                normalized_query, "local", local_page, limit, offset
            )

        # A filter miss is still a local catalog hit.  Re-syncing the same query
        # cannot make an unavailable color, category, or year suddenly match.
        if any(value is not None for value in filters.values()):
            unfiltered_results = await repository.search(
                normalized_query, pagination=Pagination(limit=1, offset=0)
            )
            if unfiltered_results:
                return _search_response(
                    normalized_query, "local", local_page, limit, offset
                )

        await self.synchronize(db, normalized_query, provider=provider)
        provider_page = await repository.search_page(
            normalized_query,
            pagination=Pagination(limit=limit, offset=offset),
            **filters,
        )
        return _search_response(
            normalized_query, "provider", provider_page, limit, offset
        )


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
    db: AsyncSession,
    query: str,
    *,
    provider: str = "bricklink",
    limit: int = 25,
    offset: int = 0,
    color: str | None = None,
    category: str | None = None,
    year: int | None = None,
) -> dict:
    return await part_catalog_service.search(
        db,
        query,
        provider=provider,
        limit=limit,
        offset=offset,
        color=color,
        category=category,
        year=year,
    )


def _search_response(
    query: str,
    source: str,
    page: PartCatalogSearchPage,
    limit: int,
    offset: int,
) -> dict:
    results: list[Part] = []
    for match in page.matches:
        part = copy(match.part)
        part.match_type = match.relevance.match_type
        part.match_confidence = match.relevance.confidence
        part.match_explanation = match.relevance.explanation
        results.append(part)
    return {
        "query": query,
        "source": source,
        "results": results,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(results),
            "has_more": offset + len(results) < page.total,
        },
    }


async def synchronize_parts(
    db: AsyncSession, query: str, *, provider: str = "bricklink"
) -> list[Part]:
    return await part_catalog_service.synchronize(db, query, provider=provider)
