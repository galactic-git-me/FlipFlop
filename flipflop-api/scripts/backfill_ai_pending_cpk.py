#!/usr/bin/env python3
"""Resolve category-known pending identities with the local LLM.

Only >=70% confidence, same-category, hard-gate-clean results are persisted.
The script is resumable because already assigned listing IDs leave the queue.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.gem_radar.cpk_extractor import extract_cpk
from app.gem_radar.opportunity_scoring import identity_gates


async def run(apply: bool, limit: int | None) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT s.listing_id, s.title, s.category, s.condition, s.delivered_price
            FROM gem_radar_scored_listings s
            LEFT JOIN gem_radar_listing_cpk c ON c.listing_id=s.listing_id
            WHERE s.classification='IDENTITY_PENDING'
              AND s.category IS NOT NULL AND c.listing_id IS NULL
            ORDER BY s.listing_id
            LIMIT COALESCE(:limit, 2147483647)
        """), {"limit": limit})).mappings().all()
        print(f"pending_queue={len(rows)} apply={str(apply).lower()}", flush=True)
        if not rows:
            return

        if apply:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            await db.execute(text(
                f"CREATE TABLE gem_radar_listing_cpk_ai_backup_{stamp} AS TABLE gem_radar_listing_cpk"
            ))
            await db.commit()
            print(f"backup=gem_radar_listing_cpk_ai_backup_{stamp}", flush=True)

        counts: Counter[str] = Counter()
        for start in range(0, len(rows), 4):
            batch = rows[start:start + 4]
            extracted = await asyncio.gather(*[
                extract_cpk(row["title"], row["category"], row["condition"])
                for row in batch
            ])
            for row, product in zip(batch, extracted):
                if product is None:
                    counts["rejected_or_unresolved"] += 1
                    continue
                if product.category != row["category"]:
                    counts["category_disagreement"] += 1
                    continue
                flags = [flag for flag in identity_gates(row["title"], product.to_dict()) if flag != "identity_incomplete"]
                if flags:
                    counts[f"veto:{flags[0]}"] += 1
                    continue
                counts["accepted"] += 1
                if not apply:
                    continue
                await db.execute(text("""
                    INSERT INTO gem_radar_listing_cpk(listing_id,cpk,cpk_data,cpk_confidence)
                    VALUES(:listing_id,:cpk,:data,:confidence)
                    ON CONFLICT(listing_id) DO NOTHING
                """), {
                    "listing_id": row["listing_id"], "cpk": product.cpk,
                    "data": json.dumps({**product.to_dict(), "extraction_method": "local_llm_controlled"}),
                    "confidence": product.confidence,
                })
                await db.execute(text("""
                    INSERT INTO gem_radar_cpk_listing_price(listing_id,cpk,price,updated_at)
                    VALUES(:listing_id,:cpk,:price,CURRENT_TIMESTAMP)
                    ON CONFLICT(listing_id) DO UPDATE
                    SET cpk=excluded.cpk,price=excluded.price,updated_at=CURRENT_TIMESTAMP
                """), {"listing_id": row["listing_id"], "cpk": product.cpk, "price": row["delivered_price"]})
            if apply:
                await db.commit()
            done = min(start + 4, len(rows))
            if done % 100 == 0 or done == len(rows):
                print(f"progress={done}/{len(rows)} outcomes={json.dumps(counts, sort_keys=True)}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    asyncio.run(run(args.apply, args.limit))
