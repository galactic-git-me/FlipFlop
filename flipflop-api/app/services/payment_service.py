"""Stripe payment processing service for quote-to-order conversion."""

import stripe
import structlog
from typing import Optional
from datetime import datetime

from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


class StripeConfig:
    """Stripe configuration wrapper."""

    def __init__(self):
        self.api_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret
        self.publishable_key = settings.stripe_publishable_key
        stripe.api_key = self.api_key


class PaymentService:
    """Handles Stripe payment intent creation and webhook processing."""

    def __init__(self):
        self.config = StripeConfig()

    async def create_payment_intent(
        self,
        customer_id: int,
        budget: float,
        quote_data: dict,
    ) -> dict:
        """
        Create a Stripe payment intent for a quote.

        Args:
            customer_id: Customer ID from database
            budget: Quote total price in GBP
            quote_data: Quote details (specs, components, etc.)

        Returns:
            Dict with client_secret, publishable_key, amount, currency

        Raises:
            ValueError: If Stripe API fails or config is missing
        """
        if not self.config.api_key:
            raise ValueError("STRIPE_SECRET_KEY not configured")

        try:
            # Convert GBP to pence (Stripe expects smallest currency unit)
            amount_pence = int(budget * 100)

            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=amount_pence,
                currency="gbp",
                metadata={
                    "customer_id": str(customer_id),
                    "budget": str(budget),
                },
                description=f"Custom PC Build Quote - £{budget}",
            )

            log.info(
                "payment_intent.created",
                intent_id=intent.id,
                customer_id=customer_id,
                amount_gbp=budget,
            )

            return {
                "client_secret": intent.client_secret,
                "publishable_key": self.config.publishable_key,
                "amount": budget,
                "currency": "gbp",
                "intent_id": intent.id,
            }

        except stripe.error.StripeError as e:
            log.error(
                "payment_intent.creation_failed",
                error=str(e),
                customer_id=customer_id,
                amount_gbp=budget,
            )
            raise ValueError(f"Failed to create payment intent: {str(e)}")

    async def handle_payment_success(
        self,
        intent_id: str,
        customer_id: int,
        quote_data: dict,
    ) -> dict:
        """
        Handle successful payment and extract payment details.

        Args:
            intent_id: Stripe PaymentIntent ID
            customer_id: Customer ID from database
            quote_data: Quote details for the order

        Returns:
            Dict with payment details (amount, currency, status)

        Raises:
            ValueError: If intent not found or payment not succeeded
        """
        try:
            intent = stripe.PaymentIntent.retrieve(intent_id)

            if intent.status != "succeeded":
                raise ValueError(f"Payment not succeeded. Status: {intent.status}")

            log.info(
                "payment_intent.succeeded",
                intent_id=intent_id,
                customer_id=customer_id,
                amount_gbp=intent.amount / 100,
            )

            return {
                "intent_id": intent_id,
                "amount": intent.amount / 100,  # Convert pence back to GBP
                "currency": intent.currency,
                "status": "completed",
                "created_at": datetime.utcfromtimestamp(intent.created),
                "charge_id": intent.latest_charge,
            }

        except stripe.error.StripeError as e:
            log.error(
                "payment_intent.retrieval_failed",
                error=str(e),
                intent_id=intent_id,
                customer_id=customer_id,
            )
            raise ValueError(f"Failed to retrieve payment intent: {str(e)}")

    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict:
        """
        Verify Stripe webhook signature and return event.

        Args:
            payload: Raw webhook request body
            signature: Stripe signature from X-Stripe-Signature header

        Returns:
            Parsed webhook event

        Raises:
            ValueError: If signature is invalid
        """
        if not self.config.webhook_secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.config.webhook_secret,
            )
            log.info(
                "webhook.verified",
                event_type=event["type"],
                event_id=event["id"],
            )
            return event

        except ValueError as e:
            log.error("webhook.invalid_payload", error=str(e))
            raise ValueError(f"Invalid webhook payload: {str(e)}")
        except stripe.error.SignatureVerificationError as e:
            log.error("webhook.signature_verification_failed", error=str(e))
            raise ValueError(f"Invalid signature: {str(e)}")

    async def refund_payment(
        self,
        intent_id: str,
        reason: str = "customer_request",
    ) -> dict:
        """
        Refund a successful payment.

        Args:
            intent_id: Stripe PaymentIntent ID
            reason: Refund reason

        Returns:
            Dict with refund details

        Raises:
            ValueError: If refund fails
        """
        try:
            intent = stripe.PaymentIntent.retrieve(intent_id)

            if not intent.latest_charge:
                raise ValueError("No charge found to refund")

            refund = stripe.Refund.create(
                charge=intent.latest_charge,
                reason=reason,
            )

            log.info(
                "payment.refunded",
                refund_id=refund.id,
                intent_id=intent_id,
                amount_gbp=refund.amount / 100,
            )

            return {
                "refund_id": refund.id,
                "amount": refund.amount / 100,
                "status": refund.status,
                "reason": reason,
            }

        except stripe.error.StripeError as e:
            log.error(
                "payment.refund_failed",
                error=str(e),
                intent_id=intent_id,
            )
            raise ValueError(f"Failed to refund payment: {str(e)}")

    async def get_payment_intent(self, intent_id: str) -> dict:
        """
        Retrieve payment intent details.

        Args:
            intent_id: Stripe PaymentIntent ID

        Returns:
            Dict with payment intent details

        Raises:
            ValueError: If intent not found
        """
        try:
            intent = stripe.PaymentIntent.retrieve(intent_id)

            return {
                "intent_id": intent.id,
                "status": intent.status,
                "amount": intent.amount / 100,
                "currency": intent.currency,
                "created_at": datetime.utcfromtimestamp(intent.created),
            }

        except stripe.error.StripeError as e:
            log.error("payment_intent.retrieval_failed", error=str(e))
            raise ValueError(f"Failed to retrieve payment intent: {str(e)}")
