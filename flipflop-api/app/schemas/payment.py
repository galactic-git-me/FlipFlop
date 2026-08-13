"""Pydantic schemas for payment requests and responses."""

from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


class PlaybookBuildConfig(BaseModel):
    """A priced-from-real-catalogue playbook build (the /configure/[slug] flow).

    `slot_selections` maps playbook_slot.id -> catalogue_variants.id — the
    backend re-validates and re-prices every one of these against the real
    catalogue; nothing about the charge amount is trusted from the client.
    """

    playbook_id: int = Field(..., gt=0)
    slot_selections: dict[int, int] = Field(default_factory=dict)
    case_id: Optional[int] = None
    chosen_week: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "playbook_id": 1,
                "slot_selections": {"1": 4, "2": 8, "3": 12},
                "case_id": 3,
                "chosen_week": "2026-W30",
            }
        }


class CreatePaymentIntentRequest(BaseModel):
    """Request to create a Stripe payment intent.

    Exactly one of `budget` (legacy flat quote) or `build_config` (real
    playbook catalogue pricing) must be supplied. When `build_config` is
    present the amount is always computed server-side from the catalogue —
    `budget` is ignored in that case rather than trusted from the client.
    """

    budget: Optional[float] = Field(None, gt=0, description="Total quote price in GBP")
    customer_id: int = Field(..., gt=0, description="Customer ID")
    build_config: Optional[PlaybookBuildConfig] = None

    @model_validator(mode="after")
    def _require_budget_or_build_config(self) -> "CreatePaymentIntentRequest":
        if self.budget is None and self.build_config is None:
            raise ValueError("Either budget or build_config must be provided")
        return self

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
    build_config: Optional[PlaybookBuildConfig] = None

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
