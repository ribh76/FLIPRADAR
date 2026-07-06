from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=80,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description=(
            "Lowercase letters, numbers, underscores, and hyphens; "
            "must start with a letter or number."
        ),
    )
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_identifier(cls, value: object) -> str:
        return str(value).strip().lower()


class UserLogin(BaseModel):
    username_or_email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("username_or_email", mode="before")
    @classmethod
    def normalize_identifier(cls, value: object) -> str:
        return str(value).strip().lower()


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
