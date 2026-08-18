from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, Enum, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class ProductType(enum.Enum):
    PREBUILT = "prebuilt"
    CONFIGURABLE_TEMPLATE = "configurable_template"


class ProductStatus(enum.Enum):
    DRAFT = "draft"
    LISTED = "listed"
    RESERVED = "reserved"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


class SoldChannel(enum.Enum):
    EBAY = "ebay"
    STOREFRONT = "storefront"


class Product(Base):
    """The canonical sellable unit. See PRD Ch.6.2."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    product_type = Column(Enum(ProductType), nullable=False)
    build_id = Column(Integer, ForeignKey("builds.id"), nullable=True)
    playbook_id = Column(Integer, ForeignKey("playbooks.id"), nullable=True)

    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    status = Column(Enum(ProductStatus), default=ProductStatus.DRAFT, nullable=False)

    sold_via_channel = Column(Enum(SoldChannel), nullable=True)
    sold_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    benchmark_report_document_id = Column(Integer, ForeignKey("cx_documents.id"), nullable=True)
    capture_3d_asset_id = Column(Integer, ForeignKey("capture_3d_assets.id"), nullable=True)
    hero_photo_url = Column(String, nullable=True)
    model_3d_url = Column(String, nullable=True)
    selected_faqs = Column(JSON, nullable=False, default=list)
    fulfilment_type = Column(String(30), nullable=False, default="prebuilt")
    handling_min_days = Column(Integer, nullable=False, default=1)
    handling_max_days = Column(Integer, nullable=False, default=1)
    delivery_min_days = Column(Integer, nullable=False, default=1)
    delivery_max_days = Column(Integer, nullable=False, default=2)
    profit_calculation_id = Column(Integer, ForeignKey("profit_calculations.id"), nullable=True)

    reserved_until = Column(DateTime, nullable=True)  # soft basket-add reservation window, Ch.9.6

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    build = relationship("Build", back_populates="product")
    listings = relationship("ProductListing", back_populates="product", cascade="all, delete-orphan")


class ListingChannel(enum.Enum):
    EBAY = "ebay"
    STOREFRONT = "storefront"


class ProductListingStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"
    FAILED = "failed"


class WithdrawalReason(enum.Enum):
    SOLD_OTHER_CHANNEL = "sold_other_channel"
    MANUAL = "manual"
    EXPIRED = "expired"
    ERROR = "error"


class ProductListing(Base):
    """Channel-specific presence of a Product. See PRD Ch.6.3, Business Rule CBR-1."""
    __tablename__ = "product_listings"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    channel = Column(Enum(ListingChannel), nullable=False)
    external_listing_id = Column(String, nullable=True)
    status = Column(Enum(ProductListingStatus), default=ProductListingStatus.PENDING, nullable=False)

    listed_at = Column(DateTime, nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)
    withdrawal_reason = Column(Enum(WithdrawalReason), nullable=True)

    view_count = Column(Integer, default=0)
    watcher_count = Column(Integer, default=0)
    offer_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="listings")
    events = relationship("ChannelEvent", back_populates="product_listing", cascade="all, delete-orphan")


class ChannelEventType(enum.Enum):
    OFFER_RECEIVED = "offer_received"
    QUESTION_RECEIVED = "question_received"
    WATCHER_ADDED = "watcher_added"
    BASKET_ADDED = "basket_added"
    SALE_CONFIRMED = "sale_confirmed"
    PAYMENT_CONFIRMED = "payment_confirmed"


class ChannelEvent(Base):
    """Email/Notification Watcher event log. See PRD Ch.6.4, Ch.9.3."""
    __tablename__ = "channel_events"

    id = Column(Integer, primary_key=True)
    product_listing_id = Column(Integer, ForeignKey("product_listings.id"), nullable=False, index=True)
    event_type = Column(Enum(ChannelEventType), nullable=False)
    payload_json = Column(JSON, nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    resulting_action = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product_listing = relationship("ProductListing", back_populates="events")
