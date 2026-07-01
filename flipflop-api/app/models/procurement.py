from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, Enum, ForeignKey, JSON
from datetime import datetime
from app.database import Base
from app.models.packaging_playbook import PackagingComponentCategory


class ProcurementSupplier(Base):
    """CXP PRD Ch.7.4."""
    __tablename__ = "procurement_suppliers"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True, nullable=False)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    lead_time_days = Column(Integer, default=0)
    shipping_cost = Column(Float, default=0.0)
    uk_warehouse = Column(Boolean, default=False)
    is_preferred = Column(Boolean, default=False)
    integration_config = Column(JSON, nullable=True)  # reserved seam for future EDI/API integration, Ch.14.5

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcurementProduct(Base):
    """CXP PRD Ch.7.5. Packaging materials/consumables/accessories — parallel to, not merged
    with, the existing component Inventory module (Ch.15)."""
    __tablename__ = "procurement_products"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True, nullable=False)
    sku = Column(String, unique=True, nullable=True)
    category = Column(Enum(PackagingComponentCategory), nullable=False)
    unit_of_measure = Column(String, nullable=True)
    unit_cost = Column(Float, default=0.0)
    preferred_supplier_id = Column(Integer, ForeignKey("procurement_suppliers.id"), nullable=True)
    purchase_url = Column(String, nullable=True)
    min_stock_level = Column(Integer, default=0)
    reorder_level = Column(Integer, default=0)
    spec_json = Column(JSON, nullable=True)  # category-specific attrs, e.g. USB capacity_bytes
    active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcurementProductSupplier(Base):
    """Alternative suppliers per product. CXP PRD Ch.7.6."""
    __tablename__ = "procurement_product_suppliers"

    id = Column(Integer, primary_key=True)
    procurement_product_id = Column(Integer, ForeignKey("procurement_products.id"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("procurement_suppliers.id"), nullable=False)
    supplier_sku = Column(String, nullable=True)
    unit_cost = Column(Float, nullable=False)
    lead_time_days_override = Column(Integer, nullable=True)


class ProcurementPurchase(Base):
    """Purchase history / stock-in ledger. CXP PRD Ch.7.7."""
    __tablename__ = "procurement_purchases"

    id = Column(Integer, primary_key=True)
    procurement_product_id = Column(Integer, ForeignKey("procurement_products.id"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("procurement_suppliers.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_cost_paid = Column(Float, nullable=False)
    purchase_date = Column(DateTime, nullable=False)
    received_date = Column(DateTime, nullable=True)
    reference = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("customers.id"), nullable=True)


from sqlalchemy import Enum as SAEnum
import enum


class ProcurementReservationStatus(enum.Enum):
    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"


class ProcurementReservation(Base):
    """Stock committed to a specific order's packaging BOM. CXP PRD Ch.7.8, Ch.14.2."""
    __tablename__ = "procurement_reservations"

    id = Column(Integer, primary_key=True)
    procurement_product_id = Column(Integer, ForeignKey("procurement_products.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    quantity_reserved = Column(Integer, nullable=False)
    status = Column(SAEnum(ProcurementReservationStatus), default=ProcurementReservationStatus.RESERVED, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
