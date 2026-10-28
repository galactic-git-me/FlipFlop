from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AISetupPurchase(Base):
    """Payment record for one optional Getting Ready AI service on an order."""

    __tablename__ = "ai_setup_purchases"
    __table_args__ = (
        UniqueConstraint("order_id", "offer_id", name="uq_ai_setup_purchase_order_offer"),
        UniqueConstraint("stripe_payment_intent_id", name="uq_ai_setup_purchase_payment_intent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    offer_id: Mapped[str] = mapped_column(String(80), nullable=False)
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    amount_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    offer_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
