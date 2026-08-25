from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BuildSoldObservation(Base):
    __tablename__ = "build_sold_observations"
    __table_args__ = (
        Index("ix_build_sold_obs_build_time", "build_id", "observed_at"),
        Index("uq_build_sold_obs_build_url", "build_id", "source_url", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    build_id: Mapped[int] = mapped_column(ForeignKey("manual_builds.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(1000))
    price: Mapped[float] = mapped_column(Float)
    postage: Mapped[float] = mapped_column(Float, default=0.0)
    condition: Mapped[str] = mapped_column(String(20), default="unknown")
    sold_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    match_basis: Mapped[str] = mapped_column(String(255))
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
