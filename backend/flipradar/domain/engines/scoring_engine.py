"""Deterministic and auditable scoring for deal-discovery listings.

The deal score deliberately separates price attractiveness from the certainty of
the set and its valuation.  This lets a large apparent discount remain visible
without allowing low-quality data to look like a high-confidence opportunity.
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

logger = logging.getLogger(__name__)
logger.debug("engine initialized name=scoring_engine")

SCORING_METHOD_VERSION: Final = "deal-score-v2"
VALUE_WEIGHT: Final = Decimal("0.30")
PRODUCT_MATCH_WEIGHT: Final = Decimal("0.15")
VALUATION_CONFIDENCE_WEIGHT: Final = Decimal("0.15")
SELLER_TRUST_WEIGHT: Final = Decimal("0.10")
MARKETPLACE_TRUST_WEIGHT: Final = Decimal("0.10")
CONDITION_COMPLETENESS_WEIGHT: Final = Decimal("0.10")
LISTING_QUALITY_WEIGHT: Final = Decimal("0.10")
_CONFIDENCE_WEIGHTS: Final = {
    "product_match": Decimal("0.25"),
    "valuation_confidence": Decimal("0.25"),
    "seller_trust": Decimal("0.15"),
    "marketplace_trust": Decimal("0.15"),
    "condition_completeness": Decimal("0.10"),
    "listing_quality": Decimal("0.10"),
}
_HUNDRED: Final = Decimal("100")
_MONEY_PRECISION: Final = Decimal("0.01")
_PERCENT_PRECISION: Final = Decimal("0.1")


def score_deal(
    *,
    asking_price: Decimal | float | int,
    shipping_price: Decimal | float | int = Decimal("0.00"),
    fair_value: Decimal | float | int | None,
    set_quality_score: Decimal | float | int = _HUNDRED,
    valuation_confidence_score: Decimal | float | int = _HUNDRED,
    product_match_confidence_score: Decimal | float | int = _HUNDRED,
    seller_trust_score: Decimal | float | int = _HUNDRED,
    marketplace_trust_score: Decimal | float | int = _HUNDRED,
    condition_score: Decimal | float | int = _HUNDRED,
    is_complete: bool | None = True,
    is_unclear: bool = False,
    is_suspicious: bool = False,
) -> dict:
    """Score one listing on a 0--100 scale.

    Inputs are normalized 0--100 scores. The returned ``score_breakdown`` can
    be stored directly with a discovery result and is the source for the
    user-facing explanation. A 25% premium maps value to 0, fair value to 50,
    and a 25% or greater discount to 100.
    """
    price = _non_negative_money("asking_price", asking_price)
    shipping = _non_negative_money("shipping_price", shipping_price)
    total_cost = _money(price + shipping)
    listing_quality = _normalized_score("set_quality_score", set_quality_score)
    valuation_confidence = _normalized_score(
        "valuation_confidence_score", valuation_confidence_score
    )
    product_match = _normalized_score(
        "product_match_confidence_score", product_match_confidence_score
    )
    seller_trust = _normalized_score("seller_trust_score", seller_trust_score)
    marketplace_trust = _normalized_score(
        "marketplace_trust_score", marketplace_trust_score
    )
    condition = _normalized_score("condition_score", condition_score)
    condition_completeness = _condition_completeness_score(condition, is_complete)
    penalties = _penalties(
        is_unclear=is_unclear,
        is_complete=is_complete,
        is_suspicious=is_suspicious,
        listing_quality=listing_quality,
    )
    components = _components(
        value_score=None,
        product_match=product_match,
        valuation_confidence=valuation_confidence,
        seller_trust=seller_trust,
        marketplace_trust=marketplace_trust,
        condition_completeness=condition_completeness,
        listing_quality=listing_quality,
    )
    confidence_score = _confidence_score(components, penalties)

    if fair_value is None:
        return _unvalued_deal(
            total_cost, price, shipping, components, penalties, confidence_score
        )

    value = _positive_money("fair_value", fair_value)
    price_delta = _money(value - total_cost)
    price_vs_fair_value_percent = _percent(price_delta / value * _HUNDRED)
    discount_percent = max(Decimal("0.0"), price_vs_fair_value_percent)
    premium_percent = max(Decimal("0.0"), -price_vs_fair_value_percent)
    value_score = _value_score(price_vs_fair_value_percent)
    components["value"] = _component(VALUE_WEIGHT, value_score)
    score = _overall_score(components, penalties)
    explanations = _explanations(
        total_cost=total_cost,
        fair_value=value,
        discount_percent=discount_percent,
        premium_percent=premium_percent,
        confidence_score=confidence_score,
        penalties=penalties,
    )

    return {
        "scoring_method_version": SCORING_METHOD_VERSION,
        "score": score,
        "deal_band": _deal_band_from_score(score),
        "confidence_score": confidence_score,
        "confidence_band": _confidence_band(confidence_score),
        "asking_price": price,
        "shipping_price": shipping,
        "total_cost": total_cost,
        "fair_value": value,
        "value_difference": price_delta,
        "price_vs_fair_value_percent": price_vs_fair_value_percent,
        "discount_percent": discount_percent,
        "premium_percent": premium_percent,
        "score_components": components,
        "score_breakdown": _score_breakdown(
            components, penalties, score, confidence_score
        ),
        "explanations": explanations,
        "explanation": " ".join(explanations),
    }


def _unvalued_deal(
    total_cost: Decimal,
    asking_price: Decimal,
    shipping_price: Decimal,
    components: dict[str, dict[str, Decimal | None]],
    penalties: list[dict[str, Decimal | str]],
    confidence_score: int,
) -> dict:
    """Return a structured non-score when no positive fair value is available."""
    return {
        "scoring_method_version": SCORING_METHOD_VERSION,
        "score": None,
        "deal_band": "unscored",
        "confidence_score": confidence_score,
        "confidence_band": _confidence_band(confidence_score),
        "asking_price": asking_price,
        "shipping_price": shipping_price,
        "total_cost": total_cost,
        "fair_value": None,
        "value_difference": None,
        "price_vs_fair_value_percent": None,
        "discount_percent": None,
        "premium_percent": None,
        "score_components": components,
        "score_breakdown": _score_breakdown(
            components, penalties, None, confidence_score
        ),
        "explanations": ["A deal score requires a positive estimated fair value."],
        "explanation": "A deal score requires a positive estimated fair value.",
    }


def _components(
    *,
    value_score: Decimal | None,
    product_match: Decimal,
    valuation_confidence: Decimal,
    seller_trust: Decimal,
    marketplace_trust: Decimal,
    condition_completeness: Decimal,
    listing_quality: Decimal,
) -> dict[str, dict[str, Decimal | None]]:
    return {
        "value": _component(VALUE_WEIGHT, value_score),
        "product_match": _component(PRODUCT_MATCH_WEIGHT, product_match),
        "valuation_confidence": _component(
            VALUATION_CONFIDENCE_WEIGHT, valuation_confidence
        ),
        "seller_trust": _component(SELLER_TRUST_WEIGHT, seller_trust),
        "marketplace_trust": _component(MARKETPLACE_TRUST_WEIGHT, marketplace_trust),
        "condition_completeness": _component(
            CONDITION_COMPLETENESS_WEIGHT, condition_completeness
        ),
        "listing_quality": _component(LISTING_QUALITY_WEIGHT, listing_quality),
    }


def _component(weight: Decimal, raw_score: Decimal | None) -> dict[str, Decimal | None]:
    return {
        "weight": weight,
        "raw_score": raw_score,
        "weighted_score": (
            _percent(raw_score * weight) if raw_score is not None else None
        ),
    }


def _overall_score(
    components: dict[str, dict[str, Decimal | None]],
    penalties: list[dict[str, Decimal | str]],
) -> int:
    weighted_score = sum(
        (
            (component["weighted_score"] or Decimal("0"))
            for component in components.values()
        ),
        Decimal("0"),
    )
    return _to_score(weighted_score - _penalty_total(penalties))


def _confidence_score(
    components: dict[str, dict[str, Decimal | None]],
    penalties: list[dict[str, Decimal | str]],
) -> int:
    base_confidence = sum(
        (
            (components[name]["raw_score"] or Decimal("0")) * weight
            for name, weight in _CONFIDENCE_WEIGHTS.items()
        ),
        Decimal("0"),
    )
    return _to_score(base_confidence - _penalty_total(penalties))


def _to_score(value: Decimal) -> int:
    return max(0, min(100, int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))))


def _condition_completeness_score(
    condition_score: Decimal, is_complete: bool | None
) -> Decimal:
    completeness_score = Decimal("100") if is_complete else Decimal("0")
    if is_complete is None:
        completeness_score = Decimal("50")
    return _percent(
        condition_score * Decimal("0.70") + completeness_score * Decimal("0.30")
    )


def _penalties(
    *,
    is_unclear: bool,
    is_complete: bool | None,
    is_suspicious: bool,
    listing_quality: Decimal,
) -> list[dict[str, Decimal | str]]:
    penalties: list[dict[str, Decimal | str]] = []
    if is_unclear:
        penalties.append(_penalty("unclear_listing", Decimal("10")))
    if is_complete is False:
        penalties.append(_penalty("incomplete_listing", Decimal("15")))
    if is_suspicious:
        penalties.append(_penalty("suspicious_listing", Decimal("25")))
    if listing_quality < Decimal("60"):
        penalties.append(_penalty("low_quality_listing", Decimal("10")))
    return penalties


def _penalty(reason: str, points: Decimal) -> dict[str, Decimal | str]:
    return {"reason": reason, "points": points}


def _penalty_total(penalties: list[dict[str, Decimal | str]]) -> Decimal:
    return sum((Decimal(str(penalty["points"])) for penalty in penalties), Decimal("0"))


def _score_breakdown(
    components: dict[str, dict[str, Decimal | None]],
    penalties: list[dict[str, Decimal | str]],
    score: int | None,
    confidence_score: int,
) -> dict[str, Any]:
    breakdown = {
        "components": components,
        "base_score": (
            _to_score(
                sum(
                    (
                        (component["weighted_score"] or Decimal("0"))
                        for component in components.values()
                    ),
                    Decimal("0"),
                )
            )
            if score is not None
            else None
        ),
        "penalties": penalties,
        "penalty_total": _penalty_total(penalties),
        "score": score,
        "confidence_score": confidence_score,
    }
    return _json_safe(breakdown)


def _json_safe(value: Any) -> Any:
    """Convert Decimal-bearing breakdown data for JSON database columns."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _value_score(price_vs_fair_value_percent: Decimal) -> Decimal:
    # -25% maps to 0, 0% to 50, and +25% maps to 100.
    return min(
        _HUNDRED,
        max(Decimal("0"), _percent((price_vs_fair_value_percent + 25) * 2)),
    )


def _non_negative_money(name: str, raw_value: Decimal | float | int) -> Decimal:
    value = Decimal(str(raw_value))
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return _money(value)


def _positive_money(name: str, raw_value: Decimal | float | int) -> Decimal:
    value = _non_negative_money(name, raw_value)
    if value == 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _normalized_score(name: str, raw_value: Decimal | float | int) -> Decimal:
    value = Decimal(str(raw_value))
    if not Decimal("0") <= value <= _HUNDRED:
        raise ValueError(f"{name} must be between 0 and 100")
    return _percent(value)


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _percent(value: Decimal) -> Decimal:
    return value.quantize(_PERCENT_PRECISION, rounding=ROUND_HALF_UP)


def _deal_band_from_score(score: int) -> str:
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "fair"
    if score >= 30:
        return "risky"
    return "poor"


def _confidence_band(confidence_score: int) -> str:
    if confidence_score >= 80:
        return "high"
    if confidence_score >= 55:
        return "medium"
    return "low"


def _explanations(
    *,
    total_cost: Decimal,
    fair_value: Decimal,
    discount_percent: Decimal,
    premium_percent: Decimal,
    confidence_score: int,
    penalties: list[dict[str, Decimal | str]],
) -> list[str]:
    if discount_percent:
        comparison = f"a {discount_percent}% discount"
    elif premium_percent:
        comparison = f"a {premium_percent}% premium"
    else:
        comparison = "at fair value"
    explanations = [
        f"Total cost is ${total_cost:.2f} versus ${fair_value:.2f} fair value "
        f"({comparison}).",
        f"Evidence confidence is {confidence_score}/100 ({_confidence_band(confidence_score)}).",
    ]
    explanations.extend(
        f"Penalty applied: {str(penalty['reason']).replace('_', ' ')} "
        f"(-{penalty['points']} points)."
        for penalty in penalties
    )
    return explanations


# Kept for the pre-existing recommendation flow. Deal discovery should call
# ``score_deal`` so shipping and normalized quality/confidence are included.
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

    margin_percent = ((fair_value - asking_price) / fair_value * _HUNDRED).quantize(
        _PERCENT_PRECISION, rounding=ROUND_HALF_UP
    )
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
