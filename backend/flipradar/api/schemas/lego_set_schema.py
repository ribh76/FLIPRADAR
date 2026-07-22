from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def validate_retirement_year(self):
        if (
            self.release_year is not None
            and self.retirement_year is not None
            and self.retirement_year < self.release_year
        ):
            raise ValueError("retirement_year must be greater than or equal to release_year")
        return self


class LegoSetResponse(LegoSetCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
