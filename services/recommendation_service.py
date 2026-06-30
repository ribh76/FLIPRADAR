import logging
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    AnalyzeRequest,
    RecommendationDecision,
    UserGoal,
)
from database.repositories import (
    create_recommendation,
    get_latest_snapshots_by_set_number,
    get_set_by_number,
)
from engine import decision_engine, price_estimator, scoring_engine

logger = logging.getLogger(__name__)


class RecommendationServiceError(Exception):
    """Base class for expected recommendation analysis failures."""

    status_code = 400


class RecommendationAnalysisError(RecommendationServiceError):
    """Raised when the service cannot complete an expected analysis path."""


class RecommendationNotFoundError(RecommendationServiceError):
    """Raised when required recommendation inputs are missing."""

    status_code = 404


def _stored_goal(user_goal: UserGoal) -> UserGoal:
    if user_goal == UserGoal.BUY:
        return UserGoal.BUY_SET
    if user_goal == UserGoal.SELL:
        return UserGoal.SELL_SET
    if user_goal in {UserGoal.HOLD, UserGoal.HOLD_OR_SELL}:
        return UserGoal.HOLD_VS_SELL
    return user_goal


def _money(value: Decimal | None) -> float | None:
    if value is None:
        return None
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(rounded)


def _json_safe_estimate(estimate: dict) -> dict:
    return {
        key: _money(value) if isinstance(value, Decimal) else value
        for key, value in estimate.items()
    }


async def _get_lego_set(db: AsyncSession, set_number: str):
    lego_set = await get_set_by_number(db, set_number)
    if lego_set is None:
        logger.info("missing set set_number=%s", set_number)
        raise RecommendationNotFoundError("LEGO set not found.")
    return lego_set


async def _save_recommendation(
    db: AsyncSession,
    lego_set,
    payload: AnalyzeRequest,
    fair_value: Decimal,
    score_result: dict,
    decision: RecommendationDecision,
    reasoning: str,
    market_summary: dict,
) -> None:
    try:
        await create_recommendation(
            db,
            {
                "lego_set_id": lego_set.id,
                "goal": _stored_goal(payload.user_goal).value,
                "decision": decision.value,
                "reason": reasoning,
                "confidence_score": Decimal(score_result["score"]).quantize(
                    Decimal("0.01")
                ),
                "asking_price": payload.asking_price,
                "fair_market_value": fair_value,
                "market_summary": market_summary,
            },
        )
    except SQLAlchemyError:
        logger.exception(
            "save failed set_number=%s recommendation=%s score=%s",
            payload.set_number,
            decision.value,
            score_result["score"],
        )
        raise
    logger.info(
        "save succeeded set_number=%s recommendation=%s score=%s",
        payload.set_number,
        decision.value,
        score_result["score"],
    )


async def analyze_set(db: AsyncSession, payload: AnalyzeRequest) -> dict:
    set_number = payload.set_number
    logger.info("pipeline started set_number=%s", set_number)

    try:
        lego_set = await _get_lego_set(db, set_number)
        snapshots = await get_latest_snapshots_by_set_number(db, set_number)
        if not snapshots:
            logger.info("missing snapshots set_number=%s snapshot_count=0", set_number)
        estimate = price_estimator.estimate_fair_value(snapshots)
        fair_value = estimate["fair_value"]
        score_result = scoring_engine.score_recommendation(
            payload.asking_price,
            fair_value,
            estimate["confidence"],
            estimate["listing_count"],
        )
        decision = decision_engine.decide(
            score_result,
            payload.user_goal,
            payload.asking_price,
            fair_value,
            has_snapshots=bool(snapshots),
        )
        logger.info(
            "recommendation generated set_number=%s recommendation=%s score=%s confidence=%s snapshot_count=%s",
            set_number,
            decision.recommendation.value,
            score_result["score"],
            estimate["confidence"],
            len(snapshots),
        )
        await _save_recommendation(
            db,
            lego_set,
            payload,
            fair_value,
            score_result,
            decision.recommendation,
            decision.reasoning,
            {
                "set_number": payload.set_number,
                "user_goal": payload.user_goal.value,
                "asking_price": _money(payload.asking_price),
                "fair_value": _money(fair_value),
                "recommendation": decision.recommendation.value,
                "confidence": estimate["confidence"],
                "reasoning": decision.reasoning,
                "snapshot_found": bool(snapshots),
                **_json_safe_estimate(estimate),
                **_json_safe_estimate(score_result),
            },
        )

        return {
            "set_number": payload.set_number,
            "user_goal": payload.user_goal,
            "asking_price": _money(payload.asking_price),
            "fair_value": _money(fair_value),
            "score": score_result["score"],
            "recommendation": decision.recommendation,
            "confidence": estimate["confidence"],
            "reasoning": decision.reasoning,
        }
    except RecommendationServiceError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("pipeline failed set_number=%s", set_number)
        raise RecommendationAnalysisError("Unable to analyze recommendation.") from exc
