from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InventoryUnit(Base):
    """A single physical unit belonging to an inventory purchase row."""

    __tablename__ = "inventory_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inventory.id", ondelete="CASCADE"), index=True
    )
    unit_number: Mapped[int] = mapped_column(Integer)
    serial_number: Mapped[str | None] = mapped_column(String(200), unique=True)
    condition_grade: Mapped[str] = mapped_column(String(32), default="unknown")
    status: Mapped[str] = mapped_column(String(32), default="ordered", index=True)
    storage_location: Mapped[str | None] = mapped_column(String(200), index=True)
    warranty_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    test_results: Mapped[dict] = mapped_column(JSON, default=dict)
    photos: Mapped[list] = mapped_column(JSON, default=list)
    exception_reason: Mapped[str | None] = mapped_column(Text)
    writeoff_amount: Mapped[float | None] = mapped_column(Float)
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("inventory_item_id", "unit_number", name="uq_inventory_unit_number"),)


class InventoryReorderRule(Base):
    __tablename__ = "inventory_reorder_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_type: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    minimum_free: Mapped[int] = mapped_column(Integer, default=0)
    maximum_free: Mapped[int] = mapped_column(Integer, default=3)
    target_free: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
