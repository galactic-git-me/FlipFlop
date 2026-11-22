"""Daily condition- and market-separated component price evidence snapshots."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ComponentPriceRangeSnapshot(Base):
    __tablename__ = "component_price_range_snapshots"
    __table_args__ = (
        UniqueConstraint("cpk", "condition", "market_kind", "geography", "snapshot_date",
                         name="uq_component_price_range_snapshot_key"),
        Index("ix_component_price_range_snapshot_identity", "cpk", "condition", "market_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cpk: Mapped[str] = mapped_column(String(255), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    market_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    geography: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    lower_gbp: Mapped[float | None] = mapped_column(Float)
    median_gbp: Mapped[float | None] = mapped_column(Float)
    upper_gbp: Mapped[float | None] = mapped_column(Float)
    raw_sample_count: Mapped[int] = mapped_column(nullable=False)
    accepted_sample_count: Mapped[int] = mapped_column(nullable=False)
    excluded_outlier_count: Mapped[int] = mapped_column(nullable=False)
    sources: Mapped[list] = mapped_column(JSON, nullable=False)
    references: Mapped[list] = mapped_column(JSON, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_from: Mapped[datetime | None] = mapped_column(DateTime)
    observed_to: Mapped[datetime | None] = mapped_column(DateTime)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
