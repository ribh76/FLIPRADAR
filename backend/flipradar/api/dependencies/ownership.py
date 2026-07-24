from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.database.repositories import get_portfolio_item_by_id
from flipradar.domain.models import PortfolioItem


async def get_owned_portfolio_item(
    item_id: UUID,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> PortfolioItem:
    item = await get_portfolio_item_by_id(db, item_id, current_user.id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found"
        )
    return item


OwnedPortfolioItem = Annotated[PortfolioItem, Depends(get_owned_portfolio_item)]
