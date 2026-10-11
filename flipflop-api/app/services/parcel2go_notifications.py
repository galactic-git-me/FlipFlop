"""Durable direct-customer email delivery for persisted courier tracking events."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from sqlalchemy import and_, or_, select

from app.database import AsyncSessionLocal
from app.models.customer import Customer
from app.models.customer_problem import CustomerProblem
from app.models.customer_problem_shipment import CustomerProblemShipment
from app.models.build import Build
from app.models.manual_build import ManualBuild
from app.models.order import Order
from app.models.product import Product
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.services.alerts import emit_alert
from app.services.email_service import send_customer_case_status_email, send_courier_event_email


log = logging.getLogger(__name__)
_MAX_ATTEMPTS = 8
_MAX_BATCH = 50
_DELIVERED_CODES = {"delivered", "delivery_confirmed", "proof_of_delivery"}


def _retry_delay(attempts: int) -> timedelta:
    return timedelta(minutes=min(360, 2 ** max(1, attempts)))


async def order_is_direct_storefront(db, order_id: int) -> bool:
    """Suppress customer mail when linked build/product evidence identifies an indirect sale."""
    builds = (await db.execute(
        select(ManualBuild)
        .join(Build, Build.manual_build_id == ManualBuild.id)
        .outerjoin(Product, Product.build_id == Build.id)
        .where(or_(Build.order_id == order_id, Product.sold_order_id == order_id))
        .distinct()
    )).scalars().all()
    if builds:
        if len(builds) != 1 or builds[0].ebay_order_id:
            return False
        if builds[0].storefront_product_id:
            product = await db.get(Product, builds[0].storefront_product_id)
            if product is None:
                return False
            channel = getattr(product.sold_via_channel, "value", product.sold_via_channel)
            if channel is not None and channel != "storefront":
                return False

    sold_channels = (await db.execute(
        select(Product.sold_via_channel).where(Product.sold_order_id == order_id)
    )).scalars().all()
    explicit_channels = {
        getattr(channel, "value", channel) for channel in sold_channels if channel is not None
    }
    return not explicit_channels or explicit_channels == {"storefront"}


async def deliver_tracking_event_notification(event_id: int) -> dict[str, str]:
    """Attempt one persisted event email, committing attempt state before SMTP."""
    async with AsyncSessionLocal() as db:
        event = (await db.execute(
            select(ShipmentTrackingEvent)
            .where(ShipmentTrackingEvent.id == event_id)
            .with_for_update(skip_locked=True)
        )).scalar_one_or_none()
        if not event or event.customer_notified_at:
            return {"status": "not_pending"}
        if not event.material:
            return {"status": "not_customer_visible"}
        now = datetime.utcnow()
        if event.customer_notification_attempts >= _MAX_ATTEMPTS:
            return {"status": "exhausted"}
        if (
            event.customer_notification_attempted_at
            and now - event.customer_notification_attempted_at < _retry_delay(event.customer_notification_attempts)
        ):
            return {"status": "backoff"}

        case_email = None
        order = None
        tracking = None
        case_reference = None
        case_status = None
        recipient_customer = None
        if event.customer_problem_shipment_id or event.customer_problem_id:
            if event.provider != "parcel2go" or event.status_code not in _DELIVERED_CODES:
                event.customer_notification_attempts = _MAX_ATTEMPTS
                await db.commit()
                return {"status": "not_customer_visible"}
            shipment = await db.get(CustomerProblemShipment, event.customer_problem_shipment_id) if event.customer_problem_shipment_id else None
            problem = (
                await db.get(CustomerProblem, shipment.customer_problem_id)
                if shipment
                else await db.get(CustomerProblem, event.customer_problem_id)
            )
            order = await db.get(Order, problem.order_id) if problem and problem.order_id else None
            if not order:
                # Manual-build/marketplace cases must stay on their source channel.
                event.customer_notification_attempts = _MAX_ATTEMPTS
                await db.commit()
                return {"status": "channel_suppressed"}
            if not await order_is_direct_storefront(db, order.id):
                event.customer_notification_attempts = _MAX_ATTEMPTS
                await db.commit()
                return {"status": "channel_suppressed"}
            recipient_customer = await db.get(Customer, order.customer_id)
            if shipment:
                case_status = "replacement_delivered" if shipment.purpose == "replacement" else problem.status
                tracking = {
                    "purpose": shipment.purpose,
                    "carrier": shipment.carrier,
                    "tracking_number": shipment.tracking_number,
                    "tracking_url": shipment.tracking_url,
                }
            else:
                tracking = dict(problem.repair_tracking or {})
                case_status = problem.status
            case_reference = f"CASE-{problem.id}"
            case_email = True
        else:
            order = await db.get(Order, event.order_id) if event.order_id else None
            if not order:
                event.customer_notification_attempts = _MAX_ATTEMPTS
                await db.commit()
                return {"status": "channel_suppressed"}
            if not await order_is_direct_storefront(db, order.id):
                event.customer_notification_attempts = _MAX_ATTEMPTS
                await db.commit()
                return {"status": "channel_suppressed"}
            recipient_customer = await db.get(Customer, order.customer_id)

        if not recipient_customer or not recipient_customer.email:
            event.customer_notification_attempts = _MAX_ATTEMPTS
            event.customer_notification_attempted_at = now
            await db.commit()
            await emit_alert(
                code="parcel2go_customer_notification_unavailable",
                source=f"shipment_event:{event.id}",
                severity="critical",
                link_url="/dispatch-zone",
                message=f"Parcel2Go tracking event {event.id} has no current direct-order email recipient.",
            )
            return {"status": "failed"}

        event.customer_notification_attempts += 1
        event.customer_notification_attempted_at = now
        name = recipient_customer.name or "there"
        email = recipient_customer.email
        if case_email:
            status_code = case_status
            order_id = order.id
            reference = case_reference
            repair_tracking = tracking
        else:
            status_code = None
            order_id = order.id
            reference = order.order_id
            description = event.description
            tracking_url = event.tracking_url
            live_map_url = event.live_map_url
        attempt_number = event.customer_notification_attempts
        await db.commit()

    try:
        if case_email:
            sent = await send_customer_case_status_email(
                email, name, reference, status_code, order_id, repair_tracking=repair_tracking
            )
        else:
            sent = await send_courier_event_email(
                email, name, reference, description, order_id=order_id,
                tracking_url=tracking_url, live_map_url=live_map_url,
            )
    except Exception:
        log.exception("parcel2go_notification.send_failed", event_id=event_id)
        sent = False

    if sent:
        async with AsyncSessionLocal() as db:
            saved = (await db.execute(
                select(ShipmentTrackingEvent)
                .where(ShipmentTrackingEvent.id == event_id)
                .with_for_update()
            )).scalar_one_or_none()
            if saved and not saved.customer_notified_at:
                saved.customer_notified_at = datetime.utcnow()
                await db.commit()
        return {"status": "sent"}

    if attempt_number >= _MAX_ATTEMPTS:
        await emit_alert(
            code="parcel2go_customer_notification_exhausted",
            source=f"shipment_event:{event_id}",
            severity="critical",
            link_url="/dispatch-zone",
            message=f"Customer email for Parcel2Go tracking event {event_id} failed after {_MAX_ATTEMPTS} attempts.",
        )
        return {"status": "failed"}
    return {"status": "pending"}


async def deliver_parcel2go_tracking_notification(event_id: int) -> dict[str, str]:
    """Backward-compatible name used by the Parcel2Go webhook adapter."""
    return await deliver_tracking_event_notification(event_id)


async def retry_pending_tracking_notifications() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        event_ids = (await db.execute(
            select(ShipmentTrackingEvent.id)
            .where(
                ShipmentTrackingEvent.material.is_(True),
                ShipmentTrackingEvent.customer_notified_at.is_(None),
                ShipmentTrackingEvent.customer_notification_attempts < _MAX_ATTEMPTS,
                or_(
                    and_(
                        ShipmentTrackingEvent.order_id.is_not(None),
                        or_(
                            ShipmentTrackingEvent.provider_event_id.is_(None),
                            ~ShipmentTrackingEvent.provider_event_id.like("dispatch:%"),
                        ),
                    ),
                    and_(
                        ShipmentTrackingEvent.provider == "parcel2go",
                        or_(
                            ShipmentTrackingEvent.customer_problem_id.is_not(None),
                            ShipmentTrackingEvent.customer_problem_shipment_id.is_not(None),
                        ),
                    ),
                ),
            )
            .order_by(ShipmentTrackingEvent.created_at.asc(), ShipmentTrackingEvent.id.asc())
            .limit(_MAX_BATCH)
        )).scalars().all()

    sent = failed = deferred = 0
    for event_id in event_ids:
        result = await deliver_tracking_event_notification(event_id)
        if result["status"] == "sent":
            sent += 1
        elif result["status"] == "failed":
            failed += 1
        else:
            deferred += 1
    return {"sent": sent, "failed": failed, "deferred": deferred}


async def retry_pending_parcel2go_notifications() -> dict[str, int]:
    """Backward-compatible scheduler entry point."""
    return await retry_pending_tracking_notifications()
