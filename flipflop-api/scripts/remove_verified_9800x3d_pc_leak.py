"""Remove one exact, reviewed complete-PC listing from the 9800X3D CPK."""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.gem_radar.identity import is_full_system_listing

CPK = "17f0f6a336174b115a2ff33e6048a844"
LISTING_ID = "377260954118"
TITLE = "Avatar The Last Airbender Collectible PC. (AMD Ryzen 7 9800X3D/MSI RTX 5070Ti)"


async def run(apply: bool) -> dict:
    async with engine.begin() as db:
        await db.execute(text("SET TRANSACTION READ WRITE" if apply else "SET TRANSACTION READ ONLY"))
        context = (await db.execute(text("SELECT current_database() name,inet_server_addr()::text address"))).mappings().one()
        address = (context["address"] or "").split("/", 1)[0]
        if apply and (not address or not ipaddress.ip_address(address).is_loopback):
            raise RuntimeError("--apply is restricted to loopback PostgreSQL")
        row = (await db.execute(text("""
            SELECT c.listing_id,c.cpk,c.cpk_data,p.price
            FROM gem_radar_listing_cpk c
            LEFT JOIN gem_radar_cpk_listing_price p USING(listing_id)
            WHERE c.listing_id=:id AND c.cpk=:cpk
        """), {"id": LISTING_ID, "cpk": CPK})).mappings().first()
        if not row:
            raise RuntimeError("Expected exact PC assignment not found")
        title = (await db.execute(text("""
            SELECT title FROM gem_radar_listing_observations
            WHERE listing_id=:id ORDER BY observed_at DESC,id DESC LIMIT 1
        """), {"id": LISTING_ID})).scalar_one_or_none()
        if title != TITLE or not is_full_system_listing(title):
            raise RuntimeError("Exact title/system gate failed")
        report = {"database": context["name"], "address": address, "apply": apply,
                  "listing_id": LISTING_ID, "title": title, "category": "complete_pc",
                  "old_cpk": CPK, "price": row["price"]}
        if not apply:
            return report

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backups = []
        for table, suffix in (("gem_radar_listing_cpk", "assignment"),
                              ("gem_radar_cpk_listing_price", "price"),
                              ("gem_radar_scored_listings", "scored")):
            name = f"ff_verified_9800x3d_pc_{suffix}_{stamp}"
            await db.execute(text(f"CREATE TABLE {name} AS SELECT * FROM {table} WHERE listing_id=:id"), {"id": LISTING_ID})
            backups.append(name)
        market_backup = f"ff_verified_9800x3d_pc_market_{stamp}"
        await db.execute(text(f"CREATE TABLE {market_backup} AS SELECT * FROM gem_radar_cpk_market_price WHERE cpk=:cpk"), {"cpk": CPK})
        backups.append(market_backup)

        await db.execute(text("DELETE FROM gem_radar_listing_cpk WHERE listing_id=:id AND cpk=:cpk"), {"id": LISTING_ID, "cpk": CPK})
        await db.execute(text("DELETE FROM gem_radar_cpk_listing_price WHERE listing_id=:id AND cpk=:cpk"), {"id": LISTING_ID, "cpk": CPK})
        await db.execute(text("""
            UPDATE gem_radar_scored_listings SET cpk=NULL,classification='INELIGIBLE',
                deal_score=0,evidence_reason='complete_system_not_component',
                reasoning_summary='Complete PC; excluded from standalone component pricing.'
            WHERE listing_id=:id
        """), {"id": LISTING_ID})
        from app.gem_radar.cpk_market import recompute_market_price
        await recompute_market_price(db, CPK, category="cpu", brand="amd", model="amd_ryzen_9800x3d")
        market = (await db.execute(text("SELECT listing_count,min_price,median_price,max_price FROM gem_radar_cpk_market_price WHERE cpk=:cpk"), {"cpk": CPK})).mappings().one()
        report["backups"] = backups
        report["after_market"] = dict(market)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    print(json.dumps(asyncio.run(run(parser.parse_args().apply)), indent=2, sort_keys=True))
