import logging
from dataclasses import dataclass
from decimal import Decimal

from flipradar.api.schemas import RecommendationDecision, UserGoal

logger = logging.getLogger(__name__)
logger.debug("engine initialized name=decision_engine")


@dataclass(frozen=True)
class DecisionResult:
    recommendation: RecommendationDecision
    reasoning: str


def decide(
    score_result: dict,
    user_goal: UserGoal,
    asking_price: Decimal | None,
    fair_value: Decimal,
    *,
    has_snapshots: bool = True,
    trend: str = "flat",
) -> DecisionResult:
    if not has_snapshots:
        return DecisionResult(
            recommendation=RecommendationDecision.WATCH,
            reasoning="No price snapshots found for this set.",
        )

    if user_goal in {UserGoal.BUY, UserGoal.BUY_SET, UserGoal.BUY_VS_PASS}:
        return _buy_decision(score_result)

    if user_goal in {UserGoal.SELL, UserGoal.SELL_SET}:
        return _sell_decision(asking_price, fair_value)

    if user_goal in {UserGoal.HOLD, UserGoal.HOLD_OR_SELL, UserGoal.HOLD_VS_SELL}:
        return _hold_or_sell_decision(score_result, trend)

    return DecisionResult(
        recommendation=RecommendationDecision.WATCH,
        reasoning="Unsupported user goal.",
    )


def _buy_decision(score_result: dict) -> DecisionResult:
    score = score_result["score"]
    margin_percent = score_result["margin_percent"]
    deal_band = score_result["deal_band"]

    if score >= 75:
        return DecisionResult(
            recommendation=RecommendationDecision.BUY,
            reasoning=(
                f"Asking price is {margin_percent}% below estimated market value; "
                f"deal strength is {deal_band}."
            ),
        )

    if score >= 55:
        return DecisionResult(
            recommendation=RecommendationDecision.WATCH,
            reasoning=(
                f"Asking price margin is {margin_percent}%; "
                f"deal strength is {deal_band}."
            ),
        )

    return DecisionResult(
        recommendation=RecommendationDecision.PASS,
        reasoning=(
            f"Asking price margin is {margin_percent}%; "
            f"deal strength is {deal_band}."
        ),
    )


def _sell_decision(asking_price: Decimal | None, fair_value: Decimal) -> DecisionResult:
    if asking_price is None:
        return DecisionResult(
            recommendation=RecommendationDecision.HOLD,
            reasoning="No asking price was provided for sell-side analysis.",
        )

    if asking_price >= fair_value:
        return DecisionResult(
            recommendation=RecommendationDecision.SELL,
            reasoning="Offer price is at or above estimated fair value.",
        )

    return DecisionResult(
        recommendation=RecommendationDecision.HOLD,
        reasoning="Offer price is below estimated fair value.",
    )


def _hold_or_sell_decision(score_result: dict, trend: str) -> DecisionResult:
    if trend == "upward":
        return DecisionResult(
            recommendation=RecommendationDecision.HOLD,
            reasoning="Market trend is upward, so holding is preferred.",
        )

    if score_result["deal_band"] in {"excellent", "strong", "fair"}:
        return DecisionResult(
            recommendation=RecommendationDecision.SELL,
            reasoning="Market trend is flat/down and current value is favorable.",
        )

    return DecisionResult(
        recommendation=RecommendationDecision.HOLD,
        reasoning="Market trend is flat/down, but current value is not favorable enough.",
    )
