from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

    # Gemini (free-tier fallback provider)
    gemini_api_key: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""

    #admin
    admin_emails: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # App
    secret_key: str = "dev-secret-change-in-prod"
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
