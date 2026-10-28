"""Schemas for buying a specific pre-built showcase unit (a Product) on
FlipFlop.shop directly — distinct from the made-to-order configurator
checkout in app/schemas/payment.py, which prices a custom build rather than
a single already-built physical unit."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProductCheckoutIntentResponse(BaseModel):
    client_secret: str
    publishable_key: str
    amount: float
    currency: str = "gbp"
    intent_id: str
    delivery_option: Optional[str] = None
    delivery_days: Optional[int] = None
    delivery_promise: Optional[str] = None

class CheckoutAddress(BaseModel):
    contact_name: str = Field(..., min_length=2, max_length=120)
    address_line1: str = Field(..., min_length=2, max_length=160)
    address_line2: str | None = Field(default=None, max_length=160)
    city: str = Field(..., min_length=2, max_length=100)
    state_or_province: str | None = Field(default=None, max_length=100)
    postal_code: str = Field(..., min_length=3, max_length=20)
    country_code: str = Field(default="GB", pattern="^[A-Z]{2}$")
    phone: str | None = Field(default=None, max_length=30)


class CheckoutAddresses(BaseModel):
    delivery: CheckoutAddress
    billing: CheckoutAddress


class ProductCheckoutIntentRequest(BaseModel):
    discount_code: Optional[str] = None
    speedy_delivery: bool = False
    # None means the customer has not submitted a choice; [] means they chose
    # not to have any optional applications pre-installed.
    software_package_ids: list[str] | None = Field(default=None, max_length=14)
    checkout_addresses: CheckoutAddresses


class ProductCheckoutOptionsRequest(BaseModel):
    intent_id: str = Field(..., min_length=8, max_length=100)
    speedy_delivery: bool = False
    # Omission preserves the existing intent choice; an empty list clears it.
    software_package_ids: list[str] | None = Field(default=None, max_length=14)
    checkout_addresses: CheckoutAddresses


class ProductCheckoutConfirmRequest(BaseModel):
    intent_id: str = Field(..., description="Stripe PaymentIntent ID")


class ProductCheckoutConfirmation(BaseModel):
    order_id: int
    product_id: int
    status: str
    amount: float
    currency: str
    payment_intent_id: str
    created_at: datetime
    ebay_listing_withdrawn: Optional[bool] = None
