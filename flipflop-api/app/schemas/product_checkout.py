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
