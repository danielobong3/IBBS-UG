from pydantic import BaseSettings, AnyUrl


class Settings(BaseSettings):
    APP_NAME: str = "IBBS"
    DEBUG: bool = True
    DATABASE_URL: AnyUrl
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "replace-me"
    ALEMBIC_LOCATION: str = "alembic"
    # JWT / auth settings
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Rate limiting for login attempts (max attempts per window)
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    # Payment provider secrets (configure in .env)
    FLUTTERWAVE_SECRET: str = ""
    MTN_SECRET: str = ""
    AIRTEL_SECRET: str = ""
    PAYMENT_CALLBACK_HOST: str = "http://localhost:8000"
    SENTRY_DSN: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
