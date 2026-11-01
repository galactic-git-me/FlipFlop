from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, JSON, Boolean, Index
from sqlalchemy.orm import relationship, synonym
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
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    REFUND_PENDING = "refund_pending"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("idx_orders_status", "status"),)

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
    cancellation_requested_at = Column(DateTime, nullable=True)
    cancellation_status = Column(String(32), nullable=True)
    refund_id = Column(String(100), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    # Current customer-requested build change and its approval/quote state.
    # The request pauses sourcing until it is declined or fully implemented.
    change_request = Column(JSON, nullable=True)

    # Nullable: real delivery estimation isn't computed yet at order-creation
    # time (payments.py / webhooks.py both used to pass None here, which
    # violated the old NOT NULL constraint).
    promised_delivery_date = Column(DateTime, nullable=True)
    actual_delivery_date = Column(DateTime, nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.AWAITING_SOURCING)
    # `status` is retained as the fulfilment status column for compatibility
    # with existing routes and migrations. Payment state is independent.
    fulfilment_status = synonym("status")
    payment_status = Column(
        String(32),
        nullable=False,
        default=PaymentStatus.PAID.value,
        server_default=PaymentStatus.PAID.value,
        index=True,
    )
    # Immutable contact snapshot used for order filtering and customer
    # correspondence even if the customer later changes their profile.
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(320), nullable=True, index=True)
    assigned_build_week = Column(String(10), nullable=True, index=True)
    delivery_at_risk = Column(Boolean, default=False, server_default="false", nullable=False)
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
    
    # Buying flow / curated journey data (Michael + AnalyticsBot requirements)
    is_gift = Column(Boolean, default=False, nullable=False)  # For self vs gift
    recipient_age_band = Column(String(20), nullable=True)  # If gift: child/teen/adult/senior
    discreet_packaging = Column(Boolean, default=False, nullable=False)
    urgency = Column(String(20), nullable=True)  # asap/this_week/flexible
    is_first_pc = Column(Boolean, nullable=True)  # First PC vs upgrade
    current_gpu = Column(String(100), nullable=True)  # If upgrade: rough current GPU or "don't_know"
    is_business_buyer = Column(Boolean, default=False, nullable=False)  # VAT invoice needed
    wants_vat_invoice = Column(Boolean, default=False, nullable=False)
    aesthetic_preference = Column(String(20), nullable=True)  # quiet/rgb
    
    # Journey analytics (budget × type × tier from curated flow)
    journey_budget_min = Column(Float, nullable=True)
    journey_budget_max = Column(Float, nullable=True)
    journey_customer_type = Column(String(50), nullable=True)  # e.g., "Great-value Gaming"
    journey_tier = Column(String(20), nullable=True)  # budget/mid/high
    
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

    @property
    def reference(self) -> str:
        """Compatibility name for the canonical human-readable order ID."""
        return self.order_id

    @property
    def total_gbp(self) -> float:
        """The charged total stored by the current checkout flow."""
        return self.customer_price

    @property
    def playbook_name(self) -> str:
        return self.playbook.name if self.playbook else ""
