"""Bounded, explainable marketplace deal discovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.database import repositories
from flipradar.domain.engines.scoring_engine import score_deal
from flipradar.services import marketplace_service

logger = logging.getLogger(__name__)

# The default keeps refresh work predictable while still covering a useful
# cross-section of the locally available catalog. Clients can request a smaller
# universe, but cannot turn the endpoint into an unbounded marketplace crawl.
DEFAULT_UNIVERSE_SIZE = 25
MAX_UNIVERSE_SIZE = 50
MAX_LISTING_AGE_DAYS = 7
MIN_MATCH_CONFIDENCE = 80
DEAL_CACHE_TTL_SECONDS = 60
REFRESH_THROTTLE_SECONDS = 60


@dataclass(frozen=True)
class DealFinderResult:
    deals: list[dict]
    refresh: dict


@dataclass(frozen=True)
class _CachedDeals:
    created_at: datetime
    deals: list[dict]


_deal_cache: dict[int, _CachedDeals] = {}
_last_refresh_at: dict[int, datetime] = {}


async def find_deals(
    db: AsyncSession,
    *,
    universe_size: int = DEFAULT_UNIVERSE_SIZE,
    refresh: bool = False,
) -> DealFinderResult:
    """Find and rank eligible listings in the default bounded catalog universe."""
    resolved_universe_size = min(max(universe_size, 1), MAX_UNIVERSE_SIZE)
    now = datetime.now(UTC)
    cached = _deal_cache.get(resolved_universe_size)
    if (
        not refresh
        and cached is not None
        and now - cached.created_at < timedelta(seconds=DEAL_CACHE_TTL_SECONDS)
    ):
        return DealFinderResult(
            deals=cached.deals,
            refresh={
                "requested": False,
                "cached": True,
                "throttled": False,
                "retry_after_seconds": None,
                "provider_errors": [],
            },
        )

    refresh_status = {
        "requested": refresh,
        "cached": False,
        "throttled": False,
        "retry_after_seconds": None,
        "provider_errors": [],
    }
    universe = await repositories.list_sets(
        db,
        pagination=repositories.Pagination(limit=resolved_universe_size, offset=0),
        order="release_year_desc",
    )
    if refresh:
        refresh_status.update(
            await _refresh_universe(
                db, universe, now=now, universe_size=resolved_universe_size
            )
        )

    set_numbers = {lego_set.set_number for lego_set in universe}
    # AsyncSession does not permit concurrent database operations, so preserve
    # the two bulk reads while issuing them sequentially.
    listings = await repositories.list_active_listings_for_set_numbers(
        db,
        set_numbers,
        seen_since=datetime.now(UTC) - timedelta(days=MAX_LISTING_AGE_DAYS),
    )
    snapshots_by_set = await repositories.get_latest_snapshots_for_set_numbers(
        db, set_numbers
    )
    seen_listing_keys: set[tuple[str, str]] = set()
    deals: list[dict] = []
    for listing in listings:
        if not _is_eligible(listing, seen_listing_keys):
            continue
        fair_value, sample_size = _fair_value_for_listing(
            listing, snapshots_by_set.get(listing.lego_set.set_number, [])
        )
        if fair_value is None:
            continue
        scored = score_deal(
            asking_price=listing.price,
            shipping_price=listing.shipping_price,
            fair_value=fair_value,
            set_quality_score=70 if listing.lego_set.data_quality_flag else 100,
            valuation_confidence_score=_valuation_confidence(sample_size),
            product_match_confidence_score=listing.match_confidence or 0,
            seller_trust_score=listing.seller_rating
            if listing.seller_rating is not None
            else 50,
            marketplace_trust_score=95
            if listing.marketplace.name == "bricklink"
            else 85,
            condition_score=_condition_score(listing.condition),
            is_complete=listing.is_complete,
            is_unclear=listing.condition == "unknown",
        )
        if scored["score"] is None:
            continue
        deals.append(
            {
                "listing_id": listing.id,
                "set_number": listing.lego_set.set_number,
                "set_name": listing.lego_set.name,
                "marketplace": {
                    "name": listing.marketplace.name,
                    "display_name": listing.marketplace.display_name,
                    "base_url": listing.marketplace.base_url,
                    "seller_name": listing.seller_name,
                    "seller_rating": listing.seller_rating,
                },
                "title": listing.title,
                "url": listing.url,
                "condition": listing.condition,
                "asking_price": listing.price,
                "shipping_price": listing.shipping_price,
                "total_cost": listing.total_price,
                "currency": listing.currency,
                "fair_value": fair_value,
                "value": fair_value,
                "valuation_sample_size": sample_size,
                "score": scored["score"],
                "deal_band": scored["deal_band"],
                "confidence_score": scored["confidence_score"],
                "confidence": scored["confidence_score"],
                "discount_percent": scored["discount_percent"],
                "discount": scored["discount_percent"],
                "last_seen_at": listing.last_seen_at,
                "explanation": scored["explanation"],
            }
        )
    ranked_deals = sorted(
        deals,
        key=lambda deal: (
            deal["score"],
            deal["confidence_score"],
            deal["discount_percent"],
        ),
        reverse=True,
    )
    _deal_cache[resolved_universe_size] = _CachedDeals(now, ranked_deals)
    return DealFinderResult(deals=ranked_deals, refresh=refresh_status)


async def _refresh_universe(
    db: AsyncSession, universe: list, *, now: datetime, universe_size: int
) -> dict:
    """Best-effort provider refresh: one provider failure must not hide saved deals."""
    last_refresh = _last_refresh_at.get(universe_size)
    if last_refresh is not None:
        elapsed = now - last_refresh
        if elapsed < timedelta(seconds=REFRESH_THROTTLE_SECONDS):
            return {
                "throttled": True,
                "retry_after_seconds": max(
                    1, int(REFRESH_THROTTLE_SECONDS - elapsed.total_seconds())
                ),
            }

    errors: list[str] = []
    for lego_set in universe:
        try:
            await marketplace_service.refresh_marketplace_data(
                lego_set.set_number, db=db
            )
        except Exception:
            errors.append(
                f"Marketplace refresh failed for set {lego_set.set_number}; saved results may be incomplete."
            )
            logger.warning(
                "deal refresh failed set_number=%s", lego_set.set_number, exc_info=True
            )
    _last_refresh_at[universe_size] = now
    _deal_cache.pop(universe_size, None)
    return {"provider_errors": errors}


def _is_eligible(listing, seen_listing_keys: set[tuple[str, str]]) -> bool:
    """Exclude expired, duplicate, mismatched, and low-confidence listings."""
    key = (listing.marketplace.name, listing.external_listing_id)
    if key in seen_listing_keys:
        return False
    seen_listing_keys.add(key)
    if listing.detected_set_number != listing.lego_set.set_number:
        return False
    if (
        listing.match_confidence is None
        or listing.match_confidence < MIN_MATCH_CONFIDENCE
    ):
        return False
    return not bool(listing.exclusion_flags)


def _fair_value_for_listing(listing, snapshots: list) -> tuple[Decimal | None, int]:
    desired_condition = (
        "new" if listing.condition == "new" or listing.is_sealed else "used_complete"
    )
    candidates = [
        snapshot
        for snapshot in snapshots
        if snapshot.metric_type == "fair_market_value"
        and snapshot.currency == listing.currency
        and snapshot.condition == desired_condition
    ]
    if not candidates:
        return None, 0
    latest = max(candidates, key=lambda snapshot: snapshot.retrieval_time)
    return latest.value, latest.sample_size


def _valuation_confidence(sample_size: int) -> int:
    return min(100, 40 + sample_size * 6)


def _condition_score(condition: str) -> int:
    return {"new": 100, "used": 80, "unknown": 50}.get(condition, 50)
