"""Backfill active listings from unique catalog aliases without invoking the LLM."""
from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.gem_radar.cpk_pipeline import _lookup_unique_catalog_alias
from app.gem_radar.cpk_market import upsert_listing_price


async def run(limit: int, dry_run: bool) -> dict:
    engine = create_async_engine(get_settings().database_url, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    matched = 0
    updated = 0
    async with factory() as db:
        rows = (await db.execute(text("""
            SELECT o.listing_id, o.title, o.category, o.delivered_price
            FROM gem_radar_listing_observations o
            LEFT JOIN gem_radar_listing_cpk c ON c.listing_id = o.listing_id
            WHERE c.listing_id IS NULL
            ORDER BY o.observed_at DESC
            LIMIT :limit
        """), {"limit": limit})).mappings().all()
        for row in rows:
            alias = await _lookup_unique_catalog_alias(db, row["title"])
            if alias is None:
                continue
            matched += 1
            if dry_run:
                continue
            cpk, data = alias
            await db.execute(text("""
                INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
                VALUES (:listing_id, :cpk, :cpk_data, 0.9)
                ON CONFLICT (listing_id) DO NOTHING
            """), {"listing_id": row["listing_id"], "cpk": cpk, "cpk_data": json.dumps(data)})
            await upsert_listing_price(db, cpk, row["listing_id"], float(row["delivered_price"]),
                                        row["category"], data.get("brand"), data.get("model"))
            updated += 1
        if not dry_run:
            await db.commit()
    await engine.dispose()
    return {"scanned": len(rows), "matched": matched, "updated": updated, "dry_run": dry_run}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(max(1, args.limit), args.dry_run)), indent=2))


if __name__ == "__main__":
    main()
