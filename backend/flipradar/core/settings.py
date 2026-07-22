from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = Field(default="FlipRadar", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    sqlalchemy_log_level: str = Field(default="WARNING", alias="SQLALCHEMY_LOG_LEVEL")
    uvicorn_access_log_level: str = Field(
        default="INFO", alias="UVICORN_ACCESS_LOG_LEVEL"
    )

    database_host: str = Field(default="localhost", alias="DATABASE_HOST")
    database_port: int = Field(default=5432, alias="DATABASE_PORT")
    database_name: str = Field(default="flipradar", alias="DATABASE_NAME")
    database_user: str = Field(default="flipradar_app", alias="DATABASE_USER")
    database_password: str = Field(alias="DATABASE_PASSWORD")
    database_ssl_mode: str = Field(default="prefer", alias="DATABASE_SSL_MODE")
    database_pool_size: int = Field(default=5, ge=1, le=50, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(
        default=10, ge=0, le=100, alias="DATABASE_MAX_OVERFLOW"
    )
    ebay_api_configured: bool = Field(default=False, alias="EBAY_API_CONFIGURED")
    bricklink_api_configured: bool = Field(
        default=False, alias="BRICKLINK_API_CONFIGURED"
    )
    jwt_secret_key: str = Field(..., min_length=32, alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60, ge=1, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @computed_field
    @property
    def database_url(self) -> str:
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
