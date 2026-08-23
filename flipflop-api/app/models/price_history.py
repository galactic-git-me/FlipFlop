"""Price history model for tracking price changes over time (Phase 2, F2.1.4)."""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PriceHistory(Base):
    """Immutable record of price changes on a build.

    Used to track pricing trends and detect patterns:
    - Price volatility (how much does price fluctuate?)
    - Decline trajectory (is price dropping steadily?)
    - Optimal timing (when to relist?)
    """
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"), index=True)
    # Price stored in pennies (£79.99 → 7999) to avoid float rounding
    price_gbp: Mapped[int] = mapped_column(Integer)
    # Reason for price change (e.g., "five_star_adjustment", "recreate_cycle", "user_manual")
    reason: Mapped[str] = mapped_column(String(100))
    # Previous price (pennies) for calculating delta
    previous_price_gbp: Mapped[int | None] = mapped_column(Integer)
    # When this price was recorded
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<PriceHistory {self.id} build={self.manual_build_id} price=£{self.price_gbp/100:.2f}>"

    @property
    def price_change_gbp(self) -> int | None:
        """Calculate price change from previous price (in pennies)."""
        if self.previous_price_gbp is None:
            return None
        return self.price_gbp - self.previous_price_gbp
