from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from datetime import datetime
from app.database import Base


class CXCostRecord(Base):
    """Cost rollup feeding the existing Profit Calculator. CXP PRD Ch.7.18, Ch.24."""
    __tablename__ = "cx_cost_records"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)

    packaging_cost = Column(Float, default=0.0)
    consumables_cost = Column(Float, default=0.0)
    accessories_cost = Column(Float, default=0.0)
    documentation_cost = Column(Float, default=0.0)
    usb_cost = Column(Float, default=0.0)
    shipping_handling_cost = Column(Float, default=0.0)
    labour_cost = Column(Float, default=0.0)
    total_cx_cost = Column(Float, default=0.0)

    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
