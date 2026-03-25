from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Civic Ledger"
    congress_api_key: str = "DEMO_KEY"
    fec_api_key: str = "DEMO_KEY"
    current_congress: int = 119
    default_cycle: int = 2026
    database_path: str = "data/civic_ledger.db"
    request_timeout_seconds: int = 30
    officials_sync_hours: int = 24
    detail_cache_hours: int = 24
    activity_cache_hours: int = 12
    finance_cache_hours: int = 18
    promise_cache_hours: int = 48

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
