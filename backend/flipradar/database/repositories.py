from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flipradar.api.schemas.validation import MarketplaceName, normalize_set_number
from flipradar.domain.models import (
    AccountToken,
    Color,
    DealScoreNotification,
    Element,
    EndedListingNotification,
    LegoSet,
    ListingEvaluation,
    Marketplace,
    MarketplaceListing,
    Notification,
    NotificationAuditLog,
    NotificationPreference,
    Part,
    PartCategory,
    Portfolio,
    PortfolioAnalysis,
    PortfolioAnalyticsSnapshot,
    PortfolioHoldingAnalytics,
    PortfolioItem,
    PortfolioItemValuationSnapshot,
    PortfolioValuationDailyRollup,
    PortfolioValuationSnapshot,
    PriceDropNotification,
    PriceSnapshot,
    PriceSnapshotRollup,
    Recommendation,
    RefreshTokenBlacklist,
    RefreshTokenSession,
    SavedSearch,
    TargetReachedNotification,
    User,
    UserNotificationSettings,
    WatchlistItem,
    WatchlistMonitoringPreference,
    WatchlistPriceHistory,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 500


class RepositoryError(Exception):
    """Base class for expected repository failures."""


class DuplicateRecordError(RepositoryError):
    """Raised when a uniqueness constraint rejects a duplicate action."""


class ConflictRecordError(RepositoryError):
    """Raised when a write conflicts with current database state."""


class LegoSetCatalogRepository:
    """Persistence boundary for catalog reads and conflict-safe writes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_number(self, set_number: str) -> LegoSet | None:
        return await get_set_by_number(self.db, set_number)

    async def list(
        self,
        *,
        pagination: Pagination | None = None,
        theme: str | None = None,
        query: str | None = None,
        order: str = "set_number",
    ) -> list[LegoSet]:
        return await list_sets(
            self.db,
            pagination=pagination,
            theme=theme,
            query=query,
            order=order,
        )

    async def upsert(self, set_data: dict[str, Any]) -> LegoSet:
        """Insert a set or update its catalog metadata by canonical set number."""
        payload = dict(set_data)
        payload["set_number"] = normalize_set_number(payload["set_number"])
        dialect_name = self.db.bind.dialect.name if self.db.bind is not None else ""
        insert = postgresql_insert if dialect_name == "postgresql" else sqlite_insert
        statement = insert(LegoSet).values(**payload)
        update_values = {
            key: value for key, value in payload.items() if key != "set_number"
        }
        update_values["updated_at"] = func.now()
        statement = statement.on_conflict_do_update(
            index_elements=[LegoSet.set_number], set_=update_values
        )
        await self.db.execute(statement)
        await self.db.flush()
        result = await self.get_by_number(payload["set_number"])
        if result is None:  # pragma: no cover - defensive database invariant
            raise RepositoryError("LEGO set upsert did not return a record")
        await self.db.refresh(result)
        return result


class PartCatalogRepository:
    """Persistence boundary for idempotent part catalog synchronization."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _upsert_catalog_entity(self, model, payload: dict[str, Any]):
        result = await self.db.execute(
            select(model).where(
                model.canonical_identifier == payload["canonical_identifier"]
            )
        )
        entity = result.scalar_one_or_none()
        if entity is None:
            entity = model(**payload)
            self.db.add(entity)
        else:
            entity.provider_identifiers = {
                **(entity.provider_identifiers or {}),
                **payload["provider_identifiers"],
            }
            entity.name = payload["name"]
            entity.aliases = _merge_catalog_values(entity.aliases, payload["aliases"])
            entity.mold_variants = _merge_catalog_values(
                entity.mold_variants, payload["mold_variants"]
            )
            entity.image_urls = _merge_catalog_values(
                entity.image_urls, payload["image_urls"]
            )
            entity.quality_flags = payload["quality_flags"]
            for field in (
                "first_known_year",
                "last_known_year",
                "source_name",
                "source_url",
                "source_updated_at",
                "fetched_at",
            ):
                setattr(entity, field, payload.get(field))
            for field in ("market_price", "market_price_currency"):
                if field in payload:
                    setattr(entity, field, payload[field])
        await self.db.flush()
        return entity

    async def upsert_category(self, payload: dict[str, Any]) -> PartCategory:
        return await self._upsert_catalog_entity(PartCategory, payload)

    async def upsert_color(self, payload: dict[str, Any]) -> Color:
        return await self._upsert_catalog_entity(Color, payload)

    async def upsert_part(self, payload: dict[str, Any]) -> Part:
        return await self._upsert_catalog_entity(Part, payload)

    async def upsert_element(self, payload: dict[str, Any]) -> Element:
        return await self._upsert_catalog_entity(Element, payload)

    async def upsert_record(self, record) -> Part:
        category = await self.upsert_category(record.category)
        color = await self.upsert_color(record.color)
        part = await self.upsert_part({**record.part, "category_id": category.id})
        part.category_id = category.id
        element = await self.upsert_element(
            {**record.element, "part_id": part.id, "color_id": color.id}
        )
        if element.part_id != part.id:
            element.part_id = part.id
        if element.color_id != color.id:
            element.color_id = color.id
        await self.db.flush()
        result = await self.db.execute(
            select(Part)
            .options(
                selectinload(Part.category),
                selectinload(Part.elements).selectinload(Element.color),
            )
            .execution_options(populate_existing=True)
            .where(Part.id == part.id)
        )
        return result.scalar_one()

    async def search(
        self,
        query: str,
        *,
        pagination: Pagination,
        color: str | None = None,
        category: str | None = None,
        year: int | None = None,
    ) -> list[Part]:
        page = await self.search_page(
            query,
            pagination=pagination,
            color=color,
            category=category,
            year=year,
        )
        return [match.part for match in page.matches]

    async def search_page(
        self,
        query: str,
        *,
        pagination: Pagination,
        color: str | None = None,
        category: str | None = None,
        year: int | None = None,
    ) -> PartCatalogSearchPage:
        """Search parts locally, ranking identifiers and strong text matches first.

        Catalog aliases are JSON documents and fuzzy matching needs to compare the
        complete descriptive record, so scoring is intentionally performed after
        eager loading the catalog records.  Pagination is applied only after that
        ranking so an exact match can never be hidden behind alphabetical rows.
        """
        normalized = _normalize_catalog_text(query)
        statement = (
            select(Part)
            .options(
                selectinload(Part.category),
                selectinload(Part.elements).selectinload(Element.color),
            )
            .execution_options(populate_existing=True)
            .order_by(Part.name, Part.canonical_identifier)
        )
        result = await self.db.execute(statement)
        candidates = list(result.scalars().unique())
        ranked = [
            PartCatalogSearchMatch(part=part, relevance=relevance)
            for part in candidates
            if (relevance := _part_match_relevance(part, normalized)) is not None
            and _part_matches_filters(part, color=color, category=category, year=year)
        ]
        ranked.sort(
            key=lambda item: (
                -item.relevance.score,
                item.part.name,
                item.part.canonical_identifier,
            )
        )
        return PartCatalogSearchPage(
            matches=ranked[pagination.offset : pagination.offset + pagination.limit],
            total=len(ranked),
        )


@dataclass(frozen=True)
class PartSearchRelevance:
    score: int
    match_type: str
    confidence: str
    explanation: str


@dataclass(frozen=True)
class PartCatalogSearchMatch:
    part: Part
    relevance: PartSearchRelevance


@dataclass(frozen=True)
class PartCatalogSearchPage:
    matches: list[PartCatalogSearchMatch]
    total: int


def _normalize_catalog_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _compact_catalog_text(value: str) -> str:
    return "".join(
        character for character in _normalize_catalog_text(value) if character.isalnum()
    )


def _part_match_relevance(part: Part, query: str) -> PartSearchRelevance | None:
    """Return a deterministic relevance score for a local part lookup."""
    compact_query = _compact_catalog_text(query)
    identifier_values = [
        part.canonical_identifier,
        part.canonical_identifier.removeprefix("part:"),
        *(part.provider_identifiers or {}).values(),
    ]
    if any(
        _compact_catalog_text(value) == compact_query for value in identifier_values
    ):
        return PartSearchRelevance(
            score=1_000,
            match_type="exact_part_number",
            confidence="exact",
            explanation="Exact part number match.",
        )

    name = _normalize_catalog_text(part.name)
    aliases = [_normalize_catalog_text(alias) for alias in part.aliases or []]
    if name == query:
        return PartSearchRelevance(
            score=900,
            match_type="exact_name",
            confidence="exact",
            explanation="Exact part name match.",
        )
    if query in aliases:
        return PartSearchRelevance(
            score=850,
            match_type="exact_alias",
            confidence="exact",
            explanation="Exact alternate part name match.",
        )
    if query in name:
        return PartSearchRelevance(
            score=700,
            match_type="name_text",
            confidence="high",
            explanation="Part name contains your search text.",
        )
    if any(query in alias for alias in aliases):
        return PartSearchRelevance(
            score=650,
            match_type="alias_text",
            confidence="high",
            explanation="An alternate part name contains your search text.",
        )

    # Avoid fuzzy matching one- or two-character queries: those are usually an
    # incomplete text search and would produce noisy catalog results.
    if len(compact_query) < 3:
        return None
    best_ratio = max(
        SequenceMatcher(None, compact_query, _compact_catalog_text(value)).ratio()
        for value in [part.name, *(part.aliases or [])]
    )
    if best_ratio < 0.72:
        return None
    return PartSearchRelevance(
        score=500 + round(best_ratio * 100),
        match_type="fuzzy",
        confidence="high" if best_ratio >= 0.85 else "medium",
        explanation=f"Close spelling match ({round(best_ratio * 100)}% similar).",
    )


def _part_matches_filters(
    part: Part,
    *,
    color: str | None,
    category: str | None,
    year: int | None,
) -> bool:
    if color and not any(
        _catalog_entity_matches(color_entity, color)
        for color_entity in part.available_colors
    ):
        return False
    if category and (
        part.category is None or not _catalog_entity_matches(part.category, category)
    ):
        return False
    if year is not None and (
        (part.first_known_year is not None and part.first_known_year > year)
        or (part.last_known_year is not None and part.last_known_year < year)
    ):
        return False
    return True


def _catalog_entity_matches(entity: Color | PartCategory, filter_value: str) -> bool:
    query = _normalize_catalog_text(filter_value)
    values = [
        entity.name,
        entity.canonical_identifier,
        entity.canonical_identifier.split(":", 1)[-1],
        *(entity.aliases or []),
        *((entity.provider_identifiers or {}).values()),
    ]
    return any(query == _normalize_catalog_text(value) for value in values)


def _merge_catalog_values(existing: list | None, incoming: list | None) -> list:
    """Merge JSON list values without losing variants during a provider refresh."""
    merged: list = []
    seen: set[str] = set()
    for value in [*(existing or []), *(incoming or [])]:
        key = json.dumps(value, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            merged.append(value)
    return merged


@dataclass(frozen=True)
class Pagination:
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit", min(max(self.limit, 1), MAX_PAGE_LIMIT))
        object.__setattr__(self, "offset", max(self.offset, 0))


def page(limit: int = DEFAULT_PAGE_LIMIT, offset: int = 0) -> Pagination:
    return Pagination(limit=limit, offset=offset)


def _apply_pagination(statement, pagination: Pagination):
    return statement.limit(pagination.limit).offset(pagination.offset)


def _marketplace_base_url(marketplace_name: str) -> str | None:
    if marketplace_name == MarketplaceName.EBAY.value:
        return "https://www.ebay.com"
    if marketplace_name == MarketplaceName.BRICKLINK.value:
        return "https://www.bricklink.com"
    return None


def _normalize_marketplace(marketplace_name: str) -> str:
    normalized_name = marketplace_name.lower().strip()
    if normalized_name not in {marketplace.value for marketplace in MarketplaceName}:
        raise ValueError("Unsupported marketplace")
    return normalized_name


# User repository
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
        db.add(Portfolio(user_id=user.id, name="Default Portfolio", currency="USD", is_default=True))
        await db.flush()
        await db.refresh(user)
    except IntegrityError as exc:
        raise DuplicateRecordError("User already exists") from exc
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating user")
        raise
    return user


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    normalized = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized))
    return result.scalar_one_or_none()


async def update_user_display_name(
    db: AsyncSession, user: User, display_name: str | None
) -> User:
    user.display_name = display_name
    await db.flush()
    await db.refresh(user)
    return user


async def mark_user_email_verified(
    db: AsyncSession, user: User, verified_at: datetime
) -> User:
    user.is_email_verified = True
    user.email_verified_at = verified_at
    await db.flush()
    await db.refresh(user)
    return user


async def update_user_password_hash(
    db: AsyncSession, user: User, hashed_password: str
) -> User:
    user.hashed_password = hashed_password
    await db.flush()
    await db.refresh(user)
    return user


async def schedule_user_deletion(
    db: AsyncSession,
    user: User,
    *,
    requested_at: datetime,
    scheduled_at: datetime,
) -> User:
    user.deletion_requested_at = requested_at
    user.deletion_scheduled_at = scheduled_at
    await db.flush()
    await db.refresh(user)
    return user


async def delete_users_scheduled_for_deletion(db: AsyncSession, now: datetime) -> int:
    result = await db.execute(
        delete(User).where(
            User.deletion_scheduled_at.is_not(None),
            User.deletion_scheduled_at <= now,
        )
    )
    await db.flush()
    return cast(CursorResult, result).rowcount or 0


async def stage_user_email_change(
    db: AsyncSession, user: User, pending_email: str
) -> User:
    user.pending_email = pending_email
    try:
        await db.flush()
        await db.refresh(user)
    except IntegrityError as exc:
        raise DuplicateRecordError("Email already exists") from exc
    return user


async def apply_user_email_change(
    db: AsyncSession, user: User, new_email: str, verified_at: datetime
) -> User:
    user.email = new_email
    user.pending_email = None
    user.is_email_verified = True
    user.email_verified_at = verified_at
    try:
        await db.flush()
        await db.refresh(user)
    except IntegrityError as exc:
        raise DuplicateRecordError("Email already exists") from exc
    return user


async def create_account_token_record(
    db: AsyncSession,
    *,
    user_id: UUID,
    purpose: str,
    token_hash: str,
    token_jti: str,
    expires_at: datetime,
    last_sent_at: datetime | None = None,
    sent_count: int = 0,
) -> AccountToken:
    token = AccountToken(
        user_id=user_id,
        purpose=purpose,
        token_hash=token_hash,
        token_jti=token_jti,
        expires_at=expires_at,
        last_sent_at=last_sent_at,
        sent_count=sent_count,
    )
    db.add(token)
    try:
        await db.flush()
        await db.refresh(token)
    except IntegrityError as exc:
        raise DuplicateRecordError("Account token already exists") from exc
    return token


async def get_account_token_by_hash(
    db: AsyncSession, token_hash: str, purpose: str
) -> AccountToken | None:
    result = await db.execute(
        select(AccountToken)
        .options(selectinload(AccountToken.user))
        .where(
            AccountToken.token_hash == token_hash,
            AccountToken.purpose == purpose,
        )
    )
    return result.scalar_one_or_none()


async def get_latest_account_token_for_user(
    db: AsyncSession, user_id: UUID, purpose: str
) -> AccountToken | None:
    result = await db.execute(
        select(AccountToken)
        .where(AccountToken.user_id == user_id, AccountToken.purpose == purpose)
        .order_by(AccountToken.created_at.desc(), AccountToken.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def mark_account_token_sent(
    db: AsyncSession, token: AccountToken, sent_at: datetime
) -> AccountToken:
    token.last_sent_at = sent_at
    token.sent_count += 1
    await db.flush()
    await db.refresh(token)
    return token


async def mark_account_token_used(
    db: AsyncSession, token: AccountToken, used_at: datetime
) -> AccountToken:
    token.used_at = used_at
    await db.flush()
    await db.refresh(token)
    return token


async def revoke_account_tokens_for_user(
    db: AsyncSession,
    *,
    user_id: UUID,
    purpose: str,
    revoked_at: datetime,
    reason: str,
) -> None:
    result = await db.execute(
        select(AccountToken).where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
            AccountToken.revoked_at.is_(None),
        )
    )
    for token in result.scalars():
        token.revoked_at = revoked_at
        token.revoked_reason = reason
    await db.flush()


async def is_refresh_token_blacklisted(db: AsyncSession, token_hash: str) -> bool:
    result = await db.execute(
        select(RefreshTokenBlacklist.id).where(
            RefreshTokenBlacklist.token_hash == token_hash
        )
    )
    return result.scalar_one_or_none() is not None


async def blacklist_refresh_token(
    db: AsyncSession,
    *,
    user_id: UUID,
    token_hash: str,
    token_jti: str,
    expires_at: datetime,
    reason: str,
) -> RefreshTokenBlacklist:
    token = RefreshTokenBlacklist(
        user_id=user_id,
        token_hash=token_hash,
        token_jti=token_jti,
        expires_at=expires_at,
        reason=reason,
    )
    db.add(token)
    try:
        await db.flush()
        await db.refresh(token)
    except IntegrityError as exc:
        raise DuplicateRecordError("Refresh token already revoked") from exc
    return token


async def create_refresh_token_session(
    db: AsyncSession,
    *,
    user_id: UUID,
    token_hash: str,
    token_jti: str,
    expires_at: datetime,
    last_seen_at: datetime,
) -> RefreshTokenSession:
    session = RefreshTokenSession(
        user_id=user_id,
        token_hash=token_hash,
        token_jti=token_jti,
        expires_at=expires_at,
        last_seen_at=last_seen_at,
    )
    db.add(session)
    try:
        await db.flush()
        await db.refresh(session)
    except IntegrityError as exc:
        raise DuplicateRecordError("Refresh token session already exists") from exc
    return session


async def get_refresh_token_session_by_hash(
    db: AsyncSession, token_hash: str
) -> RefreshTokenSession | None:
    result = await db.execute(
        select(RefreshTokenSession).where(RefreshTokenSession.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def list_active_refresh_token_sessions_for_user(
    db: AsyncSession, user_id: UUID, now: datetime
) -> list[RefreshTokenSession]:
    result = await db.execute(
        select(RefreshTokenSession)
        .where(
            RefreshTokenSession.user_id == user_id,
            RefreshTokenSession.revoked_at.is_(None),
            RefreshTokenSession.expires_at > now,
        )
        .order_by(
            RefreshTokenSession.last_seen_at.desc(),
            RefreshTokenSession.created_at.desc(),
        )
    )
    return list(result.scalars())


async def get_refresh_token_session_for_user(
    db: AsyncSession, user_id: UUID, session_id: UUID
) -> RefreshTokenSession | None:
    result = await db.execute(
        select(RefreshTokenSession).where(
            RefreshTokenSession.id == session_id,
            RefreshTokenSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def mark_refresh_token_session_seen(
    db: AsyncSession, session: RefreshTokenSession, seen_at: datetime
) -> RefreshTokenSession:
    session.last_seen_at = seen_at
    await db.flush()
    await db.refresh(session)
    return session


async def revoke_refresh_token_session(
    db: AsyncSession,
    session: RefreshTokenSession,
    *,
    revoked_at: datetime,
    reason: str,
) -> RefreshTokenSession:
    session.revoked_at = revoked_at
    session.revoked_reason = reason
    await db.flush()
    await db.refresh(session)
    return session


async def revoke_active_refresh_token_sessions_for_user(
    db: AsyncSession,
    *,
    user_id: UUID,
    revoked_at: datetime,
    reason: str,
) -> list[RefreshTokenSession]:
    sessions = await list_active_refresh_token_sessions_for_user(
        db, user_id, revoked_at
    )
    for session in sessions:
        session.revoked_at = revoked_at
        session.revoked_reason = reason
    await db.flush()
    return sessions


# Set repository
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


async def create_set(db: AsyncSession, set_data: dict[str, Any]) -> LegoSet:
    lego_set = LegoSet(**set_data)
    db.add(lego_set)
    try:
        await db.flush()
        await db.refresh(lego_set)
    except IntegrityError as exc:
        raise DuplicateRecordError("LEGO set already exists") from exc
    return lego_set


async def list_sets(
    db: AsyncSession,
    *,
    pagination: Pagination | None = None,
    theme: str | None = None,
    query: str | None = None,
    order: str = "set_number",
) -> list[LegoSet]:
    pagination = pagination or page()
    statement = select(LegoSet)
    if theme:
        statement = statement.where(func.lower(LegoSet.theme) == theme.strip().lower())
    if query:
        normalized_query = f"%{query.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(LegoSet.set_number).like(normalized_query),
                func.lower(LegoSet.name).like(normalized_query),
            )
        )
    if order == "release_year_desc":
        statement = statement.order_by(LegoSet.release_year.desc().nullslast())
    elif order == "created_at_desc":
        statement = statement.order_by(LegoSet.created_at.desc())
    else:
        statement = statement.order_by(LegoSet.set_number.asc())
    result = await db.execute(_apply_pagination(statement, pagination))
    return list(result.scalars())


# Marketplace repository
async def get_marketplace_by_name(
    db: AsyncSession, marketplace_name: str
) -> Marketplace | None:
    normalized_name = _normalize_marketplace(marketplace_name)
    result = await db.execute(
        select(Marketplace).where(Marketplace.name == normalized_name)
    )
    return result.scalar_one_or_none()


async def get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    normalized_name = _normalize_marketplace(marketplace_name)
    result = await db.execute(
        select(Marketplace).where(Marketplace.name == normalized_name)
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is not None:
        return marketplace

    marketplace = Marketplace(
        name=normalized_name,
        display_name=normalized_name.title(),
        base_url=_marketplace_base_url(normalized_name),
        fee_percent=0,
    )
    db.add(marketplace)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateRecordError("Marketplace already exists") from exc
    return marketplace


# Listing repository
async def get_existing_listing(
    db: AsyncSession, marketplace_id: UUID, external_listing_id: str
) -> MarketplaceListing | None:
    result = await db.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.marketplace_id == marketplace_id,
            MarketplaceListing.external_listing_id == external_listing_id,
        )
    )
    return result.scalar_one_or_none()


async def create_listing(
    db: AsyncSession,
    *,
    lego_set_id: UUID,
    marketplace_id: UUID,
    listing_data: dict[str, Any],
) -> MarketplaceListing:
    listing = MarketplaceListing(
        lego_set_id=lego_set_id,
        marketplace_id=marketplace_id,
        **listing_data,
    )
    db.add(listing)
    try:
        await db.flush()
        await db.refresh(listing)
    except IntegrityError as exc:
        raise DuplicateRecordError("Marketplace listing already exists") from exc
    return listing


async def update_listing(
    db: AsyncSession, listing: MarketplaceListing, listing_data: dict[str, Any]
) -> MarketplaceListing:
    """Refresh a known provider listing without creating a duplicate row."""
    for key, value in listing_data.items():
        setattr(listing, key, value)
    listing.last_seen_at = func.now()
    await db.flush()
    await db.refresh(listing)
    return listing


async def get_listing_for_evaluation(
    db: AsyncSession, listing_id: UUID
) -> MarketplaceListing | None:
    result = await db.execute(
        select(MarketplaceListing)
        .options(
            selectinload(MarketplaceListing.lego_set),
            selectinload(MarketplaceListing.marketplace),
        )
        .where(MarketplaceListing.id == listing_id)
    )
    return result.scalar_one_or_none()


async def create_listing_evaluation(
    db: AsyncSession, *, listing_id: UUID, evaluation_data: dict[str, Any]
) -> ListingEvaluation:
    evaluation = ListingEvaluation(listing_id=listing_id, **evaluation_data)
    db.add(evaluation)
    await db.flush()
    await db.refresh(evaluation)
    return evaluation


async def list_listings_for_set(
    db: AsyncSession,
    set_number: str,
    *,
    pagination: Pagination | None = None,
    condition: str | None = None,
    listing_status: str | None = None,
    marketplace_name: str | None = None,
    order: str = "last_seen_desc",
) -> list[MarketplaceListing]:
    pagination = pagination or page()
    normalized_set_number = normalize_set_number(set_number)
    statement = select(MarketplaceListing).join(LegoSet).join(Marketplace)
    statement = statement.where(LegoSet.set_number == normalized_set_number)
    if condition:
        statement = statement.where(MarketplaceListing.condition == condition)
    if listing_status:
        statement = statement.where(MarketplaceListing.listing_status == listing_status)
    if marketplace_name:
        statement = statement.where(
            Marketplace.name == _normalize_marketplace(marketplace_name)
        )
    if order == "price_asc":
        statement = statement.order_by(MarketplaceListing.total_price.asc())
    elif order == "price_desc":
        statement = statement.order_by(MarketplaceListing.total_price.desc())
    else:
        statement = statement.order_by(
            MarketplaceListing.last_seen_at.desc(),
            MarketplaceListing.created_at.desc(),
        )
    result = await db.execute(_apply_pagination(statement, pagination))
    return list(result.scalars())


async def latest_listing_for_set(
    db: AsyncSession, set_number: str
) -> MarketplaceListing | None:
    listings = await list_listings_for_set(
        db, set_number, pagination=Pagination(limit=1, offset=0)
    )
    return listings[0] if listings else None


async def list_active_listings_for_set_numbers(
    db: AsyncSession,
    set_numbers: set[str],
    *,
    seen_since: datetime,
) -> list[MarketplaceListing]:
    """Return the recent active listings needed by deal discovery in one query."""
    if not set_numbers:
        return []
    normalized_set_numbers = {
        normalize_set_number(set_number) for set_number in set_numbers
    }
    result = await db.execute(
        select(MarketplaceListing)
        .options(
            selectinload(MarketplaceListing.lego_set),
            selectinload(MarketplaceListing.marketplace),
        )
        .join(LegoSet)
        .where(
            LegoSet.set_number.in_(normalized_set_numbers),
            MarketplaceListing.listing_status == "active",
            MarketplaceListing.last_seen_at >= seen_since,
        )
        .order_by(
            MarketplaceListing.last_seen_at.desc(),
            MarketplaceListing.created_at.desc(),
        )
    )
    return list(result.scalars())


async def bulk_create_marketplace_listings(
    db: AsyncSession,
    *,
    lego_set_id: UUID,
    marketplace_id: UUID,
    listings_data: list[dict[str, Any]],
    skip_duplicates: bool = True,
) -> list[MarketplaceListing]:
    if not listings_data:
        return []
    if skip_duplicates:
        unique_listings = []
        external_ids = set()
        for item in listings_data:
            external_listing_id = item["external_listing_id"]
            if external_listing_id not in external_ids:
                external_ids.add(external_listing_id)
                unique_listings.append(item)
        result = await db.execute(
            select(MarketplaceListing.external_listing_id).where(
                MarketplaceListing.marketplace_id == marketplace_id,
                MarketplaceListing.external_listing_id.in_(external_ids),
            )
        )
        existing_ids = set(result.scalars())
        listings_data = [
            item
            for item in unique_listings
            if item["external_listing_id"] not in existing_ids
        ]
    listings = [
        MarketplaceListing(
            lego_set_id=lego_set_id,
            marketplace_id=marketplace_id,
            **listing_data,
        )
        for listing_data in listings_data
    ]
    db.add_all(listings)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateRecordError("Marketplace listing already exists") from exc
    return listings


async def mark_stale_marketplace_listings(
    db: AsyncSession,
    *,
    lego_set_id: UUID,
    stale_before: datetime,
) -> int:
    """Mark active listings unseen before the cutoff as removed."""
    result = await db.execute(
        update(MarketplaceListing)
        .where(
            MarketplaceListing.lego_set_id == lego_set_id,
            MarketplaceListing.listing_status == "active",
            MarketplaceListing.last_seen_at < stale_before,
        )
        .values(listing_status="removed", updated_at=func.now())
    )
    return cast(CursorResult, result).rowcount or 0


# Price repository
async def create_price_snapshot(
    db: AsyncSession,
    *,
    lego_set_id: UUID,
    marketplace_id: UUID,
    snapshot_data: dict[str, Any],
) -> PriceSnapshot:
    snapshot = PriceSnapshot(
        lego_set_id=lego_set_id,
        marketplace_id=marketplace_id,
        **snapshot_data,
    )
    db.add(snapshot)
    try:
        await db.flush()
        await db.refresh(snapshot)
    except IntegrityError as exc:
        raise DuplicateRecordError("Price snapshot already exists") from exc
    return snapshot


async def bulk_create_price_snapshots(
    db: AsyncSession, snapshots_data: list[dict[str, Any]]
) -> list[PriceSnapshot]:
    snapshots = [PriceSnapshot(**snapshot_data) for snapshot_data in snapshots_data]
    db.add_all(snapshots)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateRecordError("Price snapshot already exists") from exc
    return snapshots


async def latest_price_snapshot_retrieval_time(
    db: AsyncSession, set_number: str
) -> datetime | None:
    normalized_set_number = normalize_set_number(set_number)
    result = await db.execute(
        select(func.max(PriceSnapshot.retrieval_time))
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
    )
    return result.scalar_one()


async def delete_price_snapshots_before(db: AsyncSession, cutoff: datetime) -> int:
    result = await db.execute(
        delete(PriceSnapshot).where(PriceSnapshot.retrieval_time < cutoff)
    )
    await db.flush()
    return cast(CursorResult, result).rowcount or 0


async def get_price_snapshots_before(
    db: AsyncSession, cutoff: datetime
) -> list[PriceSnapshot]:
    """Return raw observations that are ready to be compacted."""
    result = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.retrieval_time < cutoff)
        .order_by(PriceSnapshot.retrieval_time.asc(), PriceSnapshot.created_at.asc())
    )
    return list(result.scalars())


async def upsert_price_snapshot_rollup(
    db: AsyncSession, rollup_data: dict[str, Any]
) -> None:
    """Persist one aggregate period, replacing it when a compaction is rerun."""
    key_fields = (
        "lego_set_id",
        "marketplace_id",
        "condition",
        "currency",
        "metric_type",
        "period",
        "period_start",
    )
    statement = select(PriceSnapshotRollup).where(
        *[
            getattr(PriceSnapshotRollup, field) == rollup_data[field]
            for field in key_fields
        ]
    )
    existing = (await db.execute(statement)).scalar_one_or_none()
    if existing is None:
        db.add(PriceSnapshotRollup(**rollup_data))
        return
    for field, value in rollup_data.items():
        if field not in key_fields:
            setattr(existing, field, value)


async def list_price_history_for_set(
    db: AsyncSession,
    set_number: str,
    *,
    period: str | None = None,
    condition: str | None = None,
    metric_type: str | None = None,
    currency: str | None = None,
) -> tuple[list[PriceSnapshot], list[PriceSnapshotRollup]]:
    """Load raw and compacted history for analytics without overlapping periods."""
    normalized_set_number = normalize_set_number(set_number)
    raw = (
        select(PriceSnapshot)
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
    )
    rollups = (
        select(PriceSnapshotRollup)
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
    )
    if condition:
        raw = raw.where(PriceSnapshot.condition == condition)
        rollups = rollups.where(PriceSnapshotRollup.condition == condition)
    if metric_type:
        raw = raw.where(PriceSnapshot.metric_type == metric_type)
        rollups = rollups.where(PriceSnapshotRollup.metric_type == metric_type)
    if currency:
        raw = raw.where(PriceSnapshot.currency == currency)
        rollups = rollups.where(PriceSnapshotRollup.currency == currency)
    if period:
        rollups = rollups.where(PriceSnapshotRollup.period == period)
    raw_rows = list((await db.execute(raw)).scalars())
    rollup_rows = list((await db.execute(rollups)).scalars())
    return raw_rows, rollup_rows


async def list_price_snapshots_for_set(
    db: AsyncSession,
    set_number: str,
    *,
    pagination: Pagination | None = None,
    condition: str | None = None,
    marketplace_name: str | None = None,
    metric_type: str | None = None,
    order: str = "snapshot_desc",
) -> list[PriceSnapshot]:
    pagination = pagination or page()
    normalized_set_number = normalize_set_number(set_number)
    statement = (
        select(PriceSnapshot)
        .options(
            selectinload(PriceSnapshot.marketplace),
            selectinload(PriceSnapshot.lego_set),
        )
        .join(LegoSet)
        .join(Marketplace)
        .where(LegoSet.set_number == normalized_set_number)
    )
    if condition:
        statement = statement.where(PriceSnapshot.condition == condition)
    if marketplace_name:
        statement = statement.where(
            Marketplace.name == _normalize_marketplace(marketplace_name)
        )
    if metric_type:
        statement = statement.where(PriceSnapshot.metric_type == metric_type)
    if order == "created_at_desc":
        statement = statement.order_by(PriceSnapshot.created_at.desc())
    else:
        statement = statement.order_by(
            PriceSnapshot.retrieval_time.desc(), PriceSnapshot.created_at.desc()
        )
    result = await db.execute(_apply_pagination(statement, pagination))
    return list(result.scalars())


async def get_recent_snapshots_by_set_number(
    db: AsyncSession, set_number: str, limit: int = 10
) -> list[PriceSnapshot]:
    return await list_price_snapshots_for_set(
        db, set_number, pagination=Pagination(limit=limit, offset=0)
    )


async def get_latest_price_snapshot_by_set_number(
    db: AsyncSession, set_number: str
) -> PriceSnapshot | None:
    snapshots = await get_recent_snapshots_by_set_number(db, set_number, limit=1)
    snapshot = snapshots[0] if snapshots else None
    if snapshot is None:
        logger.info(
            "important missing data no latest snapshot set_number=%s", set_number
        )
    return snapshot


async def get_latest_snapshots_by_set_number(
    db: AsyncSession, set_number: str
) -> list[PriceSnapshot]:
    recent_snapshots = await get_recent_snapshots_by_set_number(
        db, set_number, limit=50
    )
    latest_by_marketplace_condition_metric = {}
    for snapshot in recent_snapshots:
        latest_by_marketplace_condition_metric.setdefault(
            (snapshot.marketplace_id, snapshot.condition, snapshot.metric_type),
            snapshot,
        )
    snapshots = list(latest_by_marketplace_condition_metric.values())
    if not snapshots:
        logger.info(
            "important missing data no snapshots set_number=%s snapshot_count=0",
            set_number,
        )
    return snapshots


async def get_latest_snapshots_for_set_numbers(
    db: AsyncSession, set_numbers: set[str]
) -> dict[str, list[PriceSnapshot]]:
    if not set_numbers:
        return {}
    normalized_set_numbers = {
        normalize_set_number(set_number) for set_number in set_numbers
    }
    result = await db.execute(
        select(PriceSnapshot)
        .options(
            selectinload(PriceSnapshot.marketplace),
            selectinload(PriceSnapshot.lego_set),
        )
        .join(LegoSet)
        .where(LegoSet.set_number.in_(normalized_set_numbers))
        .order_by(
            LegoSet.set_number.asc(),
            PriceSnapshot.retrieval_time.desc(),
            PriceSnapshot.created_at.desc(),
        )
    )
    latest_by_set_and_marketplace: dict[
        str, dict[tuple[UUID, str, str], PriceSnapshot]
    ] = defaultdict(dict)
    for snapshot in result.scalars():
        set_number = snapshot.lego_set.set_number
        latest_by_set_and_marketplace[set_number].setdefault(
            (snapshot.marketplace_id, snapshot.condition, snapshot.metric_type),
            snapshot,
        )
    return {
        set_number: list(by_marketplace.values())
        for set_number, by_marketplace in latest_by_set_and_marketplace.items()
    }


async def get_price_snapshots_for_set_numbers(
    db: AsyncSession,
    set_numbers: set[str],
    *,
    since: datetime,
) -> dict[str, list[PriceSnapshot]]:
    """Load bounded historical price evidence for a portfolio refresh."""
    if not set_numbers:
        return {}
    normalized_set_numbers = {
        normalize_set_number(set_number) for set_number in set_numbers
    }
    result = await db.execute(
        select(PriceSnapshot)
        .options(
            selectinload(PriceSnapshot.marketplace),
            selectinload(PriceSnapshot.lego_set),
        )
        .join(LegoSet)
        .where(
            LegoSet.set_number.in_(normalized_set_numbers),
            PriceSnapshot.retrieval_time >= since,
        )
        .order_by(PriceSnapshot.retrieval_time.asc(), PriceSnapshot.created_at.asc())
    )
    snapshots_by_set: dict[str, list[PriceSnapshot]] = defaultdict(list)
    for snapshot in result.scalars():
        snapshots_by_set[snapshot.lego_set.set_number].append(snapshot)
    return dict(snapshots_by_set)


async def get_active_listing_supply_for_set_numbers(
    db: AsyncSession, set_numbers: set[str]
) -> dict[str, list[MarketplaceListing]]:
    """Return verified active listings for user-owned sets only."""
    if not set_numbers:
        return {}
    normalized_set_numbers = {
        normalize_set_number(set_number) for set_number in set_numbers
    }
    result = await db.execute(
        select(MarketplaceListing)
        .options(
            selectinload(MarketplaceListing.marketplace),
            selectinload(MarketplaceListing.lego_set),
        )
        .join(LegoSet)
        .where(
            LegoSet.set_number.in_(normalized_set_numbers),
            MarketplaceListing.listing_status == "active",
            MarketplaceListing.is_verified.is_(True),
        )
        .order_by(MarketplaceListing.last_seen_at.desc())
    )
    listings_by_set: dict[str, list[MarketplaceListing]] = defaultdict(list)
    for listing in result.scalars():
        listings_by_set[listing.lego_set.set_number].append(listing)
    return dict(listings_by_set)


# Portfolio repository
async def get_default_portfolio_for_user(
    db: AsyncSession, user_id: UUID, *, create_if_missing: bool = True
) -> Portfolio | None:
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user_id, Portfolio.is_default.is_(True))
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is not None or not create_if_missing:
        return portfolio
    portfolio = Portfolio(user_id=user_id, name="Default Portfolio", currency="USD", is_default=True)
    db.add(portfolio)
    await db.flush()
    return portfolio


async def get_portfolio_by_id_for_user(
    db: AsyncSession, portfolio_id: UUID, user_id: UUID
) -> Portfolio | None:
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_portfolios_for_user(db: AsyncSession, user_id: UUID) -> list[Portfolio]:
    result = await db.execute(
        select(Portfolio)
        .where(Portfolio.user_id == user_id)
        .order_by(Portfolio.is_default.desc(), Portfolio.created_at.asc())
    )
    return list(result.scalars())


async def count_portfolios_for_user(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(select(func.count()).select_from(Portfolio).where(Portfolio.user_id == user_id))
    return int(result.scalar_one())


async def create_portfolio(db: AsyncSession, user_id: UUID, portfolio_data: dict[str, Any]) -> Portfolio:
    portfolio = Portfolio(user_id=user_id, **portfolio_data)
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def update_portfolio(db: AsyncSession, portfolio: Portfolio, portfolio_data: dict[str, Any]) -> Portfolio:
    for field_name, value in portfolio_data.items():
        setattr(portfolio, field_name, value)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def reassign_portfolio_items(
    db: AsyncSession, user_id: UUID, source_portfolio_id: UUID, target_portfolio_id: UUID
) -> int:
    result = await db.execute(
        update(PortfolioItem)
        .where(PortfolioItem.user_id == user_id, PortfolioItem.portfolio_id == source_portfolio_id)
        .values(portfolio_id=target_portfolio_id)
    )
    return int(result.rowcount or 0)


async def delete_portfolio(db: AsyncSession, portfolio: Portfolio) -> None:
    await db.delete(portfolio)
    await db.flush()


async def create_portfolio_item(
    db: AsyncSession, user_id: UUID, item_data: dict[str, Any]
) -> PortfolioItem:
    normalized_set_number = normalize_set_number(item_data["set_number"])
    lego_set = await get_set_by_number(db, normalized_set_number)
    if lego_set is None:
        raise ValueError("LEGO set not found")

    persisted_data = {
        key: value for key, value in item_data.items() if key != "set_number"
    }
    if persisted_data.get("portfolio_id") is None:
        default_portfolio = await get_default_portfolio_for_user(db, user_id)
        assert default_portfolio is not None
        persisted_data["portfolio_id"] = default_portfolio.id
    item = PortfolioItem(user_id=user_id, lego_set_id=lego_set.id, **persisted_data)
    db.add(item)
    try:
        await db.flush()
        await db.refresh(item)
        await db.refresh(item, attribute_names=["lego_set"])
    except IntegrityError as exc:
        raise ConflictRecordError("Invalid portfolio item") from exc
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating portfolio item")
        raise
    return item


async def get_portfolio_items_for_user(
    db: AsyncSession,
    user_id: UUID,
    portfolio_id: UUID | None = None,
    *,
    pagination: Pagination | None = None,
    condition: str | None = None,
    theme: str | None = None,
    year: int | None = None,
    unpaginated: bool = False,
    order: str = "created_at_desc",
) -> list[PortfolioItem]:
    if pagination is None and not unpaginated:
        pagination = page()
    statement = (
        select(PortfolioItem)
        .options(selectinload(PortfolioItem.lego_set))
        .where(PortfolioItem.user_id == user_id)
    )
    if portfolio_id is not None:
        statement = statement.where(PortfolioItem.portfolio_id == portfolio_id)
    needs_catalog_join = bool(theme) or year is not None or order.startswith("theme_")
    if needs_catalog_join:
        statement = statement.join(PortfolioItem.lego_set)
    if condition:
        statement = statement.where(PortfolioItem.condition == condition)
    if theme:
        statement = statement.where(LegoSet.theme == theme)
    if year is not None:
        statement = statement.where(LegoSet.release_year == year)
    if order == "purchase_date_asc":
        statement = statement.order_by(
            PortfolioItem.purchase_date.asc(), PortfolioItem.created_at.asc()
        )
    elif order == "purchase_date_desc":
        statement = statement.order_by(
            PortfolioItem.purchase_date.desc(), PortfolioItem.created_at.desc()
        )
    elif order == "theme_asc":
        statement = statement.order_by(
            LegoSet.theme.asc(), PortfolioItem.created_at.desc()
        )
    elif order == "theme_desc":
        statement = statement.order_by(
            LegoSet.theme.desc(), PortfolioItem.created_at.desc()
        )
    elif order == "created_at_asc":
        statement = statement.order_by(PortfolioItem.created_at.asc())
    else:
        statement = statement.order_by(PortfolioItem.created_at.desc())
    result = await db.execute(
        _apply_pagination(statement, pagination) if pagination else statement
    )
    return list(result.scalars())


async def get_all_portfolio_items_for_user(
    db: AsyncSession, user_id: UUID, portfolio_id: UUID | None = None
) -> list[PortfolioItem]:
    filters = [PortfolioItem.user_id == user_id]
    if portfolio_id is not None:
        filters.append(PortfolioItem.portfolio_id == portfolio_id)
    result = await db.execute(
        select(PortfolioItem)
        .options(selectinload(PortfolioItem.lego_set))
        .where(*filters)
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

    persisted_data = dict(item_data)
    if "set_number" in persisted_data:
        lego_set = await get_set_by_number(db, persisted_data.pop("set_number"))
        if lego_set is None:
            raise ValueError("LEGO set not found")
        item.lego_set_id = lego_set.id
        item.lego_set = lego_set

    for field_name, value in persisted_data.items():
        setattr(item, field_name, value)

    try:
        await db.flush()
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while updating portfolio item")
        raise
    return await get_portfolio_item_by_id(db, item_id, user_id)


async def delete_portfolio_item(db: AsyncSession, item_id: UUID, user_id: UUID) -> bool:
    result = cast(
        CursorResult[Any],
        await db.execute(
            delete(PortfolioItem).where(
                PortfolioItem.id == item_id, PortfolioItem.user_id == user_id
            )
        ),
    )
    return bool(result.rowcount)


async def get_portfolio_valuation_snapshot_for_window(
    db: AsyncSession, user_id: UUID, window_start: datetime
) -> PortfolioValuationSnapshot | None:
    result = await db.execute(
        select(PortfolioValuationSnapshot).where(
            PortfolioValuationSnapshot.user_id == user_id,
            PortfolioValuationSnapshot.window_start == window_start,
        )
    )
    return result.scalar_one_or_none()


async def create_portfolio_valuation_snapshot(
    db: AsyncSession,
    *,
    snapshot_data: dict[str, Any],
    item_snapshots_data: list[dict[str, Any]],
) -> PortfolioValuationSnapshot:
    snapshot = PortfolioValuationSnapshot(**snapshot_data)
    db.add(snapshot)
    await db.flush()
    db.add_all(
        [
            PortfolioItemValuationSnapshot(
                portfolio_snapshot_id=snapshot.id, **item_snapshot_data
            )
            for item_snapshot_data in item_snapshots_data
        ]
    )
    await db.flush()
    return snapshot


async def create_portfolio_analytics_snapshot(
    db: AsyncSession,
    *,
    snapshot_data: dict[str, Any],
    holding_metrics_data: list[dict[str, Any]],
) -> PortfolioAnalyticsSnapshot:
    snapshot = PortfolioAnalyticsSnapshot(**snapshot_data)
    db.add(snapshot)
    await db.flush()
    db.add_all(
        [
            PortfolioHoldingAnalytics(analytics_snapshot_id=snapshot.id, **metrics)
            for metrics in holding_metrics_data
        ]
    )
    await db.flush()
    await db.refresh(snapshot, attribute_names=["holding_metrics"])
    return snapshot


async def get_latest_portfolio_analytics_snapshot(
    db: AsyncSession, user_id: UUID
) -> PortfolioAnalyticsSnapshot | None:
    result = await db.execute(
        select(PortfolioAnalyticsSnapshot)
        .options(selectinload(PortfolioAnalyticsSnapshot.holding_metrics))
        .where(PortfolioAnalyticsSnapshot.user_id == user_id)
        .order_by(
            PortfolioAnalyticsSnapshot.generated_at.desc(),
            PortfolioAnalyticsSnapshot.created_at.desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_portfolio_analysis(
    db: AsyncSession, *, analysis_data: dict[str, Any]
) -> PortfolioAnalysis:
    analysis = PortfolioAnalysis(**analysis_data)
    db.add(analysis)
    await db.flush()
    return analysis


async def list_portfolio_analyses(
    db: AsyncSession, user_id: UUID, *, limit: int, offset: int
) -> list[PortfolioAnalysis]:
    result = await db.execute(
        select(PortfolioAnalysis)
        .where(PortfolioAnalysis.user_id == user_id)
        .where(PortfolioAnalysis.deleted_at.is_(None))
        .order_by(
            PortfolioAnalysis.generated_at.desc(), PortfolioAnalysis.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars())


async def get_portfolio_analysis_for_user(
    db: AsyncSession, user_id: UUID, analysis_id: UUID
) -> PortfolioAnalysis | None:
    result = await db.execute(
        select(PortfolioAnalysis).where(
            PortfolioAnalysis.id == analysis_id,
            PortfolioAnalysis.user_id == user_id,
            PortfolioAnalysis.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def update_portfolio_analysis_metadata(
    db: AsyncSession,
    analysis: PortfolioAnalysis,
    *,
    labels: list[str],
    annotation: str | None,
) -> PortfolioAnalysis:
    analysis.labels = labels
    analysis.annotation = annotation
    await db.flush()
    return analysis


async def delete_portfolio_analysis(
    db: AsyncSession, analysis: PortfolioAnalysis
) -> None:
    analysis.deleted_at = datetime.now(UTC)
    await db.flush()


async def get_user_ids_with_portfolio_set(
    db: AsyncSession, lego_set_id: UUID
) -> list[UUID]:
    result = await db.execute(
        select(PortfolioItem.user_id)
        .where(PortfolioItem.lego_set_id == lego_set_id)
        .distinct()
    )
    return list(result.scalars())


async def get_all_user_ids(db: AsyncSession) -> list[UUID]:
    return list((await db.execute(select(User.id))).scalars())


async def get_portfolio_snapshots_before(
    db: AsyncSession, cutoff: datetime
) -> list[PortfolioValuationSnapshot]:
    return list(
        (
            await db.execute(
                select(PortfolioValuationSnapshot)
                .where(PortfolioValuationSnapshot.snapshot_at < cutoff)
                .order_by(
                    PortfolioValuationSnapshot.user_id,
                    PortfolioValuationSnapshot.snapshot_at.desc(),
                )
            )
        ).scalars()
    )


async def upsert_portfolio_daily_rollup(
    db: AsyncSession, snapshot: PortfolioValuationSnapshot
) -> None:
    existing = (
        await db.execute(
            select(PortfolioValuationDailyRollup).where(
                PortfolioValuationDailyRollup.user_id == snapshot.user_id,
                PortfolioValuationDailyRollup.rollup_date
                == snapshot.snapshot_at.date(),
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            PortfolioValuationDailyRollup(
                user_id=snapshot.user_id,
                rollup_date=snapshot.snapshot_at.date(),
                cost_basis=snapshot.cost_basis,
                market_value=snapshot.market_value,
                gain_loss=snapshot.gain_loss,
                currency=snapshot.currency,
                snapshot_at=snapshot.snapshot_at,
            )
        )
    elif snapshot.snapshot_at > existing.snapshot_at:
        for field in (
            "cost_basis",
            "market_value",
            "gain_loss",
            "currency",
            "snapshot_at",
        ):
            setattr(existing, field, getattr(snapshot, field))


async def delete_portfolio_snapshots_before(db: AsyncSession, cutoff: datetime) -> int:
    result = await db.execute(
        delete(PortfolioValuationSnapshot)
        .where(PortfolioValuationSnapshot.snapshot_at < cutoff)
        .execution_options(synchronize_session=False)
    )
    return cast(CursorResult, result).rowcount or 0


async def list_portfolio_history(
    db: AsyncSession, user_id: UUID, start: datetime | None
) -> list[PortfolioValuationSnapshot | PortfolioValuationDailyRollup]:
    raw = select(PortfolioValuationSnapshot).where(
        PortfolioValuationSnapshot.user_id == user_id
    )
    rollups = select(PortfolioValuationDailyRollup).where(
        PortfolioValuationDailyRollup.user_id == user_id
    )
    if start is not None:
        raw = raw.where(PortfolioValuationSnapshot.snapshot_at >= start)
        rollups = rollups.where(PortfolioValuationDailyRollup.snapshot_at >= start)
    raw_rows = list((await db.execute(raw)).scalars())
    rollup_rows = list((await db.execute(rollups)).scalars())
    return sorted([*raw_rows, *rollup_rows], key=lambda snapshot: snapshot.snapshot_at)


# Recommendation repository
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


async def get_latest_recommendation_for_set(
    db: AsyncSession, set_number: str
) -> Recommendation | None:
    normalized_set_number = normalize_set_number(set_number)
    result = await db.execute(
        select(Recommendation)
        .options(selectinload(Recommendation.lego_set))
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
        .order_by(Recommendation.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# Saved search repository
async def list_saved_searches_for_user(
    db: AsyncSession, user_id: UUID
) -> list[SavedSearch]:
    result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.user_id == user_id)
        .order_by(SavedSearch.updated_at.desc())
    )
    return list(result.scalars())


async def get_saved_search_for_user(
    db: AsyncSession, search_id: UUID, user_id: UUID
) -> SavedSearch | None:
    result = await db.execute(
        select(SavedSearch).where(
            SavedSearch.id == search_id, SavedSearch.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def count_saved_searches_for_user(db: AsyncSession, user_id: UUID) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(SavedSearch)
                .where(SavedSearch.user_id == user_id)
            )
        ).scalar_one()
    )


async def create_saved_search(db: AsyncSession, data: dict[str, Any]) -> SavedSearch:
    search = SavedSearch(**data)
    db.add(search)
    await db.flush()
    await db.refresh(search)
    return search


async def update_saved_search(
    db: AsyncSession, search: SavedSearch, data: dict[str, Any]
) -> SavedSearch:
    for key, value in data.items():
        setattr(search, key, value)
    await db.flush()
    await db.refresh(search)
    return search


async def delete_saved_search(db: AsyncSession, search: SavedSearch) -> None:
    await db.delete(search)
    await db.flush()


# Watchlist repository
async def list_watchlist_items_for_user(
    db: AsyncSession, user_id: UUID, *, pagination: Pagination | None = None
) -> list[WatchlistItem]:
    statement = (
        select(WatchlistItem)
        .options(
            selectinload(WatchlistItem.lego_set),
            selectinload(WatchlistItem.listing).selectinload(
                MarketplaceListing.lego_set
            ),
        )
        .where(WatchlistItem.user_id == user_id)
        .order_by(WatchlistItem.saved_at.desc(), WatchlistItem.created_at.desc())
    )
    result = await db.execute(
        _apply_pagination(statement, pagination) if pagination else statement
    )
    return list(result.scalars())


async def list_watchlist_items_for_background_refresh(
    db: AsyncSession,
) -> list[WatchlistItem]:
    result = await db.execute(
        select(WatchlistItem).options(
            selectinload(WatchlistItem.lego_set),
            selectinload(WatchlistItem.listing).selectinload(
                MarketplaceListing.lego_set
            ),
            selectinload(WatchlistItem.listing).selectinload(
                MarketplaceListing.marketplace
            ),
        )
    )
    return list(result.scalars())


async def list_watchlist_monitoring_preferences(
    db: AsyncSession,
) -> dict[UUID, WatchlistMonitoringPreference]:
    result = await db.execute(select(WatchlistMonitoringPreference))
    return {preference.user_id: preference for preference in result.scalars()}


async def get_watchlist_monitoring_preference(
    db: AsyncSession, user_id: UUID
) -> WatchlistMonitoringPreference | None:
    result = await db.execute(
        select(WatchlistMonitoringPreference).where(
            WatchlistMonitoringPreference.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def upsert_watchlist_monitoring_preference(
    db: AsyncSession, user_id: UUID, data: dict[str, Any]
) -> WatchlistMonitoringPreference:
    preference = await get_watchlist_monitoring_preference(db, user_id)
    if preference is None:
        preference = WatchlistMonitoringPreference(user_id=user_id, **data)
        db.add(preference)
    else:
        for field_name, value in data.items():
            setattr(preference, field_name, value)
    await db.flush()
    await db.refresh(preference)
    return preference


# Notification repository
async def create_notification(
    db: AsyncSession, data: dict[str, Any]
) -> Notification | None:
    notification_models = {
        "price_drop": PriceDropNotification,
        "target_reached": TargetReachedNotification,
        "ended_listing": EndedListingNotification,
        "deal_score": DealScoreNotification,
    }
    notification = notification_models[data["notification_type"]](**data)
    try:
        async with db.begin_nested():
            db.add(notification)
            await db.flush()
    except IntegrityError:
        return None
    return notification


async def get_latest_notification_by_dedupe_key(
    db: AsyncSession, user_id: UUID, dedupe_key: str
) -> Notification | None:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id, Notification.dedupe_key == dedupe_key)
        .order_by(Notification.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_notification_audit_log(
    db: AsyncSession,
    *,
    user_id: UUID,
    event: str,
    notification_id: UUID | None = None,
    channel: str | None = None,
    detail: str | None = None,
) -> NotificationAuditLog:
    audit_log = NotificationAuditLog(
        user_id=user_id,
        notification_id=notification_id,
        event=event,
        channel=channel,
        detail=detail,
    )
    db.add(audit_log)
    await db.flush()
    return audit_log


async def list_notifications_for_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    unread_only: bool = False,
    pagination: Pagination | None = None,
) -> list[Notification]:
    statement = (
        select(Notification)
        .where(Notification.user_id == user_id, Notification.is_in_app.is_(True))
        .order_by(Notification.created_at.desc())
    )
    if unread_only:
        statement = statement.where(Notification.is_read.is_(False))
    result = await db.execute(
        _apply_pagination(statement, pagination) if pagination else statement
    )
    return list(result.scalars())


async def get_notification_for_user(
    db: AsyncSession, notification_id: UUID, user_id: UUID
) -> Notification | None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.is_in_app.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def unread_notification_count(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_in_app.is_(True),
            Notification.is_read.is_(False),
        )
    )
    return int(result.scalar_one())


async def mark_notification_read(
    db: AsyncSession, notification: Notification, *, read_at: datetime
) -> Notification:
    notification.is_read = True
    notification.read_at = read_at
    await db.flush()
    return notification


async def mark_all_notifications_read(
    db: AsyncSession, user_id: UUID, *, read_at: datetime
) -> int:
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_in_app.is_(True),
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=read_at)
    )
    await db.flush()
    return cast(CursorResult, result).rowcount or 0


async def list_notification_preferences(
    db: AsyncSession, user_id: UUID
) -> dict[str, NotificationPreference]:
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    return {preference.notification_type: preference for preference in result.scalars()}


async def upsert_notification_preference(
    db: AsyncSession, user_id: UUID, notification_type: str, data: dict[str, Any]
) -> NotificationPreference:
    preferences = await list_notification_preferences(db, user_id)
    preference = preferences.get(notification_type)
    if preference is None:
        preference = NotificationPreference(
            user_id=user_id, notification_type=notification_type, **data
        )
        db.add(preference)
    else:
        for field_name, value in data.items():
            setattr(preference, field_name, value)
    await db.flush()
    await db.refresh(preference)
    return preference


async def get_user_notification_settings(
    db: AsyncSession, user_id: UUID
) -> UserNotificationSettings | None:
    result = await db.execute(
        select(UserNotificationSettings).where(
            UserNotificationSettings.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def upsert_user_notification_settings(
    db: AsyncSession, user_id: UUID, data: dict[str, Any]
) -> UserNotificationSettings:
    settings = await get_user_notification_settings(db, user_id)
    if settings is None:
        settings = UserNotificationSettings(user_id=user_id, **data)
        db.add(settings)
    else:
        for field_name, value in data.items():
            setattr(settings, field_name, value)
    await db.flush()
    await db.refresh(settings)
    return settings


async def disable_pending_notification_emails(
    db: AsyncSession, user_id: UUID, notification_type: str | None = None
) -> int:
    statement = update(Notification).where(
        Notification.user_id == user_id,
        Notification.email_eligible.is_(True),
        Notification.email_sent_at.is_(None),
    )
    if notification_type is not None:
        statement = statement.where(Notification.notification_type == notification_type)
    result = await db.execute(statement.values(email_eligible=False))
    await db.flush()
    return cast(CursorResult, result).rowcount or 0


async def list_users_with_pending_notification_emails(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User)
        .join(Notification)
        .where(
            Notification.email_eligible.is_(True),
            Notification.email_sent_at.is_(None),
        )
        .distinct()
    )
    return list(result.scalars())


async def list_pending_notification_emails(
    db: AsyncSession, user_id: UUID
) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.email_eligible.is_(True),
            Notification.email_sent_at.is_(None),
        )
        .order_by(Notification.created_at.asc())
    )
    return list(result.scalars())


async def mark_notification_emails_sent(
    db: AsyncSession, notification_ids: list[UUID], *, sent_at: datetime
) -> None:
    if notification_ids:
        await db.execute(
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .values(email_sent_at=sent_at)
        )
        await db.flush()


async def get_watchlist_item_for_user(
    db: AsyncSession, item_id: UUID, user_id: UUID
) -> WatchlistItem | None:
    result = await db.execute(
        select(WatchlistItem)
        .options(
            selectinload(WatchlistItem.lego_set),
            selectinload(WatchlistItem.listing).selectinload(
                MarketplaceListing.lego_set
            ),
        )
        .where(WatchlistItem.id == item_id, WatchlistItem.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_watchlist_item(
    db: AsyncSession, item_data: dict[str, Any]
) -> WatchlistItem:
    item = WatchlistItem(**item_data)
    db.add(item)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateRecordError("Watchlist item already exists") from exc
    return await get_watchlist_item_for_user(db, item.id, item.user_id) or item


async def update_watchlist_item(
    db: AsyncSession,
    item: WatchlistItem,
    item_data: dict[str, Any],
) -> WatchlistItem:
    for field_name, value in item_data.items():
        setattr(item, field_name, value)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateRecordError("Watchlist item already exists") from exc
    return await get_watchlist_item_for_user(db, item.id, item.user_id) or item


async def delete_watchlist_item(db: AsyncSession, item: WatchlistItem) -> None:
    await db.delete(item)
    await db.flush()


async def create_watchlist_price_history(
    db: AsyncSession, data: dict[str, Any]
) -> WatchlistPriceHistory:
    entry = WatchlistPriceHistory(**data)
    db.add(entry)
    await db.flush()
    return entry


async def list_watchlist_price_history(
    db: AsyncSession, watchlist_item_ids: list[UUID]
) -> list[WatchlistPriceHistory]:
    if not watchlist_item_ids:
        return []
    result = await db.execute(
        select(WatchlistPriceHistory)
        .where(WatchlistPriceHistory.watchlist_item_id.in_(watchlist_item_ids))
        .order_by(
            WatchlistPriceHistory.watchlist_item_id,
            WatchlistPriceHistory.observed_at.desc(),
        )
    )
    return list(result.scalars())
