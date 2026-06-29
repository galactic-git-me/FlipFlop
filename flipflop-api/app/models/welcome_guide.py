from sqlalchemy import Column, Integer, ForeignKey, DateTime, JSON, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class WelcomeGuide(Base):
    __tablename__ = "welcome_guides"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), unique=True, nullable=False)
    pdf_blob = Column(LargeBinary, nullable=True)  # PDF file
    generated_at = Column(DateTime, nullable=True)
    content_json = Column(JSON, nullable=True)  # Structured content

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="welcome_guide")
