from sqlalchemy import Column, Integer, String, DateTime, Float
from datetime import datetime
from app.database import Base


class SocialProofEvent(Base):
    """A real order or login event with a best-effort resolved location,
    used to drive the storefront's live social-proof globe."""

    __tablename__ = "social_proof_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(20), nullable=False)  # 'order' | 'login'
    display_name = Column(String(100), nullable=False)  # e.g. "Sarah M."
    product_name = Column(String(200), nullable=True)  # set for 'order' events only

    city = Column(String(120), nullable=True)
    country = Column(String(120), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
