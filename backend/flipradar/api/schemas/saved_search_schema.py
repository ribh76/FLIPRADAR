from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SavedSearchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    filter_config: dict


class SavedSearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    filter_config: dict | None = None


class SavedSearchResponse(BaseModel):
    id: UUID
    name: str
    filter_config: dict
    filter_version: int
    last_run_at: datetime | None
    result_count: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
