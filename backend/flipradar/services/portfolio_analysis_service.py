"""Orchestrate a refreshable portfolio analysis and its optional LLM narration."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas.portfolio_analysis_schema import (
    PORTFOLIO_ANALYSIS_PROMPT_VERSION,
    PortfolioRecommendationLabel,
    portfolio_recommendation_label,
)
from flipradar.database.repositories import (
    create_portfolio_analysis,
    get_portfolio_analysis_for_user,
    list_portfolio_analyses,
)
from flipradar.services import portfolio_analytics_service
from flipradar.services.llm_portfolio_analysis_service import (
    maybe_generate_portfolio_narrative,
)

PORTFOLIO_ANALYSIS_METHOD_VERSION = "portfolio-analysis-method-v1"


async def analyze_portfolio(db: AsyncSession, user_id: UUID) -> dict:
    """Refresh deterministic analytics, derive labels, then optionally narrate them."""

    analytics = await portfolio_analytics_service.refresh_portfolio_analytics(
        db, user_id
    )
    recommendations = [
        _item_recommendation(holding) for holding in analytics["holdings"]
    ]
    confidence_summary = _confidence_summary(recommendations)
    data_quality_warnings = _data_quality_warnings(analytics["holdings"])
    response = {
        "analytics": analytics,
        "item_recommendations": recommendations,
        "confidence_summary": confidence_summary,
        "data_quality_warnings": data_quality_warnings,
        "ai_narrative": None,
        "ai_narrative_status": "disabled",
    }
    narrative_result = await maybe_generate_portfolio_narrative(
        response, user_key=f"user:{user_id}"
    )
    response["ai_narrative_status"] = narrative_result.status
    if narrative_result.narrative is not None:
        response["ai_narrative"] = narrative_result.narrative
    stored = await create_portfolio_analysis(
        db,
        analysis_data={
            "user_id": user_id,
            "analytics_snapshot_id": analytics["id"],
            "generated_at": analytics["generated_at"],
            "method_version": PORTFOLIO_ANALYSIS_METHOD_VERSION,
            "prompt_version": PORTFOLIO_ANALYSIS_PROMPT_VERSION,
            "portfolio_context": _json_value(analytics),
            "ai_narrative_status": response["ai_narrative_status"],
            "ai_narrative": (
                response["ai_narrative"].model_dump(mode="json")
                if response["ai_narrative"] is not None
                else None
            ),
            "item_recommendations": _json_value(recommendations),
            "confidence_summary": confidence_summary,
            "data_quality_warnings": data_quality_warnings,
        },
    )
    response["id"] = stored.id
    response["generated_at"] = stored.generated_at
    return response


async def get_portfolio_analysis_history(
    db: AsyncSession, user_id: UUID, *, limit: int, offset: int
) -> list[dict]:
    analyses = await list_portfolio_analyses(db, user_id, limit=limit, offset=offset)
    return [_history_entry(analysis) for analysis in analyses]


async def compare_portfolio_analyses(
    db: AsyncSession,
    user_id: UUID,
    *,
    previous_analysis_id: UUID,
    current_analysis_id: UUID,
) -> dict:
    previous = await get_portfolio_analysis_for_user(db, user_id, previous_analysis_id)
    current = await get_portfolio_analysis_for_user(db, user_id, current_analysis_id)
    if previous is None or current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio analysis not found.",
        )
    previous_by_set = {
        recommendation["set_number"]: recommendation
        for recommendation in previous.item_recommendations
    }
    current_by_set = {
        recommendation["set_number"]: recommendation
        for recommendation in current.item_recommendations
    }
    changes = [
        _recommendation_change(
            previous_by_set.get(set_number), current_by_set.get(set_number)
        )
        for set_number in sorted(set(previous_by_set) | set(current_by_set))
    ]
    return {
        "previous_analysis_id": previous.id,
        "current_analysis_id": current.id,
        "previous_generated_at": previous.generated_at,
        "current_generated_at": current.generated_at,
        "changes": changes,
    }


def _item_recommendation(holding: dict) -> dict:
    signal = holding["metrics"]["signal"]
    label = portfolio_recommendation_label(signal["category"])
    return {
        "portfolio_item_id": holding["portfolio_item_id"],
        "set_number": holding["set_number"],
        "set_name": holding["metrics"].get("set_name"),
        "label": label,
        "priority": _priority_for_label(label),
        "confidence": signal["confidence"],
        "reason_codes": signal["reason_codes"],
        "data_quality_flags": holding["flags"],
    }


def _history_entry(analysis) -> dict:
    return {
        "id": analysis.id,
        "generated_at": analysis.generated_at,
        "method_version": analysis.method_version,
        "prompt_version": analysis.prompt_version,
        "ai_narrative_status": analysis.ai_narrative_status,
        "portfolio_context": analysis.portfolio_context,
        "item_recommendations": analysis.item_recommendations,
        "confidence_summary": analysis.confidence_summary,
        "data_quality_warnings": analysis.data_quality_warnings,
    }


def _recommendation_change(previous: dict | None, current: dict | None) -> dict:
    if previous is None:
        change_type = "added"
    elif current is None:
        change_type = "removed"
    elif previous["label"] != current["label"]:
        change_type = "changed"
    else:
        change_type = "unchanged"
    previous_label = previous["label"] if previous is not None else None
    current_label = current["label"] if current is not None else None
    return {
        "set_number": (current or previous)["set_number"],
        "set_name": (current or previous).get("set_name"),
        "previous_label": previous_label,
        "current_label": current_label,
        "previous_confidence": (
            previous["confidence"] if previous is not None else None
        ),
        "current_confidence": current["confidence"] if current is not None else None,
        "change_type": change_type,
        "is_reversal": {previous_label, current_label} == {"hold", "consider_selling"},
    }


def _priority_for_label(label: PortfolioRecommendationLabel) -> int:
    return {
        "consider_selling": 1,
        "watch": 2,
        "insufficient_data": 3,
        "hold": 4,
    }[label]


def _confidence_summary(recommendations: list[dict]) -> dict:
    counts = {"high": 0, "medium": 0, "low": 0}
    for recommendation in recommendations:
        counts[recommendation["confidence"]] += 1
    overall = "low" if counts["low"] else "medium" if counts["medium"] else "high"
    return {"overall": overall, "item_counts": counts}


def _data_quality_warnings(holdings: list[dict]) -> list[dict]:
    warning_definitions = {
        "insufficient_market_data": "Some holdings do not have enough market data for a current valuation.",
        "low_confidence_valuation": "Some holdings have low-confidence valuation evidence.",
        "stale_valuation": "Some holdings use valuation evidence that needs refreshing.",
        "marketplace_supply_unreliable": "Some holdings have insufficient supply evidence for a reliable supply signal.",
        "insufficient_price_trend_data": "Some holdings lack enough valuation history for a price-trend signal.",
    }
    counts = {code: 0 for code in warning_definitions}
    for holding in holdings:
        for flag in holding["flags"]:
            if flag in counts:
                counts[flag] += 1
    return [
        {
            "code": code,
            "affected_holding_count": count,
            "message": warning_definitions[code],
        }
        for code, count in counts.items()
        if count
    ]


def _json_value(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value
