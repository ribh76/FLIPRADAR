import logging

logger = logging.getLogger(__name__)
logger.debug("engine initialized name=buy_decision_engine")


def decide_buy_or_pass(
    *,
    set_number: str,
    asking_price: float,
    fair_value: float | None,
    market_low: float | None = None,
    market_high: float | None = None,
    listing_count: int = 0,
    confidence: str = "low",
    condition: str | None = None,
    shipping_price: float = 0.0,
    marketplace_fee_pct: float = 0.13,
    target_margin_pct: float = 0.15,
) -> dict:
    reason_codes = []
    del condition

    if fair_value is None or fair_value <= 0:
        logger.info(
            "buy/pass guardrail missing fair value set_number=%s listing_count=%s",
            set_number,
            listing_count,
        )
        return {
            "verdict": "WATCH",
            "score": 40,
            "confidence": "low",
            "reasoning": "Not enough market data is available to estimate fair value.",
            "reason_codes": ["missing_fair_value"],
        }

    if asking_price <= 0:
        logger.warning(
            "buy/pass guardrail invalid asking price set_number=%s asking_price=%s",
            set_number,
            asking_price,
        )
        return {
            "verdict": "PASS",
            "score": 0,
            "confidence": "low",
            "reasoning": "Asking price must be greater than zero.",
            "reason_codes": ["invalid_asking_price"],
        }

    all_in_price = asking_price + shipping_price
    discount_pct = (fair_value - all_in_price) / fair_value
    estimated_net_sale_value = fair_value * (1 - marketplace_fee_pct)
    estimated_profit = estimated_net_sale_value - all_in_price
    estimated_roi_pct = estimated_profit / all_in_price

    if discount_pct >= 0.25:
        score = 95
        reason_codes.append("deep_discount")
    elif discount_pct >= 0.20:
        score = 88
        reason_codes.append("excellent_discount")
    elif discount_pct >= 0.10:
        score = 78
        reason_codes.append("strong_discount")
    elif discount_pct >= 0.05:
        score = 65
        reason_codes.append("modest_discount")
    elif discount_pct >= 0:
        score = 55
        reason_codes.append("near_fair_value")
    elif discount_pct >= -0.10:
        score = 35
        reason_codes.append("above_fair_value")
    else:
        score = 20
        reason_codes.append("far_above_fair_value")

    if estimated_roi_pct >= target_margin_pct:
        score += 8
        reason_codes.append("meets_target_roi")
    elif estimated_roi_pct < 0:
        score -= 12
        reason_codes.append("negative_estimated_roi")

    if market_low is not None and all_in_price <= market_low:
        score += 5
        reason_codes.append("below_market_low")

    if market_high is not None and all_in_price >= market_high:
        score -= 10
        reason_codes.append("near_or_above_market_high")

    if confidence == "high":
        score += 5
        reason_codes.append("high_confidence_data")
    elif confidence == "medium":
        reason_codes.append("medium_confidence_data")
    else:
        score -= 10
        reason_codes.append("low_confidence_data")

    if listing_count >= 20:
        score += 5
        reason_codes.append("strong_market_depth")
    elif listing_count < 5:
        score -= 8
        reason_codes.append("thin_market_data")

    score = max(0, min(100, round(score)))

    if score >= 75 and discount_pct >= 0.10:
        verdict = "BUY"
    elif score >= 55:
        verdict = "WATCH"
    else:
        verdict = "PASS"

    if confidence == "low" and verdict == "BUY":
        verdict = "WATCH"
        reason_codes.append("buy_downgraded_due_to_low_confidence")

    reasoning = (
        f"The all-in price is ${all_in_price:.2f}, compared with an estimated "
        f"fair value of ${fair_value:.2f}. This is a {discount_pct * 100:.1f}% "
        f"discount to fair value, with an estimated ROI of "
        f"{estimated_roi_pct * 100:.1f}%."
    )

    return {
        "verdict": verdict,
        "score": score,
        "confidence": confidence,
        "reasoning": reasoning,
        "reason_codes": reason_codes,
        "all_in_price": round(all_in_price, 2),
        "fair_value": round(fair_value, 2),
        "discount_pct": round(discount_pct * 100, 2),
        "estimated_profit": round(estimated_profit, 2),
        "estimated_roi_pct": round(estimated_roi_pct * 100, 2),
        "target_buy_price": round(fair_value * (1 - target_margin_pct), 2),
    }
