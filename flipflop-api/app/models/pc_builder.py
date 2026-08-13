"""PC Builder - user builds, purchase plans, and build history."""
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, Text, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import enum


class PCBuildStage(enum.Enum):
    DESIGN = "design"
    BUILD = "build"
    SELL = "sell"


class PCBuild(Base):
    """Saved PC build configurations."""
    __tablename__ = "pc_builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    playbook_id: Mapped[str] = mapped_column(String(50))  # gaming, workstation, streaming, etc.
    playbook_tier: Mapped[str] = mapped_column(String(20))  # budget, midrange, highend

    # Build workflow stage: design | build | sell (default design)
    stage: Mapped[str] = mapped_column(Enum(PCBuildStage), default=PCBuildStage.DESIGN, index=True)

    # Build status within stage: draft | completed (only meaningful in sell stage)
    status: Mapped[str] = mapped_column(String(20), index=True, default="draft")

    # Component selections: [{component_type, listing_id, title, seller, actual_price, market_new, market_used}, ...]
    components: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Costs
    estimated_total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_market_new_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_market_used_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_profit: Mapped[float | None] = mapped_column(Float, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return f"<PCBuild {self.name} ({self.playbook_id}/{self.playbook_tier}) {self.status}>"


class PCBuildPurchasePlan(Base):
    """Purchase tracking for a completed build."""
    __tablename__ = "pc_build_purchase_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    build_id: Mapped[int] = mapped_column(Integer, index=True)
    build_name: Mapped[str] = mapped_column(String(255))

    # Items: [{component_type, listing_id, title, seller, estimated_price, actual_price, purchased, vendor_url}, ...]
    items: Mapped[dict] = mapped_column(JSON)

    # Totals
    estimated_total_cost: Mapped[float] = mapped_column(Float)
    actual_total_cost: Mapped[float] = mapped_column(Float, default=0.0)

    estimated_resale_new: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_resale_used: Mapped[float | None] = mapped_column(Float, nullable=True)

    estimated_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_profit: Mapped[float | None] = mapped_column(Float, nullable=True)

    items_purchased_count: Mapped[int] = mapped_column(Integer, default=0)
    items_total_count: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PCBuildPurchasePlan build={self.build_id} {self.items_purchased_count}/{self.items_total_count} items>"
