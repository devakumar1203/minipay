from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://paypal:paypal@localhost:5432/paypal"
    REDIS_URL: str = "redis://localhost:6379/0"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    JWT_SECRET: str = "minipay-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    BANK_X_API_URL: str = "http://localhost:8010"
    BANK_Y_API_URL: str = "http://localhost:8020"
    BANK_X_API_KEY: str = "bank-x-api-key-secret"
    BANK_Y_API_KEY: str = "bank-y-api-key-secret"
    BANK_HMAC_SECRET: str = "shared-hmac-secret-for-signing"
    ADMIN_EMAIL: str = "admin@minipay.com"
    ADMIN_PASSWORD: str = "Admin123!"
    # Fraud thresholds
    FRAUD_MAX_TXN_AMOUNT: int = 5000000       # 50,000 INR in paise
    FRAUD_DAILY_MAX_AMOUNT: int = 20000000     # 2,00,000 INR in paise
    FRAUD_MAX_TXN_PER_MINUTE: int = 5
    FRAUD_NEW_ACCOUNT_DAYS: int = 7
    FRAUD_NEW_ACCOUNT_MAX_TXN: int = 1000000   # 10,000 INR in paise
    FRAUD_LOGIN_MAX_ATTEMPTS: int = 5
    FRAUD_LOGIN_LOCKOUT_MINUTES: int = 15
    RECONCILIATION_PENDING_MINUTES: int = 10
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
