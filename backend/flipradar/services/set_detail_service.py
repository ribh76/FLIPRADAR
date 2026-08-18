from decimal import ROUND_HALF_UP, Decimal
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas.validation import normalize_set_number
from flipradar.database.repositories import (
    get_latest_snapshots_by_set_number,
    get_set_by_number,
)
from flipradar.domain.engines import price_estimator
from flipradar.integrations import bricklink_client


def _money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _metadata_from_lego_set(lego_set) -> dict:
    return {
        "set_number": lego_set.set_number,
        "name": lego_set.name,
        "theme": lego_set.theme,
        "subtheme": lego_set.subtheme,
        "release_year": lego_set.release_year,
        "retirement_year": lego_set.retirement_year,
        "piece_count": lego_set.piece_count,
        "minifig_count": lego_set.minifig_count,
    }


def _detail_response(metadata: dict, **valuation_fields) -> dict:
    return {
        "metadata": metadata,
        **metadata,
        **valuation_fields,
    }


def _bricklink_detail(
    set_number: str, metadata_override: dict | None = None
) -> dict:
    try:
        metadata = metadata_override or bricklink_client.client.get_set_metadata(
            set_number
        )
        latest_snapshot = bricklink_client.client.get_set_price_snapshot(set_number)
    except bricklink_client.BricklinkNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LEGO set not found"
        ) from exc

    return _detail_response(
        metadata,
        latest_snapshot={
            "id": uuid5(NAMESPACE_URL, f"flipradar:bricklink-price:{set_number}"),
            "condition": "new",
            "currency": latest_snapshot["currency"],
            "metric_type": "fair_market_value",
            "value": _money(latest_snapshot["fair_market_value"]),
            "sample_size": latest_snapshot["listing_count"],
            "source_payload": {"source": "bricklink_price_guide"},
            "retrieval_time": latest_snapshot["snapshot_at"],
            "created_at": latest_snapshot["created_at"],
        },
        fair_value=_money(latest_snapshot["fair_market_value"]),
        market_low=_money(latest_snapshot["low_price"]),
        market_high=_money(latest_snapshot["high_price"]),
        listing_count=latest_snapshot["listing_count"],
        confidence="medium",
        valuation_status="valued",
    )


def _missing_market_data(metadata: dict) -> dict:
    return _detail_response(
        metadata,
        latest_snapshot=None,
        fair_value=None,
        market_low=None,
        market_high=None,
        listing_count=0,
        confidence=None,
        valuation_status="missing_market_data",
    )


async def get_set_detail(db: AsyncSession, set_number: str) -> dict:
    normalized_set_number = normalize_set_number(set_number)
    lego_set = await get_set_by_number(db, normalized_set_number)
    if lego_set is None:
        if not bricklink_client.client.configured:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="LEGO set not found"
            )
        return _bricklink_detail(normalized_set_number)

    metadata = _metadata_from_lego_set(lego_set)
    snapshots = await get_latest_snapshots_by_set_number(db, normalized_set_number)
    latest_snapshot = snapshots[0] if snapshots else None
    if not snapshots:
        if not bricklink_client.client.configured:
            return _missing_market_data(metadata)
        try:
            return _bricklink_detail(
                normalized_set_number, metadata_override=metadata
            )
        except HTTPException:
            return _missing_market_data(metadata)

    estimate = price_estimator.estimate_fair_value(snapshots)
    if estimate["error"] is not None:
        return _detail_response(
            metadata,
            latest_snapshot=latest_snapshot,
            fair_value=None,
            market_low=None,
            market_high=None,
            listing_count=estimate["listing_count"],
            confidence=None,
            valuation_status="insufficient_data",
            valuation_error=estimate["error"]["message"],
        )
    return _detail_response(
        metadata,
        latest_snapshot=latest_snapshot,
        fair_value=_money(estimate["fair_value"]),
        market_low=_money(estimate["market_low"]),
        market_high=_money(estimate["market_high"]),
        listing_count=estimate["listing_count"],
        confidence=estimate["confidence"],
        valuation_status="valued",
        valuation_error=None,
    )
