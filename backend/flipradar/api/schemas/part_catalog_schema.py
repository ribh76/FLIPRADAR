from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class PartCatalogSearchResponse(BaseModel):
    query: str
    source: Literal["local", "provider"]
    results: list[PartCatalogResponse]


class PartCatalogSyncResponse(BaseModel):
    provider: str
    synchronized: int
    results: list[PartCatalogResponse]
