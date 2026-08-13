import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.dependencies.ownership import OwnedPortfolioItem
from flipradar.api.schemas import (
    CollectionResponse,
    PortfolioAnalysisComparisonResponse,
    PortfolioAnalysisHistoryEntry,
    PortfolioAnalysisMetadataUpdate,
    PortfolioAnalysisResponse,
    PortfolioAnalyticsResponse,
    PortfolioCreate,
    PortfolioDashboardResponse,
    PortfolioHoldingDetailResponse,
    PortfolioImportPreviewResponse,
    PortfolioImportRequest,
    PortfolioImportResponse,
    PortfolioItemCollectionResponse,
    PortfolioItemCreate,
    PortfolioItemResponse,
    PortfolioItemUpdate,
    PortfolioReassignment,
    PortfolioResponse,
    PortfolioSummaryResponse,
    PortfolioUpdate,
    PortfolioValuationHistoryResponse,
)
from flipradar.api.schemas.common_schema import collection_response
from flipradar.services import (
    portfolio_analysis_service,
    portfolio_analytics_service,
    portfolio_service,
)

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])
logger = logging.getLogger(__name__)


@router.get(
    "/portfolios", response_model=list[PortfolioResponse], summary="List portfolios"
)
async def list_portfolios(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    include_archived: bool = Query(default=False),
):
    return await portfolio_service.list_user_portfolios(
        db, current_user.id, include_archived=include_archived
    )


@router.post(
    "/portfolios",
    response_model=PortfolioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a secondary portfolio",
)
async def create_portfolio(
    payload: PortfolioCreate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await portfolio_service.create_user_portfolio(db, current_user.id, payload)


@router.patch(
    "/portfolios/{portfolio_id}",
    response_model=PortfolioResponse,
    summary="Update a portfolio",
)
async def update_portfolio(
    portfolio_id: UUID,
    payload: PortfolioUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await portfolio_service.update_user_portfolio(
        db, current_user.id, portfolio_id, payload
    )


@router.delete(
    "/portfolios/{portfolio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a portfolio and reassign its holdings",
)
async def delete_portfolio(
    portfolio_id: UUID,
    payload: PortfolioReassignment,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    await portfolio_service.delete_user_portfolio(
        db, current_user.id, portfolio_id, payload.target_portfolio_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/portfolios/{portfolio_id}/archive",
    response_model=PortfolioResponse,
    summary="Archive a portfolio",
)
async def archive_portfolio(
    portfolio_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await portfolio_service.archive_user_portfolio(
        db, current_user.id, portfolio_id, archive=True
    )


@router.post(
    "/portfolios/{portfolio_id}/unarchive",
    response_model=PortfolioResponse,
    summary="Unarchive a portfolio",
)
async def unarchive_portfolio(
    portfolio_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
):
    return await portfolio_service.archive_user_portfolio(
        db, current_user.id, portfolio_id, archive=False
    )


@router.get(
    "/portfolios/{portfolio_id}/export", summary="Export portfolio holdings as CSV"
)
async def export_portfolio(
    portfolio_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    csv_data = await portfolio_service.export_portfolio_csv(
        db, current_user.id, portfolio_id
    )
    return Response(
        csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="portfolio-{portfolio_id}.csv"'
        },
    )


@router.get("/import-template", summary="Download the portfolio import CSV template")
async def portfolio_import_template() -> Response:
    return Response(
        portfolio_service.portfolio_csv_template(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="flipradar-portfolio-import-template.csv"'
        },
    )


@router.post(
    "/import/preview",
    response_model=PortfolioImportPreviewResponse,
    summary="Validate and preview a portfolio CSV import",
)
async def preview_import_portfolio(
    payload: PortfolioImportRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    del current_user  # The preview validates catalog data only; it does not mutate user data.
    return await portfolio_service.preview_portfolio_import(db, payload)


@router.post(
    "/import",
    response_model=PortfolioImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a portfolio from a validated CSV import",
)
async def import_portfolio(
    payload: PortfolioImportRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    return await portfolio_service.import_portfolio_csv(db, current_user.id, payload)


@router.post(
    "/analyze",
    response_model=PortfolioAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze the authenticated user's portfolio",
    description=(
        "Refresh deterministic portfolio metrics and item labels, then optionally "
        "produce a grounded AI narrative over those calculated results."
    ),
)
async def analyze_portfolio(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    portfolio_id: UUID | None = Query(default=None),
) -> dict:
    logger.info("request started route=analyze_portfolio user_id=%s", current_user.id)
    response = await portfolio_analysis_service.analyze_portfolio(
        db, current_user.id, portfolio_id
    )
    logger.info(
        "request finished route=analyze_portfolio user_id=%s holdings=%s ai_status=%s",
        current_user.id,
        response["analytics"]["holding_count"],
        response["ai_narrative_status"],
    )
    return response


@router.get(
    "/analyses",
    response_model=CollectionResponse[PortfolioAnalysisHistoryEntry],
    summary="List completed portfolio analyses",
    description="Return authenticated portfolio analysis history, newest first.",
)
async def list_portfolio_analyses(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    portfolio_id: UUID | None = Query(default=None),
) -> dict:
    analyses = await portfolio_analysis_service.get_portfolio_analysis_history(
        db, current_user.id, limit=limit + 1, offset=offset, portfolio_id=portfolio_id
    )
    return collection_response(analyses, limit=limit, offset=offset)


@router.get(
    "/analyses/compare",
    response_model=PortfolioAnalysisComparisonResponse,
    summary="Compare recommendation changes between two analyses",
)
async def compare_portfolio_analyses(
    previous_analysis_id: UUID,
    current_analysis_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    return await portfolio_analysis_service.compare_portfolio_analyses(
        db,
        current_user.id,
        previous_analysis_id=previous_analysis_id,
        current_analysis_id=current_analysis_id,
    )


@router.get(
    "/analyses/{analysis_id}/export", summary="Export a portfolio analysis as CSV"
)
async def export_portfolio_analysis(
    analysis_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    return Response(
        await portfolio_analysis_service.export_portfolio_analysis_csv(
            db, current_user.id, analysis_id
        ),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="portfolio-analysis-{analysis_id}.csv"'
        },
    )


@router.patch(
    "/analyses/{analysis_id}",
    response_model=PortfolioAnalysisHistoryEntry,
    summary="Label or annotate a portfolio analysis",
)
async def update_portfolio_analysis_metadata(
    analysis_id: UUID,
    update: PortfolioAnalysisMetadataUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    return await portfolio_analysis_service.update_analysis_metadata(
        db,
        current_user.id,
        analysis_id,
        labels=update.labels,
        annotation=update.annotation,
    )


@router.delete(
    "/analyses/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a portfolio analysis from history",
)
async def delete_portfolio_analysis(
    analysis_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    await portfolio_analysis_service.remove_portfolio_analysis(
        db, current_user.id, analysis_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/analytics",
    response_model=PortfolioAnalyticsResponse,
    summary="Get the latest persisted portfolio analytics",
    description=(
        "Return the most recently stored portfolio analytics snapshot. "
        "Use the refresh endpoint to calculate a new snapshot from current market data."
    ),
)
async def get_portfolio_analytics(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    portfolio_id: UUID | None = Query(default=None),
) -> dict:
    return await portfolio_analytics_service.get_latest_portfolio_analytics(
        db, current_user.id, portfolio_id
    )


@router.post(
    "/analytics/refresh",
    response_model=PortfolioAnalyticsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Refresh and store portfolio analytics",
    description=(
        "Calculate holding performance, allocations, concentration, market evidence, "
        "and objective hold/watch/sell-consideration signals, then persist the result."
    ),
)
async def refresh_portfolio_analytics(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    portfolio_id: UUID | None = Query(default=None),
) -> dict:
    return await portfolio_analytics_service.refresh_portfolio_analytics(
        db, current_user.id, portfolio_id=portfolio_id
    )


@router.get(
    "/dashboard",
    response_model=PortfolioDashboardResponse,
    summary="Get optimized portfolio dashboard data",
)
async def get_portfolio_dashboard(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    portfolio_id: UUID | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    condition: str | None = Query(default=None),
    theme: str | None = Query(default=None, min_length=1, max_length=120),
    year: int | None = Query(default=None, ge=1949, le=2100),
    performance: str | None = Query(default=None, pattern="^(gain|loss|unvalued)$"),
    order: str = Query(
        default="purchase_date_desc",
        pattern="^(purchase_date_(asc|desc)|theme_(asc|desc)|value_(asc|desc)|gain_(asc|desc)|created_at_(asc|desc))$",
    ),
    range: str = Query(default="1m", pattern="^(1d|1w|1m|3m|180d|1y|all)$"),
) -> dict:
    return await portfolio_service.get_portfolio_dashboard(
        db,
        current_user.id,
        portfolio_id=portfolio_id,
        limit=limit,
        offset=offset,
        condition=condition,
        theme=theme,
        year=year,
        performance=performance,
        order=order,
        history_range=range,
    )


@router.get(
    "",
    response_model=PortfolioItemCollectionResponse,
    summary="List portfolio",
    description="List the authenticated user's LEGO portfolio items with valuation status.",
)
async def list_portfolio(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    portfolio_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    condition: str | None = Query(default=None),
    theme: str | None = Query(default=None, min_length=1, max_length=120),
    year: int | None = Query(default=None, ge=1949, le=2100),
    performance: str | None = Query(default=None, pattern="^(gain|loss|unvalued)$"),
    order: str = Query(
        default="purchase_date_desc",
        pattern="^(purchase_date_(asc|desc)|theme_(asc|desc)|value_(asc|desc)|gain_(asc|desc)|created_at_(asc|desc))$",
    ),
) -> dict:
    logger.info("request started route=list_portfolio user_id=%s", current_user.id)
    items = await portfolio_service.list_user_portfolio_page(
        db,
        current_user.id,
        portfolio_id=portfolio_id,
        limit=limit + 1,
        offset=offset,
        condition=condition,
        theme=theme,
        year=year,
        performance=performance,
        order=order,
    )
    logger.info("request finished route=list_portfolio user_id=%s", current_user.id)
    return collection_response(items, limit=limit, offset=offset)


@router.post(
    "/items",
    response_model=PortfolioItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add portfolio item",
    description="Add a LEGO set holding to the authenticated user's portfolio.",
)
async def add_portfolio_item(
    payload: PortfolioItemCreate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    logger.info(
        "request started route=add_portfolio_item user_id=%s set_number=%s",
        current_user.id,
        payload.set_number,
    )
    item = await portfolio_service.add_item_to_portfolio(db, current_user.id, payload)
    logger.info(
        "request finished route=add_portfolio_item user_id=%s set_number=%s",
        current_user.id,
        payload.set_number,
    )
    return item


@router.get(
    "/items/{item_id}/detail",
    response_model=PortfolioHoldingDetailResponse,
    summary="Get holding analytics",
    description="Get an owned holding with valuation history, condition comparisons, and concentration risk.",
)
async def get_portfolio_holding_detail(
    item_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    return await portfolio_service.get_portfolio_holding_detail(
        db, current_user.id, item_id
    )


@router.put(
    "/items/{item_id}",
    response_model=PortfolioItemResponse,
    summary="Update portfolio item",
    description="Update one owned portfolio item for the authenticated user.",
)
@router.patch(
    "/items/{item_id}",
    response_model=PortfolioItemResponse,
    summary="Patch portfolio item",
    description="Partially update one owned portfolio item for the authenticated user.",
)
async def update_portfolio_item(
    item_id: UUID,
    payload: PortfolioItemUpdate,
    owned_item: OwnedPortfolioItem,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    logger.info(
        "request started route=update_portfolio_item user_id=%s item_id=%s",
        current_user.id,
        item_id,
    )
    item = await portfolio_service.update_user_portfolio_item(
        db, current_user.id, item_id, payload
    )
    logger.info(
        "request finished route=update_portfolio_item user_id=%s item_id=%s",
        current_user.id,
        item_id,
    )
    return item


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete portfolio item",
    description="Delete one owned portfolio item for the authenticated user.",
)
async def delete_portfolio_item(
    item_id: UUID,
    owned_item: OwnedPortfolioItem,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    await portfolio_service.delete_user_portfolio_item(db, current_user.id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/summary",
    response_model=PortfolioSummaryResponse,
    summary="Get portfolio summary",
    description="Calculate total cost basis, estimated value, and gain/loss.",
)
async def get_portfolio_summary(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    portfolio_id: UUID | None = Query(default=None),
) -> dict:
    return await portfolio_service.calculate_portfolio_summary(
        db, current_user.id, portfolio_id
    )


@router.get(
    "/history",
    response_model=PortfolioValuationHistoryResponse,
    summary="Get portfolio valuation history",
)
async def get_portfolio_history(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
    range: str = Query(default="1m", pattern="^(1d|1w|1m|3m|180d|1y|all)$"),
) -> dict:
    return await portfolio_service.get_portfolio_valuation_history(
        db, current_user.id, range
    )
