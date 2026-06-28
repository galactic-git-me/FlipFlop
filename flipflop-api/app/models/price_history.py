from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import enum


class PriceHistoryType(str, enum.Enum):
    listing = "listing"
    part = "part"
    resale_estimate = "resale_estimate"


class PriceHistory(Base):
    """Immutable price log — never deleted, only appended."""
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[PriceHistoryType] = mapped_column(Enum(PriceHistoryType))
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    price: Mapped[float] = mapped_column(Float)
    condition: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(100))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
