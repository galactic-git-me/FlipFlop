"""Single-row settings table — keyed by name='default'."""
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, default="default")

    max_concurrent_flips: Mapped[int] = mapped_column(Integer, default=1)
    default_sell_platform: Mapped[str] = mapped_column(String(50), default="ebay")

    auto_buy_autonomous: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_buy_daily_limit: Mapped[int] = mapped_column(Integer, default=3)

    ollama_base_url: Mapped[str] = mapped_column(Text, default="http://localhost:11434")
    ollama_model: Mapped[str] = mapped_column(String(100), default="")
    openrouter_api_key: Mapped[str] = mapped_column(Text, default="")
    openrouter_primary_model: Mapped[str] = mapped_column(String(100), default="google/gemma-4-31b-it:free")
    ebay_app_id: Mapped[str] = mapped_column(Text, default="")

    image_gen_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    image_gen_provider: Mapped[str] = mapped_column(String(50), default="pollinations")

    # ── Seller Policies (playbook rows 11-15, 43, 44) — configured once here,
    # applied to every listing via the eBay Business Policies API, not
    # re-entered per build. Defaults proposed in the implementation plan.
    handling_time_days: Mapped[int] = mapped_column(Integer, default=2)
    returns_accepted: Mapped[bool] = mapped_column(Boolean, default=True)
    returns_window_days: Mapped[int] = mapped_column(Integer, default=30)
    free_shipping_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    local_pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    listing_type_default: Mapped[str] = mapped_column(String(20), default="FixedPrice")

    # ── eBay seller OAuth (3-legged) — unblocks every live eBay write
    # (posting, end/republish, Business Policies push, Promoted Listings).
    # access token is short-lived (~2h) and cached here; refresh_token is
    # long-lived (~18mo) and is what actually re-derives a valid access
    # token without the user re-consenting. Both blank until "Connect eBay"
    # is completed once in Settings.
    ebay_seller_refresh_token: Mapped[str] = mapped_column(Text, default="")
    ebay_seller_refresh_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    ebay_seller_access_token: Mapped[str] = mapped_column(Text, default="")
    ebay_seller_access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    ebay_seller_connected_at: Mapped[datetime | None] = mapped_column(DateTime)
    ebay_seller_scopes: Mapped[str] = mapped_column(Text, default="")

    # The extension's scheduler.defaultIntervalMinutes (chrome.storage.local
    # only — the backend otherwise has zero visibility into it). Synced
    # best-effort by the extension's setConfig() on every save (see
    # FlipFlopXtension/src/lib/storage.ts) via PUT /api/gem-radar/scan-interval.
    # Used to derive the "2 consecutive scan cycles missed -> inactive"
    # listing threshold — see gem_radar/observations.get_active_listing_ids.
    # Default matches the extension's own SchedulerConfigSchema default.
    gem_radar_scan_interval_minutes: Mapped[int] = mapped_column(Integer, default=180)
    # How many consecutive scan cycles a listing can go unseen before it's
    # treated as inactive — configurable in the extension's Retention
    # settings (retention.consecutiveMissesBeforeInactive), synced the same
    # way as gem_radar_scan_interval_minutes above.
    gem_radar_consecutive_misses_before_inactive: Mapped[int] = mapped_column(Integer, default=2)
    # Retention config (extension's retention.scrapeArtifactsHours /
    # preserveWatchedListingEvidence), synced the same way — see
    # app/main.py's _gem_radar_retention_loop, which previously ignored
    # these entirely and hardcoded 24h / no watched-evidence preservation.
    gem_radar_scrape_artifacts_hours: Mapped[int] = mapped_column(Integer, default=24)
    gem_radar_preserve_watched_evidence: Mapped[bool] = mapped_column(Boolean, default=True)

    # CPK-based deal classification (see app/gem_radar/deal_classification.py).
    # Market price for a CPK is only trusted once 2+ listings have
    # contributed to it (app/gem_radar/cpk_market.py) — a listing's %
    # offset is computed against whichever of lower/median/upper the user
    # picks here. All four thresholds are % offset from that market price
    # (negative = listing priced below market = a better deal); a listing
    # worse than deal_average_deal_threshold_pct falls through to POOR_DEAL.
    deal_market_price_source: Mapped[str] = mapped_column(String(10), default="median")  # lower|median|upper
    deal_super_gem_threshold_pct: Mapped[float] = mapped_column(Float, default=-30.0)
    deal_gem_threshold_pct: Mapped[float] = mapped_column(Float, default=-20.0)
    deal_ok_deal_threshold_pct: Mapped[float] = mapped_column(Float, default=-10.0)
    deal_average_deal_threshold_pct: Mapped[float] = mapped_column(Float, default=5.0)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
