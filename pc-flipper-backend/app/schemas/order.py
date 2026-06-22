from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal


class DeliveryAddressIn(BaseModel):
    line1: str = Field(..., min_length=1, max_length=255)
    line2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    postcode: str = Field(..., min_length=1, max_length=20)
    country: str = Field(..., min_length=1, max_length=100)


class OrderCheckoutRequest(BaseModel):
    playbook_id: int = Field(..., gt=0)
    build_config: Dict[str, Any] = Field(..., description="Component selections and case choice")
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_email: EmailStr
    delivery_address: DeliveryAddressIn
    chosen_week: str = Field(..., pattern=r'^\d{4}-W\d{2}$', description="ISO week format: YYYY-Www")


class OrderCheckoutResponse(BaseModel):
    reference: str = Field(..., description="Human-readable order reference e.g., FF-2026-0042")
    stripe_url: str = Field(..., description="Stripe Checkout Session URL")


class OrderConfirmationOut(BaseModel):
    reference: str
    playbook_name: str
    build_config: Dict[str, Any]
    customer_name: str
    customer_email: str
    delivery_address: Dict[str, str]
    subtotal_gbp: Decimal
    tax_gbp: Decimal
    total_gbp: Decimal
    assigned_build_week: Optional[str]
    estimated_arrival_date: Optional[date]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CapacitySlotsOut(BaseModel):
    week: str = Field(..., description="ISO week format: YYYY-Www")
    week_start: str = Field(..., description="ISO date format: YYYY-MM-DD")
    available: int = Field(..., ge=0, description="Remaining available slots this week")
    capacity: int = Field(..., gt=0, description="Total capacity for this week")


class BuildCapacityOut(BaseModel):
    default_per_week: int


class CapacityOverrideIn(BaseModel):
    max_builds: Optional[int] = Field(None, ge=0, description="null = week closed, 0+ = override capacity")
    note: Optional[str] = Field(None, max_length=500)


class AdminOrderOut(BaseModel):
    id: int
    reference: str
    playbook_name: str
    customer_name: str
    customer_email: str
    total_gbp: Decimal
    status: str
    assigned_build_week: Optional[str]
    delivery_at_risk: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminOrderUpdateIn(BaseModel):
    status: Optional[str] = Field(None, pattern=r'^(pending_payment|confirmed|building|shipped|cancelled)$')
    note: Optional[str] = Field(None, max_length=500)
