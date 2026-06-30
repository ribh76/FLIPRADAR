import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)
logger.debug("engine initialized name=scoring_engine")


def score_recommendation(
    asking_price: Decimal | None,
    fair_value: Decimal,
    confidence: str,
    listing_count: int,
) -> dict:
    if asking_price is None or fair_value <= 0:
        return {
            "score": 25,
            "margin_percent": Decimal("0.0"),
            "deal_band": "bad",
        }

    margin_percent = (
        (fair_value - asking_price) / fair_value * Decimal("100")
    ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    score = int(Decimal("70") + margin_percent)
    score += _confidence_adjustment(confidence)
    score += _listing_count_adjustment(listing_count)

    return {
        "score": max(0, min(100, score)),
        "margin_percent": margin_percent,
        "deal_band": _deal_band(margin_percent),
    }


def _confidence_adjustment(confidence: str) -> int:
    if confidence == "high":
        return 0
    if confidence == "medium":
        return -4
    return -10


def _listing_count_adjustment(listing_count: int) -> int:
    if listing_count >= 8:
        return 0
    if listing_count >= 3:
        return -3
    return -5


def _deal_band(margin_percent: Decimal) -> str:
    if margin_percent >= Decimal("20.0"):
        return "excellent"
    if margin_percent >= Decimal("10.0"):
        return "strong"
    if margin_percent >= Decimal("0.0"):
        return "fair"
    if margin_percent >= Decimal("-10.0"):
        return "weak"
    return "bad"
