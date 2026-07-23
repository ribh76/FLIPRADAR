from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from flipradar.api.schemas.lego_set_schema import LegoSetResponse
from flipradar.api.schemas.listing_schema import ListingResponse
from flipradar.api.schemas.portfolio_schema import PortfolioItemResponse
from flipradar.api.schemas.pricing_schema import PriceSnapshotResponse


class ApiError(BaseModel):
    code: str
    message: str
    details: Any | None = None
    request_id: str | None = None


class ApiErrorResponse(BaseModel):
    error: ApiError


class PaginationMeta(BaseModel):
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    count: int = Field(..., ge=0)
    has_more: bool


class CollectionResponse[T](BaseModel):
    data: list[T]
    pagination: PaginationMeta

    model_config = ConfigDict(from_attributes=True)


LegoSetCollectionResponse = CollectionResponse[LegoSetResponse]
ListingCollectionResponse = CollectionResponse[ListingResponse]
PortfolioItemCollectionResponse = CollectionResponse[PortfolioItemResponse]
PriceSnapshotCollectionResponse = CollectionResponse[PriceSnapshotResponse]


def collection_response(items: list, *, limit: int, offset: int) -> dict:
    has_more = len(items) > limit
    data = items[:limit]
    return {
        "data": data,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(data),
            "has_more": has_more,
        },
    }
