"""'Bought It' workflow (PRD §26). Creates a provisional purchase in the
existing InventoryItem table — FlipFlopOS remains the system of record;
this never writes to a separate Gem-Radar-owned store. Duplicate protection
relies on the partial unique index added by migration 20260706_0014
(marketplace, listing_id) — a second Bought It for the same listing returns
the existing row instead of raising a constraint error.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryItem
from app.gem_radar.schemas import BoughtItPayload, BoughtItResponse
from app.gem_radar.seller_intelligence import increment_purchase_count


async def create_provisional_purchase(db: AsyncSession, payload: BoughtItPayload) -> BoughtItResponse:
    existing_result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.marketplace == payload.marketplace,
            InventoryItem.listing_id == payload.listing_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return BoughtItResponse(inventory_item_id=existing.id, duplicate_of=existing.id)

    item = InventoryItem(
        component_name=payload.title,
        component_type="unknown",  # Gem Radar's identity resolution is best-effort; category correction happens in the existing /inventory admin UI
        quantity=payload.quantity,
        base_price=payload.actual_item_price_paid,
        shipping_cost=payload.postage_paid,
        discount_amount=payload.discount_amount,
        purchase_date=payload.purchase_date.replace(tzinfo=None) if payload.purchase_date.tzinfo else payload.purchase_date,
        source="eBay",
        notes=f"Gem Radar extension purchase. {payload.notes}".strip(),
        marketplace=payload.marketplace,
        listing_id=payload.listing_id,
        listing_url=payload.listing_url,
        seller_name=payload.seller,
        purchase_status="PURCHASED_MANUAL",
        reconciliation_status="PENDING_EMAIL_CONFIRMATION",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    if payload.seller:
        await increment_purchase_count(db, payload.seller)

    return BoughtItResponse(inventory_item_id=item.id, duplicate_of=None)
