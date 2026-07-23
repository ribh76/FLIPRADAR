import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import get_current_user
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    PortfolioItemCollectionResponse,
    PortfolioItemCreate,
    PortfolioItemResponse,
    PortfolioItemUpdate,
    PortfolioSummaryResponse,
)
from flipradar.api.schemas.common_schema import collection_response
from flipradar.domain.models import User
from flipradar.services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])
logger = logging.getLogger(__name__)


@router.get(
    "",
    response_model=PortfolioItemCollectionResponse,
    summary="List portfolio",
    description="List the authenticated user's LEGO portfolio items with valuation status.",
)
async def list_portfolio(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    condition: str | None = Query(default=None),
    order: str = Query(default="created_at_desc"),
) -> list[dict]:
    logger.info("request started route=list_portfolio user_id=%s", current_user.id)
    items = await portfolio_service.list_user_portfolio_page(
        db,
        current_user.id,
        limit=limit + 1,
        offset=offset,
        condition=condition,
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
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
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
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
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
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
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
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    return await portfolio_service.calculate_portfolio_summary(db, current_user.id)
