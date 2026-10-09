"""
Curated Component SKU model - Primary + Backup SKU support.

Each playbook component slot supports:
- Primary SKU (preferred, BuildBot-approved)
- Backup SKU(s) (compatibility-locked fallback when primary is OOS)

BuildBot owns the compatibility matrix. Live vendor availability checks determine
which SKU to use. Analytics tags orders with sku_source=primary|backup.

Permanent BOM replacements require Michael Approve in /approvals.
MeshyBot remesh only if visible part swaps (case, GPU, etc.).
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class ComponentSlot(enum.Enum):
    """Component slot types for curated playbooks."""
    CPU = "cpu"
    MOTHERBOARD = "motherboard"
    RAM = "ram"
    GPU = "gpu"
    STORAGE = "storage"
    CASE = "case"
    PSU = "psu"
    COOLING = "cooling"
    OS = "os"


class SKUAvailabilityStatus(enum.Enum):
    """SKU availability status from vendor checks."""
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"
    DISCONTINUED = "discontinued"


class CuratedComponentSKU(Base):
    """
    Primary + Backup SKU definitions for curated playbook components.
    
    BuildBot provides the compatibility-locked matrix. Daily FlipFlopXtension
    scrapes are too slow - shop/API check live vendor availability and soft-swap
    to backup when primary is OOS.
    
    Shop behavior:
    - Never sell hard-OOS configuration
    - Soft-fail to backup SKU
    - Hide tier/ship until resolved if all SKUs OOS
    
    Analytics:
    - Tag funnel/order with sku_source=primary|backup
    
    Governance:
    - Permanent BOM replacement requires Michael Approve
    - MeshyBot remesh only if visible part swaps
    """
    __tablename__ = "curated_component_skus"

    id = Column(Integer, primary_key=True, index=True)
    
    # Playbook + slot identification
    curated_build_id = Column(String(50), nullable=False, index=True)  # e.g., "FF-GVG-02"
    component_slot = Column(String(50), nullable=False)  # cpu, gpu, ram, etc.
    
    # SKU details
    is_primary = Column(Boolean, default=True, nullable=False)  # True=primary, False=backup
    priority = Column(Integer, default=0, nullable=False)  # 0=primary, 1=first backup, 2=second backup, etc.
    
    # Component spec
    component_title = Column(String(500), nullable=False)  # Human-readable title
    component_spec = Column(JSON, nullable=True)  # Detailed specs (for compatibility validation)
    
    # Vendor/sourcing info
    preferred_vendor = Column(String(100), nullable=True)  # overclockers, scan, amazon, etc.
    vendor_sku = Column(String(255), nullable=True)  # Vendor's SKU/product code
    vendor_url = Column(String(1000), nullable=True)  # Direct product page URL
    
    # Pricing (from bot approval queue)
    target_cost_gbp = Column(Float, nullable=True)  # Target procurement cost
    approved_cost_gbp = Column(Float, nullable=True)  # Approved cost from PricingBot
    
    # Availability tracking
    availability_status = Column(String(50), default="unknown", nullable=False)
    availability_checked_at = Column(DateTime, nullable=True)
    availability_check_source = Column(String(100), nullable=True)  # extension/api/manual
    
    # Stock level hints (from vendor API or scrape)
    estimated_stock_level = Column(Integer, nullable=True)  # Quantity available (if known)
    low_stock_threshold = Column(Integer, default=5, nullable=False)  # When to warn
    
    # Compatibility constraints (BuildBot-owned)
    compatibility_notes = Column(JSON, nullable=True)  # Compatibility requirements
    requires_approval_for_swap = Column(Boolean, default=False, nullable=False)  # Visible parts need approval
    requires_remesh = Column(Boolean, default=False, nullable=False)  # Visible parts need MeshyBot remesh
    
    # BuildBot approval tracking
    bot_approval_queue_id = Column(Integer, nullable=True)  # Reference to approval queue
    approved_by = Column(String(255), nullable=True)  # Admin who approved (if manual)
    approved_at = Column(DateTime, nullable=True)
    
    # Deactivation (when SKU is permanently replaced)
    is_active = Column(Boolean, default=True, nullable=False)
    deactivated_at = Column(DateTime, nullable=True)
    deactivation_reason = Column(String(500), nullable=True)
    
    # Metadata
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_curated_component_skus_build_slot', 'curated_build_id', 'component_slot'),
        Index('ix_curated_component_skus_build_slot_priority', 'curated_build_id', 'component_slot', 'priority'),
        Index('ix_curated_component_skus_active', 'is_active'),
        Index('ix_curated_component_skus_availability', 'availability_status'),
    )


class CuratedBuildAvailability(Base):
    """
    Tracks overall availability status for curated builds.
    
    Computed from component SKU availability. Updated on:
    - Vendor availability checks
    - SKU swap events
    - Manual availability updates
    
    Used by shop to determine if build is sellable.
    """
    __tablename__ = "curated_build_availability"

    id = Column(Integer, primary_key=True, index=True)
    
    curated_build_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Overall availability
    is_available = Column(Boolean, default=True, nullable=False)  # Can we sell it?
    availability_status = Column(String(50), default="available", nullable=False)  # available/low_stock/out_of_stock
    
    # Component-level status
    components_status = Column(JSON, nullable=True)  # Per-slot status summary
    
    # Active SKUs (what we're currently using)
    active_skus = Column(JSON, nullable=True)  # Map of slot -> active SKU details
    
    # Backup usage tracking
    using_backup_count = Column(Integer, default=0, nullable=False)  # How many backups in use
    backup_slots = Column(JSON, nullable=True)  # List of slots using backup SKUs
    
    # Availability check metadata
    last_checked_at = Column(DateTime, nullable=True)
    last_check_source = Column(String(100), nullable=True)
    next_check_due_at = Column(DateTime, nullable=True)  # For scheduled checks
    
    # Shop visibility
    is_visible_on_shop = Column(Boolean, default=True, nullable=False)
    hidden_reason = Column(String(500), nullable=True)  # Why it's hidden (if applicable)
    
    # Analytics
    sku_swap_count = Column(Integer, default=0, nullable=False)  # Total swaps (lifetime)
    last_sku_swap_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SKUSwapEvent(Base):
    """
    Logs when a component SKU is swapped from primary to backup (or vice versa).
    
    Used for:
    - Analytics (sku_source=primary|backup tagging)
    - Audit trail
    - Stock forecasting
    - Alerting when swaps become frequent
    """
    __tablename__ = "sku_swap_events"

    id = Column(Integer, primary_key=True, index=True)
    
    curated_build_id = Column(String(50), nullable=False, index=True)
    component_slot = Column(String(50), nullable=False)
    
    # Swap details
    from_sku_id = Column(Integer, ForeignKey("curated_component_skus.id"), nullable=True)
    to_sku_id = Column(Integer, ForeignKey("curated_component_skus.id"), nullable=False)
    
    swap_reason = Column(String(100), nullable=False)  # out_of_stock/price_change/manual/etc.
    swap_source = Column(String(100), default="system", nullable=False)  # system/admin/bot
    
    # Context
    availability_status_before = Column(String(50), nullable=True)
    availability_status_after = Column(String(50), nullable=True)
    
    # Order association (if swap triggered by order attempt)
    triggered_by_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    # Admin who approved manual swap (if applicable)
    approved_by = Column(String(255), nullable=True)
    
    swapped_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    from_sku = relationship("CuratedComponentSKU", foreign_keys=[from_sku_id])
    to_sku = relationship("CuratedComponentSKU", foreign_keys=[to_sku_id])
