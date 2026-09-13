"""Safely map sold rows whose normalized key has exactly one CPK candidate."""
from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


async def run(dry_run: bool) -> dict:
    engine = create_async_engine(get_settings().database_url, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(text("""
            WITH candidates AS (
                SELECT regexp_replace(upper(coalesce(cpk_data->>'model', '')), '[^A-Z0-9]', '', 'g') AS match_key, cpk
                FROM gem_radar_listing_cpk
                WHERE cpk IS NOT NULL
                UNION
                SELECT regexp_replace(upper(coalesce(cpk_data->>'brand', '') || coalesce(cpk_data->>'model', '')), '[^A-Z0-9]', '', 'g'), cpk
                FROM gem_radar_listing_cpk
                WHERE cpk IS NOT NULL
            ), unique_keys AS (
                SELECT match_key, min(cpk) AS cpk
                FROM candidates
                WHERE length(match_key) >= 5
                GROUP BY match_key
                HAVING count(DISTINCT cpk) = 1
            )
            SELECT u.match_key, u.cpk, count(s.id) AS rows
            FROM unique_keys u
            JOIN gem_radar_sold_observations s ON s.match_key = u.match_key AND s.cpk IS NULL
            GROUP BY u.match_key, u.cpk
            ORDER BY count(s.id) DESC
        """))).mappings().all()
        updated = 0
        if not dry_run:
            for row in rows:
                result = await db.execute(text("""
                    UPDATE gem_radar_sold_observations
                    SET cpk = :cpk, identity_confidence = 0.9, updated_at = now()
                    WHERE match_key = :match_key AND cpk IS NULL
                """), {"cpk": row["cpk"], "match_key": row["match_key"]})
                updated += result.rowcount or 0
            await db.commit()
    await engine.dispose()
    return {"unique_keys": len(rows), "eligible_rows": sum(int(r["rows"]) for r in rows), "updated_rows": updated, "dry_run": dry_run}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.dry_run)), indent=2))


if __name__ == "__main__":
    main()
