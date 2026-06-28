from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_name: Mapped[str] = mapped_column(String(300))
    component_type: Mapped[str] = mapped_column(String(50))  # gpu, cpu, ram, ssd, psu, motherboard, cooler
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    base_price: Mapped[float] = mapped_column(Float)  # Base price of the component
    shipping_cost: Mapped[float] = mapped_column(Float, default=0.0)  # Shipping cost
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Discount applied
    purchase_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str | None] = mapped_column(String(100))  # eBay, Amazon, local, auction, etc.
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def actual_cost(self) -> float:
        """Calculate actual cost: base_price + shipping_cost - discount_amount"""
        return self.base_price + self.shipping_cost - self.discount_amount

    @property
    def total_landed_cost(self) -> float:
        """Calculate total landed cost: actual_cost * quantity"""
        return self.actual_cost * self.quantity

    def __repr__(self):
        return f"<InventoryItem {self.component_name} x{self.quantity} £{self.actual_cost}>"
