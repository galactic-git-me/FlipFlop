from sqlalchemy import Column, Integer, String, Float, JSON, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)

    # Basic info
    name = Column(String, nullable=False, index=True)
    brand = Column(String, nullable=True)
    model = Column(String, nullable=True)

    # Sourcing data
    source_site = Column(String, nullable=False, index=True)  # "Amazon", "Overclockers"
    source_url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

    # Pricing
    price = Column(Float, nullable=True)
    price_new = Column(Float, nullable=True)  # Current price (may differ from original)
    rrp = Column(Float, nullable=True)  # Recommended retail price

    # Amazon-specific signals (most reliable source of demand data)
    rating = Column(Float, nullable=True)  # Out of 5
    review_count = Column(Integer, nullable=True)
    sales_velocity = Column(String, nullable=True)  # e.g., "50+ bought in last month"
    bestseller_rank = Column(Integer, nullable=True)  # Amazon bestseller rank (lower = more popular)

    # Case attributes
    form_factors = Column(JSON, nullable=True, default=list)  # ["ATX", "MATX", "ITX"]
    keywords = Column(JSON, nullable=True, default=list)  # ["gaming", "RGB", "tempered-glass"]

    # 3D model status
    has_3d_model = Column(Boolean, default=False, index=True)
    model_3d_url = Column(String, nullable=True)  # URL to .glb/.gltf file
    model_3d_source = Column(String, nullable=True)  # "manufacturer_cad", "community_cad", "meshy_ai"

    # Sourcing workflow status
    status = Column(
        String,
        default="pending",
        index=True,
        comment="pending → sourcing → ready_for_approval → approved → modeling → completed"
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Case(id={self.id}, name={self.name}, source={self.source_site}, price={self.price})>"
