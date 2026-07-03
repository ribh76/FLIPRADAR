import logging
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ConfidenceBand,
    RecommendationDecision,
    RecommendationResponse,
    UserGoal,
)
from models import LegoSet, Recommendation
from services import recommendation_service

router = APIRouter(tags=["Analyze"])
logger = logging.getLogger(__name__)


def _confidence_band(score: Decimal) -> ConfidenceBand:
    if score >= 80:
        return ConfidenceBand.HIGH
    if score >= 55:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


async def _latest_recommendation_for_set(
    db: AsyncSession, set_number: str
) -> dict | None:
    result = await db.execute(
        select(Recommendation)
        .join(LegoSet)
        .where(LegoSet.set_number == set_number)
        .order_by(Recommendation.created_at.desc())
        .limit(1)
    )
    recommendation = result.scalar_one_or_none()
    if recommendation is None:
        return None

    lego_set = await db.get(LegoSet, recommendation.lego_set_id)
    fair_value = recommendation.fair_market_value or Decimal("0.00")
    return {
        "id": recommendation.id,
        "lego_set_id": recommendation.lego_set_id,
        "set_number": lego_set.set_number if lego_set else set_number,
        "user_goal": UserGoal(recommendation.goal),
        "recommendation": RecommendationDecision(recommendation.decision),
        "fair_value": int(fair_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "confidence": _confidence_band(recommendation.confidence_score),
        "confidence_score": recommendation.confidence_score,
        "asking_price": recommendation.asking_price,
        "reason": recommendation.reason,
        "market_summary": recommendation.market_summary,
        "created_at": recommendation.created_at,
    }


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
            "major validation failure route=analyze_set set_number=%s",
            payload.set_number,
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
    recommendation = await _latest_recommendation_for_set(db, set_number)
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
