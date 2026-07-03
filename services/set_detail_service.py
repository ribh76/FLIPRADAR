from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories import get_latest_snapshots_by_set_number, get_set_by_number
from engine import price_estimator


def _money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def get_set_detail(db: AsyncSession, set_number: str) -> dict:
    lego_set = await get_set_by_number(db, set_number)
    if lego_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LEGO set not found"
        )

    snapshots = await get_latest_snapshots_by_set_number(db, set_number)
    latest_snapshot = snapshots[0] if snapshots else None
    if not snapshots:
        return {
            "set_number": lego_set.set_number,
            "name": lego_set.name,
            "theme": lego_set.theme,
            "subtheme": lego_set.subtheme,
            "release_year": lego_set.release_year,
            "retirement_year": lego_set.retirement_year,
            "piece_count": lego_set.piece_count,
            "minifig_count": lego_set.minifig_count,
            "latest_snapshot": None,
            "fair_value": None,
            "market_low": None,
            "market_high": None,
            "listing_count": 0,
            "confidence": None,
            "valuation_status": "missing_market_data",
        }

    estimate = price_estimator.estimate_fair_value(snapshots)
    return {
        "set_number": lego_set.set_number,
        "name": lego_set.name,
        "theme": lego_set.theme,
        "subtheme": lego_set.subtheme,
        "release_year": lego_set.release_year,
        "retirement_year": lego_set.retirement_year,
        "piece_count": lego_set.piece_count,
        "minifig_count": lego_set.minifig_count,
        "latest_snapshot": latest_snapshot,
        "fair_value": _money(estimate["fair_value"]),
        "market_low": _money(estimate["market_low"]),
        "market_high": _money(estimate["market_high"]),
        "listing_count": estimate["listing_count"],
        "confidence": estimate["confidence"],
        "valuation_status": "valued",
    }
