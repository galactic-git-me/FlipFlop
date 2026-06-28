from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Date, Numeric, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    playbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("playbooks.id"))
    playbook_name: Mapped[str] = mapped_column(String(255))
    build_config: Mapped[dict] = mapped_column(JSON)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_email: Mapped[str] = mapped_column(String(255))
    delivery_address: Mapped[dict] = mapped_column(JSON)
    subtotal_gbp: Mapped[float] = mapped_column(Numeric(10, 2))
    tax_gbp: Mapped[float] = mapped_column(Numeric(10, 2))
    total_gbp: Mapped[float] = mapped_column(Numeric(10, 2))
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending_payment",
        nullable=False,
    )
    assigned_build_week: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    estimated_arrival_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    delivery_at_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_orders_status", "status"),
        Index("idx_orders_week", "assigned_build_week"),
        Index("idx_orders_email", "customer_email"),
    )
