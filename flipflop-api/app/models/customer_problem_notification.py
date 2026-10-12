from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomerProblemNotification(Base):
    """Durable email outbox entry for a customer aftercare case update."""

    __tablename__ = "customer_problem_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("customer_problems.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    status_code: Mapped[str] = mapped_column(String(40), nullable=False)
    repair_tracking_snapshot: Mapped[dict | None] = mapped_column(JSON)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    last_error: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
