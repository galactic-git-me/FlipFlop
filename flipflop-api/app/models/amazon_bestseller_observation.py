"""Daily Amazon Best Sellers observations matched to canonical products."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AmazonBestsellerObservation(Base):
    __tablename__ = "amazon_bestseller_observations"
    __table_args__ = (
        Index("ix_amazon_bestseller_obs_cpk_time", "cpk", "captured_at"),
        Index("ix_amazon_bestseller_obs_category_rank", "category", "rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    list_name: Mapped[str] = mapped_column(String(200))
    asin: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    rank: Mapped[int] = mapped_column(Integer)
    cpk: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
