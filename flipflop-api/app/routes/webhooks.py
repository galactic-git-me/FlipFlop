"""Webhook handlers for external services (Stripe, etc.)."""

import structlog
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.order import Order, OrderStatus
from app.models.customer import Customer
from app.models.playbook import Playbook
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.models.order_checkout_snapshot import OrderCheckoutSnapshot
from app.models.ai_setup_purchase import AISetupPurchase
from app.models.getting_started_job import GettingStartedJob
from app.models.customer_problem import CustomerProblem
from app.models.customer_problem_shipment import CustomerProblemShipment
from app.models.manual_build import ManualBuild
from app.models.build import Build
from app.models.product import Product
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.models.warranty import WarrantyClaim, WarrantyReserve
from app.services.payment_service import PaymentService
from app.services.email_service import send_order_confirmation_email
from app.services.parcel2go_notifications import deliver_parcel2go_tracking_notification
from app.services.social_proof import record_order_event
from app.services.alerts import emit_alert
from app.config import get_settings
from app.services.warranty_service import (
    ensure_order_reserve,
    ensure_manual_build_reserve,
    lock_warranty_reserve_then_claim,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _notify_parcel2go_tracking_event(db: AsyncSession, event: ShipmentTrackingEvent) -> bool:
    """Deliver or persist a retry for this already-committed provider event."""
    if not event.material or event.customer_notified_at:
        return True
    result = await deliver_parcel2go_tracking_notification(event.id)
    return result["status"] in {"sent", "not_pending", "not_customer_visible", "channel_suppressed", "exhausted", "failed"}


@router.post("/parcel2go", status_code=200)
async def parcel2go_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate and persist Parcel2Go courier events without external writes."""
    settings = get_settings()
    secret = settings.parcel2go_webhook_secret
    if not secret:
        raise HTTPException(503, "Parcel2Go webhook secret is not configured")

    raw_body = await request.body()
    if len(raw_body) > 64 * 1024:
        raise HTTPException(413, "Webhook payload is too large")
    try:
        envelope = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid JSON webhook payload")
    if not isinstance(envelope, dict):
        raise HTTPException(400, "Invalid webhook envelope")

    event_id = str(envelope.get("Id") or "").strip()
    timestamp_text = str(envelope.get("Timestamp") or "").strip()
    signature = str(envelope.get("Signature") or "").strip()
    event_type = str(envelope.get("Type") or "").strip()
    payload = envelope.get("Payload")
    if not event_id or len(event_id) > 200 or not timestamp_text or not signature or not event_type:
        raise HTTPException(400, "Webhook envelope is missing required fields")
    try:
        timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "Invalid webhook timestamp")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    # Parcel2Go signs Id:Timestamp(yyyy-MM-dd HH:mm:ss):Type with HMAC-SHA256.
    canonical_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    signed = f"{event_id}:{canonical_timestamp}:{event_type}".encode("utf-8")
    expected_signature = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    supplied_signature = signature.lower()
    if not hmac.compare_digest(expected_signature, supplied_signature):
        raise HTTPException(401, "Invalid webhook signature")

    existing = (await db.execute(select(ShipmentTrackingEvent).where(
        ShipmentTrackingEvent.provider == "parcel2go",
        ShipmentTrackingEvent.provider_event_id == event_id,
    ))).scalar_one_or_none()
    if existing:
        if not await _notify_parcel2go_tracking_event(db, existing):
            raise HTTPException(503, "Tracking event was saved; customer notification will be retried")
        return {"status": "duplicate", "event_id": existing.id}
    now = datetime.now(timezone.utc)
    if abs((now - timestamp.astimezone(timezone.utc)).total_seconds()) > 600:
        raise HTTPException(400, "Webhook timestamp is outside the accepted window")
    if event_type.lower() != "tracking":
        return {"status": "ignored", "reason": "unsupported_event_type"}
    if not isinstance(payload, dict):
        raise HTTPException(400, "Tracking event payload is invalid")

    provider_order_id = str(payload.get("OrderLineId") or "").strip()
    if not provider_order_id:
        raise HTTPException(400, "Tracking event has no OrderLineId")
    build = (await db.execute(select(ManualBuild).where(
        ManualBuild.parcel2go_order_line_id == provider_order_id
    ).with_for_update())).scalar_one_or_none()
    repair_shipment = (await db.execute(select(CustomerProblemShipment).where(
        CustomerProblemShipment.provider == "parcel2go",
        CustomerProblemShipment.provider_reference == provider_order_id,
    ))).scalar_one_or_none()
    repair_case = await db.get(CustomerProblem, repair_shipment.customer_problem_id) if repair_shipment else None
    if build and repair_shipment:
        raise HTTPException(409, "This Parcel2Go line is linked to more than one shipment type; reconcile the duplicate reference")
    if not build and not repair_shipment:
        # Ask Parcel2Go to retry briefly if booking persistence and webhook delivery race.
        raise HTTPException(404, "No FlipFlop shipment matches this Parcel2Go order line")

    stage = str(payload.get("TrackingStage") or payload.get("StatusCode") or "unknown").strip()
    status_code = "_".join(stage.lower().replace("-", " ").split())[:80] or "unknown"
    description = str(payload.get("StatusDescription") or stage or "Courier tracking update").strip()[:2000]
    occurred_at_text = str(payload.get("Timestamp") or timestamp_text)
    try:
        parsed_occurred_at = datetime.fromisoformat(occurred_at_text.replace("Z", "+00:00"))
        if parsed_occurred_at.tzinfo is None:
            parsed_occurred_at = parsed_occurred_at.replace(tzinfo=timezone.utc)
        parsed_occurred_at = parsed_occurred_at.astimezone(timezone.utc)
        if parsed_occurred_at > now:
            log.warning(
                "parcel2go.future_tracking_stage_timestamp",
                provider_event_id=event_id,
                stage_timestamp=parsed_occurred_at.isoformat(),
            )
            occurred_at = now.replace(tzinfo=None)
        else:
            occurred_at = parsed_occurred_at.replace(tzinfo=None)
    except ValueError:
        log.warning("parcel2go.invalid_tracking_stage_timestamp", provider_event_id=event_id)
        occurred_at = now.replace(tzinfo=None)

    # Where a sold Ready-to-Ship item has an order, keep events on the order
    # timeline; marketplace/guest sales without an order remain build-scoped.
    linked_order = None
    if build:
        linked_order = (await db.execute(
            select(Order)
            .join(Build, Build.order_id == Order.id)
            .where(Build.manual_build_id == build.id)
            .limit(1)
        )).scalar_one_or_none()
        if not linked_order:
            linked_order = (await db.execute(
                select(Order)
                .join(Product, Product.sold_order_id == Order.id)
                .join(Build, Product.build_id == Build.id)
                .where(Build.manual_build_id == build.id)
                .limit(1)
            )).scalar_one_or_none()

    delivered = status_code in {"delivered", "delivery_confirmed", "proof_of_delivery"}
    locked_repair_claim = None
    locked_repair_reserve = None
    if repair_shipment:
        # Keep the same lock order as admin claim/status updates and reserve
        # release: reserve -> claim -> case -> shipment. Locking the shipment
        # first here could deadlock against an admin saving tracking while a
        # return-delivered webhook tried to hold the reserve.
        claim_reference = (await db.execute(
            select(WarrantyClaim).where(
                WarrantyClaim.customer_problem_id == repair_shipment.customer_problem_id
            )
        )).scalar_one_or_none()
        if claim_reference:
            locked_repair_reserve, locked_repair_claim = await lock_warranty_reserve_then_claim(
                db, claim_reference.id
            )
        repair_case = (await db.execute(
            select(CustomerProblem)
            .where(CustomerProblem.id == repair_shipment.customer_problem_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
        repair_shipment = (await db.execute(
            select(CustomerProblemShipment)
            .where(CustomerProblemShipment.id == repair_shipment.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
        if repair_case is None or repair_shipment is None:
            raise HTTPException(409, "The repair shipment or linked customer case changed during tracking update")

    event = ShipmentTrackingEvent(
        order_id=linked_order.id if linked_order else None,
        manual_build_id=None if linked_order else build.id if build else None,
        customer_problem_shipment_id=repair_shipment.id if repair_shipment else None,
        provider="parcel2go",
        provider_event_id=event_id,
        status_code=status_code,
        description=description,
        tracking_url=(
            repair_shipment.tracking_url
            if repair_shipment
            else ((build.evidence_data or {}).get("shipment_booking_confirmation") or {}).get("tracking_url")
        ),
        # The portal timeline records each provider stage; notify for each
        # distinct courier event as requested by the customer lifecycle.
        material=True,
        occurred_at=occurred_at,
    )
    db.add(event)

    if repair_case and repair_shipment:
        current_tracking = dict(repair_case.repair_tracking or {})
        current_tracking.update({
            "latest_status_code": status_code,
            "latest_status_description": description,
            "latest_location": str(payload.get("Location") or "").strip()[:300] or None,
            "latest_occurred_at": occurred_at.isoformat(),
        })
        repair_case.repair_tracking = current_tracking
        repair_case.updated_at = datetime.utcnow()
        if delivered and repair_shipment.purpose == "customer_return" and repair_case.status == "return_in_transit":
            repair_case.status = "received_for_inspection"
            if locked_repair_claim:
                locked_repair_claim.status = "received_for_inspection"
                locked_repair_claim.resolved_at = None
                if locked_repair_reserve:
                    from app.services.warranty_service import recalculate_reserve_status
                    await recalculate_reserve_status(db, locked_repair_reserve)
    if delivered and build:
        build.delivered_at = min(value for value in (build.delivered_at, occurred_at) if value is not None)
        build.warranty_started_at = min(
            value for value in (build.warranty_started_at, build.delivered_at) if value is not None
        )
        build.dispatch_status = "delivered"
        if linked_order:
            linked_order.delivered_at = min(
                value for value in (linked_order.delivered_at, occurred_at) if value is not None
            )
            linked_order.actual_delivery_date = min(
                value for value in (linked_order.actual_delivery_date, linked_order.delivered_at) if value is not None
            )
            linked_order.status = OrderStatus.COMPLETED
            reserve = await ensure_order_reserve(db, linked_order, linked_order.delivered_at)
            from app.services.warranty_service import recalculate_reserve_status
            await recalculate_reserve_status(db, reserve)
        else:
            reserve = await ensure_manual_build_reserve(db, build, build.warranty_started_at)
            from app.services.warranty_service import recalculate_reserve_status
            if reserve is not None:
                await recalculate_reserve_status(db, reserve)

    await db.flush()
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        duplicate = (await db.execute(select(ShipmentTrackingEvent).where(
            ShipmentTrackingEvent.provider == "parcel2go",
            ShipmentTrackingEvent.provider_event_id == event_id,
        ))).scalar_one_or_none()
        if duplicate:
            if not await _notify_parcel2go_tracking_event(db, duplicate):
                raise HTTPException(503, "Tracking event was saved; customer notification will be retried")
            return {"status": "duplicate", "event_id": duplicate.id}
        raise

    if not await _notify_parcel2go_tracking_event(db, event):
        raise HTTPException(503, "Tracking event was saved; customer notification will be retried")
    return {"status": "processed", "event_id": event.id}


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
    if intent["metadata"].get("purchase_type") == "ai_setup_service":
        await _handle_ai_setup_payment_succeeded(intent, db)
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
        fulfilment_type = str(intent["metadata"].get("fulfilment_type") or "custom").lower().replace("-", "_").replace(" ", "_")
        budget_tier = str(intent["metadata"].get("budget_tier") or "").strip() or None
        playbook_id_text = str(intent["metadata"].get("playbook_id") or "")
        playbook_id = int(playbook_id_text) if playbook_id_text.isdigit() else None
        specs = {"fulfilment_type": fulfilment_type, "recovery_source": "stripe_webhook_metadata"}
        if budget_tier:
            specs["budget_tier"] = budget_tier
        curated_build_id = str(intent["metadata"].get("curated_build_id") or "").strip()
        if curated_build_id:
            specs["curated_build_id"] = curated_build_id
        encoded_selections = str(intent["metadata"].get("slot_selections") or "")
        selections: dict[int, int] = {}
        try:
            for pair in encoded_selections.split(","):
                if pair:
                    slot_id, variant_id = pair.split(":", 1)
                    selections[int(slot_id)] = int(variant_id)
        except (ValueError, TypeError):
            selections = {}
        if playbook_id and selections:
            rows = (await db.execute(
                select(PlaybookSlot, CatalogueVariant, Listing)
                .join(CatalogueVariant, CatalogueVariant.slot_id == PlaybookSlot.id)
                .join(Listing, Listing.id == CatalogueVariant.listing_id)
                .where(
                    PlaybookSlot.playbook_id == playbook_id,
                    PlaybookSlot.id.in_(selections.keys()),
                    CatalogueVariant.id.in_(selections.values()),
                    CatalogueVariant.status == "active",
                )
            )).all()
            slots = [
                {"slot_id": slot.id, "slot_type": slot.slot_type, "variant_id": variant.id,
                 "title": listing.title, "price": variant.display_price}
                for slot, variant, listing in rows
                if selections.get(slot.id) == variant.id
            ]
            if len(slots) == len(selections):
                specs["slots"] = slots
                case_id_text = str(intent["metadata"].get("case_id") or "")
                case_id = int(case_id_text) if case_id_text.isdigit() else None
                specs["case_id"] = case_id
                if case_id is not None:
                    specs["case_name"] = (await db.execute(
                        select(CaseCatalogue.name).where(CaseCatalogue.id == case_id)
                    )).scalar_one_or_none()
                specs["chosen_week"] = str(intent["metadata"].get("chosen_week") or "") or None
        address_snapshot = (await db.execute(
            select(OrderCheckoutSnapshot).where(
                OrderCheckoutSnapshot.payment_intent_id == intent_id,
                OrderCheckoutSnapshot.customer_id == customer_id,
            ).with_for_update()
        )).scalar_one_or_none()
        if address_snapshot and address_snapshot.build_snapshot:
            # The payment-intent path saved the server-priced configuration.
            # Prefer it over live catalogue/admin state during webhook recovery.
            specs.update(address_snapshot.build_snapshot)
        if address_snapshot:
            specs["delivery_address"] = address_snapshot.delivery_address
            specs["billing_address"] = address_snapshot.billing_address
        software_profile = specs.get("software_profile")
        if playbook_id and not software_profile:
            playbook = await db.get(Playbook, playbook_id)
            if playbook:
                try:
                    if curated_build_id:
                        from app.services.product_software import software_profile_for_curated_cell_from_db
                        software_profile = await software_profile_for_curated_cell_from_db(
                            db, curated_build_id, playbook.name, playbook.software_profile
                        )
                    else:
                        from app.services.product_software import software_profile_for_playbook_cell_from_db
                        if budget_tier and fulfilment_type not in {"curated", "curated_for_you"}:
                            software_profile = await software_profile_for_playbook_cell_from_db(
                                db, playbook.name, budget_tier, playbook.software_profile
                            )
                        else:
                            from app.services.software_catalogue import effective_software_profile_for_playbook
                            software_profile = effective_software_profile_for_playbook(playbook.name, playbook.software_profile)
                except ValueError as exc:
                    log.warning("webhook.software_profile_unavailable", intent_id=intent_id, error=str(exc))
        from app.services.software_catalogue import customer_software_selection_from_metadata
        try:
            software_package_ids = customer_software_selection_from_metadata(
                intent["metadata"],
                software_profile.get("recommended_package_ids", []) if software_profile else [],
            )
        except ValueError as exc:
            log.warning("webhook.software_selection_invalid", intent_id=intent_id, error=str(exc))
            software_package_ids = []
        order = Order(
            order_id=f"ORD-{intent_id[-12:]}",
            customer_id=customer_id,
            status=OrderStatus.AWAITING_SOURCING,
            specs={
                **specs,
                **({"software_profile": software_profile} if software_profile else {}),
                "software_package_ids": software_package_ids,
            },
            customer_price=amount,
            component_costs=float(specs.get("parts_total") or 0),
            overhead_amount=float(specs.get("overhead") or 0),
            promised_delivery_date=None,
            stripe_payment_intent_id=intent_id,
            notes=f"Payment processed via Stripe webhook. Intent: {intent_id}",
        )

        db.add(order)
        if address_snapshot is not None:
            await db.delete(address_snapshot)
        await db.flush()
        order_id = order.id

        from app.services.getting_started_jobs import ensure_order_job, normalize_source_type
        await ensure_order_job(
            db,
            order_id=order.id,
            customer_id=customer_id,
            playbook_id=playbook_id,
            source_type=normalize_source_type(fulfilment_type),
        )

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


async def _handle_ai_setup_payment_succeeded(intent: dict, db: AsyncSession) -> None:
    """Idempotently attach a server-priced, succeeded AI add-on to its job."""
    intent_id = str(intent.get("id") or "")
    purchase = (await db.execute(
        select(AISetupPurchase).where(
            AISetupPurchase.stripe_payment_intent_id == intent_id
        ).with_for_update()
    )).scalar_one_or_none()
    if not purchase:
        # Return a webhook error so Stripe retries if delivery beats the API
        # transaction that persists the purchase row.
        raise RuntimeError(f"AI setup purchase record not found for payment intent {intent_id}")
    metadata = intent.get("metadata") or {}
    if (
        str(metadata.get("purchase_type")) != "ai_setup_service"
        or str(metadata.get("customer_id")) != str(purchase.customer_id)
        or str(metadata.get("order_id")) != str(purchase.order_id)
        or str(metadata.get("offer_id")) != purchase.offer_id
        or str(metadata.get("offer_price_pence")) != str(round(purchase.amount_gbp * 100))
        or int(intent.get("amount") or 0) != round(purchase.amount_gbp * 100)
    ):
        raise RuntimeError(f"AI setup payment metadata or amount mismatch for {intent_id}")
    if purchase.status == "paid":
        return

    job = (await db.execute(
        select(GettingStartedJob).where(
            GettingStartedJob.order_id == purchase.order_id
        ).with_for_update()
    )).scalar_one_or_none()
    if not job:
        raise RuntimeError(f"Getting Ready job missing for paid AI setup order {purchase.order_id}")
    now = datetime.utcnow()
    service = {
        **purchase.offer_snapshot,
        "purchase_id": purchase.id,
        "payment_status": "paid",
        "purchased_at": now.isoformat(),
    }
    services = list(job.purchased_ai_services or [])
    if not any(item.get("purchase_id") == purchase.id for item in services if isinstance(item, dict)):
        services.append(service)
    job.purchased_ai_services = services
    job.manifest = None
    job.generated_at = None
    job.reviewed_at = None
    job.status = "awaiting_admin_review"
    job.checklist = {
        **(job.checklist or {}),
        "ai_services_complete": "not_ready",
        "content_manifest": "not_ready",
        "artifacts_generated": "not_ready",
        "artifacts_reviewed": "not_ready",
        "customer_package": "not_ready",
    }
    job.updated_at = now
    purchase.status = "paid"
    purchase.paid_at = now
    purchase.updated_at = now
    await db.commit()
    log.info(
        "webhook.ai_setup_purchase.paid",
        purchase_id=purchase.id,
        order_id=purchase.order_id,
        offer_id=purchase.offer_id,
        intent_id=intent_id,
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

    from app.services.product_software import software_profile_for_product
    from app.services.software_catalogue import SOFTWARE_CATALOGUE, customer_software_selection_from_metadata
    software_profile = await software_profile_for_product(db, product)
    try:
        software_package_ids = customer_software_selection_from_metadata(
            intent.get("metadata", {}),
            software_profile.get("recommended_package_ids", []),
        )
    except ValueError as exc:
        log.warning("webhook.product_payment.invalid_software_selection", product_id=product.id, error=str(exc))
        software_package_ids = list(software_profile.get("recommended_package_ids", []))

    assignment = ((manual_build.evidence_data or {}).get("playbook_assignment") or {}) if manual_build else {}
    playbook_id = assignment.get("playbook_id") or product.playbook_id
    order = Order(
        order_id=f"ORD-PROD-{intent_id[-12:]}",
        customer_id=customer_id,
        status=OrderStatus.READY_TO_PACKAGE,
        specs={
            "product_id": product.id, "build_title": product.title,
            "delivery_address": (product.checkout_addresses or {}).get("delivery"),
            "billing_address": (product.checkout_addresses or {}).get("billing"),
            "fulfilment_type": product.fulfilment_type or "prebuilt",
            "delivery_option": intent.get("metadata", {}).get("delivery_option", "standard"),
            "delivery_promise": intent.get("metadata", {}).get("delivery_promise"),
            "delivery_days": intent.get("metadata", {}).get("delivery_days"),
            "software_profile": software_profile,
            "software_package_ids": software_package_ids,
            "software_estimated_minutes_saved": sum(
                int(item["estimated_minutes_saved"]) for item in SOFTWARE_CATALOGUE
                if item["package_id"] in software_package_ids
            ),
            **({
                "curated_build_id": assignment.get("curated_build_id"),
                "playbook_cell": f"{assignment.get('customer_type')} / {assignment.get('budget_tier')}",
            } if assignment else {}),
        },
        customer_price=amount,
        component_costs=0.0,
        overhead_amount=0.0,
        stripe_payment_intent_id=intent_id,
        playbook_id=playbook_id,
        notes=f"Pre-built showcase purchase (via webhook fallback). Product #{product.id}. Intent: {intent_id}",
    )
    db.add(order)
    await db.flush()

    from app.services.getting_started_jobs import ensure_order_job
    await ensure_order_job(
        db,
        order_id=order.id,
        customer_id=customer_id,
        playbook_id=playbook_id,
        source_type="ready_to_ship",
        manual_build_id=manual_build.id if manual_build else None,
    )

    product.status = ProductStatus.SOLD
    product.sold_via_channel = SoldChannel.STOREFRONT
    product.sold_order_id = order.id
    product.reserved_until = None
    product.updated_at = datetime.utcnow()
    if manual_build:
        delivery_address = (product.checkout_addresses or {}).get("delivery") or {}
        manual_build.buyer_name = delivery_address.get("contact_name") or customer.name
        manual_build.buyer_address_json = dict(delivery_address)
        manual_build.customer_id = customer.id
        manual_build.customer_email = customer.email
        manual_build.sale_price_actual = amount

    # manual_build.status is deliberately left unset here — withdraw_ebay_for_sold_build's
    # own idempotency guard skips the withdrawal once status == "sold", so it
    # must stay unset until after that call runs below. Product.status = SOLD,
    # committed next, is the authoritative signal a concurrent confirm_checkout
    # / sync_ebay_order check relies on.
    will_withdraw_ebay = bool(manual_build and manual_build.ebay_sku)
    if manual_build and not will_withdraw_ebay:
        # A storefront-only build has no marketplace withdrawal to wait for,
        # but it still needs to appear in the sold-build dispatch queue.
        manual_build.status = "sold"
        from app.services.inventory_lifecycle import record_sale
        await record_sale(db, manual_build, amount)
        manual_build.updated_at = datetime.utcnow()

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
        manual_build.sale_price_actual = amount
        from app.services.inventory_lifecycle import record_sale
        await record_sale(db, manual_build, amount)
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
