import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.api.route_classification import RouteClassification, route_metadata
from flipradar.api.schemas import (
    PriceAnalyticsResponse,
    PriceSnapshotCollectionResponse,
    PriceSnapshotCreate,
    PriceSnapshotResponse,
)
from flipradar.api.schemas.common_schema import collection_response
from flipradar.domain.models import PriceSnapshot
from flipradar.domain.models.enums import PriceMetricType, SnapshotCondition
from flipradar.services import price_snapshot_service
from flipradar.services.errors import ServiceError

router = APIRouter(tags=["Marketplace/Internal"])
logger = logging.getLogger(__name__)


# Creates a price snapshot. It accepts a set number, marketplace, pricing bands, and returns the stored snapshot.
@router.post(
    "/snapshots",
    response_model=PriceSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create price snapshot",
    **route_metadata(RouteClassification.INTERNAL, "Store a price snapshot."),
)
async def create_price_snapshot(
    payload: PriceSnapshotCreate, db: AsyncSession = Depends(get_db_session)
) -> PriceSnapshot:
    """Create one price snapshot linked to a LEGO set and marketplace."""
    logger.info(
        "request started route=create_price_snapshot set_number=%s marketplace=%s",
        payload.set_number,
        payload.marketplace_name,
    )
    try:
        snapshot = await price_snapshot_service.create_price_snapshot(db, payload)
    except ServiceError as exc:
        logger.warning(
            "major validation failure route=create_price_snapshot set_number=%s marketplace=%s",
            payload.set_number,
            payload.marketplace_name,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    logger.info(
        "request finished route=create_price_snapshot set_number=%s marketplace=%s",
        payload.set_number,
        payload.marketplace_name,
    )
    return snapshot


# Lists snapshots for a set. It accepts a set number and returns historical snapshot rows.
@router.get(
    "/snapshots/{set_number}",
    response_model=PriceSnapshotCollectionResponse,
    summary="List price snapshots",
    **route_metadata(RouteClassification.INTERNAL, "List stored snapshot history."),
)
async def list_price_snapshots(
    set_number: str,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    condition: str | None = Query(default=None),
    marketplace_name: str | None = Query(default=None),
    metric_type: str | None = Query(default=None),
    order: str = Query(default="snapshot_desc"),
) -> dict:
    """List all price snapshots for one LEGO set number."""
    logger.info("request started route=list_price_snapshots set_number=%s", set_number)
    snapshots = await price_snapshot_service.list_price_snapshots_for_set(
        db,
        set_number,
        limit=limit + 1,
        offset=offset,
        condition=condition,
        marketplace_name=marketplace_name,
        metric_type=metric_type,
        order=order,
    )
    logger.info(
        "request finished route=list_price_snapshots set_number=%s snapshot_count=%s",
        set_number,
        len(snapshots),
    )
    return collection_response(snapshots, limit=limit, offset=offset)


@router.get(
    "/snapshots/{set_number}/analytics",
    response_model=PriceAnalyticsResponse,
    summary="Get advanced price analytics",
    **route_metadata(
        RouteClassification.INTERNAL,
        "Calculate descriptive price analytics from stored raw and compacted history.",
    ),
)
async def get_price_analytics(
    set_number: str,
    db: AsyncSession = Depends(get_db_session),
    condition: SnapshotCondition = Query(default=SnapshotCondition.NEW),
    metric_type: PriceMetricType = Query(default=PriceMetricType.FAIR_MARKET_VALUE),
    currency: str = Query(default="USD", min_length=3, max_length=3),
) -> dict:
    try:
        return await price_snapshot_service.get_price_analytics(
            db,
            set_number,
            condition=condition.value,
            metric_type=metric_type.value,
            currency=currency,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


# Fetches the latest snapshot for a set. It accepts a set number and returns the newest pricing snapshot.
@router.get(
    "/snapshots/{set_number}/latest",
    response_model=PriceSnapshotResponse,
    summary="Get latest price snapshot",
    **route_metadata(RouteClassification.INTERNAL, "Fetch the latest stored snapshot."),
)
async def get_latest_price_snapshot(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> PriceSnapshot:
    """Fetch the latest price snapshot for one LEGO set number."""
    logger.info(
        "request started route=get_latest_price_snapshot set_number=%s", set_number
    )
    snapshot = await price_snapshot_service.get_latest_price_snapshot_by_set_number(
        db, set_number
    )
    if snapshot is None:
        logger.warning(
            "major validation failure route=get_latest_price_snapshot set_number=%s snapshot_count=0",
            set_number,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found"
        )
    logger.info(
        "request finished route=get_latest_price_snapshot set_number=%s snapshot_count=1",
        set_number,
    )
    return snapshot
