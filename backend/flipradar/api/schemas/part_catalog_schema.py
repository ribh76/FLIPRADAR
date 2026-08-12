from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from flipradar.api.schemas.common_schema import PaginationMeta


class CatalogEntityResponse(BaseModel):
    id: UUID
    canonical_identifier: str
    provider_identifiers: dict[str, str]
    name: str
    aliases: list[str]
    mold_variants: list[dict | str]
    image_urls: list[str]
    quality_flags: list[str]
    first_known_year: int | None
    last_known_year: int | None
    source_name: str | None
    source_url: str | None
    source_updated_at: datetime | None
    fetched_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PartCatalogResponse(CatalogEntityResponse):
    category: CatalogEntityResponse | None
    available_colors: list[CatalogEntityResponse] = Field(default_factory=list)
    market_price: float | None = None
    market_price_currency: str | None = None


class PartCatalogSearchResult(PartCatalogResponse):
    match_type: Literal[
        "exact_part_number",
        "exact_name",
        "exact_alias",
        "name_text",
        "alias_text",
        "fuzzy",
    ]
    match_confidence: Literal["exact", "high", "medium"]
    match_explanation: str


class PartCatalogSearchResponse(BaseModel):
    query: str
    source: Literal["local", "provider"]
    results: list[PartCatalogSearchResult]
    pagination: PaginationMeta


class PartCatalogSyncResponse(BaseModel):
    provider: str
    synchronized: int
    results: list[PartCatalogResponse]
