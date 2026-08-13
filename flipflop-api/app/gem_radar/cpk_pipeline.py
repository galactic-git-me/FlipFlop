"""Phase 1 of the CPK-driven market-price system, wired into LIVE ingestion
(app/api/gem_radar.py's _submit_scan_body — called for every listing the
FlipFlopXtension submits, the only source of listing data this backend
has). This is deliberately the entire ingestion pipeline now: no eBay/vendor
polling, no scoring, no classification — those are Phase 2's job, and only
run in bulk once the extension signals a whole scan sweep is complete (see
deal_classification.py and the /scan-sweep-complete endpoint).

scripts/phase1_accumulate_cpk_prices.py reuses this same function as an
offline backfill tool for historical observations — the logic lives here
once, not duplicated between the live path and the CLI script.
"""
from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gem_radar.cpk_extractor import extract_cpk
from app.gem_radar.cpk_market import upsert_listing_price, upsert_scan_price
from app.gem_radar.benchmarks import normalize_match_key


async def assign_cpk_and_accumulate_price(
    db: AsyncSession,
    listing_id: str,
    title: str,
    category: str | None,
    condition: str | None,
    price: float | None,
    scan_price: float | None = None,
) -> str | None:
    """Looks up (or extracts, via one LLM call if genuinely new) this
    listing's CPK, persists it to gem_radar_listing_cpk, and folds its price
    into that CPK's market-price aggregate (gem_radar_cpk_market_price via
    cpk_market.upsert_listing_price). If scan_price is provided, records it
    as a scan observation for cross-vendor market aggregation.
    Returns the CPK, or None if extraction failed or was too low-confidence to
    trust (e.g. not a recognisable PC component) — the listing still gets its
    observation row regardless via the caller, it just never gets folded into
    any CPK's market price.
    """
    existing = await db.execute(
        text("SELECT cpk, cpk_data FROM gem_radar_listing_cpk WHERE listing_id = :listing_id"),
        {"listing_id": listing_id},
    )
    row = existing.fetchone()

    if row is not None:
        cpk = row[0]
        cpk_data = row[1] or {}
        brand = cpk_data.get("brand")
        model = cpk_data.get("model")
        extracted_category = cpk_data.get("category")
    else:
        extracted = await extract_cpk(title, category, condition)
        if extracted is None:
            return None

        await db.execute(
            text(
                """
                INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
                VALUES (:listing_id, :cpk, :cpk_data, :cpk_confidence)
                ON CONFLICT (listing_id) DO UPDATE SET
                    cpk = EXCLUDED.cpk,
                    cpk_data = EXCLUDED.cpk_data,
                    cpk_confidence = EXCLUDED.cpk_confidence,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "listing_id": listing_id,
                "cpk": extracted.cpk,
                "cpk_data": json.dumps(extracted.to_dict()),
                "cpk_confidence": extracted.confidence,
            },
        )
        cpk = extracted.cpk
        brand = extracted.brand
        model = extracted.model
        extracted_category = extracted.category

    if price is not None:
        await upsert_listing_price(
            db,
            cpk=cpk,
            listing_id=listing_id,
            price=price,
            category=extracted_category or category,
            brand=brand,
            model=model,
        )

    if scan_price is not None:
        match_key = normalize_match_key(title)
        await upsert_scan_price(
            db,
            cpk=cpk,
            match_key=match_key,
            price=scan_price,
            category=extracted_category or category,
            brand=brand,
            model=model,
        )

    return cpk
