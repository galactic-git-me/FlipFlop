from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./pcflipper.db"
    sync_database_url: str = "sqlite:///./pcflipper.db"
    redis_url: str = ""  # empty = Redis disabled

    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_primary_model: str = "google/gemma-4-31b-it:free"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"

    ebay_app_id: str = ""
    ebay_client_secret: str = ""

    stability_api_key: str = ""
    image_gen_provider: str = "pollinations"

    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0
    max_concurrent_scrapers: int = 3

    flip_scan_interval_minutes: int = 60
    parts_update_interval_hours: int = 24
    estimation_interval_hours: int = 24

    max_concurrent_flips: int = 1
    auto_buy_autonomous: bool = False
    auto_buy_daily_limit: int = 3

    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
