from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.database import repositories
from flipradar.services.deal_finder_service import DealFilters, find_deals
from flipradar.services.errors import (
    ServiceConflictError,
    ServiceNotFoundError,
    ServiceValidationError,
)

FILTER_VERSION = 1
SAVED_SEARCH_LIMIT = 25


def migrate_filter_config(version: int, config: dict) -> tuple[int, dict]:
    """Upgrade persisted filters before validation; version zero used min_price."""
    migrated = dict(config)
    if version == 0 and "min_price" in migrated:
        migrated["min_budget"] = migrated.pop("min_price")
        version = 1
    if version != FILTER_VERSION:
        raise ServiceValidationError("Unsupported saved-search filter version")
    return version, migrated


def validate_filter_config(config: dict, version: int = FILTER_VERSION) -> dict:
    _, migrated = migrate_filter_config(version, config)
    allowed = set(DealFilters.__dataclass_fields__) - {"order"}
    unknown = set(migrated) - allowed - {"order"}
    if unknown:
        raise ServiceValidationError(
            f"Unsupported deal filters: {', '.join(sorted(unknown))}"
        )
    try:
        filters = DealFilters(**migrated)
        filters.validate()
    except (TypeError, ValueError) as exc:
        raise ServiceValidationError(str(exc)) from exc
    return {key: value for key, value in migrated.items() if value is not None}


async def list_saved_searches(db: AsyncSession, user_id: UUID):
    return await repositories.list_saved_searches_for_user(db, user_id)


async def create_saved_search(
    db: AsyncSession, user_id: UUID, name: str, filter_config: dict
):
    if (
        await repositories.count_saved_searches_for_user(db, user_id)
        >= SAVED_SEARCH_LIMIT
    ):
        raise ServiceConflictError(
            f"Saved search limit of {SAVED_SEARCH_LIMIT} reached"
        )
    return await repositories.create_saved_search(
        db,
        {
            "user_id": user_id,
            "name": name.strip(),
            "filter_config": validate_filter_config(filter_config),
            "filter_version": FILTER_VERSION,
        },
    )


async def update_saved_search(
    db: AsyncSession,
    user_id: UUID,
    search_id: UUID,
    *,
    name: str | None,
    filter_config: dict | None,
):
    search = await _owned_search(db, user_id, search_id)
    data = {}
    if name is not None:
        data["name"] = name.strip()
    if filter_config is not None:
        data.update(
            filter_config=validate_filter_config(filter_config),
            filter_version=FILTER_VERSION,
        )
    return await repositories.update_saved_search(db, search, data)


async def duplicate_saved_search(db: AsyncSession, user_id: UUID, search_id: UUID):
    search = await _owned_search(db, user_id, search_id)
    return await create_saved_search(
        db, user_id, f"{search.name} copy", search.filter_config
    )


async def delete_saved_search(db: AsyncSession, user_id: UUID, search_id: UUID) -> None:
    await repositories.delete_saved_search(
        db, await _owned_search(db, user_id, search_id)
    )


async def record_saved_search_run(
    db: AsyncSession, user_id: UUID, search_id: UUID, result_count: int
):
    search = await _owned_search(db, user_id, search_id)
    return await repositories.update_saved_search(
        db, search, {"last_run_at": datetime.now(UTC), "result_count": result_count}
    )


async def run_saved_search(db: AsyncSession, user_id: UUID, search_id: UUID):
    search = await _owned_search(db, user_id, search_id)
    version, config = migrate_filter_config(search.filter_version, search.filter_config)
    filters = DealFilters(**config)
    filters.validate()
    result = await find_deals(db, filters=filters)
    return await repositories.update_saved_search(
        db,
        search,
        {
            "filter_config": config,
            "filter_version": version,
            "last_run_at": datetime.now(UTC),
            "result_count": len(result.deals),
        },
    )


async def _owned_search(db: AsyncSession, user_id: UUID, search_id: UUID):
    search = await repositories.get_saved_search_for_user(db, search_id, user_id)
    if search is None:
        raise ServiceNotFoundError("Saved search not found")
    return search
