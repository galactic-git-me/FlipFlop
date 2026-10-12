"""Retry durable direct-storefront dispatch email notifications."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.customer import Customer
from app.models.manual_build import ManualBuild
from app.models.order import Order
from app.models.product import Product
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.services.alerts import emit_alert
from app.services.email_service import send_shipment_update_email


log = logging.getLogger(__name__)
_MAX_ATTEMPTS = 8
_MAX_BATCH = 50


def _retry_delay(attempts: int) -> timedelta:
    """Use bounded exponential backoff so a mail outage cannot cause a hot loop."""
    return timedelta(minutes=min(360, 2 ** max(1, attempts)))


async def retry_pending_dispatch_notifications() -> dict[str, int]:
    """Retry unsent direct-storefront dispatch emails without contacting marketplaces."""
    sent_count = skipped_count = failed_count = 0
    async with AsyncSessionLocal() as db:
        candidate_ids = (await db.execute(
            select(ShipmentTrackingEvent.id)
            .where(
                ShipmentTrackingEvent.provider_event_id.like("dispatch:%"),
                ShipmentTrackingEvent.order_id.is_not(None),
                ShipmentTrackingEvent.material.is_(True),
                ShipmentTrackingEvent.customer_notified_at.is_(None),
                ShipmentTrackingEvent.customer_notification_attempts < _MAX_ATTEMPTS,
            )
            .order_by(ShipmentTrackingEvent.created_at.asc(), ShipmentTrackingEvent.id.asc())
            .limit(_MAX_BATCH)
        )).scalars().all()

        for event_id in candidate_ids:
            event = (await db.execute(
                select(ShipmentTrackingEvent)
                .where(ShipmentTrackingEvent.id == event_id)
                .with_for_update(skip_locked=True)
            )).scalar_one_or_none()
            if event is None or event.customer_notified_at:
                skipped_count += 1
                await db.rollback()
                continue
            now = datetime.utcnow()
            last_attempt = event.customer_notification_attempted_at
            if last_attempt and now - last_attempt < _retry_delay(event.customer_notification_attempts):
                skipped_count += 1
                await db.rollback()
                continue

            order = await db.get(Order, event.order_id)
            build_match = re.match(r"^dispatch:(\d+):", event.provider_event_id or "")
            build = await db.get(ManualBuild, int(build_match.group(1))) if build_match else None
            # Only direct storefront sales receive off-platform email. eBay,
            # Vinted and other manual channel buyers stay on their source site.
            direct_storefront = bool(order and build and not build.ebay_order_id)
            if direct_storefront and build.storefront_product_id:
                product = await db.get(Product, build.storefront_product_id)
                channel = getattr(product.sold_via_channel, "value", product.sold_via_channel) if product else None
                direct_storefront = channel == "storefront"
            customer = await db.get(Customer, order.customer_id) if direct_storefront and order else None
            if not direct_storefront or not customer or not customer.email:
                # Keep the portal event, but record that no off-platform email
                # is permitted or possible for this channel/recipient.
                event.material = False
                await db.commit()
                skipped_count += 1
                continue

            event.customer_notification_attempts += 1
            event.customer_notification_attempted_at = now
            notification_event_id = event.id
            recipient = customer.email
            name = customer.name or "there"
            reference = order.order_id
            order_id = order.id
            carrier = build.parcel2go_service_slug.split("-")[0] if build.parcel2go_service_slug else "courier"
            tracking_number = build.tracking_number
            booking = (build.evidence_data or {}).get("shipment_booking_confirmation") or {}
            tracking_url = booking.get("tracking_url")
            estimated_delivery = order.estimated_delivery
            await db.commit()

            try:
                was_sent = await send_shipment_update_email(
                    recipient,
                    name,
                    reference,
                    carrier,
                    tracking_number,
                    tracking_url,
                    estimated_delivery,
                    order_id,
                )
            except Exception:
                log.exception("dispatch_notification.retry_failed: %s", notification_event_id)
                was_sent = False

            if was_sent:
                saved = await db.get(ShipmentTrackingEvent, notification_event_id)
                if saved and not saved.customer_notified_at:
                    saved.customer_notified_at = datetime.utcnow()
                    await db.commit()
                sent_count += 1
            else:
                failed_count += 1
                if event.customer_notification_attempts >= _MAX_ATTEMPTS:
                    log.error(
                        "dispatch_notification.retry_limit_reached event_id=%s attempts=%s",
                        notification_event_id,
                        event.customer_notification_attempts,
                    )
                    await emit_alert(
                        code="dispatch_notification_delivery_failed",
                        source=f"shipment_event:{notification_event_id}",
                        severity="critical",
                        link_url="/dispatch-zone",
                        message=(
                            f"Customer dispatch email for tracking event {notification_event_id} "
                            f"failed after {_MAX_ATTEMPTS} attempts. Contact the buyer and review mail delivery."
                        ),
                    )

    return {"sent": sent_count, "skipped": skipped_count, "failed": failed_count}
