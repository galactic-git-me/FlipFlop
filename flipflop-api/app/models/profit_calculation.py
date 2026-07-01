from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from datetime import datetime
from app.database import Base


class ProfitCalculation(Base):
    """Per-Product/per-channel profit breakdown, extends existing Profit Calculator. PRD Ch.6.7."""
    __tablename__ = "profit_calculations"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)

    component_cost = Column(Float, default=0.0)
    cx_cost = Column(Float, default=0.0)
    channel_fee = Column(Float, default=0.0)
    gross_profit = Column(Float, nullable=True)
    margin_pct = Column(Float, nullable=True)

    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
