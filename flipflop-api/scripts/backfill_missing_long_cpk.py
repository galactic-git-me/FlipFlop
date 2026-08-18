#!/usr/bin/env python3
"""Backfill CPKs stranded by the former VARCHAR(50) listing-id limit.

Resumable: each pass selects only observation IDs that still have no row in
gem_radar_listing_cpk. Four independent sessions keep Ollama and PostgreSQL
work isolated while matching the application's extraction parallelism.
"""
from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.gem_radar.cpk_pipeline import assign_cpk_and_accumulate_price


WORKERS = 4


async def load_pending() -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT DISTINCT ON (o.listing_id)
                o.listing_id, o.title, o.category,
                o.condition_normalised, o.delivered_price, o.scan_price
            FROM gem_radar_listing_observations o
            LEFT JOIN gem_radar_listing_cpk c ON c.listing_id = o.listing_id
            WHERE c.listing_id IS NULL AND length(o.listing_id) > 50
            ORDER BY o.listing_id, o.observed_at DESC, o.id DESC
        """))).mappings().all()
        return [dict(row) for row in rows]


async def process(row: dict) -> str:
    try:
        async with AsyncSessionLocal() as db:
            cpk = await assign_cpk_and_accumulate_price(
                db,
                row["listing_id"],
                row["title"],
                row["category"],
                row["condition_normalised"],
                row["delivered_price"],
                row["scan_price"],
            )
            await db.commit()
            return "assigned" if cpk else "unresolved"
    except Exception as exc:
        print(f"error listing_id={row['listing_id']!r} detail={exc}", flush=True)
        return "error"


async def main() -> None:
    pending = await load_pending()
    print(f"pending={len(pending)} workers={WORKERS}", flush=True)
    counts: Counter[str] = Counter()
    for start in range(0, len(pending), WORKERS):
        batch = pending[start:start + WORKERS]
        outcomes = await asyncio.gather(*(process(row) for row in batch))
        counts.update(outcomes)
        done = min(start + WORKERS, len(pending))
        if done % 20 == 0 or done == len(pending):
            print(
                f"progress={done}/{len(pending)} assigned={counts['assigned']} "
                f"unresolved={counts['unresolved']} errors={counts['error']}",
                flush=True,
            )
    print(
        f"complete total={len(pending)} assigned={counts['assigned']} "
        f"unresolved={counts['unresolved']} errors={counts['error']}",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
