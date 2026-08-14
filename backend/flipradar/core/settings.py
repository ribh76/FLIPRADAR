from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LlmProviderName(StrEnum):
    ANTHROPIC = "anthropic"


class ApplicationSettings(BaseModel):
    name: str
    environment: AppEnvironment
    debug: bool
    frontend_url: str


class DatabaseSettings(BaseModel):
    url_override: str | None
    host: str
    port: int
    name: str
    user: str
    password: str
    ssl_mode: str
    pool_size: int
    max_overflow: int
    wait_timeout_seconds: int
    alembic_url_override: str | None

    @property
    def url(self) -> str:
        if self.url_override:
            return self.url_override
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{self.name}"

    @property
    def alembic_url(self) -> str:
        return self.alembic_url_override or self.url


class AuthenticationSettings(BaseModel):
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    email_verification_token_expire_minutes: int
    password_reset_token_expire_minutes: int
    mfa_token_expire_minutes: int
    mfa_max_attempts: int
    account_token_resend_cooldown_seconds: int
    password_min_length: int


class EmailSettings(BaseModel):
    enabled: bool
    provider: str
    from_address: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str | None
    auth_email_app_password: str | None
    timeout_seconds: int

    @property
    def configured(self) -> bool:
        if not self.enabled:
            return False
        return bool(self.smtp_host and self.smtp_username and self.password)

    @property
    def password(self) -> str | None:
        return self.auth_email_app_password or self.smtp_password


class ProviderSettings(BaseModel):
    enabled: bool
    configured: bool
    timeout_seconds: int
    api_key: str | None = None
    api_secret: str | None = None
    consumer_key: str | None = None
    consumer_secret: str | None = None
    token_value: str | None = None
    token_secret: str | None = None

    @property
    def usable(self) -> bool:
        return self.enabled and self.configured


class MarketplaceApiSettings(BaseModel):
    ebay: ProviderSettings
    bricklink: ProviderSettings


class LlmSettings(BaseModel):
    enabled: bool
    provider: LlmProviderName
    api_key: str | None
    model: str
    timeout_seconds: int
    max_tokens: int
    max_retries: int
    retry_backoff_seconds: float
    user_rate_limit: int
    global_rate_limit: int
    rate_limit_window_seconds: int
    input_cost_per_million_tokens: float
    output_cost_per_million_tokens: float

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.api_key)


class LoggingSettings(BaseModel):
    level: str
    sqlalchemy_level: str
    uvicorn_access_level: str


class ObservabilitySettings(BaseModel):
    release: str
    sentry_dsn: str | None
    error_rate_alert_threshold_percent: float
    error_rate_alert_minimum_requests: int
    error_rate_alert_window_seconds: int


class CorsSettings(BaseModel):
    allowed_origins: list[str]
    allow_credentials: bool
    allow_methods: list[str]
    allow_headers: list[str]


def _split_csv(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    app_name: str = Field(default="FlipRadar", alias="APP_NAME")
    app_env: AppEnvironment = Field(default=AppEnvironment.DEVELOPMENT, alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    frontend_url: str = Field(default="http://127.0.0.1:5173", alias="FRONTEND_URL")
    app_release: str = Field(default="unknown", alias="APP_RELEASE")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    sqlalchemy_log_level: str = Field(default="WARNING", alias="SQLALCHEMY_LOG_LEVEL")
    uvicorn_access_log_level: str = Field(
        default="INFO", alias="UVICORN_ACCESS_LOG_LEVEL"
    )
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    error_rate_alert_threshold_percent: float = Field(
        default=5.0, ge=0, le=100, alias="ERROR_RATE_ALERT_THRESHOLD_PERCENT"
    )
    error_rate_alert_minimum_requests: int = Field(
        default=20, ge=1, alias="ERROR_RATE_ALERT_MINIMUM_REQUESTS"
    )
    error_rate_alert_window_seconds: int = Field(
        default=300, ge=1, alias="ERROR_RATE_ALERT_WINDOW_SECONDS"
    )

    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")
    database_host: str = Field(default="localhost", alias="DATABASE_HOST")
    database_port: int = Field(default=5432, alias="DATABASE_PORT")
    database_name: str = Field(default="flipradar", alias="DATABASE_NAME")
    database_user: str = Field(default="flipradar_app", alias="DATABASE_USER")
    database_password: str = Field(
        default="flipradar_dev_password", alias="DATABASE_PASSWORD"
    )
    database_ssl_mode: str = Field(default="prefer", alias="DATABASE_SSL_MODE")
    database_pool_size: int = Field(default=5, ge=1, le=50, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(
        default=10, ge=0, le=100, alias="DATABASE_MAX_OVERFLOW"
    )
    database_wait_timeout_seconds: int = Field(
        default=60, ge=1, alias="DATABASE_WAIT_TIMEOUT"
    )
    alembic_database_url: str | None = Field(default=None, alias="ALEMBIC_DATABASE_URL")

    jwt_secret_key: str = Field(
        default="local-development-secret-change-before-production",
        min_length=32,
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=15, ge=1, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(
        default=30, ge=1, alias="REFRESH_TOKEN_EXPIRE_DAYS"
    )
    email_verification_token_expire_minutes: int = Field(
        default=30, ge=1, alias="EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES"
    )
    password_reset_token_expire_minutes: int = Field(
        default=15, ge=1, alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES"
    )
    mfa_token_expire_minutes: int = Field(
        default=60, ge=60, le=60, alias="MFA_TOKEN_EXPIRE_MINUTES"
    )
    mfa_max_attempts: int = Field(default=5, ge=1, le=10, alias="MFA_MAX_ATTEMPTS")
    account_token_resend_cooldown_seconds: int = Field(
        default=300, ge=1, alias="ACCOUNT_TOKEN_RESEND_COOLDOWN_SECONDS"
    )
    password_min_length: int = Field(default=8, ge=8, alias="PASSWORD_MIN_LENGTH")

    email_enabled: bool = Field(default=False, alias="EMAIL_ENABLED")
    email_provider: str = Field(default="smtp", alias="EMAIL_PROVIDER")
    email_from_address: str = Field(
        default="auth@flipradar.com", alias="EMAIL_FROM_ADDRESS"
    )
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="auth@flipradar.com", alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    auth_email_app_password: str | None = Field(
        default=None, alias="AUTH_EMAIL_APP_PASSWORD"
    )
    email_timeout_seconds: int = Field(default=10, ge=1, alias="EMAIL_TIMEOUT_SECONDS")

    ebay_api_enabled: bool = Field(default=False, alias="EBAY_API_ENABLED")
    ebay_api_configured: bool = Field(default=False, alias="EBAY_API_CONFIGURED")
    ebay_api_key: str | None = Field(default=None, alias="EBAY_API_KEY")
    ebay_api_secret: str | None = Field(default=None, alias="EBAY_API_SECRET")
    ebay_api_timeout_seconds: int = Field(
        default=10, ge=1, alias="EBAY_API_TIMEOUT_SECONDS"
    )

    bricklink_api_enabled: bool = Field(default=False, alias="BRICKLINK_API_ENABLED")
    bricklink_api_configured: bool = Field(
        default=False, alias="BRICKLINK_API_CONFIGURED"
    )
    bricklink_consumer_key: str | None = Field(
        default=None, alias="BRICKLINK_CONSUMER_KEY"
    )
    bricklink_consumer_secret: str | None = Field(
        default=None, alias="BRICKLINK_CONSUMER_SECRET"
    )
    bricklink_token_value: str | None = Field(
        default=None, alias="BRICKLINK_TOKEN_VALUE"
    )
    bricklink_token_secret: str | None = Field(
        default=None, alias="BRICKLINK_TOKEN_SECRET"
    )
    bricklink_api_timeout_seconds: int = Field(
        default=10, ge=1, alias="BRICKLINK_API_TIMEOUT_SECONDS"
    )

    pricing_currency: str = Field(
        default="USD", min_length=3, max_length=3, alias="PRICING_CURRENCY"
    )
    pricing_freshness_hours: int = Field(
        default=24, ge=1, alias="PRICING_FRESHNESS_HOURS"
    )
    pricing_retention_days: int = Field(
        default=730, ge=1, alias="PRICING_RETENTION_DAYS"
    )
    portfolio_valuation_retention_days: int = Field(
        default=180, ge=1, alias="PORTFOLIO_VALUATION_RETENTION_DAYS"
    )

    llm_enabled: bool = Field(default=False, alias="LLM_ENABLED")
    llm_provider: LlmProviderName = Field(
        default=LlmProviderName.ANTHROPIC, alias="LLM_PROVIDER"
    )
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(default="claude-sonnet-4-6", alias="LLM_MODEL")
    llm_timeout_seconds: int = Field(default=30, ge=1, alias="LLM_TIMEOUT_SECONDS")
    llm_max_tokens: int = Field(default=1500, ge=1, alias="LLM_MAX_TOKENS")
    llm_max_retries: int = Field(default=2, ge=0, le=5, alias="LLM_MAX_RETRIES")
    llm_retry_backoff_seconds: float = Field(
        default=0.25, ge=0, le=10, alias="LLM_RETRY_BACKOFF_SECONDS"
    )
    llm_user_rate_limit: int = Field(default=10, ge=1, alias="LLM_USER_RATE_LIMIT")
    llm_global_rate_limit: int = Field(default=100, ge=1, alias="LLM_GLOBAL_RATE_LIMIT")
    llm_rate_limit_window_seconds: int = Field(
        default=60, ge=1, alias="LLM_RATE_LIMIT_WINDOW_SECONDS"
    )
    llm_input_cost_per_million_tokens: float = Field(
        default=3.0, ge=0, alias="LLM_INPUT_COST_PER_MILLION_TOKENS"
    )
    llm_output_cost_per_million_tokens: float = Field(
        default=15.0, ge=0, alias="LLM_OUTPUT_COST_PER_MILLION_TOKENS"
    )

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str | None = Field(default=None, alias="CELERY_BROKER_URL")
    celery_result_backend: str | None = Field(
        default=None, alias="CELERY_RESULT_BACKEND"
    )
    watchlist_worker_enabled: bool = Field(
        default=False, alias="WATCHLIST_WORKER_ENABLED"
    )
    watchlist_provider_hourly_limit: int = Field(
        default=60, ge=1, alias="WATCHLIST_PROVIDER_HOURLY_LIMIT"
    )

    cors_allowed_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        alias="CORS_ALLOWED_ORIGINS",
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: str = Field(default="*", alias="CORS_ALLOW_METHODS")
    cors_allow_headers: str = Field(default="*", alias="CORS_ALLOW_HEADERS")

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator(
        "database_url_override",
        "alembic_database_url",
        "smtp_password",
        "auth_email_app_password",
        "ebay_api_key",
        "ebay_api_secret",
        "bricklink_consumer_key",
        "bricklink_consumer_secret",
        "bricklink_token_value",
        "bricklink_token_secret",
        "anthropic_api_key",
        "sentry_dsn",
        mode="before",
    )
    @classmethod
    def blank_optional_strings_are_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_environment(self) -> Settings:
        if self.app_env == AppEnvironment.PRODUCTION:
            self._validate_production()
        return self

    def _validate_production(self) -> None:
        unsafe_secret = {
            "local-development-secret-change-before-production",
            "replace-with-at-least-32-random-characters",
        }
        if self.app_debug:
            raise ValueError("APP_DEBUG must be false in production.")
        if self.jwt_secret_key in unsafe_secret or len(self.jwt_secret_key) < 48:
            raise ValueError("JWT_SECRET_KEY must be a strong production secret.")
        if not self.database_url_override and self.database_password in {
            "flipradar_dev_password",
            "replace-with-a-secure-password",
        }:
            raise ValueError("DATABASE_PASSWORD must be a production secret.")
        if self.database_ssl_mode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("DATABASE_SSL_MODE must require SSL in production.")
        allowed_origins = _split_csv(self.cors_allowed_origins)
        if "*" in allowed_origins or not allowed_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must be explicit in production.")

    @property
    def application(self) -> ApplicationSettings:
        return ApplicationSettings(
            name=self.app_name,
            environment=self.app_env,
            debug=self.app_debug,
            frontend_url=self.frontend_url,
        )

    @property
    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings(
            url_override=self.database_url_override,
            host=self.database_host,
            port=self.database_port,
            name=self.database_name,
            user=self.database_user,
            password=self.database_password,
            ssl_mode=self.database_ssl_mode,
            pool_size=self.database_pool_size,
            max_overflow=self.database_max_overflow,
            wait_timeout_seconds=self.database_wait_timeout_seconds,
            alembic_url_override=self.alembic_database_url,
        )

    @property
    def auth(self) -> AuthenticationSettings:
        return AuthenticationSettings(
            jwt_secret_key=self.jwt_secret_key,
            jwt_algorithm=self.jwt_algorithm,
            access_token_expire_minutes=self.access_token_expire_minutes,
            refresh_token_expire_days=self.refresh_token_expire_days,
            email_verification_token_expire_minutes=(
                self.email_verification_token_expire_minutes
            ),
            password_reset_token_expire_minutes=self.password_reset_token_expire_minutes,
            mfa_token_expire_minutes=self.mfa_token_expire_minutes,
            mfa_max_attempts=self.mfa_max_attempts,
            account_token_resend_cooldown_seconds=(
                self.account_token_resend_cooldown_seconds
            ),
            password_min_length=self.password_min_length,
        )

    @property
    def email(self) -> EmailSettings:
        return EmailSettings(
            enabled=self.email_enabled,
            provider=self.email_provider,
            from_address=self.email_from_address,
            smtp_host=self.smtp_host,
            smtp_port=self.smtp_port,
            smtp_username=self.smtp_username,
            smtp_password=self.smtp_password,
            auth_email_app_password=self.auth_email_app_password,
            timeout_seconds=self.email_timeout_seconds,
        )

    @property
    def marketplace(self) -> MarketplaceApiSettings:
        return MarketplaceApiSettings(
            ebay=ProviderSettings(
                enabled=self.ebay_api_enabled,
                configured=self.ebay_api_configured,
                timeout_seconds=self.ebay_api_timeout_seconds,
                api_key=self.ebay_api_key,
                api_secret=self.ebay_api_secret,
            ),
            bricklink=ProviderSettings(
                enabled=self.bricklink_api_enabled,
                configured=self.bricklink_api_configured,
                timeout_seconds=self.bricklink_api_timeout_seconds,
                consumer_key=self.bricklink_consumer_key,
                consumer_secret=self.bricklink_consumer_secret,
                token_value=self.bricklink_token_value,
                token_secret=self.bricklink_token_secret,
            ),
        )

    @property
    def llm(self) -> LlmSettings:
        return LlmSettings(
            enabled=self.llm_enabled,
            provider=self.llm_provider,
            api_key=self.anthropic_api_key,
            model=self.llm_model,
            timeout_seconds=self.llm_timeout_seconds,
            max_tokens=self.llm_max_tokens,
            max_retries=self.llm_max_retries,
            retry_backoff_seconds=self.llm_retry_backoff_seconds,
            user_rate_limit=self.llm_user_rate_limit,
            global_rate_limit=self.llm_global_rate_limit,
            rate_limit_window_seconds=self.llm_rate_limit_window_seconds,
            input_cost_per_million_tokens=self.llm_input_cost_per_million_tokens,
            output_cost_per_million_tokens=self.llm_output_cost_per_million_tokens,
        )

    @property
    def logging(self) -> LoggingSettings:
        return LoggingSettings(
            level=self.log_level,
            sqlalchemy_level=self.sqlalchemy_log_level,
            uvicorn_access_level=self.uvicorn_access_log_level,
        )

    @property
    def observability(self) -> ObservabilitySettings:
        return ObservabilitySettings(
            release=self.app_release,
            sentry_dsn=self.sentry_dsn,
            error_rate_alert_threshold_percent=(
                self.error_rate_alert_threshold_percent
            ),
            error_rate_alert_minimum_requests=self.error_rate_alert_minimum_requests,
            error_rate_alert_window_seconds=self.error_rate_alert_window_seconds,
        )

    @property
    def cors(self) -> CorsSettings:
        return CorsSettings(
            allowed_origins=_split_csv(self.cors_allowed_origins),
            allow_credentials=self.cors_allow_credentials,
            allow_methods=_split_csv(self.cors_allow_methods),
            allow_headers=_split_csv(self.cors_allow_headers),
        )

    @property
    def database_url(self) -> str:
        return self.database.url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
