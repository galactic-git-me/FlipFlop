from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://flipper:flipper@127.0.0.1:5432/pcflipper"
    sync_database_url: str = "postgresql://flipper:flipper@127.0.0.1:5432/pcflipper"
    # Optional acceleration cache. Leave blank when Redis is not installed;
    # sold-comps pricing continues to use its database-backed path.
    redis_url: str = ""

    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_primary_model: str = "google/gemma-4-31b-it:free"
    ollama_base_url: str = ""  # Disabled by default (set to enable, e.g. http://localhost:11434 — the default local Ollama port)
    ollama_model: str  # Must be set via OLLAMA_MODEL env var
    scrapingbee_api_key: str = ""  # For eBay sold comps scraping

    ebay_app_id: str = ""
    ebay_client_secret: str = ""
    # "production" | "sandbox"
    ebay_environment: str = "production"
    # Separate sandbox credentials for testing the listing/publish flow without
    # touching production (which is used for sourcing real listings).
    ebay_sandbox_app_id: str = ""
    ebay_sandbox_client_secret: str = ""
    ebay_sandbox_oauth_user_token: str = ""
    # Long-lived (~18 month) refresh token — used to silently mint fresh
    # 2-hour access tokens without repeating the browser sign-in flow.
    ebay_sandbox_refresh_token: str = ""
    # Sandbox Business Policy IDs (Payment/Return/Fulfillment) — required by
    # the Inventory API's createOffer call. Created once via the Account API.
    ebay_sandbox_payment_policy_id: str = ""
    ebay_sandbox_return_policy_id: str = ""
    ebay_sandbox_fulfillment_policy_id: str = ""

    # Which environment the listing/publish flow actually posts to —
    # "sandbox" (default, no real fees) or "production" (live, real listing).
    # Everything below this line mirrors the sandbox_* fields above but for
    # production, so credentials/token/policies switch together with this.
    ebay_listing_environment: str = "sandbox"
    ebay_production_oauth_user_token: str = ""
    ebay_production_refresh_token: str = ""
    ebay_production_payment_policy_id: str = ""
    ebay_production_return_policy_id: str = ""
    ebay_production_fulfillment_policy_id: str = ""
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
    # Single-seller store: unlike ebay_app_id/client_secret (app-level client
    # credentials, used for read-only Browse/search calls), listing writes
    # (create/end/republish) need a seller-authorized OAuth token, which eBay
    # only issues via a one-time 3-legged OAuth consent flow. No consent UI
    # exists yet — set this manually (and refresh it periodically) until one
    # is built. Background jobs that need it degrade gracefully when it's blank.
    ebay_seller_access_token: str = ""
    # eBay's OAuth quirk: the "redirect_uri" param in the authorize URL is
    # actually the RuName (a string identifier) you register for your app in
    # the eBay Developer Portal, not a literal callback URL — the portal maps
    # it to your real callback URL (ebay_oauth_callback_url below) server-side.
    ebay_ru_name: str = ""
    ebay_oauth_callback_url: str = "http://localhost:8000/api/ebay/oauth/callback"
    # Optional dedicated key material for encrypting OAuth tokens at rest.
    # When omitted, the eBay client secret is used so existing deployments
    # gain encryption without introducing another unmanaged production secret.
    ebay_token_encryption_key: str = ""
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

    # Meshy text-to-3D (component_3d_asset family-bucket generation pipeline —
    # see app/services/meshy_generation.py). Empty by default; the service
    # no-ops with a clear error until this is set, same convention as
    # anthropic_api_key etc.
    meshy_api_key: str = ""

    # Parcel2Go courier quotes (app/services/parcel2go_courier.py) — used by
    # the build sell page to quote real tracked-delivery cost from a build's
    # package weight/dimensions, so the asking price can bake in accurate
    # shipping instead of a hand-guessed flat rate. OAuth2 client_credentials
    # grant; create credentials at parcel2go.com/myaccount/api (sandbox) or
    # the production account equivalent.
    parcel2go_client_id: str = ""
    parcel2go_client_secret: str = ""
    # "sandbox" (default, no real charges) | "production"
    parcel2go_environment: str = "sandbox"

    # Figural price-only shipping-insurance quotes. These legacy environment
    # variable names already hold the Figural API key and secret in this app.
    # The pre-sale flow only calls /v2/parcel/get_price.
    secursus_api_identifier: str = ""
    secursus_api_secret_key: str = ""
    # Seller's own collection address — used as every booking's
    # CollectionAddress (where the courier picks up from) and as the
    # Parcel2Go order's CustomerDetails. Constant across all shipments,
    # unlike the buyer's DeliveryAddress which comes from the real eBay
    # order and differs every time.
    seller_forename: str = ""
    seller_surname: str = ""
    seller_email: str = ""
    seller_phone: str = ""
    seller_address_property: str = ""
    seller_address_street: str = ""
    seller_address_town: str = ""
    seller_address_county: str = ""
    seller_address_postcode: str = ""
    seller_address_country_iso: str = "GBR"

    # Destination used to verify time-sensitive case-supplier promises. Amazon
    # and Overclockers availability is postcode-specific; a Prime badge alone
    # is not sufficient evidence of next-day delivery.
    case_catalogue_delivery_postcode: str = "TW12 1JQ"

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

    # Full frozen-priority queue content sourcing. Candidates still require
    # owner approval before Meshy generation or publishing.
    case_content_sourcing_enabled: bool = True
    case_content_sourcing_interval_minutes: int = 30
    case_content_sourcing_batch_size: int = 100
    case_content_sourcing_concurrency: int = 2
    case_content_request_delay_seconds: float = 0.4

    max_concurrent_flips: int = 1
    max_concurrent_search_terms: int = 2  # Limit concurrent gem_radar searches to ease RAM pressure (95% full)
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

    frontend_url: str = "http://localhost:4313"
    # Admin UI destination for backend-owned browser flows such as eBay OAuth.
    # Kept separate from the public storefront URL used by customer-facing links.
    admin_frontend_url: str = ""
    admin_api_key: str = ""

    # Comma-separated list of origins allowed to call this API in dev/CORS.
    cors_allowed_origins: str = "http://localhost:4312,http://localhost:4313"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""

    smtp_host: str = ""
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "noreply@flipflop.co.uk"

    # Email monitor (IMAP)
    imap_host: str = ""
    imap_user: str = ""
    imap_pass: str = ""
    imap_folder: str = "INBOX"
    email_monitor_enabled: bool = False
    email_monitor_interval_seconds: int = 300  # 5 minutes

    # Auth
    secret_key: str = "dev-secret-key-change-in-production"  # MUST be set via environment in production
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 168  # 1 week

    # OAuth2 - Google
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/auth/callback"

    # OAuth2 - GitHub
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:3000/auth/callback"

    # "dev" clears search_telemetry on every startup so figures start fresh.
    # "production" preserves history across restarts.
    app_env: str = "dev"
    # Production storefront API mode: serve catalogue, auth, orders and
    # payments without starting ingestion, browser, scheduler or LLM workers.
    # Those remain on the GPU workstation and publish completed results to the
    # production database through the worker integration path.
    web_only: bool = False

    class Config:
        env_file = (".env.local", ".env")
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
