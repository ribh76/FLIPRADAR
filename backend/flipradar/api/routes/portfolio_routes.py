import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.dependencies.ownership import OwnedPortfolioItem
from flipradar.api.schemas import (
    PortfolioItemCollectionResponse,
    PortfolioItemCreate,
    PortfolioItemResponse,
    PortfolioItemUpdate,
    PortfolioDashboardResponse,
    PortfolioSummaryResponse,
    PortfolioValuationHistoryResponse,
)
from flipradar.api.schemas.common_schema import collection_response
from flipradar.services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])
logger = logging.getLogger(__name__)


@router.get(
    "/dashboard",
    response_model=PortfolioDashboardResponse,
    summary="Get optimized portfolio dashboard data",
)
async def get_portfolio_dashboard(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
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
) -> dict:
    return await portfolio_service.calculate_portfolio_summary(db, current_user.id)


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
