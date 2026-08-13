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
    ollama_model: Mapped[str] = mapped_column(String(100), default="gemma3:4b")
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

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
