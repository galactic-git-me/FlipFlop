"""One-off cleanup for the cpk_extractor.py placeholder-echo bug (fixed
2026-08-14): deletes every gem_radar_listing_cpk row whose stored cpk_data
brand/model is the literal LLM-prompt placeholder text, along with the price
contributions and cached market-price rows for the CPKs that only existed
because of this bug, then re-runs extract_cpk (now guarded against the same
failure) for every affected listing so they get real CPKs. Finishes with a
fresh Phase 2 classification pass so SUPER_GEM/GEM counts reflect the
cleaned-up data.

Safe to re-run: idempotent given the fix is in place, since a listing that
now extracts cleanly won't match the placeholder markers again.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.gem_radar.cpk_extractor import _is_placeholder_echo, extract_cpk
from app.gem_radar.cpk_market import upsert_listing_price
from app.gem_radar.phase2_runner import run_phase2_classification


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT DISTINCT cpk FROM gem_radar_listing_cpk
                WHERE cpk_data->>'brand' = 'lowercase brand name'
                   OR cpk_data->>'model' LIKE 'normalized-model-id%'
                """
            )
        )
        bad_cpks = [row[0] for row in result.fetchall()]
        print(f"Corrupted CPKs to clear: {len(bad_cpks)}")

        result = await db.execute(
            text(
                """
                SELECT clc.listing_id, lo.title, lo.condition_normalised
                FROM gem_radar_listing_cpk clc
                JOIN gem_radar_listing_observations lo ON lo.listing_id = clc.listing_id
                WHERE clc.cpk_data->>'brand' = 'lowercase brand name'
                   OR clc.cpk_data->>'model' LIKE 'normalized-model-id%'
                """
            )
        )
        affected = result.fetchall()
        print(f"Affected listings to re-extract: {len(affected)}")

        # Clear the corrupted rows and everything downstream of them so
        # nothing keeps reading stale market-price data for these CPKs
        # while re-extraction runs.
        await db.execute(
            text("DELETE FROM gem_radar_cpk_market_price WHERE cpk = ANY(:cpks)"),
            {"cpks": bad_cpks},
        )
        await db.execute(
            text(
                """
                DELETE FROM gem_radar_cpk_listing_price
                WHERE listing_id = ANY(:listing_ids)
                """
            ),
            {"listing_ids": [row[0] for row in affected]},
        )
        await db.execute(
            text("DELETE FROM gem_radar_listing_cpk WHERE cpk = ANY(:cpks)"),
            {"cpks": bad_cpks},
        )
        await db.commit()
        print("Cleared corrupted rows.")

        re_extracted = 0
        still_failed = 0
        for i, (listing_id, title, condition) in enumerate(affected, 1):
            extracted = await extract_cpk(title, category=None, condition=condition)
            if extracted is None:
                still_failed += 1
                continue

            # Defensive: the freshly-fixed extractor should never return a
            # placeholder echo again, but never persist one if it somehow did.
            if _is_placeholder_echo(extracted.brand) or _is_placeholder_echo(extracted.model):
                still_failed += 1
                continue

            await db.execute(
                text(
                    """
                    INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
                    VALUES (:listing_id, :cpk, :cpk_data, :cpk_confidence)
                    ON CONFLICT (listing_id) DO UPDATE SET
                        cpk = EXCLUDED.cpk, cpk_data = EXCLUDED.cpk_data,
                        cpk_confidence = EXCLUDED.cpk_confidence, updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "listing_id": listing_id,
                    "cpk": extracted.cpk,
                    "cpk_data": json.dumps(extracted.to_dict()),
                    "cpk_confidence": extracted.confidence,
                },
            )

            price_row = await db.execute(
                text("SELECT delivered_price FROM gem_radar_listing_observations WHERE listing_id = :id"),
                {"id": listing_id},
            )
            price = price_row.scalar()
            if price is not None:
                await upsert_listing_price(
                    db, cpk=extracted.cpk, listing_id=listing_id, price=price,
                    category=extracted.category, brand=extracted.brand, model=extracted.model,
                )
            await db.commit()
            re_extracted += 1

            if i % 200 == 0:
                print(f"  ...{i}/{len(affected)} processed ({re_extracted} re-extracted, {still_failed} still failed)")

        print(f"Re-extraction complete: {re_extracted} succeeded, {still_failed} still failed/low-confidence")

        print("Running Phase 2 classification...")
        phase2_result = await run_phase2_classification(db)
        print("=" * 80)
        print(f"Total CPK-tagged: {phase2_result.total_cpk_tagged}")
        print(f"Classified: {phase2_result.classified_count}")
        print(f"Unsettled: {phase2_result.unsettled_count}")
        for label, count in sorted(phase2_result.classification_counts.items(), key=lambda kv: -kv[1]):
            print(f"  {label}: {count}")


asyncio.run(main())
