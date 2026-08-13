"""
Row 49 fix for the "sold-comp pricing ratchets down" risk: a fast or
near-asking sale is an underpriced signal that should push the *next*
similar build's initial pricing anchor up, not just reset to the same
starting point every cycle. Keyed by CPU tier (the same tiering used by
FlipIntelligence) as a simple, low-cardinality proxy for "similar build".
"""
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PricingBias(Base):
    __tablename__ = "pricing_bias"

    cpu_tier: Mapped[str] = mapped_column(String(50), primary_key=True)
    anchor_bias_pct: Mapped[float] = mapped_column(Float, default=0.0)
    triggered_by_flip_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
