from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Component(Base):
    __tablename__ = "component_catalogue"

    id = Column(Integer, primary_key=True)
    category = Column(String, index=True, nullable=False)
    manufacturer = Column(String, nullable=False)
    model = Column(String, nullable=False)
    variant = Column(String, nullable=True)

    market_price = Column(Float, nullable=False)
    used_market_price = Column(Float, nullable=True)

    search_volume = Column(Float, default=0.0)

    vendor_prices = relationship("VendorPrice", back_populates="component")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VendorPrice(Base):
    __tablename__ = "vendor_prices"

    id = Column(Integer, primary_key=True)
    component_id = Column(Integer, ForeignKey("component_catalogue.id"), nullable=False)
    vendor = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    stock_status = Column(String, nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    url = Column(String, nullable=True)

    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    component = relationship("Component", back_populates="vendor_prices")
