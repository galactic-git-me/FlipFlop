from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OrderCheckoutSnapshot(Base):
    """Short-lived private address snapshot held until a paid order is created."""

    __tablename__ = "order_checkout_snapshots"
    __table_args__ = (Index("ix_order_checkout_snapshots_payment_intent_id", "payment_intent_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_intent_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_address: Mapped[dict] = mapped_column(JSON, nullable=False)
    billing_address: Mapped[dict] = mapped_column(JSON, nullable=False)
    build_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
