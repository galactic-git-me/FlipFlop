#!/usr/bin/env python3
"""Audit controlled-LLM CPKs, quarantine vetoes and split value variants."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.gem_radar.cpk_extractor import canonical_variant_model
from app.gem_radar.opportunity_scoring import identity_gates


async def main() -> None:
    async with AsyncSessionLocal() as db:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        await db.execute(text(f"CREATE TABLE gem_radar_listing_cpk_variant_backup_{stamp} AS TABLE gem_radar_listing_cpk"))
        rows = (await db.execute(text("""
            SELECT c.listing_id,c.cpk,c.cpk_data,c.cpk_confidence,o.title
            FROM gem_radar_listing_cpk c
            JOIN LATERAL(SELECT title FROM gem_radar_listing_observations o
              WHERE o.listing_id=c.listing_id ORDER BY observed_at DESC,id DESC LIMIT 1)o ON TRUE
            WHERE c.cpk_data->>'extraction_method'='local_llm_controlled'
        """))).mappings().all()
        counts: Counter[str] = Counter()
        for row in rows:
            data = dict(row["cpk_data"])
            flags = [f for f in identity_gates(row["title"], data) if f != "identity_incomplete"]
            if flags:
                await db.execute(text("DELETE FROM gem_radar_cpk_listing_price WHERE listing_id=:id"), {"id": row["listing_id"]})
                await db.execute(text("DELETE FROM gem_radar_listing_cpk WHERE listing_id=:id"), {"id": row["listing_id"]})
                await db.execute(text("UPDATE gem_radar_identity_extraction_attempt SET outcome=:outcome,detail=:detail,attempted_at=CURRENT_TIMESTAMP WHERE listing_id=:id"), {
                    "id": row["listing_id"], "outcome": f"veto_post_audit:{flags[0]}", "detail": json.dumps({"flags": flags}),
                })
                counts[f"quarantined:{flags[0]}"] += 1
                continue
            model = canonical_variant_model(data["category"], data["model"], row["title"])
            cpk = hashlib.sha256(f"{data['category']}|{data['brand']}|{model}".encode()).hexdigest()[:16]
            if model != data["model"] or cpk != row["cpk"]:
                data["model"] = model
                data["cpk"] = cpk
                await db.execute(text("UPDATE gem_radar_listing_cpk SET cpk=:cpk,cpk_data=:data,updated_at=CURRENT_TIMESTAMP WHERE listing_id=:id"), {"cpk": cpk, "data": json.dumps(data), "id": row["listing_id"]})
                await db.execute(text("UPDATE gem_radar_cpk_listing_price SET cpk=:cpk,updated_at=CURRENT_TIMESTAMP WHERE listing_id=:id"), {"cpk": cpk, "id": row["listing_id"]})
                counts["variant_rekeyed"] += 1
            else:
                counts["unchanged"] += 1
        await db.commit()
        print({"reviewed": len(rows), "outcomes": dict(counts), "backup": f"gem_radar_listing_cpk_variant_backup_{stamp}"})


if __name__ == "__main__":
    asyncio.run(main())
