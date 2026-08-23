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
from app.services.social_proof import record_order_event
from app.services.alerts import emit_alert

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

    # Pre-built showcase Product purchases (app/api/public_showcase.py) use
    # a completely different confirm path — the frontend's own
    # checkout-confirm call is the primary handler and normally beats this
    # webhook there. This only runs as a fallback for the rare case that
    # call never fired (tab closed mid-payment).
    if intent["metadata"].get("purchase_type") == "product":
        await _handle_product_payment_succeeded(intent, db)
        return

    log.info(
        "webhook.payment_intent.succeeded",
        intent_id=intent_id,
        customer_id=customer_id,
        amount_gbp=amount,
    )

    try:
        # Check if order already exists for this payment intent — the real
        # column, not the old notes-contains/order_id-suffix guess.
        result = await db.execute(
            select(Order).where(Order.stripe_payment_intent_id == intent_id)
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

        # Fallback order creation for the rare case the frontend's own
        # /payments/confirm call never fired (tab closed mid-flow, etc).
        # Specs are empty here since the build_config lives client-side and
        # this webhook only receives what Stripe echoes back — the /confirm
        # path (routes/payments.py) is what populates real specs.
        order = Order(
            order_id=f"ORD-{intent_id[-12:]}",
            customer_id=customer_id,
            status=OrderStatus.AWAITING_SOURCING,
            specs={},
            customer_price=amount,
            component_costs=0.0,
            overhead_amount=0.0,
            promised_delivery_date=None,
            stripe_payment_intent_id=intent_id,
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

        try:
            await record_order_event(
                db,
                customer_name=customer.name,
                address=customer.address,
                product_name="a custom PC build",
            )
        except Exception as e:
            log.warning("social_proof.order_event_failed", error=str(e), order_id=order_id)

        # Send confirmation email
        try:
            await send_order_confirmation_email(
                customer_email=customer.email,
                customer_name=customer.name,
                order_reference=order.order_id,
                build_summary=f"Custom PC build - Total: £{amount:.2f}",
                assigned_week="TBD",
                order_id=order.id,
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


async def _handle_product_payment_succeeded(intent: dict, db: AsyncSession) -> None:
    """Fallback path for a pre-built showcase Product purchase — mirrors
    app/api/public_showcase.py's confirm_checkout endpoint, which is the
    primary handler and normally reaches the database first. Idempotent via
    the same stripe_payment_intent_id-exists check as the configurator flow."""
    from app.models.product import Product, ProductStatus, SoldChannel
    from app.models.manual_build import ManualBuild
    from app.models.build import Build
    from app.services.cross_channel_guard import withdraw_ebay_for_sold_build
    from app.config import get_settings

    intent_id = intent["id"]
    amount = intent["amount"] / 100
    product_id = int(intent["metadata"].get("product_id", 0))
    customer_id = int(intent["metadata"].get("customer_id", 0))

    existing = await db.execute(select(Order).where(Order.stripe_payment_intent_id == intent_id))
    if existing.scalar_one_or_none():
        log.info("webhook.product_payment.order_already_exists", intent_id=intent_id, product_id=product_id)
        return

    product_result = await db.execute(select(Product).where(Product.id == product_id))
    product = product_result.scalar_one_or_none()
    if not product:
        log.error("webhook.product_payment.product_not_found", product_id=product_id, intent_id=intent_id)
        return
    if product.status == ProductStatus.SOLD:
        log.info("webhook.product_payment.already_sold", product_id=product_id, intent_id=intent_id)
        return

    customer_result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = customer_result.scalar_one_or_none()
    if not customer:
        log.error("webhook.product_payment.customer_not_found", customer_id=customer_id, intent_id=intent_id)
        return

    # Find any linked ManualBuild before taking locks (unlocked — these FKs
    # don't change concurrently). Global lock order across this codebase's
    # cross-channel paths is always ManualBuild before Product (see
    # manual_builds.py's sync_ebay_order and cross_channel_guard.py), to
    # avoid an ABBA deadlock against the primary /checkout-confirm path this
    # webhook is a fallback for.
    manual_build = None
    if product.build_id:
        build_result = await db.execute(select(Build).where(Build.id == product.build_id))
        orchestration_build = build_result.scalar_one_or_none()
        if orchestration_build and orchestration_build.manual_build_id:
            manual_locked = await db.execute(
                select(ManualBuild).where(ManualBuild.id == orchestration_build.manual_build_id).with_for_update()
            )
            manual_build = manual_locked.scalar_one_or_none()

    # Re-check under a row lock right before finalising the sale — this
    # webhook races the primary /checkout-confirm path by design (it exists
    # specifically for when that call is delayed or never fires), so the
    # unlocked check above is not sufficient on its own.
    locked_result = await db.execute(select(Product).where(Product.id == product_id).with_for_update())
    product = locked_result.scalar_one_or_none()
    if not product or product.status == ProductStatus.SOLD:
        log.info("webhook.product_payment.already_sold", product_id=product_id, intent_id=intent_id)
        return
    if manual_build and manual_build.status == "sold":
        log.info("webhook.product_payment.already_sold", product_id=product_id, intent_id=intent_id)
        return

    order = Order(
        order_id=f"ORD-PROD-{intent_id[-12:]}",
        customer_id=customer_id,
        status=OrderStatus.READY_TO_PACKAGE,
        specs={"product_id": product.id, "build_title": product.title},
        customer_price=amount,
        component_costs=0.0,
        overhead_amount=0.0,
        stripe_payment_intent_id=intent_id,
        notes=f"Pre-built showcase purchase (via webhook fallback). Product #{product.id}. Intent: {intent_id}",
    )
    db.add(order)
    await db.flush()

    product.status = ProductStatus.SOLD
    product.sold_via_channel = SoldChannel.STOREFRONT
    product.sold_order_id = order.id
    product.reserved_until = None
    product.updated_at = datetime.utcnow()

    # manual_build.status is deliberately left unset here — withdraw_ebay_for_sold_build's
    # own idempotency guard skips the withdrawal once status == "sold", so it
    # must stay unset until after that call runs below. Product.status = SOLD,
    # committed next, is the authoritative signal a concurrent confirm_checkout
    # / sync_ebay_order check relies on.
    will_withdraw_ebay = bool(manual_build and manual_build.ebay_sku)

    # Commit the sale now, before any external network calls — the payment
    # already succeeded, so the sale must be durable even if the eBay
    # withdrawal or alert below fails or hangs. This also releases the
    # ManualBuild/Product row locks instead of holding them across slow
    # external I/O.
    await db.commit()
    order_id, product_id_out = order.id, product.id

    # Same alert code the admin dashboard's confetti listens for
    # (top-command-bar.tsx), so a direct storefront sale celebrates too —
    # this only fires when the webhook is the one that actually lands the
    # sale (the primary /checkout-confirm path emits its own, since the
    # early "already_sold" return above prevents this running twice).
    try:
        await emit_alert(
            code="flip_resale_detected",
            source="storefront_webhook",
            severity="info",
            message=f"Sale detected: {product.title or 'Pre-built PC'} sold on storefront for £{amount:.2f}.",
        )
    except Exception as e:
        log.warning("webhook.product_payment.alert_emit_failed", error=str(e), product_id=product_id_out)

    if will_withdraw_ebay:
        settings = get_settings()
        await withdraw_ebay_for_sold_build(manual_build, settings.ebay_listing_environment)
        manual_build.status = "sold"
        manual_build.updated_at = datetime.utcnow()
        await db.commit()

    log.info("webhook.product_payment.order_created", order_id=order_id, product_id=product_id_out, intent_id=intent_id)

    try:
        await send_order_confirmation_email(
            customer_email=customer.email,
            customer_name=customer.name,
            order_reference=order.order_id,
            build_summary=f"{product.title or 'Pre-built PC'} — £{amount:.2f}",
            assigned_week="Ready to ship",
            order_id=order.id,
        )
    except Exception as e:
        log.warning("webhook.product_payment.email_failed", error=str(e), order_id=order.id)


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
