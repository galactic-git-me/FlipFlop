import enum
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, Enum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class FlipStage(str, enum.Enum):
    selected = "selected"
    building = "building"
    ready_for_sale = "ready_for_sale"
    sold = "sold"


class Flip(Base):
    __tablename__ = "flips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("listings.id"), index=True)

    stage: Mapped[FlipStage] = mapped_column(Enum(FlipStage), default=FlipStage.selected)

    # Selected upgrades stored as JSON: {category: part_id}
    selected_upgrade_ids: Mapped[dict] = mapped_column(JSON, default=dict)

    # Costs
    base_cost: Mapped[float] = mapped_column(Float, default=0.0)
    upgrade_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    platform_fee_pct: Mapped[float] = mapped_column(Float, default=0.127)

    # Estimates — versioned
    initial_estimated_resale: Mapped[float | None] = mapped_column(Float)
    current_estimated_resale: Mapped[float | None] = mapped_column(Float)
    initial_estimated_profit: Mapped[float | None] = mapped_column(Float)
    current_estimated_profit: Mapped[float | None] = mapped_column(Float)

    # Actuals
    actual_sale_price: Mapped[float | None] = mapped_column(Float)
    actual_profit: Mapped[float | None] = mapped_column(Float)
    sale_platform: Mapped[str | None] = mapped_column(String(100))

    # Listing content
    generated_title: Mapped[str | None] = mapped_column(String(500))
    generated_description: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime)

    listing = relationship("Listing", foreign_keys=[listing_id])

    def __repr__(self):
        return f"<Flip {self.id} stage={self.stage} profit={self.current_estimated_profit}>"
