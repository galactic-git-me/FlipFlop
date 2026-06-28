"""
FlipIntelligence — immutable record written when a flip is marked as sold.
Powers the /intel/* endpoints and recommendation engine.
"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class FlipIntelligence(Base):
    __tablename__ = "flip_intelligence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flip_id: Mapped[int] = mapped_column(Integer, ForeignKey("flips.id"), unique=True, index=True)

    # Buy side
    source_site: Mapped[str] = mapped_column(String(100), index=True)
    buy_price: Mapped[float] = mapped_column(Float)
    gem_score_at_buy: Mapped[float] = mapped_column(Float, default=0.0)
    cpu_tier: Mapped[str | None] = mapped_column(String(50), index=True)
    had_gpu: Mapped[bool] = mapped_column(Boolean, default=False)
    had_storage: Mapped[bool] = mapped_column(Boolean, default=False)
    ram_gb: Mapped[int | None] = mapped_column(Integer)
    case_theme: Mapped[str | None] = mapped_column(String(100), index=True)
    upgrade_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float)

    # Sell side
    sell_price: Mapped[float] = mapped_column(Float)
    sell_platform: Mapped[str] = mapped_column(String(50), index=True)
    days_to_sell: Mapped[int] = mapped_column(Integer, default=0)

    # Outcomes
    profit: Mapped[float] = mapped_column(Float)
    roi_pct: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
