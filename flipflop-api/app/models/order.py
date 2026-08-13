from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class OrderStatus(enum.Enum):
    AWAITING_SOURCING = "awaiting_sourcing"
    PARTS_ORDERED = "parts_ordered"
    BUILDING = "building"
    QA = "qa"
    READY_TO_PACKAGE = "ready_to_package"
    PACKAGING_IN_PROGRESS = "packaging_in_progress"
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

    # Stripe PaymentIntent id — the real idempotency/lookup key for payment
    # confirmation, replacing the old approach of grepping it out of `notes`.
    stripe_payment_intent_id = Column(String, nullable=True, index=True)

    # Nullable: real delivery estimation isn't computed yet at order-creation
    # time (payments.py / webhooks.py both used to pass None here, which
    # violated the old NOT NULL constraint).
    promised_delivery_date = Column(DateTime, nullable=True)
    actual_delivery_date = Column(DateTime, nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.AWAITING_SOURCING)
    notes = Column(String, nullable=True)
    rating = Column(Integer, nullable=True)

    # Phase 2 fields: Theme and OS component associations
    theme_id = Column(Integer, ForeignKey('desktop_themes.id'), nullable=True)
    playbook_id = Column(Integer, ForeignKey('playbooks.id'), nullable=True)

    # Admin workflow timing fields
    sourcing_started_at = Column(DateTime, nullable=True)
    sourcing_approved_at = Column(DateTime, nullable=True)
    building_started_at = Column(DateTime, nullable=True)
    building_completed_at = Column(DateTime, nullable=True)
    qa_started_at = Column(DateTime, nullable=True)
    qa_passed_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    # Shipping tracking
    tracking_number = Column(String(100), nullable=True)
    carrier = Column(String(50), nullable=True)  # 'royal_mail', 'ups', 'dhl', 'fedex'
    estimated_delivery = Column(DateTime, nullable=True)

    # Commerce & CXP platform fields (docs/prd/flipflop-commerce-and-cxp-platform-prd.md)
    fast_track_selected = Column(Boolean, default=False, nullable=False)
    fast_track_fee = Column(Float, default=0.0, nullable=False)
    packaging_playbook_id = Column(Integer, ForeignKey("packaging_playbooks.id"), nullable=True)  # snapshot, BR-2

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="orders")
    os_component = relationship("OSComponent", back_populates="assigned_order", uselist=False)
    theme = relationship("DesktopTheme", back_populates="orders")
    playbook = relationship("Playbook", back_populates="orders")
    welcome_guide = relationship("WelcomeGuide", back_populates="order", uselist=False)
    checklists = relationship("OrderChecklist", cascade="all, delete-orphan")
    photos = relationship("OrderPhoto", cascade="all, delete-orphan")
