from typing import ClassVar
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://fieldops:fieldops@localhost:5432/fieldops"
    APP_ENV: str = "development"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # LLM reliability parameters
    LLM_PROVIDER: str = "openai"  # "openai" or "fake"
    LOAD_TEST_MODE: bool = False
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 3

    # Database connection reliability and pool tuning
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: float = 30.0
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # Business timezone & scheduling parameters
    BUSINESS_TIMEZONE: str = "Asia/Tokyo"
    DEFAULT_APPOINTMENT_DURATION_MINUTES: int = 120
    DEFAULT_SLOT_STEP_MINUTES: int = 60

    # Application flags & security
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["*"]
    MAX_REQUEST_MESSAGE_LENGTH: int = 2000

    # JWT Authentication & Authorization security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Rate limiting configuration (Phase 18)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_MAX_REQUESTS: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 60
    RATE_LIMIT_SERVICE_REQUEST_MAX_REQUESTS: int = 60
    RATE_LIMIT_SERVICE_REQUEST_WINDOW_SECONDS: int = 60

    # Workflow checkpoint parameters
    CHECKPOINTER_BACKEND: str = "sqlite"  # "sqlite" or "postgres"
    CHECKPOINT_DB_PATH: str = "checkpoints.sqlite"
    CHECKPOINT_POSTGRES_POOL_SIZE: int = 10

    # Redis & Task Queue (Celery) configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    # External Integration providers
    CALENDAR_PROVIDER: str = "fake"  # "fake" or "google"
    EMAIL_PROVIDER: str = "fake"
    ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION: bool = False

    # Google Calendar Integration settings (Phase 25)
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_SERVICE_ACCOUNT_FILE: str | None = None
    GOOGLE_CREDENTIALS_JSON: str | None = None
    GOOGLE_CALENDAR_DELEGATED_USER: str | None = None
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None
    GOOGLE_OAUTH_REFRESH_TOKEN: str | None = None
    GOOGLE_CALENDAR_DRY_RUN: bool = False
    GOOGLE_API_TIMEOUT_SECONDS: float = 15.0

    # Inbound Intake configuration (Phase 16)
    WEBHOOK_SHARED_SECRET: str = "fieldops-webhook-secret-dev"
    ENABLE_FAKE_INTAKE: bool | None = None

    @field_validator("CALENDAR_PROVIDER")
    @classmethod
    def validate_calendar_provider(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in ("fake", "google"):
            raise ValueError(f"Unsupported calendar provider '{v}'. Must be 'fake' or 'google'.")
        return clean

    @field_validator("EMAIL_PROVIDER")
    @classmethod
    def validate_email_provider(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in ("fake",):
            raise ValueError(f"Unsupported email provider '{v}'. Only 'fake' is currently supported.")
        return clean

    @field_validator("CHECKPOINTER_BACKEND")
    @classmethod
    def validate_checkpointer_backend(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in ("sqlite", "postgres"):
            raise ValueError(f"Unsupported CHECKPOINTER_BACKEND '{v}'. Must be 'sqlite' or 'postgres'.")
        return clean

    INSECURE_JWT_SECRETS: ClassVar[set[str]] = {
        "secret",
        "secretkey",
        "changeme",
        "admin",
        "password",
        "default",
        "test",
        "dev",
        "fieldops-insecure-secret-key-change-in-production",
        "fieldops-admin-super-secret-key-change-in-production",
        "fieldops-customer-secret-key-change-in-production",
    }

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str | None) -> str:
        if not v or not str(v).strip():
            raise ValueError("JWT_SECRET must be configured and cannot be empty.")
        clean = str(v).strip()
        if len(clean) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long for cryptographic security.")
        if clean.lower() in cls.INSECURE_JWT_SECRETS:
            raise ValueError(f"JWT_SECRET cannot use known insecure default secret: '{clean}'")
        return clean

    @model_validator(mode="after")
    def validate_production_guard(self) -> "Settings":
        # Default ENABLE_FAKE_INTAKE based on environment if not explicitly set
        if self.ENABLE_FAKE_INTAKE is None:
            self.ENABLE_FAKE_INTAKE = self.APP_ENV != "production"

        if self.APP_ENV == "production":
            if self.DEBUG:
                raise ValueError("Production configuration error: DEBUG mode cannot be enabled in production.")

            if self.WEBHOOK_SHARED_SECRET == "fieldops-webhook-secret-dev":
                raise ValueError(
                    "Production configuration error: Default insecure WEBHOOK_SHARED_SECRET is not allowed in production."
                )

            if self.CHECKPOINTER_BACKEND == "sqlite":
                raise ValueError(
                    "Production configuration error: Local SQLite checkpointer is not allowed in production. "
                    "Set CHECKPOINTER_BACKEND='postgres' to ensure shared checkpointing across API replicas."
                )

            if (
                self.CALENDAR_PROVIDER == "fake" or self.EMAIL_PROVIDER == "fake"
            ) and not self.ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION:
                raise ValueError(
                    "Production configuration error: Fake integration providers are not allowed in production "
                    "unless ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION=true is explicitly configured."
                )
        return self

    @property
    def postgres_dsn(self) -> str:
        """Return standard PostgreSQL connection string without driver suffix for psycopg."""
        url = self.DATABASE_URL
        if "+psycopg" in url:
            return url.replace("+psycopg", "")
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "")
        return url

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
