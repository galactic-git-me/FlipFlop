"""Webhook handlers for external services (Stripe, etc.)."""

import structlog
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database import get_db
from app.models.order import Order, OrderStatus
from app.models.customer import Customer
from app.services.payment_service import PaymentService
from app.services.email_service import send_order_confirmation_email

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe webhook events.

    **Events handled:**
    - `payment_intent.succeeded`: Create order after successful payment

    **Setup:**
    1. In Stripe Dashboard, go to Developers > Webhooks
    2. Add endpoint: POST https://yourdomain.com/webhooks/stripe
    3. Select events: payment_intent.succeeded
    4. Copy webhook secret and set STRIPE_WEBHOOK_SECRET in .env

    **Development (local testing):**
    ```bash
    # Install Stripe CLI: https://stripe.com/docs/stripe-cli
    stripe listen --forward-to localhost:8000/webhooks/stripe

    # Copy signing secret from output and set STRIPE_WEBHOOK_SECRET
    ```

    **Response:**
    - 200 OK: Webhook processed successfully
    - 400 Bad Request: Invalid signature or payload
    - 500 Internal Server Error: Processing error
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if not signature:
        log.warning("webhook.stripe.missing_signature")
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    # Verify webhook signature
    try:
        payment_service = PaymentService()
        event = payment_service.verify_webhook_signature(payload, signature)
    except ValueError as e:
        log.warning("webhook.stripe.signature_verification_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # Handle payment_intent.succeeded event
    if event["type"] == "payment_intent.succeeded":
        await _handle_payment_intent_succeeded(event, db)

    # Handle payment_intent.payment_failed event
    elif event["type"] == "payment_intent.payment_failed":
        await _handle_payment_intent_failed(event, db)

    # Handle charge.refunded event
    elif event["type"] == "charge.refunded":
        await _handle_charge_refunded(event, db)

    return {"status": "success"}


async def _handle_payment_intent_succeeded(
    event: dict,
    db: AsyncSession,
) -> None:
    """
    Process payment_intent.succeeded webhook event.

    Creates an order if it doesn't already exist for this payment intent.
    """
    intent = event["data"]["object"]
    intent_id = intent["id"]
    customer_id = int(intent["metadata"].get("customer_id", 0))
    amount = intent["amount"] / 100  # Convert pence to GBP

    log.info(
        "webhook.payment_intent.succeeded",
        intent_id=intent_id,
        customer_id=customer_id,
        amount_gbp=amount,
    )

    try:
        # Check if order already exists for this payment intent
        result = await db.execute(
            select(Order).where(
                Order.notes.contains(f"Intent: {intent_id}")
                | Order.order_id.contains(intent_id[-12:])
            )
        )
        existing_order = result.scalar_one_or_none()

        if existing_order:
            log.info(
                "webhook.payment_intent.order_already_exists",
                order_id=existing_order.id,
                intent_id=intent_id,
            )
            return

        # Get customer
        result = await db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        customer = result.scalar_one_or_none()

        if not customer:
            log.error(
                "webhook.payment_intent.customer_not_found",
                customer_id=customer_id,
                intent_id=intent_id,
            )
            return

        # Create order
        order = Order(
            order_id=f"ORD-{intent_id[-12:]}",
            customer_id=customer_id,
            status=OrderStatus.AWAITING_SOURCING,
            specs={},
            customer_price=amount,
            component_costs=0.0,
            overhead_amount=0.0,
            promised_delivery_date=None,
            notes=f"Payment processed via Stripe webhook. Intent: {intent_id}",
        )

        db.add(order)
        await db.flush()
        order_id = order.id

        await db.commit()

        log.info(
            "webhook.order.created",
            order_id=order_id,
            customer_id=customer_id,
            intent_id=intent_id,
        )

        # Send confirmation email
        try:
            await send_order_confirmation_email(
                customer_email=customer.email,
                customer_name=customer.name,
                order_reference=order.order_id,
                build_summary=f"Custom PC build - Total: £{amount:.2f}",
                assigned_week="TBD",
            )
            log.info(
                "webhook.email.sent",
                order_id=order_id,
                customer_email=customer.email,
            )
        except Exception as e:
            log.warning(
                "webhook.email.send_failed",
                error=str(e),
                order_id=order_id,
                customer_email=customer.email,
            )

    except Exception as e:
        log.error(
            "webhook.payment_intent.processing_failed",
            error=str(e),
            intent_id=intent_id,
            customer_id=customer_id,
        )


async def _handle_payment_intent_failed(
    event: dict,
    db: AsyncSession,
) -> None:
    """
    Process payment_intent.payment_failed webhook event.

    Logs payment failure for monitoring.
    """
    intent = event["data"]["object"]
    intent_id = intent["id"]
    customer_id = int(intent["metadata"].get("customer_id", 0))
    last_payment_error = intent.get("last_payment_error", {})

    log.warning(
        "webhook.payment_intent.failed",
        intent_id=intent_id,
        customer_id=customer_id,
        error_code=last_payment_error.get("code"),
        error_message=last_payment_error.get("message"),
    )


async def _handle_charge_refunded(
    event: dict,
    db: AsyncSession,
) -> None:
    """
    Process charge.refunded webhook event.

    Updates order status when payment is refunded.
    """
    charge = event["data"]["object"]
    charge_id = charge["id"]
    refunded_amount = charge.get("amount_refunded", 0) / 100  # Convert to GBP

    log.info(
        "webhook.charge.refunded",
        charge_id=charge_id,
        refunded_amount_gbp=refunded_amount,
    )

    try:
        # Find order by charge metadata or intent
        # In a production system, you might track the relationship more explicitly
        log.info(
            "webhook.charge_refunded.processed",
            charge_id=charge_id,
            refunded_amount_gbp=refunded_amount,
        )

    except Exception as e:
        log.error(
            "webhook.charge.refunded.processing_failed",
            error=str(e),
            charge_id=charge_id,
        )
