"""One-off backfill: recompute every existing CPK using the corrected hash
input (category|brand|model only — see app/gem_radar/cpk_extractor.py) and
rebuild the market-price aggregates from scratch.

Why this is needed: the CPK used to be hashed from category|brand|model|specs,
where `specs` is an LLM-extracted free-form dict that varies listing-to-listing
for the identical physical product (depends on how much detail happened to be
in that seller's title). That meant almost no two listings of the same product
ever shared a CPK, so gem_radar_cpk_market_price.listing_count never reached
the 2-listing settlement threshold and market prices stayed unassigned.

This script does NOT call the LLM again — category/brand/model are already
cached in gem_radar_listing_cpk.cpk_data from the original extraction, so the
new CPK is just a cheap local re-hash. After it runs, listings that are
genuinely the same product (down to brand+model) will collapse onto the same
CPK, and gem_radar_cpk_market_price is rebuilt to match.

Run once, then let the normal Phase 2 trigger (or a manual
`python -m app.gem_radar.phase2_runner` equivalent) reclassify against the
now-settled prices.
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal

BATCH_SIZE = 500


def compute_cpk(category: str, brand: str, model: str) -> str:
    cpk_input = f"{category}|{brand}|{model}"
    return hashlib.sha256(cpk_input.encode()).hexdigest()[:16]


async def rehash_listing_cpks() -> dict[str, str]:
    """Recomputes gem_radar_listing_cpk.cpk for every row from its stored
    cpk_data. Returns {old_cpk: new_cpk} for rows that actually changed, so
    the price tables can be rebuilt without a second DB pass."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT listing_id, cpk, cpk_data FROM gem_radar_listing_cpk ORDER BY listing_id")
        )
        rows = result.fetchall()
        total = len(rows)
        print(f"Rehashing {total} existing CPK assignments...")

        old_to_new: dict[str, str] = {}
        updated = 0
        skipped_missing_data = 0

        for i in range(0, total, BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            for listing_id, old_cpk, cpk_data in batch:
                cpk_data = cpk_data or {}
                category = cpk_data.get("category")
                brand = cpk_data.get("brand")
                model = cpk_data.get("model")
                if not (category and brand and model):
                    skipped_missing_data += 1
                    continue

                new_cpk = compute_cpk(category, brand, model)
                if new_cpk != old_cpk:
                    await db.execute(
                        text("UPDATE gem_radar_listing_cpk SET cpk = :new_cpk WHERE listing_id = :listing_id"),
                        {"new_cpk": new_cpk, "listing_id": listing_id},
                    )
                    old_to_new[old_cpk] = new_cpk
                    updated += 1

            await db.commit()
            done = min(i + BATCH_SIZE, total)
            print(f"  [{done}/{total}] updated={updated} skipped={skipped_missing_data}")

        print(f"Done: {updated} CPKs rehashed, {skipped_missing_data} rows skipped (missing cpk_data).")
        return old_to_new


async def rebuild_cpk_listing_price(old_to_new: dict[str, str]) -> None:
    """gem_radar_cpk_listing_price.cpk must follow the same rehash — it's keyed
    off the same listing_id -> cpk relationship, just duplicated for price
    aggregation. Joins back to gem_radar_listing_cpk (already rehashed above)
    rather than replaying old_to_new, so it stays correct even for CPKs this
    script didn't touch."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                UPDATE gem_radar_cpk_listing_price clp
                SET cpk = lc.cpk
                FROM gem_radar_listing_cpk lc
                WHERE clp.listing_id = lc.listing_id
                  AND clp.cpk IS DISTINCT FROM lc.cpk
                """
            )
        )
        await db.commit()
        print(f"gem_radar_cpk_listing_price: {result.rowcount} rows re-keyed to corrected CPK.")


async def rebuild_market_price_aggregates() -> None:
    """Full rebuild of gem_radar_cpk_market_price from gem_radar_cpk_listing_price
    now that prices are keyed by the corrected CPK — cheaper and safer than
    trying to patch aggregates in place for every CPK merge."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM gem_radar_cpk_market_price"))

        await db.execute(
            text(
                """
                INSERT INTO gem_radar_cpk_market_price
                    (cpk, category, brand, model, min_price, median_price, max_price, listing_count, updated_at)
                SELECT
                    clp.cpk,
                    lc.cpk_data->>'category',
                    lc.cpk_data->>'brand',
                    lc.cpk_data->>'model',
                    MIN(clp.price),
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY clp.price),
                    MAX(clp.price),
                    COUNT(*),
                    CURRENT_TIMESTAMP
                FROM gem_radar_cpk_listing_price clp
                JOIN gem_radar_listing_cpk lc ON lc.listing_id = clp.listing_id
                WHERE clp.updated_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                GROUP BY clp.cpk, lc.cpk_data->>'category', lc.cpk_data->>'brand', lc.cpk_data->>'model'
                """
            )
        )
        await db.commit()

        settled = await db.execute(
            text("SELECT COUNT(*) FROM gem_radar_cpk_market_price WHERE listing_count >= 2")
        )
        total = await db.execute(text("SELECT COUNT(*) FROM gem_radar_cpk_market_price"))
        print(
            f"gem_radar_cpk_market_price rebuilt: {total.scalar()} CPKs total, "
            f"{settled.scalar()} now settled (>=2 contributing listings)."
        )


async def main() -> None:
    old_to_new = await rehash_listing_cpks()
    await rebuild_cpk_listing_price(old_to_new)
    await rebuild_market_price_aggregates()
    print()
    print("Backfill complete. Run Phase 2 classification (or wait for the next")
    print("scan-sweep-complete signal) to reclassify against the now-settled prices.")


if __name__ == "__main__":
    asyncio.run(main())
