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
    actual_cost: Mapped[float] = mapped_column(Float)  # Price you actually paid
    purchase_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str | None] = mapped_column(String(100))  # eBay, Amazon, local, auction, etc.
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<InventoryItem {self.component_name} x{self.quantity} £{self.actual_cost}>"
