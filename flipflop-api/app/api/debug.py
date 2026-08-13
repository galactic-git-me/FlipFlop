"""
Debug / audit endpoints — expose the full resale-estimation trace so every
valuation can be independently verified.

GET /debug/resale
  Re-runs the eBay comp scrape for a given spec and returns:
    • Every comp seen (title, price, url)
    • Every comp excluded (with reason)
    • The raw price set (min/max/median/avg)
    • Exactly which tier was used and why
    • Step-by-step calculation
    • Sanity check against buy price

These endpoints are read-only and never modify the database.
"""

from fastapi import APIRouter, Query
from app.services.resale_scraper import get_resale_audit, SoldComp, ResaleAudit
from app.database import AsyncSessionLocal
from app.services.submission_queue_service import SubmissionQueueService

router = APIRouter(prefix="/debug", tags=["debug"])


def _comp_dict(c: SoldComp) -> dict:
    return {
        "title":            c.title,
        "price":            round(c.price, 2) if c.price else None,
        "url":              c.url or None,
        "excluded":         c.excluded,
        "exclusion_reason": c.exclusion_reason or None,
    }


@router.get("/resale")
async def debug_resale(
    cpu:          str | None  = Query(None, description="CPU string, e.g. 'Intel Core i7-9700K'"),
    gpu:          str | None  = Query(None, description="GPU string, e.g. 'RTX 3060'"),
    ram_gb:       int | None  = Query(None),
    ram_type:     str | None  = Query(None),
    storage_gb:   int | None  = Query(None),
    storage_type: str | None  = Query(None),
    buy_price:    float | None = Query(None, description="The price the listing is being sold for"),
):
    """
    Full resale-estimation audit.

    Returns every eBay comp seen, every exclusion, and every calculation step
    so the valuation is completely transparent and auditable.

    This re-runs the live eBay scrape on every call — not cached.
    Allow 5–15 seconds for the response.
    """
    audit: ResaleAudit = await get_resale_audit(
        cpu=cpu, ram_gb=ram_gb, ram_type=ram_type,
        storage_gb=storage_gb, storage_type=storage_type,
        gpu=gpu, buy_price=buy_price,
    )

    included = [_comp_dict(c) for c in audit.included_comps]
    excluded = [_comp_dict(c) for c in audit.excluded_comps]
    prices   = sorted(c.price for c in audit.included_comps if c.price)

    return {
        # ── Step 1: Source data ────────────────────────────────────────────
        "query":         audit.query,
        "ebay_url":      audit.ebay_url,
        "total_items_seen":   len(audit.all_comps),
        "items_included":     len(included),
        "items_excluded":     len(excluded),
        "listings_included": included,
        "listings_excluded": excluded,

        # ── Step 2: Raw price set ──────────────────────────────────────────
        "prices":      prices,
        "price_min":   audit.price_min   or None,
        "price_max":   audit.price_max   or None,
        "price_median": audit.price_median or None,
        "price_avg":   audit.price_avg   or None,

        # ── Step 3: Exact calculation ──────────────────────────────────────
        "tier_used":         audit.tier_used,
        "case_premium_added": audit.case_premium_added,
        "resale_low":        audit.resale_low,
        "resale_median":     audit.resale_median,
        "resale_high":       audit.resale_high,
        "calculation_steps": audit.calculation_steps,

        # ── Step 5: Sanity check ───────────────────────────────────────────
        "buy_price":           audit.buy_price,
        "sanity_verdict":      audit.sanity_verdict or None,
        "sanity_explanation":  audit.sanity_explanation or None,
    }


@router.post("/queue-recovery")
async def recover_stuck_submissions():
    """
    Manually recover submissions stuck in 'processing' state.
    Resets them to 'pending' so the queue processor can retry them.
    """
    async with AsyncSessionLocal() as db:
        count = await SubmissionQueueService.recover_stuck_processing(db)
        return {
            "status": "ok",
            "recovered": count,
            "message": f"Recovered {count} stuck submissions back to pending state"
        }
