import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

EMAIL_FORMAT_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._%+-]*@[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*\.(com|org)$"
)


def normalize_email_address(value: object) -> str:
    return str(value).strip().lower()


def normalize_account_identifier(value: object) -> str:
    return str(value).strip().lower()


def validate_password_strength_value(value: str) -> str:
    letter_count = sum(character.isalpha() for character in value)
    has_number = any(character.isdigit() for character in value)
    has_special = any(
        not character.isalnum() and not character.isspace() for character in value
    )
    if letter_count < 2 or not has_number or not has_special:
        raise ValueError(
            "Password must include at least two letters, one number, and one special character"
        )
    return value


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

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> str:
        return normalize_account_identifier(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str:
        return normalize_email_address(value)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: EmailStr) -> str:
        normalized = normalize_email_address(value)
        if EMAIL_FORMAT_PATTERN.fullmatch(normalized) is None:
            raise ValueError(
                "Email must use username@domain.com or username@domain.org"
            )
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return validate_password_strength_value(value)


class UserLogin(BaseModel):
    username_or_email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("username_or_email", mode="before")
    @classmethod
    def normalize_identifier(cls, value: object) -> str:
        return normalize_account_identifier(value)


class UserResponse(BaseModel):
    id: UUID
    username: str
    display_name: str | None = None
    email: str
    pending_email: str | None = None
    is_email_verified: bool
    deletion_requested_at: datetime | None = None
    deletion_scheduled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1)


class EmailVerificationRequest(BaseModel):
    token: str = Field(..., min_length=1)


class EmailVerificationResponse(BaseModel):
    verified: bool
    message: str


class ResendVerificationResponse(BaseModel):
    sent: bool
    throttled: bool = False
    message: str


class PasswordResetRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str:
        return normalize_email_address(value)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return validate_password_strength_value(value)


class PasswordResetResponse(BaseModel):
    message: str


class AccountSettingsUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return validate_password_strength_value(value)


class EmailChangeRequest(BaseModel):
    new_email: EmailStr
    current_password: str = Field(..., min_length=1, max_length=128)

    @field_validator("new_email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str:
        return normalize_email_address(value)

    @field_validator("new_email")
    @classmethod
    def validate_email_format(cls, value: EmailStr) -> str:
        normalized = normalize_email_address(value)
        if EMAIL_FORMAT_PATTERN.fullmatch(normalized) is None:
            raise ValueError(
                "Email must use username@domain.com or username@domain.org"
            )
        return normalized


class EmailChangeConfirmRequest(BaseModel):
    token: str = Field(..., min_length=1)


class AccountActionResponse(BaseModel):
    message: str


class AccountDeletionRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)


class AccountDeletionResponse(BaseModel):
    message: str
    deletion_scheduled_at: datetime


class RefreshSessionResponse(BaseModel):
    id: UUID
    created_at: datetime
    last_seen_at: datetime | None = None
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)
