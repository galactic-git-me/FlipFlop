"""Marks a Flip as sold from a verified external signal — the eBay order
API, an eBay sold-notification email, or a storefront sale — and emits the
flip_resale_detected alert that drives the admin dashboard's confetti.

Centralizes logic that used to live only in POST /flips/{id}/sold, so every
automated detector (app/services/ebay_sales_tracker.py, the eBay branch of
app/services/email_monitor.py) reports a sale the same, idempotent way.
"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flip import Flip, FlipStage
from app.models.flip_intelligence import FlipIntelligence
from app.models.listing import Classification, Listing, ListingStatus
from app.services.alerts import emit_alert

log = structlog.get_logger(__name__)


async def find_flip_by_ebay_listing_id(db: AsyncSession, ebay_listing_id: str) -> Flip | None:
    result = await db.execute(select(Flip).where(Flip.ebay_listing_id == ebay_listing_id))
    return result.scalar_one_or_none()


def extract_cpu_tier(cpu: str | None) -> str | None:
    if not cpu:
        return None
    cpu_lower = cpu.lower()
    if "xeon" in cpu_lower:
        return "Xeon"
    if "i9" in cpu_lower:
        return "i9"
    if "i7" in cpu_lower:
        return "i7"
    if "i5" in cpu_lower:
        return "i5"
    if "i3" in cpu_lower:
        return "i3"
    if "ryzen 9" in cpu_lower:
        return "Ryzen 9"
    if "ryzen 7" in cpu_lower:
        return "Ryzen 7"
    if "ryzen 5" in cpu_lower:
        return "Ryzen 5"
    if "ryzen 3" in cpu_lower:
        return "Ryzen 3"
    return cpu.split()[0] if cpu else None


async def derive_case_theme(flip: Flip, db: AsyncSession) -> str | None:
    """Resolve case theme from selected upgrades, if a case part is selected.
    Supports both keyed JSON (e.g. {"case": 123}) and arbitrary value maps."""
    from app.models.part import Part

    selected = dict(flip.selected_upgrade_ids or {})
    if not selected:
        return None

    candidate_ids: list[int] = []
    if "case" in selected:
        try:
            candidate_ids.append(int(selected["case"]))
        except Exception as exc:
            log.warning("flip_sale.case_id.invalid", value=selected.get("case"), error=str(exc))
    for _, v in selected.items():
        try:
            iv = int(v)
            if iv not in candidate_ids:
                candidate_ids.append(iv)
        except Exception:
            continue

    for part_id in candidate_ids:
        part = await db.get(Part, part_id)
        if not part:
            continue
        if str(part.category.value) == "case":
            return (part.theme or part.name or "").strip() or None
    return None


async def process_flip_sale(
    db: AsyncSession,
    flip: Flip,
    *,
    sale_price: float,
    sale_platform: str,
    source: str,
    sold_at: datetime | None = None,
    platform_fee: float | None = None,
) -> Flip | None:
    """Marks `flip` sold, writes its FlipIntelligence record, and emits the
    flip_resale_detected alert. Idempotent — no-ops (returns None) if the
    flip is already marked sold, so pollers can call this repeatedly without
    double-counting a sale. `source` identifies the detector for logging
    (e.g. "ebay_order_api", "ebay_sold_email", "storefront_webhook")."""
    if flip.stage == FlipStage.sold:
        log.debug("flip_sale.already_sold", flip_id=flip.id, source=source)
        return None

    sold_at = sold_at or datetime.utcnow()
    fee = platform_fee if platform_fee is not None else sale_price * flip.platform_fee_pct

    flip.stage = FlipStage.sold
    flip.sold_at = sold_at
    flip.actual_sale_price = sale_price
    flip.sale_platform = sale_platform
    flip.actual_selling_fee = fee
    flip.actual_profit = sale_price - flip.total_cost - fee

    listing = await db.get(Listing, flip.listing_id)
    if listing:
        listing.status = ListingStatus.sold
        listing.sold_at = sold_at
        listing.classification = Classification.already_flipped

    days = (sold_at - flip.created_at).days if flip.created_at else 0
    roi = (flip.actual_profit / flip.total_cost * 100) if flip.total_cost else 0

    intel = FlipIntelligence(
        flip_id=flip.id,
        source_site=listing.source_name if listing else "unknown",
        buy_price=listing.price if listing else flip.base_cost,
        gem_score_at_buy=listing.gem_score if listing else 0,
        cpu_tier=extract_cpu_tier(listing.cpu if listing else None),
        had_gpu=bool(listing.gpu) if listing else False,
        had_storage=bool(listing.storage_gb) if listing else False,
        ram_gb=listing.ram_gb if listing else None,
        case_theme=await derive_case_theme(flip, db),
        upgrade_cost=flip.upgrade_cost,
        total_cost=flip.total_cost,
        sell_price=sale_price,
        sell_platform=sale_platform,
        days_to_sell=days,
        profit=flip.actual_profit,
        roi_pct=roi,
    )
    db.add(intel)
    await db.flush()

    log.info(
        "flip_sale.detected",
        flip_id=flip.id,
        source=source,
        sale_platform=sale_platform,
        sale_price=sale_price,
        actual_profit=flip.actual_profit,
    )

    try:
        await emit_alert(
            code="flip_resale_detected",
            source=source,
            severity="info",
            message=(
                f"Resale detected: Flip #{flip.id} sold on {sale_platform or 'unknown'} "
                f"with profit £{float(flip.actual_profit or 0.0):.2f}."
            ),
        )
    except Exception as exc:
        log.warning("flip_sale.alert_emit_failed", flip_id=flip.id, error=str(exc))

    return flip
