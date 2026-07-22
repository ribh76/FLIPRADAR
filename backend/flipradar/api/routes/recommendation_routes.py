import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    RecommendationResponse,
)
from flipradar.services import recommendation_service

router = APIRouter(tags=["Analyze"])
logger = logging.getLogger(__name__)


# Runs the main recommendation analysis. It accepts set number, user goal, asking price, and returns a decision.
@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze a set decision",
    description="Return BUY/PASS/WATCH/SELL/HOLD advice using stored market snapshots.",
)
async def analyze_set(
    payload: AnalyzeRequest, db: AsyncSession = Depends(get_db_session)
) -> dict:
    """Analyze a LEGO set for BUY/PASS/SELL/HOLD/WATCH guidance."""
    logger.info("request started route=analyze_set set_number=%s", payload.set_number)
    try:
        response = await recommendation_service.analyze_set(db, payload)
    except recommendation_service.RecommendationServiceError as exc:
        logger.warning(
            "major validation failure route=analyze_set set_number=%s status_code=%s error_type=%s detail=%s",
            payload.set_number,
            exc.status_code,
            type(exc).__name__,
            str(exc),
        )
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc
    logger.info(
        "request finished route=analyze_set set_number=%s recommendation=%s score=%s confidence=%s",
        payload.set_number,
        response.get("recommendation"),
        response.get("score"),
        response.get("confidence"),
    )
    return response


# Fetches the latest recommendation for a set. It accepts a set number and returns the newest recommendation.
@router.get(
    "/recommendations/{set_number}",
    response_model=RecommendationResponse,
    summary="Get latest set recommendation",
    description="Return the latest saved recommendation for one LEGO set number.",
)
async def get_latest_recommendation(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> dict:
    """Fetch the latest recommendation result for one LEGO set number."""
    logger.info(
        "request started route=get_latest_recommendation set_number=%s", set_number
    )
    recommendation = await recommendation_service.get_latest_recommendation_for_set(
        db, set_number
    )
    if recommendation is None:
        logger.warning(
            "major validation failure route=get_latest_recommendation set_number=%s",
            set_number,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found",
        )
    logger.info(
        "request finished route=get_latest_recommendation set_number=%s recommendation=%s confidence=%s",
        set_number,
        recommendation.get("recommendation"),
        recommendation.get("confidence"),
    )
    return recommendation


@router.get(
    "/recommendation/{set_number}",
    response_model=RecommendationResponse,
    deprecated=True,
    summary="Deprecated latest recommendation route",
    description="Deprecated compatibility route. Use GET /recommendations/{set_number}.",
)
async def get_latest_recommendation_deprecated(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> dict:
    return await get_latest_recommendation(set_number, db)
