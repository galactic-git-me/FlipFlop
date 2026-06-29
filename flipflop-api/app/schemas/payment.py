"""Pydantic schemas for payment requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CreatePaymentIntentRequest(BaseModel):
    """Request to create a Stripe payment intent."""

    budget: float = Field(..., gt=0, description="Total quote price in GBP")
    customer_id: int = Field(..., gt=0, description="Customer ID")

    class Config:
        json_schema_extra = {
            "example": {
                "budget": 1200.00,
                "customer_id": 1,
            }
        }


class PaymentIntentResponse(BaseModel):
    """Response with Stripe payment intent details."""

    client_secret: str = Field(..., description="Stripe client secret for frontend")
    publishable_key: str = Field(..., description="Stripe publishable key")
    amount: float = Field(..., description="Payment amount in GBP")
    currency: str = Field(default="gbp", description="Currency code")
    intent_id: str = Field(..., description="Stripe PaymentIntent ID")

    class Config:
        json_schema_extra = {
            "example": {
                "client_secret": "pi_1234567890_secret_0987654321",
                "publishable_key": "pk_test_1234567890",
                "amount": 1200.00,
                "currency": "gbp",
                "intent_id": "pi_1234567890",
            }
        }


class ConfirmPaymentRequest(BaseModel):
    """Request to confirm payment and create order."""

    intent_id: str = Field(..., description="Stripe PaymentIntent ID")
    customer_id: int = Field(..., gt=0, description="Customer ID")

    class Config:
        json_schema_extra = {
            "example": {
                "intent_id": "pi_1234567890",
                "customer_id": 1,
            }
        }


class PaymentConfirmation(BaseModel):
    """Response confirming successful payment and order creation."""

    order_id: int = Field(..., description="Created Order ID")
    status: str = Field(..., description="Order status")
    amount: float = Field(..., description="Payment amount in GBP")
    currency: str = Field(..., description="Currency code")
    payment_intent_id: str = Field(..., description="Stripe PaymentIntent ID")
    created_at: datetime = Field(..., description="Order creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": 42,
                "status": "awaiting_sourcing",
                "amount": 1200.00,
                "currency": "gbp",
                "payment_intent_id": "pi_1234567890",
                "created_at": "2024-06-29T12:00:00Z",
            }
        }


class PaymentStatusResponse(BaseModel):
    """Response with current payment status."""

    intent_id: str = Field(..., description="Stripe PaymentIntent ID")
    status: str = Field(..., description="Payment status")
    amount: float = Field(..., description="Amount in GBP")
    currency: str = Field(..., description="Currency code")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "intent_id": "pi_1234567890",
                "status": "succeeded",
                "amount": 1200.00,
                "currency": "gbp",
                "created_at": "2024-06-29T12:00:00Z",
            }
        }


class RefundRequest(BaseModel):
    """Request to refund a payment."""

    intent_id: str = Field(..., description="Stripe PaymentIntent ID to refund")
    reason: str = Field(
        default="customer_request",
        description="Refund reason",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intent_id": "pi_1234567890",
                "reason": "customer_request",
            }
        }


class RefundResponse(BaseModel):
    """Response with refund details."""

    refund_id: str = Field(..., description="Stripe Refund ID")
    amount: float = Field(..., description="Refund amount in GBP")
    status: str = Field(..., description="Refund status")
    reason: str = Field(..., description="Refund reason")

    class Config:
        json_schema_extra = {
            "example": {
                "refund_id": "re_1234567890",
                "amount": 1200.00,
                "status": "succeeded",
                "reason": "customer_request",
            }
        }
