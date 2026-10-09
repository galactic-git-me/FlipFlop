"""Move confidently identified standalone fans out of legacy case CPKs.

Preview by default; pass --apply to update the DEV database transactionally.
The old case-based opportunity score is invalidated until the next Phase 2 run.
"""
import argparse
import asyncio
import json

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.gem_radar.cpk_market import upsert_listing_price
from app.gem_radar.fan_category import correct_case_fan_cpk


async def run(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT c.listing_id, c.cpk, c.cpk_data, s.title, s.delivered_price
            FROM gem_radar_listing_cpk c
            JOIN LATERAL (
                SELECT title, delivered_price FROM gem_radar_scored_listings
                WHERE listing_id = c.listing_id ORDER BY scored_at DESC, id DESC LIMIT 1
            ) s ON TRUE
            WHERE c.cpk_data->>'category' = 'case'
        """))).all()
        changes = []
        for listing_id, old_cpk, data, title, price in rows:
            new_cpk, corrected = correct_case_fan_cpk(title, data)
            if corrected.get("category") == "fan" and new_cpk != old_cpk:
                changes.append((listing_id, old_cpk, new_cpk, corrected, price))
        print(f"case identities examined={len(rows)}; fan corrections={len(changes)}; old CPKs={len({r[1] for r in changes})}")
        if not apply:
            return
        old_cpks = {row[1] for row in changes}
        for listing_id, _old, new_cpk, data, price in changes:
            await db.execute(text("""
                UPDATE gem_radar_listing_cpk SET cpk=:cpk, cpk_data=CAST(:data AS jsonb),
                    updated_at=CURRENT_TIMESTAMP WHERE listing_id=:id
            """), {"cpk": new_cpk, "data": json.dumps(data), "id": listing_id})
            await db.execute(text("""
                UPDATE gem_radar_scored_listings SET cpk=:cpk, category='fan',
                    classification='INSUFFICIENT_DATA', decision='INVESTIGATE', deal_score=0,
                    expected_profit=NULL, roi_pct=NULL, walk_away_price=NULL,
                    market_lower_price=NULL, market_median_price=NULL, market_upper_price=NULL,
                    conservative_resale_price=NULL, pct_offset=NULL,
                    evidence_status='INSUFFICIENT_DATA', evidence_reason='category_corrected_pending_rescore',
                    scoring_explanation=CAST(:explanation AS jsonb), updated_at=CURRENT_TIMESTAMP
                WHERE listing_id=:id
            """), {"cpk": new_cpk, "id": listing_id, "explanation": json.dumps({"reasons": ["Fan identity corrected; awaiting fresh market scoring."], "market": None})})
            if price is not None and price > 0:
                await upsert_listing_price(db, new_cpk, listing_id, float(price), "fan", data["brand"], data["model"])
            else:
                await db.execute(text("UPDATE gem_radar_cpk_listing_price SET cpk=:cpk WHERE listing_id=:id"), {"cpk": new_cpk, "id": listing_id})
        # Old case market caches must not retain prices that belonged to fans.
        for old_cpk in old_cpks:
            remaining = (await db.execute(text("""
                SELECT p.listing_id, p.price, c.cpk_data FROM gem_radar_cpk_listing_price p
                JOIN gem_radar_listing_cpk c ON c.listing_id=p.listing_id
                WHERE p.cpk=:cpk ORDER BY p.updated_at DESC LIMIT 1
            """), {"cpk": old_cpk})).first()
            if remaining:
                data = remaining[2] or {}
                await upsert_listing_price(db, old_cpk, remaining[0], float(remaining[1]), data.get("category"), data.get("brand"), data.get("model"))
            else:
                await db.execute(text("DELETE FROM gem_radar_cpk_market_price WHERE cpk=:cpk"), {"cpk": old_cpk})
        await db.commit()
        print(f"committed corrections={len(changes)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
