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

    # Gem Radar "Bought It" provenance (PRD §26). listing_id/marketplace form a
    # partial unique index (migration 20260706_0014) for duplicate-purchase
    # protection. Full delivery/dispatch tracking stays out of the extension
    # per PRD §27.1 — reconciliation_status is updated by the FlipFlopOS email
    # monitor when/if it exists, not by the extension itself.
    marketplace: Mapped[str | None] = mapped_column(String(50))
    listing_id: Mapped[str | None] = mapped_column(String(255), index=True)
    listing_url: Mapped[str | None] = mapped_column(String(1000))
    seller_name: Mapped[str | None] = mapped_column(String(200))
    purchase_status: Mapped[str] = mapped_column(String(32), default="MANUAL")
    reconciliation_status: Mapped[str] = mapped_column(String(32), default="NOT_APPLICABLE")

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
