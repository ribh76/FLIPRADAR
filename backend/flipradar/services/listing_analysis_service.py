"""Persisted, explainable analysis for an individual marketplace listing."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.database import repositories
from flipradar.domain.engines.scoring_engine import score_deal
from flipradar.services import product_matching_engine

VALUATION_FRESHNESS_DAYS = 7


async def analyze_listing(db: AsyncSession, listing_id: UUID):
    listing = await repositories.get_listing_for_evaluation(db, listing_id)
    if listing is None:
        return None
    match = product_matching_engine.match_listing_to_set(
        listing.title,
        set_number=listing.lego_set.set_number,
        set_name=listing.lego_set.name,
    )
    inferred_complete, inferred_sealed = _parse_completeness(listing.title)
    updates = {
        "detected_set_number": match.detected_set_number,
        "match_confidence": Decimal(match.confidence),
        "match_reasons": list(match.match_reasons),
        "exclusion_flags": list(match.exclusion_reasons),
        "is_complete": (
            listing.is_complete
            if listing.is_complete is not None
            else inferred_complete
        ),
        "is_sealed": (
            listing.is_sealed if listing.is_sealed is not None else inferred_sealed
        ),
    }
    listing = await repositories.update_listing(db, listing, updates)
    fair_value, sample_size, retrieved_at = await _fair_value(listing, db)
    risk_flags = _risk_flags(listing, retrieved_at)
    scored = score_deal(
        asking_price=listing.price,
        shipping_price=listing.shipping_price,
        fair_value=fair_value,
        set_quality_score=70 if listing.lego_set.data_quality_flag else 100,
        valuation_confidence_score=min(100, 40 + sample_size * 6),
        product_match_confidence_score=listing.match_confidence or 0,
        seller_trust_score=(
            listing.seller_rating if listing.seller_rating is not None else 50
        ),
        marketplace_trust_score=95 if listing.marketplace.name == "bricklink" else 85,
        condition_score={"new": 100, "used": 80, "unknown": 50}.get(
            listing.condition, 50
        ),
        is_complete=listing.is_complete,
        is_unclear=listing.condition == "unknown",
        is_suspicious=bool(risk_flags),
    )
    decision = _decision(scored, match.confidence, fair_value)
    reasons = list(scored["explanations"]) + [
        f"Product match: {reason.replace('_', ' ')}." for reason in match.match_reasons
    ]
    if not reasons:
        reasons = ["No reliable product-match evidence was found."]
    return await repositories.create_listing_evaluation(
        db,
        listing_id=listing.id,
        evaluation_data={
            "fair_value": fair_value,
            "total_cost": scored["total_cost"],
            "discount_percent": scored["discount_percent"],
            "premium_percent": scored["premium_percent"],
            "product_match_confidence": Decimal(match.confidence),
            "decision": decision,
            "decision_confidence": Decimal(scored["confidence_score"]),
            "reasons": reasons,
            "risk_flags": risk_flags,
            "score_breakdown": scored["score_breakdown"],
            "valuation_sample_size": sample_size,
            "valuation_retrieved_at": retrieved_at,
        },
    )


async def _fair_value(listing, db: AsyncSession):
    snapshots = (
        await repositories.get_latest_snapshots_for_set_numbers(
            db, {listing.lego_set.set_number}
        )
    ).get(listing.lego_set.set_number, [])
    condition = (
        "new" if listing.condition == "new" or listing.is_sealed else "used_complete"
    )
    candidates = [
        snapshot
        for snapshot in snapshots
        if snapshot.metric_type == "fair_market_value"
        and snapshot.currency == listing.currency
        and snapshot.condition == condition
    ]
    if not candidates:
        return None, 0, None
    snapshot = max(candidates, key=lambda item: item.retrieval_time)
    return snapshot.value, snapshot.sample_size, snapshot.retrieval_time


def _parse_completeness(title: str) -> tuple[bool | None, bool | None]:
    text = title.lower()
    complete = (
        False
        if any(
            term in text for term in ("incomplete", "missing", "parts only", "box only")
        )
        else True if "complete" in text else None
    )
    sealed = True if "sealed" in text or "unopened" in text else None
    return complete, sealed


def _risk_flags(listing, retrieved_at: datetime | None) -> list[str]:
    flags = list(listing.exclusion_flags or [])
    if not listing.is_verified:
        flags.append("manual_entry")
    if listing.condition == "unknown":
        flags.append("unknown_condition")
    if listing.is_complete is False:
        flags.append("incomplete_listing")
    if listing.seller_rating is None:
        flags.append("seller_rating_unavailable")
    elif listing.seller_rating < 80:
        flags.append("low_seller_rating")
    if listing.listing_status != "active":
        flags.append(f"listing_{listing.listing_status}")
    if retrieved_at is None:
        flags.append("missing_fair_value")
    elif _as_utc(retrieved_at) < datetime.now(UTC) - timedelta(
        days=VALUATION_FRESHNESS_DAYS
    ):
        flags.append("stale_fair_value")
    return list(dict.fromkeys(flags))


def _decision(scored: dict, match_confidence: int, fair_value: Decimal | None) -> str:
    if fair_value is None or match_confidence < 80:
        return "insufficient_data"
    if scored["confidence_score"] < 55:
        return "watch"
    if scored["score"] >= 70:
        return "buy"
    if scored["score"] >= 45:
        return "watch"
    return "pass"


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
