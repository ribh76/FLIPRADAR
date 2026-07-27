from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from flipradar.api.schemas.validation import SetNumber


class LegoSetCreate(BaseModel):
    set_number: SetNumber = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)
    theme: str | None = Field(default=None, max_length=120)
    subtheme: str | None = Field(default=None, max_length=120)
    release_year: int | None = Field(default=None, ge=1949, le=2100)
    retirement_year: int | None = Field(default=None, ge=1949, le=2100)
    piece_count: int | None = Field(default=None, ge=0)
    minifig_count: int | None = Field(default=None, ge=0)
    msrp: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    region: str | None = Field(default=None, min_length=2, max_length=16)
    image_urls: list[str] | None = Field(default=None)
    source_name: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=1000)
    data_quality_flag: bool = False
    completeness_flag: bool = False

    @field_validator("original_currency", "region", mode="before")
    @classmethod
    def normalize_uppercase_metadata(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @model_validator(mode="after")
    def validate_retirement_year(self):
        if (
            self.release_year is not None
            and self.retirement_year is not None
            and self.retirement_year < self.release_year
        ):
            raise ValueError(
                "retirement_year must be greater than or equal to release_year"
            )
        return self


class LegoSetResponse(LegoSetCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
