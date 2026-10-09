"""
Curated Purchase Plan models.

Creates shopping lists for Michael when customers purchase curated builds.
Tracks inventory lifecycle via email parsing (order confirmation → tracking → delivered → dispatched).

Design:
- Purchase plan = shopping list for a curated order
- Each line: component, quantity, expected price, vendor links (primary + backup)
- Group by vendor for efficient shopping
- Track what's already in inventory (no purchase needed)
- Email-driven status updates (ordered → tracking → delivered → build-ready → dispatched)
- Ad-hoc purchases (bargain buys) also tracked for future use
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime, ForeignKey, Text, Index, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class PurchasePlanStatus(enum.Enum):
    """Overall purchase plan status."""
    DRAFT = "draft"  # Created but not yet confirmed
    PENDING = "pending"  # Confirmed, awaiting Michael's purchases
    PARTIALLY_ORDERED = "partially_ordered"  # Some items ordered
    FULLY_ORDERED = "fully_ordered"  # All items ordered
    PARTIALLY_DELIVERED = "partially_delivered"  # Some items delivered
    FULLY_DELIVERED = "fully_delivered"  # All items delivered
    BUILD_READY = "build_ready"  # All components ready, can build
    COMPLETED = "completed"  # Build completed and dispatched


class ComponentLineStatus(enum.Enum):
    """Status for individual component line items."""
    TO_BUY = "to_buy"  # Needs to be purchased
    FROM_INVENTORY = "from_inventory"  # Already in inventory
    ORDERED = "ordered"  # Order placed with vendor
    TRACKING = "tracking"  # Tracking number received
    DELIVERED = "delivered"  # Delivered to Michael
    BUILD_READY = "build_ready"  # Ready for build
    DISPATCHED = "dispatched"  # Used in build and shipped to customer


class CuratedPurchasePlan(Base):
    """
    Purchase plan / shopping list for curated build orders.
    
    Created when customer purchases curated build. Provides Michael with:
    - Shopping list grouped by vendor
    - Expected costs vs inventory items
    - Clickable links to specific listings
    - Email tracking integration
    """
    __tablename__ = "curated_purchase_plans"

    id = Column(Integer, primary_key=True, index=True)
    
    # Order association
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True, nullable=False, index=True)
    curated_build_id = Column(String(50), nullable=False, index=True)  # e.g., "FF-GVG-02"
    
    # Status tracking
    status = Column(String(50), default="pending", nullable=False, index=True)
    
    # Financial summary
    total_expected_cost_gbp = Column(Float, default=0.0, nullable=False)
    total_from_inventory_cost_gbp = Column(Float, default=0.0, nullable=False)  # Value of inventory items used
    total_to_buy_cost_gbp = Column(Float, default=0.0, nullable=False)  # Cost of items to purchase
    total_actual_cost_gbp = Column(Float, nullable=True)  # Actual cost after purchases (from emails)
    
    # Component counts
    total_components = Column(Integer, default=0, nullable=False)
    components_from_inventory = Column(Integer, default=0, nullable=False)
    components_to_buy = Column(Integer, default=0, nullable=False)
    components_ordered = Column(Integer, default=0, nullable=False)
    components_delivered = Column(Integer, default=0, nullable=False)
    
    # Vendor grouping (for efficient shopping)
    primary_vendor = Column(String(100), nullable=True)  # Vendor with most items
    vendor_summary = Column(JSON, nullable=True)  # Map of vendor -> item count
    
    # Build association (after components delivered)
    specific_build_id = Column(Integer, ForeignKey("builds.id"), nullable=True, index=True)  # Links to build history gallery
    
    # Admin notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    all_ordered_at = Column(DateTime, nullable=True)  # When all items ordered
    all_delivered_at = Column(DateTime, nullable=True)  # When all items delivered
    build_completed_at = Column(DateTime, nullable=True)  # When build finished
    dispatched_at = Column(DateTime, nullable=True)  # When shipped to customer
    
    # Relationships
    order = relationship("Order", back_populates="purchase_plan")
    component_lines = relationship("PurchasePlanComponentLine", back_populates="purchase_plan", cascade="all, delete-orphan")
    inventory_links = relationship("PurchasePlanInventoryLink", back_populates="purchase_plan", cascade="all, delete-orphan")


class PurchasePlanComponentLine(Base):
    """
    Individual component line in purchase plan.
    
    Includes:
    - Component details (name, slot, spec)
    - Quantity needed
    - Expected pay price
    - Primary vendor link (lowest price)
    - Secondary vendor link (second-lowest price)
    - Status tracking (to_buy → ordered → tracking → delivered → dispatched)
    - Inventory item link (if from inventory)
    """
    __tablename__ = "purchase_plan_component_lines"

    id = Column(Integer, primary_key=True, index=True)
    
    purchase_plan_id = Column(Integer, ForeignKey("curated_purchase_plans.id"), nullable=False, index=True)
    
    # Component identification
    component_slot = Column(String(50), nullable=False)  # cpu, gpu, ram, etc.
    component_title = Column(String(500), nullable=False)
    component_spec = Column(JSON, nullable=True)  # Detailed specs
    
    # Quantity
    quantity = Column(Integer, default=1, nullable=False)
    
    # Pricing
    expected_unit_price_gbp = Column(Float, nullable=False)
    expected_total_price_gbp = Column(Float, nullable=False)  # quantity * unit_price
    actual_unit_price_gbp = Column(Float, nullable=True)  # From email confirmation
    actual_total_price_gbp = Column(Float, nullable=True)  # From email confirmation
    
    # Primary vendor (lowest price)
    primary_vendor_name = Column(String(100), nullable=False)
    primary_vendor_listing_url = Column(String(1000), nullable=False)  # Clickable link
    primary_vendor_sku = Column(String(255), nullable=True)
    primary_vendor_price_gbp = Column(Float, nullable=False)
    
    # Secondary vendor (second-lowest price, backup option)
    secondary_vendor_name = Column(String(100), nullable=True)
    secondary_vendor_listing_url = Column(String(1000), nullable=True)  # Clickable link
    secondary_vendor_sku = Column(String(255), nullable=True)
    secondary_vendor_price_gbp = Column(Float, nullable=True)
    
    # Status tracking
    status = Column(String(50), default="to_buy", nullable=False, index=True)
    source = Column(String(50), default="to_buy", nullable=False)  # "to_buy" or "from_inventory"
    
    # Order tracking (from email)
    order_confirmation_email_id = Column(Integer, ForeignKey("email_events.id"), nullable=True)
    order_date = Column(DateTime, nullable=True)
    order_reference = Column(String(255), nullable=True)  # Vendor order number
    
    # Shipping tracking (from email)
    tracking_email_id = Column(Integer, ForeignKey("email_events.id"), nullable=True)
    tracking_number = Column(String(255), nullable=True)
    courier = Column(String(100), nullable=True)
    expected_delivery_date = Column(DateTime, nullable=True)
    
    # Delivery tracking (from email)
    delivery_email_id = Column(Integer, ForeignKey("email_events.id"), nullable=True)
    delivery_date = Column(DateTime, nullable=True)
    
    # Inventory link (if from inventory)
    inventory_item_id = Column(Integer, ForeignKey("inventory.id"), nullable=True, index=True)
    inventory_reserved_at = Column(DateTime, nullable=True)
    
    # Build usage
    used_in_build_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    purchase_plan = relationship("CuratedPurchasePlan", back_populates="component_lines")
    inventory_item = relationship("InventoryItem", foreign_keys=[inventory_item_id])
    order_confirmation_email = relationship("EmailEvent", foreign_keys=[order_confirmation_email_id])
    tracking_email = relationship("EmailEvent", foreign_keys=[tracking_email_id])
    delivery_email = relationship("EmailEvent", foreign_keys=[delivery_email_id])
    
    __table_args__ = (
        Index('ix_purchase_plan_component_lines_plan_slot', 'purchase_plan_id', 'component_slot'),
        Index('ix_purchase_plan_component_lines_plan_status', 'purchase_plan_id', 'status'),
    )


class PurchasePlanInventoryLink(Base):
    """
    Links inventory items reserved for a purchase plan.
    
    Tracks inventory lifecycle:
    - Reserved: Inventory item allocated to this plan
    - Build-ready: Delivered and ready for assembly
    - Dispatched: Build completed and shipped to customer (archive inventory)
    """
    __tablename__ = "purchase_plan_inventory_links"

    id = Column(Integer, primary_key=True, index=True)
    
    purchase_plan_id = Column(Integer, ForeignKey("curated_purchase_plans.id"), nullable=False, index=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory.id"), nullable=False, index=True)
    component_line_id = Column(Integer, ForeignKey("purchase_plan_component_lines.id"), nullable=True)
    
    # Reservation details
    quantity_reserved = Column(Integer, default=1, nullable=False)
    reserved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reserved_by = Column(String(255), nullable=True)  # Admin who reserved
    
    # Status
    status = Column(String(50), default="reserved", nullable=False)  # reserved/build_ready/dispatched/released
    
    # Build usage
    used_in_build_at = Column(DateTime, nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    
    # If released (not used in this build)
    released_at = Column(DateTime, nullable=True)
    release_reason = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    purchase_plan = relationship("CuratedPurchasePlan", back_populates="inventory_links")
    inventory_item = relationship("InventoryItem")
    component_line = relationship("PurchasePlanComponentLine")


class AdHocPurchaseRecord(Base):
    """
    Ad-hoc purchases (Michael's bargain buys not tied to customer order).
    
    Tracked via email monitoring. Adds to inventory for future curated builds.
    """
    __tablename__ = "ad_hoc_purchase_records"

    id = Column(Integer, primary_key=True, index=True)
    
    # Purchase details
    component_title = Column(String(500), nullable=False)
    component_slot = Column(String(50), nullable=True)  # cpu, gpu, ram, etc. (if identified)
    quantity = Column(Integer, default=1, nullable=False)
    
    # Pricing
    unit_price_gbp = Column(Float, nullable=False)
    total_price_gbp = Column(Float, nullable=False)
    
    # Vendor info
    vendor_name = Column(String(100), nullable=False)
    listing_url = Column(String(1000), nullable=True)
    vendor_sku = Column(String(255), nullable=True)
    
    # Order tracking (from email)
    order_confirmation_email_id = Column(Integer, ForeignKey("email_events.id"), nullable=True, index=True)
    order_date = Column(DateTime, nullable=True)
    order_reference = Column(String(255), nullable=True)
    
    # Shipping tracking
    tracking_email_id = Column(Integer, ForeignKey("email_events.id"), nullable=True)
    tracking_number = Column(String(255), nullable=True)
    courier = Column(String(100), nullable=True)
    expected_delivery_date = Column(DateTime, nullable=True)
    
    # Delivery tracking
    delivery_email_id = Column(Integer, ForeignKey("email_events.id"), nullable=True)
    delivery_date = Column(DateTime, nullable=True)
    
    # Inventory link (created after delivery)
    inventory_item_id = Column(Integer, ForeignKey("inventory.id"), nullable=True, index=True)
    added_to_inventory_at = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(50), default="ordered", nullable=False, index=True)  # ordered/tracking/delivered/in_inventory
    
    # Notes
    notes = Column(Text, nullable=True)
    bargain_reason = Column(String(500), nullable=True)  # Why it was a good deal
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    order_confirmation_email = relationship("EmailEvent", foreign_keys=[order_confirmation_email_id])
    tracking_email = relationship("EmailEvent", foreign_keys=[tracking_email_id])
    delivery_email = relationship("EmailEvent", foreign_keys=[delivery_email_id])
    inventory_item = relationship("InventoryItem")
