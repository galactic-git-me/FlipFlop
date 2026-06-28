from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExternalDemandSignal(Base):
    __tablename__ = "external_demand_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)  # google_trends|reddit|steam_hardware
    topic: Mapped[str] = mapped_column(String(128), index=True)
    query: Mapped[str | None] = mapped_column(String(255), index=True)
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    signal_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
