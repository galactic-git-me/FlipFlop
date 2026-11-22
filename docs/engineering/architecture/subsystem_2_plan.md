# Subsystem 2: Orders & Capacity Management — Implementation Plan

**Status:** Planning Phase  
**Goal:** Complete order management, Stripe checkout, and build slot capacity system  
**Duration:** Estimated 4-5 days (backend engineer level)  
**Dependencies:** Subsystem 1 (Storefront) ✅ Complete  
**Target Start:** 2026-06-22  
**Context:** This plan feeds into Subsystem 3 (Delivery Tracker) with order metadata

---

## 1. Architecture Overview

### Order Flow Diagram

```
Customer Configurator (PC: Subsystem 1 at pc-flipper-customer/)
    ↓
POST /api/orders/checkout
    ↓ (FastAPI Backend at pc-flipper-backend/)
Backend Creates:
  - Order row (status: pending_payment)
  - Stripe Checkout Session
    ↓
Stripe Redirect to Payment
    ↓
POST /api/stripe/webhook (checkout.session.completed)
    ↓
Backend Updates:
  - Order status: confirmed
  - Auto-assign build week
  - Reserve slot capacity
  - Send confirmation email
    ↓
GET /api/orders/[reference] (Customer sees confirmation)
    ↓
Admin Reviews Capacity
    ↓
GET /api/admin/orders (list, filter, manage)
PATCH /api/admin/capacity (override weeks, set global default)
    ↓
Subsystem 3: Delivery Tracker consumes order data
```

### System Components

1. **Orders Table** — Persistent storage of customer orders with all build configuration
2. **Build Capacity** — Global defaults for build slots per week
3. **Build Capacity Overrides** — Per-week exceptions (holidays, maintenance, low capacity)
4. **Stripe Integration** — Payment processing with secure webhook handling
5. **Email Service** — Transactional emails (order confirmation, status updates)
6. **Admin Dashboard** — Capacity overview and order management (in pc-flipper admin UI)

### Technology Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| API Framework | FastAPI | Async, modern, type hints |
| ORM | SQLAlchemy 2.0 (async) | Existing in pc-flipper-backend |
| Database | PostgreSQL | Existing; migrations via Alembic |
| Payment | Stripe API | PCI-compliant, secure |
| Email | SendGrid or AWS SES | Reliable transactional email |
| Auth | Existing (JWT/session) | Reuse from pc-flipper |
| Validation | Pydantic v2 | Existing in pc-flipper-backend |

---

## 2. Database Schema

### 2.1 `orders` Table

Stores complete order data including build configuration, customer details, and status.

```python
# File: pc-flipper-backend/app/models/order.py

from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Date, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Order(Base):
    """
    Represents a customer order for a custom-built PC.
    
    Status lifecycle:
      pending_payment → confirmed → building → shipped → delivered
                                              ↓
                                           cancelled
    """
    __tablename__ = "orders"

    # ─── Primary Key & Reference ──────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(
        String(20), 
        unique=True, 
        nullable=False, 
        index=True
    )
    # Format: FF-YYYY-NNNNN (e.g., FF-2026-00042)
    # Human-readable reference for customer communication

    # ─── Playbook & Build Configuration ───────────────────────────────────────
    playbook_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("playbooks.id"),
        nullable=False
    )
    playbook_name: Mapped[str] = mapped_column(String(255))
    # Snapshot of playbook name at order time (immutable for history)

    # {
    #   "gpu": {
    #     "variant_id": 45,
    #     "name": "NVIDIA RTX 4090",
    #     "display_price": 1899.99,
    #     "rrp_gbp": 1999.99
    #   },
    #   "cpu": { ... },
    #   "motherboard": { ... },
    #   "ram": { ... },
    #   "storage": { ... },
    #   "psu": { ... },
    #   "cooler": { ... },
    #   "case": {
    #     "variant_id": 12,
    #     "name": "Corsair Crystal Series 570X",
    #     "display_price": 129.99,
    #     "rrp_gbp": 149.99
    #   }
    # }
    build_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Complete snapshot of chosen components (for order history & fulfillment)

    # ─── Customer Details ─────────────────────────────────────────────────────
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # {
    #   "line1": "123 Main Street",
    #   "line2": "Flat 4B",
    #   "city": "London",
    #   "postcode": "SW1A 2AA",
    #   "country": "UK"
    # }
    delivery_address: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Immutable snapshot; used for shipping label generation

    # ─── Pricing ──────────────────────────────────────────────────────────────
    subtotal_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Sum of all component prices

    tax_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    # VAT or other taxes

    total_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # subtotal_gbp + tax_gbp

    discount_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    # Any promotional discount applied

    # ─── Payment Integration ──────────────────────────────────────────────────
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    # Stripe Checkout Session ID (for webhook matching)

    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    # Stripe Payment Intent ID (for reconciliation)

    # ─── Order Status & Fulfillment ───────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(50), default="pending_payment", index=True)
    # pending_payment | confirmed | building | shipped | delivered | cancelled

    assigned_build_week: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    # ISO week format: 2026-W27
    # Auto-assigned when payment confirmed; used for capacity tracking

    estimated_arrival_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Computed from assigned_build_week + build duration + shipping time
    # Updated by Subsystem 3 (Delivery Tracker)

    delivery_at_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    # Flag set by Subsystem 3 if fulfillment is delayed

    # ─── Metadata ──────────────────────────────────────────────────────────────
    admin_notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Internal notes for build team

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payment_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Timestamp when Stripe webhook confirmed payment

    # ─── Indexes for queries ──────────────────────────────────────────────────
    __table_args__ = (
        Index("idx_orders_status_week", "status", "assigned_build_week"),
        Index("idx_orders_customer_email", "customer_email"),
        Index("idx_orders_created_at", "created_at"),
    )
```

### 2.2 `build_capacity` Table

Global default for build slots per week.

```python
# File: pc-flipper-backend/app/models/build_capacity.py

from datetime import datetime
from sqlalchemy import Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BuildCapacity(Base):
    """
    Global capacity settings for build slots.
    
    Typically one row; represents the default number of builds
    that can be scheduled per week. Overrides per-week in BuildCapacityOverride.
    """
    __tablename__ = "build_capacity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    default_per_week: Mapped[int] = mapped_column(Integer, default=3)
    # Default number of builds allowed per week (e.g., 3)
    # Can be overridden per-week via BuildCapacityOverride

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 2.3 `build_capacity_overrides` Table

Per-week exceptions to global capacity.

```python
# File: pc-flipper-backend/app/models/build_capacity_override.py

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BuildCapacityOverride(Base):
    """
    Per-week capacity overrides.
    
    Examples:
      - week 2026-W25: max_builds=0, note="Summer holiday" (week closed)
      - week 2026-W26: max_builds=2, note="Maintenance" (reduced capacity)
      - week 2026-W27: max_builds=5 (increased for high demand)
    """
    __tablename__ = "build_capacity_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    week: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    # ISO week format: 2026-W27
    # Represents Monday 2026-06-29 to Sunday 2026-07-05

    max_builds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Set to null = week is closed (no builds accepted)
    # Set to 0 = week is closed (no builds accepted)
    # Set to N > 0 = override default capacity for this week

    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Context for why override exists:
    # "holiday", "maintenance", "high-demand prep", etc.

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_capacity_override_week", "week"),
    )
```

### 2.4 Alembic Migration

```bash
# Command to generate:
# cd pc-flipper-backend
# alembic revision --autogenerate -m "add orders and capacity tables"

# File: pc-flipper-backend/alembic/versions/XXX_add_orders_and_capacity_tables.py

def upgrade():
    # Create build_capacity table
    op.create_table(
        'build_capacity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('default_per_week', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create build_capacity_overrides table
    op.create_table(
        'build_capacity_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('week', sa.String(20), nullable=False, unique=True),
        sa.Column('max_builds', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('week', name='uq_week')
    )
    op.create_index('idx_capacity_override_week', 'build_capacity_overrides', ['week'])
    
    # Create orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(20), nullable=False, unique=True),
        sa.Column('playbook_id', sa.Integer(), nullable=False),
        sa.Column('playbook_name', sa.String(255), nullable=False),
        sa.Column('build_config', sa.JSON(), nullable=False),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('customer_email', sa.String(255), nullable=False),
        sa.Column('customer_phone', sa.String(20), nullable=True),
        sa.Column('delivery_address', sa.JSON(), nullable=False),
        sa.Column('subtotal_gbp', sa.Numeric(10, 2), nullable=False),
        sa.Column('tax_gbp', sa.Numeric(10, 2), nullable=False, server_default='0.0'),
        sa.Column('total_gbp', sa.Numeric(10, 2), nullable=False),
        sa.Column('discount_gbp', sa.Numeric(10, 2), nullable=False, server_default='0.0'),
        sa.Column('stripe_session_id', sa.String(255), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending_payment'),
        sa.Column('assigned_build_week', sa.String(20), nullable=True),
        sa.Column('estimated_arrival_date', sa.Date(), nullable=True),
        sa.Column('delivery_at_risk', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('admin_notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('payment_confirmed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['playbook_id'], ['playbooks.id']),
        sa.UniqueConstraint('reference', name='uq_order_reference')
    )
    op.create_index('idx_orders_reference', 'orders', ['reference'])
    op.create_index('idx_orders_customer_email', 'orders', ['customer_email'])
    op.create_index('idx_orders_status_week', 'orders', ['status', 'assigned_build_week'])
    op.create_index('idx_orders_created_at', 'orders', ['created_at'])
    op.create_index('idx_orders_stripe_session_id', 'orders', ['stripe_session_id'])
    op.create_index('idx_orders_stripe_payment_intent', 'orders', ['stripe_payment_intent_id'])

def downgrade():
    op.drop_table('orders')
    op.drop_table('build_capacity_overrides')
    op.drop_table('build_capacity')
```

---

## 3. Pydantic Schemas

### 3.1 Request/Response Schemas

```python
# File: pc-flipper-backend/app/schemas/order.py

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class OrderSlotOut(BaseModel):
    """Represents an available build week slot."""
    week: str  # ISO week: 2026-W27
    week_start: date  # Monday of that week
    available: int  # Remaining slots
    capacity: int  # Total capacity for that week


class ComponentVariant(BaseModel):
    """A single component choice in the build configuration."""
    variant_id: int
    name: str
    display_price: float
    rrp_gbp: Optional[float] = None


class BuildConfigIn(BaseModel):
    """Complete build configuration from customer."""
    # Keys: gpu, cpu, motherboard, ram, storage, psu, cooler, case
    # Values: ComponentVariant
    pass


class DeliveryAddressIn(BaseModel):
    """Customer delivery address."""
    line1: str
    line2: Optional[str] = None
    city: str
    postcode: str
    country: str


class OrderCheckoutRequest(BaseModel):
    """POST /api/orders/checkout request."""
    playbook_id: int
    build_config: dict  # {component: ComponentVariant, ...}
    customer_name: str
    customer_email: EmailStr
    customer_phone: Optional[str] = None
    delivery_address: DeliveryAddressIn
    chosen_week: str  # ISO week: 2026-W27


class OrderCheckoutResponse(BaseModel):
    """POST /api/orders/checkout response."""
    stripe_url: str  # Redirect customer here
    reference: str  # FF-2026-00042
    order_id: int


class OrderConfirmationOut(BaseModel):
    """GET /api/orders/[reference] response."""
    reference: str
    playbook_name: str
    build_config: dict
    customer_name: str
    customer_email: str
    delivery_address: DeliveryAddressIn
    subtotal_gbp: float
    tax_gbp: float
    total_gbp: float
    discount_gbp: float
    status: str  # pending_payment | confirmed | building | shipped | delivered | cancelled
    assigned_build_week: Optional[str] = None
    estimated_arrival_date: Optional[date] = None
    delivery_at_risk: bool = False
    created_at: datetime
    payment_confirmed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderListOut(BaseModel):
    """GET /api/admin/orders response item."""
    id: int
    reference: str
    customer_name: str
    customer_email: str
    playbook_name: str
    total_gbp: float
    status: str
    assigned_build_week: Optional[str] = None
    delivery_at_risk: bool
    created_at: datetime

    class Config:
        from_attributes = True


class OrderUpdateRequest(BaseModel):
    """PATCH /api/admin/orders/[id] request."""
    status: Optional[str] = None  # building | shipped | delivered | cancelled
    admin_notes: Optional[str] = None
    estimated_arrival_date: Optional[date] = None


class BuildCapacitySettingsOut(BaseModel):
    """GET /api/admin/capacity response."""
    id: int
    default_per_week: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BuildCapacityOverrideOut(BaseModel):
    """Individual capacity override."""
    week: str
    max_builds: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BuildCapacityOverrideRequest(BaseModel):
    """PUT /api/admin/capacity/overrides/[week] request."""
    max_builds: Optional[int] = None
    note: Optional[str] = None
```

---

## 4. API Endpoints (7 Total)

### 4.1 Public Endpoints

#### Endpoint 1: GET /api/orders/slots
**Purpose:** Show customer available build weeks (called on configurator page load)

**Implementation:**
```python
# File: pc-flipper-backend/app/api/orders.py

@router.get("/slots", response_model=list[OrderSlotOut])
async def get_available_slots(
    db: AsyncSession = Depends(get_db),
):
    """
    Return next 8 weeks with available capacity.
    
    Logic:
      1. Get global default from build_capacity table
      2. Load overrides from build_capacity_overrides
      3. Count confirmed/building orders per week
      4. Calculate available = capacity - booked
      5. Return only weeks with available > 0 AND week >= today + 5 business days
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func, and_
    from app.models.build_capacity import BuildCapacity, BuildCapacityOverride
    from app.models.order import Order
    
    # Get global default
    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    capacity_settings = capacity_result.scalar()
    default_capacity = capacity_settings.default_per_week if capacity_settings else 3
    
    today = datetime.utcnow().date()
    results = []
    
    # Generate next 8 weeks starting from today + 5 business days
    current_date = today + timedelta(days=7)  # Simplified: 7 days = ~5 business days
    
    for week_offset in range(8):
        week_start = current_date + timedelta(weeks=week_offset)
        iso_week = week_start.isocalendar()
        week_str = f"{iso_week[0]}-W{iso_week[1]:02d}"
        
        # Check for override
        override = await db.execute(
            select(BuildCapacityOverride).where(BuildCapacityOverride.week == week_str)
        )
        override_row = override.scalar()
        
        if override_row is not None and override_row.max_builds is None:
            # Week is closed
            continue
        
        capacity = override_row.max_builds if override_row else default_capacity
        
        # Count booked slots
        booked = await db.execute(
            select(func.count(Order.id)).where(
                and_(
                    Order.assigned_build_week == week_str,
                    Order.status.in_(["confirmed", "building"])
                )
            )
        )
        booked_count = booked.scalar() or 0
        available = capacity - booked_count
        
        if available > 0:
            results.append(OrderSlotOut(
                week=week_str,
                week_start=week_start,
                available=available,
                capacity=capacity
            ))
    
    return results
```

**Example Response:**
```json
[
  {
    "week": "2026-W27",
    "week_start": "2026-06-29",
    "available": 2,
    "capacity": 3
  },
  {
    "week": "2026-W28",
    "week_start": "2026-07-06",
    "available": 3,
    "capacity": 3
  }
]
```

---

#### Endpoint 2: POST /api/orders/checkout
**Purpose:** Create order and Stripe session (called when customer clicks "Order Now")

**Implementation:**
```python
@router.post("/checkout", response_model=OrderCheckoutResponse, status_code=201)
async def create_checkout(
    order_data: OrderCheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create Order row and initiate Stripe Checkout Session.
    
    Logic:
      1. Validate all variant IDs are active (via playbook catalogue)
      2. Validate chosen_week has available capacity
      3. Create Order row with status=pending_payment
      4. Create Stripe Checkout Session with line items
      5. Save stripe_session_id to order
      6. Return checkout URL
    
    Error cases:
      - Variant ID not found in playbook
      - Week has no available capacity
      - Stripe API error
    """
    from app.models.order import Order
    from app.models.playbook import Playbook
    from app.models.build_capacity import BuildCapacity, BuildCapacityOverride
    import stripe
    import secrets
    from app.config import get_settings
    
    settings = get_settings()
    
    # 1. Validate playbook exists
    playbook_result = await db.execute(
        select(Playbook).where(Playbook.id == order_data.playbook_id)
    )
    playbook = playbook_result.scalar()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    # 2. Validate week has capacity
    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    capacity_settings = capacity_result.scalar()
    default_capacity = capacity_settings.default_per_week if capacity_settings else 3
    
    override = await db.execute(
        select(BuildCapacityOverride).where(
            BuildCapacityOverride.week == order_data.chosen_week
        )
    )
    override_row = override.scalar()
    
    if override_row is not None and override_row.max_builds is None:
        raise HTTPException(status_code=409, detail="Week not accepting orders")
    
    capacity = override_row.max_builds if override_row else default_capacity
    
    booked = await db.execute(
        select(func.count(Order.id)).where(
            and_(
                Order.assigned_build_week == order_data.chosen_week,
                Order.status.in_(["confirmed", "building"])
            )
        )
    )
    booked_count = booked.scalar() or 0
    if booked_count >= capacity:
        raise HTTPException(status_code=409, detail="Week is fully booked")
    
    # 3. Generate order reference
    reference = generate_order_reference(db)  # FF-YYYY-NNNNN
    
    # 4. Create Order row
    order = Order(
        reference=reference,
        playbook_id=playbook.id,
        playbook_name=playbook.name,
        build_config=order_data.build_config,
        customer_name=order_data.customer_name,
        customer_email=order_data.customer_email,
        customer_phone=order_data.customer_phone,
        delivery_address=order_data.delivery_address.dict(),
        subtotal_gbp=calculate_subtotal(order_data.build_config),
        tax_gbp=0.0,  # Calculate VAT if needed
        total_gbp=calculate_subtotal(order_data.build_config),
        status="pending_payment",
    )
    db.add(order)
    await db.flush()  # Get order.id without committing
    
    # 5. Create Stripe Checkout Session
    stripe.api_key = settings.stripe_secret_key
    
    line_items = []
    for component_name, component_data in order_data.build_config.items():
        line_items.append({
            "price_data": {
                "currency": "gbp",
                "product_data": {
                    "name": f"{component_name.title()} - {component_data['name']}",
                },
                "unit_amount": int(component_data["display_price"] * 100),  # Stripe wants pence
            },
            "quantity": 1,
        })
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        customer_email=order_data.customer_email,
        success_url=f"{settings.frontend_url}/order/{reference}",
        cancel_url=f"{settings.frontend_url}/configure/{playbook.slug}",
        metadata={"order_id": order.id, "reference": reference},
    )
    
    # 6. Save Stripe session ID
    order.stripe_session_id = session.id
    await db.commit()
    
    return OrderCheckoutResponse(
        stripe_url=session.url,
        reference=reference,
        order_id=order.id,
    )


def generate_order_reference(db: AsyncSession) -> str:
    """Generate unique order reference FF-YYYY-NNNNN."""
    from datetime import datetime
    import secrets
    
    year = datetime.utcnow().year
    
    # Generate random 5-digit suffix until unique
    while True:
        suffix = secrets.randbelow(99999)
        reference = f"FF-{year}-{suffix:05d}"
        
        # Check if exists (simplified; use DB query in real impl)
        existing = db.execute(
            select(Order).where(Order.reference == reference)
        )
        if not existing.scalar():
            return reference
```

**Example Request:**
```json
{
  "playbook_id": 1,
  "build_config": {
    "gpu": {
      "variant_id": 45,
      "name": "NVIDIA RTX 4090",
      "display_price": 1899.99,
      "rrp_gbp": 1999.99
    },
    "cpu": {
      "variant_id": 12,
      "name": "Intel Core i9-13900K",
      "display_price": 589.99,
      "rrp_gbp": 599.99
    },
    "case": {
      "variant_id": 8,
      "name": "Corsair Crystal Series 570X",
      "display_price": 129.99,
      "rrp_gbp": 149.99
    }
  },
  "customer_name": "John Doe",
  "customer_email": "john@example.com",
  "customer_phone": "+44-7911-123456",
  "delivery_address": {
    "line1": "123 Main Street",
    "line2": "Flat 4B",
    "city": "London",
    "postcode": "SW1A 2AA",
    "country": "UK"
  },
  "chosen_week": "2026-W27"
}
```

**Example Response:**
```json
{
  "stripe_url": "https://checkout.stripe.com/pay/cs_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "reference": "FF-2026-00042",
  "order_id": 1234
}
```

---

#### Endpoint 3: GET /api/orders/[reference]
**Purpose:** Show order confirmation (called after customer lands on /order/[reference] post-Stripe)

**Implementation:**
```python
@router.get("/{reference}", response_model=OrderConfirmationOut)
async def get_order_confirmation(
    reference: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch order by human-readable reference."""
    order = await db.execute(
        select(Order).where(Order.reference == reference)
    )
    order_row = order.scalar()
    
    if not order_row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return OrderConfirmationOut.from_orm(order_row)
```

**Example Response:**
```json
{
  "reference": "FF-2026-00042",
  "playbook_name": "Gaming Rig",
  "build_config": { ... },
  "customer_name": "John Doe",
  "customer_email": "john@example.com",
  "delivery_address": { ... },
  "subtotal_gbp": 2699.97,
  "tax_gbp": 0.0,
  "total_gbp": 2699.97,
  "discount_gbp": 0.0,
  "status": "confirmed",
  "assigned_build_week": "2026-W27",
  "estimated_arrival_date": "2026-07-15",
  "delivery_at_risk": false,
  "created_at": "2026-06-22T10:30:00Z",
  "payment_confirmed_at": "2026-06-22T10:35:15Z"
}
```

---

### 4.2 Webhook Endpoint

#### Endpoint 4: POST /api/stripe/webhook
**Purpose:** Handle Stripe payment completion (Stripe calls this)

**Implementation:**
```python
# File: pc-flipper-backend/app/api/stripe_webhooks.py

from fastapi import APIRouter, Request, HTTPException
import stripe
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.order import Order
from sqlalchemy import select

router = APIRouter(prefix="/stripe", tags=["stripe"])
settings = get_settings()


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    
    Security: Verify webhook signature before processing.
    
    Events handled:
      - checkout.session.completed: Payment confirmed → Update order status
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    # 1. Verify Stripe signature (security critical)
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # 2. Handle checkout.session.completed
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session["metadata"]["order_id"]
        
        async with AsyncSessionLocal() as db:
            # Fetch order
            result = await db.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar()
            
            if not order:
                return {"received": True}, 200  # Silently ignore unknown order
            
            # Update status
            order.status = "confirmed"
            order.stripe_payment_intent_id = session.get("payment_intent")
            order.payment_confirmed_at = datetime.utcnow()
            
            # Auto-assign build week (find earliest available)
            assigned_week = await find_available_week_for_order(db, order)
            if assigned_week:
                order.assigned_build_week = assigned_week
            
            await db.commit()
            
            # Send confirmation email (async, non-blocking)
            # await send_order_confirmation_email(order)
    
    return {"received": True}, 200


async def find_available_week_for_order(
    db: AsyncSession,
    order: Order,
) -> Optional[str]:
    """
    Find earliest available week for order.
    
    Constraints:
      - Week must have available capacity
      - Week must be >= today + 5 business days
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func, and_
    from app.models.build_capacity import BuildCapacity, BuildCapacityOverride
    
    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    capacity_settings = capacity_result.scalar()
    default_capacity = capacity_settings.default_per_week if capacity_settings else 3
    
    today = datetime.utcnow().date()
    current_date = today + timedelta(days=7)
    
    for week_offset in range(12):  # Check next 12 weeks
        week_start = current_date + timedelta(weeks=week_offset)
        iso_week = week_start.isocalendar()
        week_str = f"{iso_week[0]}-W{iso_week[1]:02d}"
        
        # Check override
        override = await db.execute(
            select(BuildCapacityOverride).where(
                BuildCapacityOverride.week == week_str
            )
        )
        override_row = override.scalar()
        
        if override_row is not None and override_row.max_builds is None:
            continue  # Week closed
        
        capacity = override_row.max_builds if override_row else default_capacity
        
        # Count booked
        booked = await db.execute(
            select(func.count(Order.id)).where(
                and_(
                    Order.assigned_build_week == week_str,
                    Order.status.in_(["confirmed", "building"]),
                    Order.id != order.id,  # Exclude this order
                )
            )
        )
        booked_count = booked.scalar() or 0
        
        if booked_count < capacity:
            return week_str
    
    return None  # No available week found
```

---

### 4.3 Admin Endpoints (Protected)

All admin endpoints require authentication (implement via auth guard middleware).

#### Endpoint 5: GET /api/admin/orders
**Purpose:** List all orders with filtering

**Implementation:**
```python
# File: pc-flipper-backend/app/api/admin/orders.py

@router.get("", response_model=list[OrderListOut])
async def list_orders(
    status: Optional[str] = Query(None),
    week: Optional[str] = Query(None),
    customer_email: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    # Add auth dependency here
):
    """
    List orders with optional filtering.
    
    Query params:
      - status: pending_payment | confirmed | building | shipped | delivered | cancelled
      - week: ISO week 2026-W27
      - customer_email: Filter by email
      - limit/offset: Pagination
    """
    query = select(Order)
    
    if status:
        query = query.where(Order.status == status)
    if week:
        query = query.where(Order.assigned_build_week == week)
    if customer_email:
        query = query.where(Order.customer_email.ilike(f"%{customer_email}%"))
    
    query = query.order_by(Order.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    return result.scalars().all()
```

---

#### Endpoint 6: PATCH /api/admin/orders/[id]
**Purpose:** Update order status (confirmed → building → shipped)

**Implementation:**
```python
@router.patch("/{order_id}")
async def update_order(
    order_id: int,
    update_data: OrderUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update order status and notes."""
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404)
    
    if update_data.status:
        order.status = update_data.status
    if update_data.admin_notes:
        order.admin_notes = update_data.admin_notes
    if update_data.estimated_arrival_date:
        order.estimated_arrival_date = update_data.estimated_arrival_date
    
    await db.commit()
    return order
```

---

#### Endpoint 7: GET /api/admin/capacity

**Implementation:**
```python
@router.get("/capacity", response_model=BuildCapacitySettingsOut)
async def get_capacity_settings(
    db: AsyncSession = Depends(get_db),
):
    """Get current capacity settings."""
    result = await db.execute(select(BuildCapacity).limit(1))
    settings = result.scalar()
    
    if not settings:
        # Create default
        settings = BuildCapacity(default_per_week=3)
        db.add(settings)
        await db.commit()
    
    return BuildCapacitySettingsOut.from_orm(settings)
```

---

#### Endpoint 8: PATCH /api/admin/capacity/default

**Implementation:**
```python
@router.patch("/capacity/default")
async def update_capacity_default(
    new_default: int,
    db: AsyncSession = Depends(get_db),
):
    """Update global default capacity per week."""
    result = await db.execute(select(BuildCapacity).limit(1))
    settings = result.scalar()
    
    if not settings:
        settings = BuildCapacity(default_per_week=new_default)
        db.add(settings)
    else:
        settings.default_per_week = new_default
    
    await db.commit()
    return BuildCapacitySettingsOut.from_orm(settings)
```

---

#### Endpoint 9: PUT /api/admin/capacity/overrides/[week]

**Implementation:**
```python
@router.put("/capacity/overrides/{week}")
async def set_capacity_override(
    week: str,
    override_data: BuildCapacityOverrideRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set or remove capacity override for a week."""
    result = await db.execute(
        select(BuildCapacityOverride).where(
            BuildCapacityOverride.week == week
        )
    )
    override = result.scalar()
    
    if override_data.max_builds is None:
        # Remove override or mark week as closed
        if override:
            override.max_builds = None
            override.note = override_data.note
        else:
            override = BuildCapacityOverride(
                week=week,
                max_builds=None,
                note=override_data.note,
            )
            db.add(override)
    else:
        # Set capacity override
        if not override:
            override = BuildCapacityOverride(week=week)
            db.add(override)
        
        override.max_builds = override_data.max_builds
        override.note = override_data.note
    
    await db.commit()
    return BuildCapacityOverrideOut.from_orm(override)
```

---

## 5. Stripe Integration Setup

### 5.1 One-Time Configuration

1. **Create Stripe Account**
   - Login to https://dashboard.stripe.com
   - Get API Keys:
     - Publishable Key: `pk_live_...`
     - Secret Key: `sk_live_...`
   - Get Webhook Secret:
     - Dashboard → Developers → Webhooks
     - Create webhook for `https://yourdomain.com/api/stripe/webhook`
     - Copy Signing Secret: `whsec_...`

2. **Environment Variables** (add to `.env.local`)
   ```bash
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

3. **Frontend Environment** (add to pc-flipper-customer/.env.local)
   ```bash
   NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
   ```

### 5.2 Dependencies

```bash
# Backend
cd pc-flipper-backend
pip install stripe

# Frontend
cd pc-flipper-customer
npm install @stripe/react-stripe-js @stripe/js
```

### 5.3 Testing with Stripe CLI

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli

# Start listening to webhook events
stripe listen --forward-to localhost:8000/api/stripe/webhook

# Forward webhook signing secret to .env.local
export STRIPE_WEBHOOK_SECRET=whsec_...
```

### 5.4 Test Card Numbers

Use these in Stripe test mode:
- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- Requires auth: `4000 0025 0000 3155`

---

## 6. Task Breakdown (8 Implementation Tasks)

### Task S2-1: Database Schema & Migrations
**Effort:** 2-4 hours  
**Status:** Pending  
**Description:**
- Create SQLAlchemy models: Order, BuildCapacity, BuildCapacityOverride
- Write Alembic migration script
- Seed build_capacity with default_per_week=3
- Run migration on dev database
- Verify schema with `\dt` in psql

**Acceptance Criteria:**
- ✓ Models created and registered in app.models.__init__.py
- ✓ Migration runs without errors
- ✓ build_capacity table has one row with default_per_week=3
- ✓ All indexes created correctly
- ✓ Can query tables via async SQLAlchemy

**Files Created/Modified:**
- `/app/models/order.py` (new)
- `/app/models/build_capacity.py` (new)
- `/app/models/build_capacity_override.py` (new)
- `/alembic/versions/XXX_add_orders_and_capacity_tables.py` (new)
- `/app/models/__init__.py` (add imports)

---

### Task S2-2: Pydantic Schemas
**Effort:** 1-2 hours  
**Status:** Pending  
**Description:**
- Create Pydantic v2 request/response schemas
- Validate email, numeric precision, enum values
- Add docstrings for API documentation

**Acceptance Criteria:**
- ✓ All schemas validate correctly
- ✓ OrderCheckoutRequest accepts all required fields
- ✓ OrderConfirmationOut serializes from ORM objects
- ✓ Numeric fields use Decimal for precision

**Files Created/Modified:**
- `/app/schemas/order.py` (new)

---

### Task S2-3: API Endpoint — GET /api/orders/slots
**Effort:** 2-3 hours  
**Status:** Pending  
**Description:**
- Calculate available capacity per week
- Return next 8 weeks with availability
- Handle overrides and booked slots
- Write unit & integration tests

**Acceptance Criteria:**
- ✓ Endpoint returns correct weeks
- ✓ Respects global default capacity
- ✓ Respects per-week overrides
- ✓ Excludes full weeks (available=0)
- ✓ Excludes weeks within 5 business days
- ✓ Tests pass (unit + integration)

**Test Scenarios:**
1. No orders → all weeks available (capacity=3)
2. Override week to 2 → returns 2 available
3. 3 orders booked → week unavailable
4. Override week to null → week excluded

---

### Task S2-4: Stripe Integration Setup
**Effort:** 1-2 hours  
**Status:** Pending  
**Description:**
- Install stripe Python package
- Add STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET to config
- Create webhook endpoint stub
- Test Stripe API connection

**Acceptance Criteria:**
- ✓ stripe package installed
- ✓ Settings loads Stripe keys from .env.local
- ✓ Can create Checkout Session via Stripe API (test)
- ✓ Webhook endpoint returns 200 (no-op)

**Files Created/Modified:**
- `/app/config.py` (add Stripe config)
- `/app/api/stripe_webhooks.py` (new, stub)

---

### Task S2-5: API Endpoint — POST /api/orders/checkout
**Effort:** 3-4 hours  
**Status:** Pending  
**Description:**
- Validate playbook and variants exist
- Check week has available capacity
- Generate unique order reference
- Create Order row
- Create Stripe Checkout Session
- Return checkout URL to customer

**Acceptance Criteria:**
- ✓ Order reference unique and formatted FF-YYYY-NNNNN
- ✓ Rejects invalid playbook ID
- ✓ Rejects full week
- ✓ Creates Stripe session with correct line items
- ✓ Returns valid Stripe checkout URL
- ✓ Tests cover all error cases

**Test Scenarios:**
1. Valid request → returns Stripe URL
2. Invalid playbook → 404
3. Week full → 409 Conflict
4. Invalid week format → 400 Bad Request

---

### Task S2-6: API Endpoint — POST /api/stripe/webhook
**Effort:** 2-3 hours  
**Status:** Pending  
**Description:**
- Verify Stripe webhook signature (security critical)
- Handle checkout.session.completed event
- Update order status to confirmed
- Auto-assign build week
- Send confirmation email
- Handle edge cases gracefully

**Acceptance Criteria:**
- ✓ Rejects unsigned/tampered webhooks
- ✓ Updates order.status → confirmed
- ✓ Assigns earliest available week
- ✓ Sets payment_confirmed_at timestamp
- ✓ Returns 200 OK to Stripe
- ✓ Idempotent (safe to replay)

**Test Scenarios:**
1. Valid event → order confirmed
2. Tampered signature → 400
3. Unknown order ID → 200 (silently ignored)
4. Webhook replayed twice → idempotent

---

### Task S2-7: API Endpoint — GET /api/orders/[reference]
**Effort:** 1-2 hours  
**Status:** Pending  
**Description:**
- Fetch order by human-readable reference
- Return full order details for confirmation page
- Handle not found gracefully

**Acceptance Criteria:**
- ✓ Fetches order by reference (not ID)
- ✓ Returns all fields needed for confirmation page
- ✓ Returns 404 if order not found
- ✓ Tests cover success and error cases

---

### Task S2-8: Admin Endpoints (5 endpoints)
**Effort:** 4-5 hours  
**Status:** Pending  
**Description:**
- GET /api/admin/orders (list, filter, paginate)
- PATCH /api/admin/orders/[id] (update status/notes)
- GET /api/admin/capacity (read current settings)
- PATCH /api/admin/capacity/default (update default)
- PUT /api/admin/capacity/overrides/[week] (set/remove overrides)
- Add auth guards (protect all admin routes)
- Write tests

**Acceptance Criteria:**
- ✓ All 5 endpoints working
- ✓ Pagination works (limit, offset)
- ✓ Filtering works (status, week, email)
- ✓ Auth guard blocks unauthenticated requests
- ✓ Tests verify filtering and permissions

---

### Task S2-9: Email Notifications
**Effort:** 2-3 hours  
**Status:** Pending  
**Description:**
- Setup SendGrid or AWS SES
- Create order confirmation email template
- Send email on checkout.session.completed
- Send status update emails (building, shipped)
- Handle bounces/failures gracefully

**Acceptance Criteria:**
- ✓ Emails send successfully (test mode)
- ✓ HTML template renders correctly
- ✓ Customer gets confirmation within 1 minute
- ✓ Errors logged (don't block webhook)
- ✓ Tests verify email sending

**Email Templates:**
1. Order Confirmation (on payment)
2. Building Started (on status update)
3. Shipped (on status update)

---

## 7. Testing Strategy

### Unit Tests

```python
# File: pc-flipper-backend/tests/test_orders.py

import pytest
from datetime import datetime, date
from app.models.order import Order
from app.models.build_capacity import BuildCapacity, BuildCapacityOverride
from app.schemas.order import OrderCheckoutRequest


@pytest.mark.asyncio
async def test_get_available_slots_returns_next_8_weeks(db):
    """Test that slots endpoint returns next 8 weeks."""
    # Setup
    capacity = BuildCapacity(default_per_week=3)
    db.add(capacity)
    await db.commit()
    
    # Test
    response = await client.get("/api/orders/slots")
    assert response.status_code == 200
    slots = response.json()
    assert len(slots) <= 8
    assert slots[0]["available"] == 3


@pytest.mark.asyncio
async def test_create_checkout_generates_unique_reference(db):
    """Test that order reference is unique."""
    # Create first order
    resp1 = await client.post("/api/orders/checkout", json={...})
    ref1 = resp1.json()["reference"]
    
    # Create second order
    resp2 = await client.post("/api/orders/checkout", json={...})
    ref2 = resp2.json()["reference"]
    
    assert ref1 != ref2


@pytest.mark.asyncio
async def test_create_checkout_rejects_full_week(db):
    """Test that checkout rejects when week is full."""
    # Setup: Book 3 slots (default capacity)
    for i in range(3):
        order = Order(
            reference=f"FF-2026-{i:05d}",
            playbook_id=1,
            playbook_name="Test",
            build_config={},
            customer_name="Test",
            customer_email="test@example.com",
            delivery_address={},
            subtotal_gbp=100,
            tax_gbp=0,
            total_gbp=100,
            status="confirmed",
            assigned_build_week="2026-W27",
        )
        db.add(order)
    await db.commit()
    
    # Test: Try to book 4th slot
    response = await client.post("/api/orders/checkout", json={
        "playbook_id": 1,
        "build_config": {},
        "customer_name": "Test",
        "customer_email": "test@example.com",
        "delivery_address": {},
        "chosen_week": "2026-W27",
    })
    
    assert response.status_code == 409
    assert "fully booked" in response.json()["detail"]


@pytest.mark.asyncio
async def test_stripe_webhook_confirms_order(db):
    """Test that webhook updates order status."""
    # Setup: Create pending order
    order = Order(...)
    db.add(order)
    await db.commit()
    
    # Simulate Stripe webhook
    payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"order_id": order.id},
                "payment_intent": "pi_test_123",
            }
        }
    }
    
    # Test
    response = await client.post(
        "/api/stripe/webhook",
        json=payload,
        headers={"stripe-signature": sign_webhook(payload)},
    )
    
    assert response.status_code == 200
    
    # Verify order updated
    updated = await db.get(Order, order.id)
    assert updated.status == "confirmed"
    assert updated.assigned_build_week is not None
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_end_to_end_checkout_flow(db, stripe_client):
    """
    Full flow: Create order → Pay → Webhook → Confirmation.
    
    1. POST /api/orders/checkout
    2. Get Stripe checkout URL
    3. Simulate Stripe payment
    4. Receive webhook
    5. Verify order status updated
    6. Verify GET /api/orders/[reference] returns confirmed
    """
    # 1. Create order
    response = await client.post("/api/orders/checkout", json={
        "playbook_id": 1,
        "build_config": {...},
        "customer_name": "John Doe",
        "customer_email": "john@example.com",
        "delivery_address": {...},
        "chosen_week": "2026-W27",
    })
    
    assert response.status_code == 201
    data = response.json()
    reference = data["reference"]
    stripe_session_id = extract_session_from_url(data["stripe_url"])
    
    # 2. Simulate Stripe webhook
    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": stripe_session_id,
                "metadata": {"order_id": data["order_id"]},
                "payment_intent": "pi_test_123",
            }
        }
    }
    
    webhook_response = await client.post(
        "/api/stripe/webhook",
        json=webhook_payload,
        headers={"stripe-signature": sign_webhook(webhook_payload)},
    )
    
    assert webhook_response.status_code == 200
    
    # 3. Verify confirmation
    confirmation = await client.get(f"/api/orders/{reference}")
    assert confirmation.status_code == 200
    order_data = confirmation.json()
    assert order_data["status"] == "confirmed"
    assert order_data["assigned_build_week"] == "2026-W27"
```

### Manual Testing

```bash
# 1. Start dev server
cd pc-flipper-backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. Start Stripe CLI listener
stripe listen --forward-to localhost:8000/api/stripe/webhook

# 3. Test slots endpoint
curl http://localhost:8000/api/orders/slots

# 4. Test checkout (use test card 4242 4242 4242 4242)
curl -X POST http://localhost:8000/api/orders/checkout \
  -H "Content-Type: application/json" \
  -d @checkout_request.json

# 5. In Stripe test dashboard, simulate payment
# (Stripe CLI will forward webhook to /api/stripe/webhook)

# 6. Verify order confirmed
curl http://localhost:8000/api/orders/FF-2026-00001
```

---

## 8. Implementation Timeline

| Task | Hours | Effort | Cumulative | Status |
|------|-------|--------|-----------|--------|
| S2-1: Schema & Migrations | 3 | Medium | 3h | 📋 Pending |
| S2-2: Pydantic Schemas | 1.5 | Easy | 4.5h | 📋 Pending |
| S2-3: Stripe Setup | 1.5 | Easy | 6h | 📋 Pending |
| S2-4: GET /api/orders/slots | 2.5 | Medium | 8.5h | 📋 Pending |
| S2-5: POST /api/orders/checkout | 3.5 | Hard | 12h | 📋 Pending |
| S2-6: POST /api/stripe/webhook | 2.5 | Hard | 14.5h | 📋 Pending |
| S2-7: GET /api/orders/[reference] | 1.5 | Easy | 16h | 📋 Pending |
| S2-8: Admin Endpoints (5) | 4.5 | Hard | 20.5h | 📋 Pending |
| S2-9: Email Notifications | 2.5 | Medium | 23h | 📋 Pending |
| **TOTAL** | **~23 hours** | - | - | - |

**Recommended Pace:** 5-6 hours/day over 4-5 days

**Week 1 (Mon-Tue):** Tasks S2-1 through S2-4 (8.5 hours)  
**Week 1 (Wed-Thu):** Tasks S2-5 through S2-7 (7.5 hours)  
**Week 1 (Fri) + Week 2:** Tasks S2-8 and S2-9 (7 hours)

---

## 9. Deployment Checklist

### Pre-Launch

- [ ] All tests passing (unit + integration)
- [ ] Stripe keys configured for production
- [ ] Database migration tested on staging
- [ ] Webhook endpoint publicly accessible
- [ ] Email service tested with real SMTP
- [ ] Load testing: Can handle concurrent checkouts
- [ ] Error handling: Graceful degradation if Stripe is down
- [ ] Admin dashboard updated to show orders

### Go-Live

- [ ] Enable Stripe production mode (not test)
- [ ] Monitor webhook delivery (Stripe Dashboard)
- [ ] Check email delivery (SendGrid logs)
- [ ] Alert if order processing fails
- [ ] Test end-to-end with real payment

### Post-Launch

- [ ] Monitor orders per day
- [ ] Check capacity utilization
- [ ] Review customer support tickets for issues
- [ ] Track Stripe API error rates

---

## 10. Next Steps

1. **Review & Approve** this plan
2. **Request changes** if needed (e.g., different payment provider, email service)
3. **Proceed to Task S2-1** (Database Schema)
4. **Use TDD approach:** Write tests first, implement after
5. **After S2-6**, do manual end-to-end testing with Stripe test mode
6. **Document API** in OpenAPI/Swagger once endpoints complete

---

## Appendix A: Reference Information

### Frontend Integration (pc-flipper-customer)

The Next.js app will need:

1. **Configurator Page** → Calls `POST /api/orders/checkout`
2. **Order Confirmation Page** (`/order/[reference]`) → Calls `GET /api/orders/[reference]`
3. **Stripe Redirect Handler** → Redirects from Stripe to `/order/[reference]`

### Subsystem 3 Handoff (Delivery Tracker)

This subsystem provides:
- Order data (customer, delivery address, build config)
- Build week assignment (when fulfillment starts)
- Order status (confirmed, building, shipped)
- Estimated arrival date (for communication)

Subsystem 3 will:
- Track build progress
- Update estimated_arrival_date
- Set delivery_at_risk flag if delayed
- Communicate with customer via email

### External Dependencies

- **Stripe Account** → API keys needed
- **Email Service** → SendGrid/SES account + API key
- **Database** → PostgreSQL (existing)

---

## Appendix B: Example Environment Variables

```bash
# .env.local (pc-flipper-backend)

DATABASE_URL=postgresql+asyncpg://flipper:flipper@127.0.0.1:5432/pcflipper
FRONTEND_URL=http://localhost:3000

STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_test_...

SENDGRID_API_KEY=SG.xxx_...
SENDGRID_FROM_EMAIL=noreply@flipflop.co.uk

ADMIN_API_KEY=secret-key-for-admin-endpoints
```

---

**Document Created:** 2026-06-22  
**Status:** Ready for Implementation  
**Owner:** Backend Engineering  
**Version:** 1.0
