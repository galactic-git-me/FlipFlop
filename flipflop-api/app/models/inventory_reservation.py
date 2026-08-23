"""Inventory Reservation model for Phase 2 F2.2.

Prevents overselling by reserving inventory when listing to a channel.
One build can have multiple reservations (one per channel).
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)  # which channel has this reservation
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=1)
    reserved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
