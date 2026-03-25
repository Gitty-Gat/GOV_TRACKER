from typing import Literal

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Civic Ledger"
    congress_api_key: str = "DEMO_KEY"
    fec_api_key: str = "DEMO_KEY"
    current_congress: int = 119
    default_cycle: int = 2026
    database_url: str | None = None
    database_path: str = "data/civic_ledger.db"
    request_timeout_seconds: int = 30
    officials_sync_hours: int = 24
    detail_cache_hours: int = 24
    activity_cache_hours: int = 12
    finance_cache_hours: int = 18
    promise_cache_hours: int = 48
    vercel_team_id: str | None = None
    vercel_project_id: str | None = None
    vercel_token: str | None = None
    render_api_key: str | None = None
    render_owner_id: str | None = None
    render_service_id: str | None = None
    render_api_url: str = "https://api.render.com/v1"
    preferred_deploy_target: Literal["vercel", "render"] = "render"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
