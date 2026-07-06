import logging

logger = logging.getLogger(__name__)
logger.debug("engine initialized name=hold_sell_engine")


def decide_sell_or_hold(
    *,
    set_number: str,
    fair_value: float | None,
    market_low: float | None = None,
    market_high: float | None = None,
    listing_count: int = 0,
    confidence: str = "low",
    purchase_price: float | None = None,
    quantity: int = 1,
    condition: str | None = None,
    recent_fair_values: list[float] | None = None,
    marketplace_fee_pct: float = 0.13,
    target_profit_pct: float = 0.25,
) -> dict:
    reason_codes = []
    del condition

    if fair_value is None or fair_value <= 0:
        logger.info(
            "sell/hold guardrail missing fair value set_number=%s listing_count=%s",
            set_number,
            listing_count,
        )
        return {
            "verdict": "HOLD",
            "score": 40,
            "confidence": "low",
            "reasoning": (
                "Not enough market data is available to estimate current resale value."
            ),
            "reason_codes": ["missing_fair_value"],
        }

    if quantity <= 0:
        logger.warning(
            "sell/hold guardrail invalid quantity set_number=%s quantity=%s",
            set_number,
            quantity,
        )
        return {
            "verdict": "HOLD",
            "score": 0,
            "confidence": "low",
            "reasoning": "Quantity must be greater than zero.",
            "reason_codes": ["invalid_quantity"],
        }

    estimated_net_sell_value = fair_value * (1 - marketplace_fee_pct)
    total_estimated_net_value = estimated_net_sell_value * quantity

    if purchase_price is not None and purchase_price > 0:
        cost_basis = purchase_price * quantity
        profit = total_estimated_net_value - cost_basis
        profit_pct = profit / cost_basis
    else:
        cost_basis = None
        profit = None
        profit_pct = None
        reason_codes.append("missing_purchase_price")

    trend_pct = 0.0
    trend_label = "unknown"

    if recent_fair_values and len(recent_fair_values) >= 3:
        previous_values = recent_fair_values[:-1]
        latest_value = recent_fair_values[-1]
        previous_average = sum(previous_values) / len(previous_values)

        if previous_average > 0:
            trend_pct = (latest_value - previous_average) / previous_average

            if trend_pct >= 0.08:
                trend_label = "rising"
                reason_codes.append("price_trend_rising")
            elif trend_pct <= -0.08:
                trend_label = "falling"
                reason_codes.append("price_trend_falling")
            else:
                trend_label = "flat"
                reason_codes.append("price_trend_flat")
    else:
        reason_codes.append("insufficient_trend_data")

    score = 50

    if profit_pct is not None:
        if profit_pct >= 0.75:
            score += 30
            reason_codes.append("very_strong_profit")
        elif profit_pct >= 0.50:
            score += 24
            reason_codes.append("strong_profit")
        elif profit_pct >= target_profit_pct:
            score += 16
            reason_codes.append("target_profit_met")
        elif profit_pct >= 0.10:
            score += 5
            reason_codes.append("small_profit")
        elif profit_pct >= 0:
            score -= 5
            reason_codes.append("near_break_even")
        else:
            score -= 20
            reason_codes.append("estimated_loss")

    if trend_label == "rising":
        score -= 15
        reason_codes.append("hold_due_to_upward_trend")
    elif trend_label == "flat":
        score += 5
        reason_codes.append("sell_more_reasonable_in_flat_market")
    elif trend_label == "falling":
        score += 15
        reason_codes.append("sell_due_to_downward_trend")

    if listing_count >= 20:
        score += 8
        reason_codes.append("liquid_market")
    elif listing_count >= 8:
        score += 3
        reason_codes.append("moderate_market_depth")
    elif listing_count < 5:
        score -= 8
        reason_codes.append("thin_market")

    if confidence == "high":
        score += 5
        reason_codes.append("high_confidence_data")
    elif confidence == "low":
        score -= 10
        reason_codes.append("low_confidence_data")

    if market_high is not None and fair_value >= market_high * 0.95:
        score += 5
        reason_codes.append("near_market_high")

    if market_low is not None and fair_value <= market_low * 1.05:
        score -= 5
        reason_codes.append("near_market_low")

    score = max(0, min(100, round(score)))

    if score >= 70:
        verdict = "SELL"
    elif score >= 50:
        verdict = "WATCH"
    else:
        verdict = "HOLD"

    if confidence == "low" and verdict == "SELL":
        if profit_pct is None or profit_pct < 0.50:
            verdict = "WATCH"
            reason_codes.append("sell_downgraded_due_to_low_confidence")

    if profit_pct is not None:
        reasoning = (
            f"Estimated net sell value is ${total_estimated_net_value:.2f}, "
            f"compared with a cost basis of ${cost_basis:.2f}. "
            f"Estimated gain/loss is ${profit:.2f}, or {profit_pct * 100:.1f}%. "
            f"The recent price trend is {trend_label}."
        )
    else:
        reasoning = (
            f"Estimated fair value is ${fair_value:.2f}, but no purchase price "
            f"was provided, so the recommendation is based on market strength, "
            f"trend, and confidence. The recent price trend is {trend_label}."
        )

    return {
        "verdict": verdict,
        "score": score,
        "confidence": confidence,
        "reasoning": reasoning,
        "reason_codes": reason_codes,
        "fair_value": round(fair_value, 2),
        "estimated_net_sell_value": round(estimated_net_sell_value, 2),
        "total_estimated_net_value": round(total_estimated_net_value, 2),
        "cost_basis": round(cost_basis, 2) if cost_basis is not None else None,
        "profit": round(profit, 2) if profit is not None else None,
        "profit_pct": round(profit_pct * 100, 2) if profit_pct is not None else None,
        "trend_pct": round(trend_pct * 100, 2),
        "trend_label": trend_label,
        "target_sell_price": round(fair_value, 2),
    }
