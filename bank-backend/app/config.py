from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://bank_x:bank_x@localhost:5433/bank_x"
    JWT_SECRET: str = "bank-jwt-secret-dev"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 120
    BANK_ID: str = "bank_x"
    BANK_NAME: str = "Bank X"
    API_KEY: str = "bank-x-api-key-secret"
    HMAC_SECRET: str = "shared-hmac-secret-for-signing"
    SEED_BALANCE: int = 1000000  # 10,000 INR in paise
    PORT: int = 8010
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

