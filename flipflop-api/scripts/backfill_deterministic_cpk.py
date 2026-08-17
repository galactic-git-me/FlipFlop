#!/usr/bin/env python3
"""Backfill trustworthy categories/CPKs without an external model call.

Dry-run by default. Only identities with category, brand, model and >=0.70
deterministic exact-SKU confidence receive a CPK. Ambiguous rows retain an
explicit identity state during Phase 2 instead of being silently omitted.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.gem_radar.identity import resolve_identity
from app.gem_radar.opportunity_scoring import identity_gates


def slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


async def run(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text("""
            WITH latest AS (
              SELECT DISTINCT ON (o.listing_id) o.listing_id,o.title,o.condition_normalised,
                     o.delivered_price,o.category
              FROM gem_radar_listing_observations o
              ORDER BY o.listing_id,o.observed_at DESC,o.id DESC
            )
            SELECT l.* FROM latest l
            LEFT JOIN gem_radar_listing_cpk c USING(listing_id)
            WHERE c.listing_id IS NULL
        """))).mappings().all()
        categories: dict[str, str] = {}
        exact = []
        reasons = Counter()
        for row in rows:
            identity = resolve_identity(row["title"], row["delivered_price"])
            if identity.category:
                categories[row["listing_id"]] = identity.category
            flags = identity_gates(row["title"], {
                "category": identity.category, "brand": identity.brand, "model": identity.model,
            })
            hard = [flag for flag in flags if flag != "identity_incomplete"]
            if hard:
                reasons[hard[0]] += 1
                continue
            if not identity.category:
                reasons["category_unresolved"] += 1
                continue
            if not identity.brand or not identity.model or (identity.exact_sku_confidence or 0) < 0.70:
                reasons["model_or_brand_ambiguous"] += 1
                continue
            brand, model = slug(identity.brand), slug(identity.model)
            cpk = hashlib.sha256(f"{identity.category}|{brand}|{model}".encode()).hexdigest()[:16]
            data = {
                "category": identity.category, "brand": brand, "model": model,
                "specs": {}, "confidence": identity.exact_sku_confidence, "cpk": cpk,
                "extraction_method": "deterministic",
            }
            exact.append((row, cpk, data, float(identity.exact_sku_confidence)))
        print(f"missing_cpk={len(rows)} categories_resolved={len(categories)} exact_cpk={len(exact)}")
        print("unresolved=" + json.dumps(reasons, sort_keys=True))
        if not apply:
            print("dry_run=true; pass --apply to write changes")
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        await db.execute(text(f"CREATE TABLE gem_radar_listing_cpk_backup_{stamp} AS TABLE gem_radar_listing_cpk"))
        await db.execute(text(f"CREATE TABLE gem_radar_observation_category_backup_{stamp} AS SELECT id,listing_id,category FROM gem_radar_listing_observations"))
        for listing_id, category in categories.items():
            await db.execute(text("""
                UPDATE gem_radar_listing_observations SET category=:category
                WHERE listing_id=:listing_id AND category IS NULL
            """), {"category": category, "listing_id": listing_id})
        for row, cpk, data, confidence in exact:
            await db.execute(text("""
                INSERT INTO gem_radar_listing_cpk(listing_id,cpk,cpk_data,cpk_confidence)
                VALUES(:listing_id,:cpk,:data,:confidence)
                ON CONFLICT(listing_id) DO NOTHING
            """), {"listing_id": row["listing_id"], "cpk": cpk, "data": json.dumps(data), "confidence": confidence})
            await db.execute(text("""
                INSERT INTO gem_radar_cpk_listing_price(listing_id,cpk,price,updated_at)
                VALUES(:listing_id,:cpk,:price,CURRENT_TIMESTAMP)
                ON CONFLICT(listing_id) DO UPDATE SET cpk=excluded.cpk,price=excluded.price,updated_at=CURRENT_TIMESTAMP
            """), {"listing_id": row["listing_id"], "cpk": cpk, "price": row["delivered_price"]})
        await db.commit()
        print(f"applied=true categories_updated={len(categories)} cpks_inserted={len(exact)} backup_stamp={stamp}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
