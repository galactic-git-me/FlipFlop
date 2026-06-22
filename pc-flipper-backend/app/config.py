from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://flipper:flipper@127.0.0.1:5432/pcflipper"
    sync_database_url: str = "postgresql://flipper:flipper@127.0.0.1:5432/pcflipper"
    redis_url: str = ""  # empty = Redis disabled

    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_primary_model: str = "google/gemma-4-31b-it:free"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"

    ebay_app_id: str = ""
    ebay_client_secret: str = ""
    # "production" | "sandbox"
    ebay_environment: str = "production"
    # Use official eBay API as primary path; scraper is fallback.
    ebay_use_api: bool = True
    ebay_proxy_url: str = ""
    outbound_proxy_url: str = ""
    ebay_delay_min_seconds: float = 4.0
    ebay_delay_max_seconds: float = 10.0
    ebay_block_cooldown_seconds: float = 45.0
    ebay_block_circuit_breaker_threshold: int = 4
    ebay_block_circuit_breaker_cooldown_minutes: int = 45
    ebay_playwright_state_path: str = "data/ebay_playwright_state.json"
    browser_cdp_url: str = ""
    ebay_verification_token: str = ""
    # Public HTTPS callback URL that eBay is configured to call for deletion notifications.
    # Example: https://your-domain.tld/api/ebay/marketplace-account-deletion
    ebay_notification_endpoint: str = ""
    ebay_reselling_enabled: bool = True
    ebay_message_poll_interval_seconds: int = 300
    ebay_sales_poll_interval_seconds: int = 1800
    ebay_walkaway_margin_pct: float = 0.15
    # Set to 0.0 when eBay is running a fee promotion (e.g. private sellers pay 0%)
    ebay_final_value_fee_pct: float = 0.127
    flipflop_logo_path: str = "public/flipflop-logo.png"
    merkandi_api_key: str = ""

    stability_api_key: str = ""
    image_gen_provider: str = "pollinations"

    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0
    max_concurrent_scrapers: int = 8
    source_retry_delay_minutes: int = 8
    source_retry_max_terms: int = 20

    flip_scan_interval_minutes: int = 60
    parts_update_interval_hours: int = 24
    estimation_interval_hours: int = 24
    compliant_ingestion_manifest_path: str = "config/compliant_sources.json"
    compliant_ingestion_interval_hours: int = 6

    max_concurrent_flips: int = 1
    auto_buy_autonomous: bool = False
    auto_buy_daily_limit: int = 3

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "FlipFlop/1.0 PC deal scanner (by /u/flipflop_bot)"

    ntfy_topic: str = ""
    ram_watch_enabled: bool = True
    ram_watch_threshold_gbp: float = 240.0   # DDR5 RAM
    ram_watch_ddr4_threshold_gbp: float = 55.0
    ram_watch_cpu_threshold_gbp: float = 100.0
    ram_watch_mobo_threshold_gbp: float = 70.0
    ram_watch_gpu_threshold_gbp: float = 200.0

    frontend_url: str = "http://localhost:3000"
    admin_api_key: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""

    # "dev" clears search_telemetry on every startup so figures start fresh.
    # "production" preserves history across restarts.
    app_env: str = "dev"

    class Config:
        env_file = (".env.local", ".env")
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
