from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum, JSON
from datetime import datetime
from app.database import Base
import enum


class LifecycleEventType(enum.Enum):
    DELIVERY_CONFIRMED = "delivery_confirmed"
    GETTING_STARTED_EMAIL = "getting_started_email"
    CHECK_IN_7DAY = "check_in_7day"
    SATISFACTION_SURVEY_30DAY = "satisfaction_survey_30day"
    REVIEW_REQUEST = "review_request"
    MAINTENANCE_REMINDER = "maintenance_reminder"
    DRIVER_BIOS_UPDATE_NOTICE = "driver_bios_update_notice"
    WARRANTY_REMINDER = "warranty_reminder"
    UPGRADE_CAMPAIGN = "upgrade_campaign"
    TRADE_IN_OFFER = "trade_in_offer"
    LOYALTY_CAMPAIGN = "loyalty_campaign"
    REFERRAL_INVITE = "referral_invite"


class LifecycleEventStatus(enum.Enum):
    SCHEDULED = "scheduled"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class LifecycleEvent(Base):
    """Post-sale customer touchpoint ledger. PRD Ch.6.9, Ch.16."""
    __tablename__ = "lifecycle_events"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    event_type = Column(Enum(LifecycleEventType), nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    status = Column(Enum(LifecycleEventStatus), default=LifecycleEventStatus.SCHEDULED, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    response_captured_json = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
