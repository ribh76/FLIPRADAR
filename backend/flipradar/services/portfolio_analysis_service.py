"""Orchestrate a refreshable portfolio analysis and its optional LLM narration."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.services import portfolio_analytics_service
from flipradar.services.llm_portfolio_analysis_service import (
    maybe_generate_portfolio_narrative,
)


async def analyze_portfolio(db: AsyncSession, user_id: UUID) -> dict:
    """Refresh deterministic analytics, derive labels, then optionally narrate them."""

    analytics = await portfolio_analytics_service.refresh_portfolio_analytics(
        db, user_id
    )
    recommendations = [
        _item_recommendation(holding) for holding in analytics["holdings"]
    ]
    response = {
        "analytics": analytics,
        "item_recommendations": recommendations,
        "ai_narrative": None,
        "ai_narrative_status": "disabled",
    }
    narrative_result = await maybe_generate_portfolio_narrative(
        response, user_key=f"user:{user_id}"
    )
    response["ai_narrative_status"] = narrative_result.status
    if narrative_result.narrative is not None:
        response["ai_narrative"] = narrative_result.narrative
    return response


def _item_recommendation(holding: dict) -> dict:
    signal = holding["metrics"]["signal"]
    return {
        "portfolio_item_id": holding["portfolio_item_id"],
        "set_number": holding["set_number"],
        "set_name": holding["metrics"].get("set_name"),
        "label": signal["category"],
        "confidence": signal["confidence"],
        "reason_codes": signal["reason_codes"],
        "data_quality_flags": holding["flags"],
    }
