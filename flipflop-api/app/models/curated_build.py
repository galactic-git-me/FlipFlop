"""Curated Build model - managed catalogue of pre-designed PC builds."""
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CuratedBuild(Base):
    """Admin-managed curated PC builds from definitions.json."""
    __tablename__ = "curated_builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Reference to the definition ID from curated_build_definitions.json
    definition_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    
    # Build identity (mirrored from definition for query performance)
    segment: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    use: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Component specification from definition
    components: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Pricing information
    estimated_price_gbp: Mapped[float | None] = mapped_column(Float, nullable=True)
    components_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    markup_percentage: Mapped[float] = mapped_column(Float, default=25.0)
    
    # Publishing status
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Display order and priority
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Availability tracking
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    availability_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Admin notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CuratedBuild {self.definition_id} {self.name} (published={self.is_published})>"
