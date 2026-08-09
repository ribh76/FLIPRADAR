"""Explainable, non-advisory hold/sell consideration signals."""

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)
logger.debug("engine initialized name=hold_sell_engine")


class RecommendationCategory(StrEnum):
    HOLD = "hold"
    WATCH = "watch"
    CONSIDER_SELLING = "consider_selling"
    INSUFFICIENT_DATA = "insufficient_data"


RECOMMENDATION_CATEGORY_DEFINITIONS = {
    RecommendationCategory.HOLD: (
        "Available evidence does not currently support changing the holding."
    ),
    RecommendationCategory.WATCH: (
        "Evidence is mixed or incomplete; monitor before taking an action."
    ),
    RecommendationCategory.CONSIDER_SELLING: (
        "Available evidence may support considering a sale; it is not a prediction "
        "or a recommendation to transact."
    ),
    RecommendationCategory.INSUFFICIENT_DATA: (
        "The available evidence is not sufficient to form a directional signal."
    ),
}

# Weights add to 100. Each factor is scored from -1 to +1 and contributes at
# most half of its weight to the 0-100 consideration score around a 50 baseline.
WEIGHTED_INPUTS = {
    "modelled_gain_loss": 35,
    "price_direction": 20,
    "valuation_confidence": 15,
    "concentration": 10,
    "supply_and_demand": 10,
    "freshness": 10,
}

NON_ADVISORY_WARNING = (
    "This is a data-driven consideration, not financial advice. Market conditions, "
    "fees, demand, and realised proceeds may differ from these modelled inputs."
)


def _weighted_input(
    *,
    factor: str,
    signal: float,
    available: bool,
    rationale: str,
) -> dict:
    weight = WEIGHTED_INPUTS[factor]
    contribution = round((weight * max(-1.0, min(1.0, signal))) / 2, 2)
    return {
        "factor": factor,
        "weight": weight,
        "signal": round(signal, 2),
        "contribution": contribution,
        "available": available,
        "rationale": rationale,
    }


def _trend(recent_fair_values: list[float] | None) -> tuple[str, float | None]:
    if not recent_fair_values or len(recent_fair_values) < 3:
        return "insufficient_data", None
    previous_values = recent_fair_values[:-1]
    previous_average = sum(previous_values) / len(previous_values)
    if previous_average <= 0:
        return "insufficient_data", None
    trend_pct = (recent_fair_values[-1] - previous_average) / previous_average
    if trend_pct >= 0.08:
        return "rising", trend_pct
    if trend_pct <= -0.08:
        return "falling", trend_pct
    return "flat", trend_pct


def _confidence_band(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _category_for_score(score: int) -> RecommendationCategory:
    if score >= 65:
        return RecommendationCategory.CONSIDER_SELLING
    if score >= 45:
        return RecommendationCategory.WATCH
    return RecommendationCategory.HOLD


def _base_insufficient_result(*, reason_code: str, warning: str, score: int) -> dict:
    return {
        "verdict": "HOLD",
        "category": RecommendationCategory.INSUFFICIENT_DATA.value,
        "score": score,
        "confidence": "low",
        "recommendation_confidence": "low",
        "reasoning": RECOMMENDATION_CATEGORY_DEFINITIONS[
            RecommendationCategory.INSUFFICIENT_DATA
        ],
        "reason_codes": [reason_code],
        "reasons": [
            {
                "code": reason_code,
                "factor": "valuation_confidence",
                "impact": "neutral",
                "statement": warning,
            }
        ],
        "warnings": [warning, NON_ADVISORY_WARNING],
        "weighted_inputs": [],
    }


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
    concentration_percent: float | None = None,
    marketplace_supply: int | None = None,
    supply_reliable: bool | None = None,
    demand_signal: str | None = None,
    valuation_age_days: int | None = None,
) -> dict:
    """Return an explainable holding signal without making a financial promise.

    ``verdict`` remains compatible with the persisted recommendation enum. The
    richer ``category`` distinguishes a SELL-compatible "consider selling"
    signal from insufficient data and should be preferred by new consumers.
    """
    del condition, market_low, market_high
    if fair_value is None or fair_value <= 0:
        logger.info("hold/sell lacks fair value set_number=%s", set_number)
        return _base_insufficient_result(
            reason_code="missing_fair_value",
            warning="A current modelled valuation is unavailable for this holding.",
            score=40,
        )
    if quantity <= 0:
        logger.warning(
            "hold/sell invalid quantity set_number=%s quantity=%s", set_number, quantity
        )
        return _base_insufficient_result(
            reason_code="invalid_quantity",
            warning="A positive quantity is required to calculate this holding signal.",
            score=0,
        )

    warnings = [NON_ADVISORY_WARNING]
    reasons: list[dict] = []
    reason_codes: list[str] = []
    estimated_net_sell_value = fair_value * (1 - marketplace_fee_pct)
    total_estimated_net_value = estimated_net_sell_value * quantity
    cost_basis = (
        purchase_price * quantity if purchase_price and purchase_price > 0 else None
    )
    profit = total_estimated_net_value - cost_basis if cost_basis is not None else None
    profit_pct = profit / cost_basis if cost_basis else None

    if profit_pct is None:
        gain_signal, gain_code, gain_statement = (
            0.0,
            "missing_purchase_price",
            "Purchase cost is unavailable, so gain/loss cannot be modelled.",
        )
        warnings.append(gain_statement)
    elif profit_pct >= 0.75:
        gain_signal, gain_code, gain_statement = (
            1.0,
            "very_strong_profit",
            "The modelled net amount is materially above the recorded cost basis.",
        )
    elif profit_pct >= 0.50:
        gain_signal, gain_code, gain_statement = (
            0.8,
            "strong_profit",
            "The modelled net amount is above the recorded cost basis.",
        )
    elif profit_pct >= target_profit_pct:
        gain_signal, gain_code, gain_statement = (
            0.55,
            "target_profit_met",
            "The modelled net amount meets the supplied target threshold.",
        )
    elif profit_pct >= 0.10:
        gain_signal, gain_code, gain_statement = (
            0.2,
            "small_profit",
            "The modelled net amount is modestly above the recorded cost basis.",
        )
    elif profit_pct >= 0:
        gain_signal, gain_code, gain_statement = (
            -0.15,
            "near_break_even",
            "The modelled net amount is close to the recorded cost basis.",
        )
    else:
        gain_signal, gain_code, gain_statement = (
            -0.7,
            "estimated_loss",
            "The modelled net amount is below the recorded cost basis.",
        )
    reason_codes.append(gain_code)
    reasons.append(
        {
            "code": gain_code,
            "factor": "modelled_gain_loss",
            "impact": (
                "supports_considering_sale" if gain_signal > 0 else "supports_holding"
            ),
            "statement": gain_statement,
        }
    )
    weighted_inputs = [
        _weighted_input(
            factor="modelled_gain_loss",
            signal=gain_signal,
            available=profit_pct is not None,
            rationale=gain_statement,
        )
    ]

    trend_label, trend_pct = _trend(recent_fair_values)
    trend_signals = {"rising": -0.75, "flat": 0.15, "falling": 0.75}
    trend_signal = trend_signals.get(trend_label, 0.0)
    trend_code = f"price_trend_{trend_label}"
    trend_statement = {
        "rising": "Recent modelled prices are moving upward; waiting may be worth monitoring.",
        "flat": "Recent modelled prices are broadly flat.",
        "falling": "Recent modelled prices are moving downward; a sale may warrant review.",
        "insufficient_data": "There are not enough historical valuation points to assess direction.",
    }[trend_label]
    reason_codes.append(trend_code)
    if trend_label == "insufficient_data":
        warnings.append(trend_statement)
    reasons.append(
        {
            "code": trend_code,
            "factor": "price_direction",
            "impact": (
                "supports_considering_sale"
                if trend_signal > 0
                else "supports_holding" if trend_signal < 0 else "neutral"
            ),
            "statement": trend_statement,
        }
    )
    weighted_inputs.append(
        _weighted_input(
            factor="price_direction",
            signal=trend_signal,
            available=trend_pct is not None,
            rationale=trend_statement,
        )
    )

    confidence_signals = {"high": 0.4, "medium": 0.1, "low": -0.45}
    confidence_signal = confidence_signals.get(confidence, -0.7)
    confidence_code = f"valuation_confidence_{confidence if confidence in confidence_signals else 'missing'}"
    confidence_statement = f"The valuation evidence is assessed as {confidence if confidence in confidence_signals else 'unavailable'} confidence."
    reason_codes.append(confidence_code)
    if confidence_signal < 0:
        warnings.append(confidence_statement)
    reasons.append(
        {
            "code": confidence_code,
            "factor": "valuation_confidence",
            "impact": (
                "supports_considering_sale"
                if confidence_signal > 0
                else "reduces_confidence"
            ),
            "statement": confidence_statement,
        }
    )
    weighted_inputs.append(
        _weighted_input(
            factor="valuation_confidence",
            signal=confidence_signal,
            available=confidence in confidence_signals,
            rationale=confidence_statement,
        )
    )

    if concentration_percent is None:
        concentration_signal, concentration_statement = (
            0.0,
            "Portfolio concentration is unavailable for this signal.",
        )
        warnings.append(concentration_statement)
    elif concentration_percent >= 40:
        concentration_signal, concentration_statement = (
            0.45,
            "This holding is a large share of portfolio value.",
        )
    elif concentration_percent >= 20:
        concentration_signal, concentration_statement = (
            0.2,
            "This holding is a meaningful share of portfolio value.",
        )
    else:
        concentration_signal, concentration_statement = (
            0.0,
            "This holding has limited portfolio concentration impact.",
        )
    reason_codes.append("portfolio_concentration")
    reasons.append(
        {
            "code": "portfolio_concentration",
            "factor": "concentration",
            "impact": (
                "supports_considering_sale" if concentration_signal > 0 else "neutral"
            ),
            "statement": concentration_statement,
        }
    )
    weighted_inputs.append(
        _weighted_input(
            factor="concentration",
            signal=concentration_signal,
            available=concentration_percent is not None,
            rationale=concentration_statement,
        )
    )

    resolved_supply = (
        marketplace_supply if marketplace_supply is not None else listing_count
    )
    if supply_reliable is None:
        supply_reliable = resolved_supply >= 3
    if not supply_reliable:
        supply_signal, supply_statement = (
            0.0,
            "Marketplace supply is not reliable enough to influence the signal.",
        )
        warnings.append(supply_statement)
    elif resolved_supply >= 20:
        supply_signal, supply_statement = (
            0.5,
            "Verified marketplace supply appears deep enough to support liquidity.",
        )
    elif resolved_supply >= 8:
        supply_signal, supply_statement = (
            0.2,
            "Verified marketplace supply appears moderately available.",
        )
    else:
        supply_signal, supply_statement = (
            -0.5,
            "Verified marketplace supply appears thin.",
        )
    demand_signals = {"strong": 0.45, "moderate": 0.15, "weak": -0.3}
    if demand_signal in demand_signals:
        supply_signal = max(
            -1.0, min(1.0, supply_signal + demand_signals[demand_signal])
        )
        supply_statement += f" Demand evidence is {demand_signal}."
    elif demand_signal is None:
        warnings.append(
            "Demand evidence is unavailable and does not influence the signal."
        )
    reason_codes.append("supply_and_demand")
    reasons.append(
        {
            "code": "supply_and_demand",
            "factor": "supply_and_demand",
            "impact": (
                "supports_considering_sale"
                if supply_signal > 0
                else "supports_holding" if supply_signal < 0 else "neutral"
            ),
            "statement": supply_statement,
        }
    )
    weighted_inputs.append(
        _weighted_input(
            factor="supply_and_demand",
            signal=supply_signal,
            available=supply_reliable or demand_signal in demand_signals,
            rationale=supply_statement,
        )
    )

    if valuation_age_days is None:
        freshness_signal, freshness_statement = (
            0.0,
            "Valuation freshness is unavailable.",
        )
        warnings.append(freshness_statement)
    elif valuation_age_days <= 2:
        freshness_signal, freshness_statement = (
            0.4,
            "Valuation evidence is very recent.",
        )
    elif valuation_age_days <= 7:
        freshness_signal, freshness_statement = 0.2, "Valuation evidence is recent."
    elif valuation_age_days <= 14:
        freshness_signal, freshness_statement = (
            0.0,
            "Valuation evidence is aging but within the freshness window.",
        )
    elif valuation_age_days <= 30:
        freshness_signal, freshness_statement = (
            -0.5,
            "Valuation evidence is stale and reduces confidence.",
        )
    else:
        freshness_signal, freshness_statement = (
            -0.8,
            "Valuation evidence is materially stale and reduces confidence.",
        )
    reason_codes.append("valuation_freshness")
    reasons.append(
        {
            "code": "valuation_freshness",
            "factor": "freshness",
            "impact": (
                "supports_considering_sale"
                if freshness_signal > 0
                else "reduces_confidence" if freshness_signal < 0 else "neutral"
            ),
            "statement": freshness_statement,
        }
    )
    weighted_inputs.append(
        _weighted_input(
            factor="freshness",
            signal=freshness_signal,
            available=valuation_age_days is not None,
            rationale=freshness_statement,
        )
    )

    score = max(
        0, min(100, round(50 + sum(item["contribution"] for item in weighted_inputs)))
    )
    recommendation_confidence_score = 100
    recommendation_confidence_score -= {"high": 0, "medium": 15, "low": 55}.get(
        confidence, 55
    )
    recommendation_confidence_score -= 15 if trend_pct is None else 0
    recommendation_confidence_score -= 10 if not supply_reliable else 0
    recommendation_confidence_score -= (
        20 if valuation_age_days is None else 15 if valuation_age_days > 14 else 0
    )
    recommendation_confidence_score -= 5 if profit_pct is None else 0
    recommendation_confidence = _confidence_band(
        max(0, recommendation_confidence_score)
    )

    category = _category_for_score(score)
    if (
        category is RecommendationCategory.CONSIDER_SELLING
        and recommendation_confidence == "low"
    ):
        category = RecommendationCategory.WATCH
        reason_codes.append("consideration_downgraded_low_confidence")
        warnings.append(
            "The signal was limited to watch because the supporting evidence has low confidence."
        )
    verdict = (
        "SELL"
        if category is RecommendationCategory.CONSIDER_SELLING
        else "WATCH" if category is RecommendationCategory.WATCH else "HOLD"
    )
    reasoning = (
        f"{RECOMMENDATION_CATEGORY_DEFINITIONS[category]} "
        f"The consideration score is {score}/100 with {recommendation_confidence} recommendation confidence."
    )
    return {
        "verdict": verdict,
        "category": category.value,
        "score": score,
        "confidence": recommendation_confidence,
        "recommendation_confidence": recommendation_confidence,
        "reasoning": reasoning,
        "reason_codes": reason_codes,
        "reasons": reasons,
        "warnings": warnings,
        "weighted_inputs": weighted_inputs,
        "fair_value": round(fair_value, 2),
        "estimated_net_sell_value": round(estimated_net_sell_value, 2),
        "total_estimated_net_value": round(total_estimated_net_value, 2),
        "cost_basis": round(cost_basis, 2) if cost_basis is not None else None,
        "profit": round(profit, 2) if profit is not None else None,
        "profit_pct": round(profit_pct * 100, 2) if profit_pct is not None else None,
        "trend_pct": round(trend_pct * 100, 2) if trend_pct is not None else None,
        "trend_label": trend_label,
        "target_sell_price": round(fair_value, 2),
    }
