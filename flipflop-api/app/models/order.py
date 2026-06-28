from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class OrderStatus(enum.Enum):
    AWAITING_SOURCING = "awaiting_sourcing"
    PARTS_ORDERED = "parts_ordered"
    BUILDING = "building"
    QA = "qa"
    READY_TO_SHIP = "ready_to_ship"
    SHIPPED = "shipped"
    COMPLETED = "completed"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_id = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)

    specs = Column(JSON, nullable=False)

    customer_price = Column(Float, nullable=False)
    component_costs = Column(Float, nullable=False)
    labor_hours = Column(Float, default=3.0)
    labor_rate = Column(Float, default=25.0)
    overhead_amount = Column(Float, nullable=False)
    profit = Column(Float, nullable=True)

    promised_delivery_date = Column(DateTime, nullable=False)
    actual_delivery_date = Column(DateTime, nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.AWAITING_SOURCING)
    notes = Column(String, nullable=True)
    rating = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")
