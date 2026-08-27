from sqlalchemy import Column, Integer, String, Float, JSON, Boolean, DateTime
from app.database import Base
from datetime import datetime


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
    model_3d_source = Column(String, nullable=True)  # "manufacturer_cad", "community_cad", "meshy_ai", "sketchfab"
    model_3d_creator = Column(String, nullable=True)  # Creator/artist name
    model_3d_license = Column(String, nullable=True)  # License type (e.g., "CC-BY-4.0")
    model_3d_quality = Column(String, nullable=True)  # "low", "medium", "high" based on polygon count
    model_3d_vertices = Column(Integer, nullable=True)  # Vertex count
    model_3d_polygons = Column(Integer, nullable=True)  # Triangle/polygon count
    model_3d_file_size = Column(Integer, nullable=True)  # File size in bytes

    # Sourcing workflow status
    status = Column(
        String,
        default="pending",
        index=True,
        comment="pending → sourcing → ready_for_approval → approved → modeling → completed"
    )

    # Frozen top-30 campaign position. This is intentionally separate from the
    # live Amazon rank, which can change while a ten-case batch is being worked.
    priority_3d_rank = Column(Integer, nullable=True, index=True)
    priority_3d_batch = Column(Integer, nullable=True, index=True)
    priority_3d_frozen_at = Column(DateTime, nullable=True)
    # Auditable sourcing funnel: manufacturer model search, third-party model
    # search, image set, YouTube references, Meshy job, validation and rights.
    sourcing_3d_evidence = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Case(id={self.id}, name={self.name}, source={self.source_site}, price={self.price})>"
