"""Customer-safe purchase activity projected from confirmed, persisted orders.

No second event write, geocoding requirement or catalogue-price lookup: an
order's paid total and checkout snapshot are the evidence. Never expose the
order reference, payment identifier, address or customer identity.
"""
from datetime import datetime, timedelta, timezone
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from app.models.order import Order, OrderStatus
from app.models.customer import Customer


def public_purchase(order: Order) -> dict | None:
    if not order.stripe_payment_intent_id or order.status == OrderStatus.CANCELLED or order.refund_id:
        return None
    try:
        paid = float(order.customer_price)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(paid) or paid <= 0 or not order.created_at:
        return None
    specs = order.specs if isinstance(order.specs, dict) else {}
    payment = specs.get("payment_evidence")
    if not isinstance(payment, dict) or payment.get("provider") != "stripe" or payment.get("status") != "succeeded" or payment.get("livemode") is not True or payment.get("currency") != "gbp":
        return None
    product_id = specs.get("product_id")
    title = specs.get("build_title") or specs.get("build_name")
    # Curated identity comes from the saved selected build id, never a fuzzy name match.
    curated_id = specs.get("curated_build_id")
    if not title and isinstance(curated_id, str):
        from app.services.curated_build_policy import definitions
        definition = next((item for item in definitions()["builds"] if item["id"] == curated_id), None)
        if definition:
            title = definition["name"]
    title = title if isinstance(title, str) and title.strip() else "Custom FlipFlop PC"
    # The snapshot page preserves the purchased choices instead of opening a reset configurator.
    href = f"/builds/{product_id}" if type(product_id) is int and product_id > 0 else f"/purchases/{order.id}"
    created_at = order.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    parts = []
    for slot in specs.get("slots", []) if isinstance(specs.get("slots"), list) else []:
        if not isinstance(slot, dict):
            continue
        category, name = slot.get("slot_type"), slot.get("title")
        if category in {"cpu", "gpu", "motherboard", "ram", "storage", "psu", "cooling", "case", "fan"} and isinstance(name, str):
            parts.append({"category": category, "name": name[:300]})
    if isinstance(specs.get("case_name"), str):
        parts.append({"category": "case", "name": specs["case_name"][:300]})
    customer = getattr(order, "customer", None)
    metadata = getattr(customer, "profile_metadata", None)
    display_name = None
    if isinstance(metadata, dict) and metadata.get("public_purchase_name_consent") is True:
        names = [part for part in str(getattr(customer, "name", "")).split() if part]
        if names:
            display_name = names[0] if len(names) == 1 else f"{names[0]} {names[-1][0]}."
    return {
        "id": order.id, "event_type": "order", "product_name": title[:200],
        "product_url": href, "amount_gbp": round(paid, 2),
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "simulated": False, "parts": parts, "display_name": display_name,
    }


def paid_orders():
    return select(Order).options(load_only(
        Order.id, Order.specs, Order.customer_price, Order.created_at,
        Order.stripe_payment_intent_id, Order.status, Order.refund_id,
    ), selectinload(Order.customer).load_only(Customer.name, Customer.profile_metadata)).where(
        Order.stripe_payment_intent_id.is_not(None),
        Order.status != OrderStatus.CANCELLED,
        Order.refund_id.is_(None),
        Order.customer_price > 0,
        Order.specs["payment_evidence"]["livemode"].as_boolean().is_(True),
    )


async def recent_purchases(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(paid_orders().where(
        Order.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24),
    ).order_by(Order.created_at.desc(), Order.id.desc()).limit(20))).scalars().all()
    return [purchase for order in rows if (purchase := public_purchase(order)) is not None]


async def purchase_by_id(db: AsyncSession, purchase_id: int) -> dict | None:
    order = (await db.execute(paid_orders().where(Order.id == purchase_id))).scalar_one_or_none()
    return public_purchase(order) if order else None
