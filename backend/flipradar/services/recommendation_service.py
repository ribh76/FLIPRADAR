import logging
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import (
    AnalyzeRequest,
    ConfidenceBand,
    RecommendationDecision,
    UserGoal,
)
from flipradar.api.schemas.validation import normalize_set_number
from flipradar.database.repositories import (
    create_recommendation,
    get_latest_snapshots_by_set_number,
    get_recent_snapshots_by_set_number,
    get_set_by_number,
)
from flipradar.database.repositories import (
    get_latest_recommendation_for_set as repository_get_latest_recommendation_for_set,
)
from flipradar.domain.engines import (
    buy_decision_engine,
    decision_engine,
    hold_sell_engine,
    price_estimator,
)

logger = logging.getLogger(__name__)


class RecommendationServiceError(Exception):
    """Base class for expected recommendation analysis failures."""

    status_code = 400


class RecommendationAnalysisError(RecommendationServiceError):
    """Raised when the service cannot complete an expected analysis path."""


class RecommendationNotFoundError(RecommendationServiceError):
    """Raised when required recommendation inputs are missing."""

    status_code = 404


class RecommendationValidationError(RecommendationServiceError):
    """Raised when analyze input is valid JSON but incomplete for the goal."""

    status_code = 422


class InsufficientValuationDataError(RecommendationServiceError):
    """Raised when automated pricing cannot safely support a decision."""

    status_code = 422


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


def _confidence_band(score: Decimal) -> ConfidenceBand:
    if score >= 80:
        return ConfidenceBand.HIGH
    if score >= 55:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


async def get_latest_recommendation_for_set(
    db: AsyncSession, set_number: str
) -> dict | None:
    normalized_set_number = normalize_set_number(set_number)
    recommendation = await repository_get_latest_recommendation_for_set(
        db, normalized_set_number
    )
    if recommendation is None:
        return None

    fair_value = recommendation.fair_market_value or Decimal("0.00")
    return {
        "id": recommendation.id,
        "lego_set_id": recommendation.lego_set_id,
        "set_number": recommendation.lego_set.set_number,
        "user_goal": UserGoal(recommendation.goal),
        "recommendation": RecommendationDecision(recommendation.decision),
        "fair_value": int(fair_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "confidence": _confidence_band(recommendation.confidence_score),
        "confidence_score": recommendation.confidence_score,
        "asking_price": recommendation.asking_price,
        "reason": recommendation.reason,
        "market_summary": recommendation.market_summary,
        "created_at": recommendation.created_at,
        "updated_at": recommendation.updated_at,
    }


async def _get_lego_set(db: AsyncSession, set_number: str):
    lego_set = await get_set_by_number(db, set_number)
    if lego_set is None:
        logger.info("missing set set_number=%s", set_number)
        raise RecommendationNotFoundError("LEGO set not found.")
    return lego_set


def _requires_asking_price(user_goal: UserGoal) -> bool:
    return user_goal in {UserGoal.BUY, UserGoal.BUY_SET, UserGoal.BUY_VS_PASS}


def _is_buy_goal(user_goal: UserGoal) -> bool:
    return user_goal in {UserGoal.BUY, UserGoal.BUY_SET, UserGoal.BUY_VS_PASS}


def _is_sell_or_hold_goal(user_goal: UserGoal) -> bool:
    return user_goal in {
        UserGoal.SELL,
        UserGoal.SELL_SET,
        UserGoal.HOLD,
        UserGoal.HOLD_OR_SELL,
        UserGoal.HOLD_VS_SELL,
    }


def _validate_required_inputs(payload: AnalyzeRequest) -> None:
    if _requires_asking_price(payload.user_goal) and payload.asking_price is None:
        logger.warning(
            "missing required asking price set_number=%s user_goal=%s",
            payload.set_number,
            payload.user_goal.value,
        )
        raise RecommendationValidationError(
            "asking_price is required for buy analysis."
        )


def _buy_score_result(buy_result: dict) -> dict:
    return {
        "score": buy_result["score"],
        "margin_percent": Decimal(str(buy_result.get("discount_pct", 0))).quantize(
            Decimal("0.01")
        ),
        "deal_band": _deal_band_from_reason_codes(buy_result["reason_codes"]),
        "reason_codes": buy_result["reason_codes"],
    }


def _deal_band_from_reason_codes(reason_codes: list[str]) -> str:
    if "deep_discount" in reason_codes or "excellent_discount" in reason_codes:
        return "excellent"
    if "strong_discount" in reason_codes:
        return "strong"
    if "modest_discount" in reason_codes or "near_fair_value" in reason_codes:
        return "fair"
    if "above_fair_value" in reason_codes:
        return "weak"
    return "bad"


def _buy_response_details(buy_result: dict) -> dict:
    return {
        "reason_codes": buy_result.get("reason_codes"),
        "all_in_price": buy_result.get("all_in_price"),
        "discount_pct": buy_result.get("discount_pct"),
        "estimated_profit": buy_result.get("estimated_profit"),
        "estimated_roi_pct": buy_result.get("estimated_roi_pct"),
        "target_buy_price": buy_result.get("target_buy_price"),
    }


def _hold_sell_score_result(hold_sell_result: dict) -> dict:
    return {
        "score": hold_sell_result["score"],
        "margin_percent": Decimal(str(hold_sell_result.get("profit_pct") or 0)),
        "deal_band": _hold_sell_band_from_reason_codes(
            hold_sell_result["reason_codes"]
        ),
        "reason_codes": hold_sell_result["reason_codes"],
    }


def _hold_sell_band_from_reason_codes(reason_codes: list[str]) -> str:
    if "very_strong_profit" in reason_codes or "strong_profit" in reason_codes:
        return "excellent"
    if "target_profit_met" in reason_codes:
        return "strong"
    if "small_profit" in reason_codes or "near_break_even" in reason_codes:
        return "fair"
    if "estimated_loss" in reason_codes:
        return "bad"
    return "unknown"


def _hold_sell_response_details(hold_sell_result: dict) -> dict:
    return {
        "reason_codes": hold_sell_result.get("reason_codes"),
        "estimated_net_sell_value": hold_sell_result.get("estimated_net_sell_value"),
        "total_estimated_net_value": hold_sell_result.get("total_estimated_net_value"),
        "cost_basis": hold_sell_result.get("cost_basis"),
        "profit": hold_sell_result.get("profit"),
        "profit_pct": hold_sell_result.get("profit_pct"),
        "trend_pct": hold_sell_result.get("trend_pct"),
        "trend_label": hold_sell_result.get("trend_label"),
        "target_sell_price": hold_sell_result.get("target_sell_price"),
    }


def _pricing_condition(condition: str) -> str | None:
    if condition in {"new", "sealed"}:
        return "new"
    if condition == "used":
        return "used_complete"
    return None


def _snapshot_price(snapshot) -> Decimal | None:
    return (
        snapshot.value
        if snapshot.metric_type in {"fair_market_value", "median"}
        else None
    )


async def _recent_fair_values(db: AsyncSession, set_number: str) -> list[float]:
    recent_snapshots = await get_recent_snapshots_by_set_number(
        db, set_number, limit=10
    )
    values = [
        value
        for snapshot in reversed(recent_snapshots)
        if (value := _snapshot_price(snapshot)) is not None
    ]
    return [float(value) for value in values]


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
        _validate_required_inputs(payload)
        snapshots = await get_latest_snapshots_by_set_number(db, set_number)
        if not snapshots:
            logger.info("missing snapshots set_number=%s snapshot_count=0", set_number)
        pricing_condition = _pricing_condition(payload.condition)
        override = payload.manual_valuation_override
        estimate = price_estimator.estimate_fair_value(
            snapshots,
            condition=pricing_condition,
            manual_value=override.expected_value if override else None,
            manual_low=override.low_value if override else None,
            manual_high=override.high_value if override else None,
            manual_reason=override.reason if override else None,
        )
        if estimate["error"] is not None:
            raise InsufficientValuationDataError(estimate["error"]["message"])
        fair_value = estimate["fair_value"]
        analysis_details = {}
        if _is_buy_goal(payload.user_goal):
            buy_result = buy_decision_engine.decide_buy_or_pass(
                set_number=set_number,
                asking_price=float(payload.asking_price or Decimal("0.00")),
                fair_value=float(fair_value) if fair_value > 0 else None,
                market_low=(
                    float(estimate["market_low"])
                    if estimate["market_low"] > 0
                    else None
                ),
                market_high=(
                    float(estimate["market_high"])
                    if estimate["market_high"] > 0
                    else None
                ),
                listing_count=estimate["listing_count"],
                confidence=estimate["confidence"],
                condition=payload.condition,
                shipping_price=float(payload.shipping_price),
                marketplace_fee_pct=float(payload.marketplace_fee_pct),
                target_margin_pct=float(payload.target_margin_pct),
            )
            score_result = _buy_score_result(buy_result)
            decision = decision_engine.DecisionResult(
                recommendation=RecommendationDecision(buy_result["verdict"]),
                reasoning=buy_result["reasoning"],
            )
            analysis_details = _buy_response_details(buy_result)
        elif _is_sell_or_hold_goal(payload.user_goal):
            hold_sell_result = hold_sell_engine.decide_sell_or_hold(
                set_number=set_number,
                fair_value=float(fair_value) if fair_value > 0 else None,
                market_low=(
                    float(estimate["market_low"])
                    if estimate["market_low"] > 0
                    else None
                ),
                market_high=(
                    float(estimate["market_high"])
                    if estimate["market_high"] > 0
                    else None
                ),
                listing_count=estimate["listing_count"],
                confidence=estimate["confidence"],
                purchase_price=(
                    float(payload.purchase_price)
                    if payload.purchase_price is not None
                    else None
                ),
                quantity=payload.quantity,
                condition=payload.condition,
                recent_fair_values=await _recent_fair_values(db, set_number),
                marketplace_fee_pct=float(payload.marketplace_fee_pct),
                target_profit_pct=float(payload.target_profit_pct),
            )
            score_result = _hold_sell_score_result(hold_sell_result)
            decision = decision_engine.DecisionResult(
                recommendation=RecommendationDecision(hold_sell_result["verdict"]),
                reasoning=hold_sell_result["reasoning"],
            )
            analysis_details = _hold_sell_response_details(hold_sell_result)
        else:
            raise RecommendationValidationError("Unsupported user goal.")
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
                "condition": payload.condition,
                "shipping_price": _money(payload.shipping_price),
                "marketplace_fee_pct": _money(payload.marketplace_fee_pct),
                "target_margin_pct": _money(payload.target_margin_pct),
                "target_profit_pct": _money(payload.target_profit_pct),
                "purchase_price": _money(payload.purchase_price),
                "quantity": payload.quantity,
                "manual_valuation_override": (
                    payload.manual_valuation_override.model_dump(mode="json")
                    if payload.manual_valuation_override
                    else None
                ),
                **_json_safe_estimate(estimate),
                **_json_safe_estimate(score_result),
                **analysis_details,
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
            "market_low": _money(estimate["market_low"]),
            "market_high": _money(estimate["market_high"]),
            "listing_count": estimate["listing_count"],
            "valuation_source": estimate["valuation_source"],
            **analysis_details,
        }
    except RecommendationServiceError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("pipeline failed set_number=%s", set_number)
        raise RecommendationAnalysisError("Unable to analyze recommendation.") from exc
