from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class InventoryAllocation(Base):
    __tablename__ = "inventory_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventory.id"), index=True)
    flip_id: Mapped[int] = mapped_column(Integer, ForeignKey("flips.id"), index=True)

    quantity_allocated: Mapped[int] = mapped_column(Integer)
    cost_per_unit_at_allocation: Mapped[float] = mapped_column(Float)

    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    inventory_item = relationship("InventoryItem", foreign_keys=[inventory_item_id])
    flip = relationship("Flip", foreign_keys=[flip_id])

    @property
    def total_allocated_cost(self) -> float:
        """Calculate total allocated cost: cost_per_unit_at_allocation * quantity_allocated"""
        return self.cost_per_unit_at_allocation * self.quantity_allocated

    def __repr__(self):
        return f"<InventoryAllocation flip={self.flip_id} inventory={self.inventory_item_id} qty={self.quantity_allocated} £{self.total_allocated_cost}>"
