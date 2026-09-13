"""Apply only deterministic identity proposals.

By default this updates proposals created from exact identifiers (GTIN/MPN/
model) at confidence >= .95. Title-only and ambiguous proposals are left for
manual review. Use ``--dry-run`` to inspect the count before writing.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


async def run(limit: int, dry_run: bool) -> dict:
    engine = create_async_engine(get_settings().database_url, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(text("""
            SELECT p.id, p.sold_observation_id, p.suggested_cpk
            FROM gem_radar_identity_proposals p
            JOIN gem_radar_sold_observations s ON s.id = p.sold_observation_id
            WHERE p.status = 'pending'
              AND p.method = 'exact_identifier'
              AND p.confidence >= 0.95
              AND p.suggested_cpk IS NOT NULL
              AND s.cpk IS NULL
            ORDER BY p.id
            LIMIT :limit
        """), {"limit": limit})).mappings().all()
        if not dry_run:
            for row in rows:
                updated = await db.execute(text("""
                    UPDATE gem_radar_sold_observations
                    SET cpk = :cpk, identity_confidence = :confidence, updated_at = now()
                    WHERE id = :sold_id AND cpk IS NULL
                """), {"cpk": row["suggested_cpk"], "confidence": 0.99, "sold_id": row["sold_observation_id"]})
                if updated.rowcount:
                    await db.execute(text("""
                        UPDATE gem_radar_identity_proposals
                        SET status = 'approved', reviewer = 'deterministic-identifier',
                            reviewed_at = now(), updated_at = now()
                        WHERE id = :id
                    """), {"id": row["id"]})
            await db.commit()
    await engine.dispose()
    return {"eligible": len(rows), "dry_run": dry_run}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(max(1, args.limit), args.dry_run)), indent=2))


if __name__ == "__main__":
    main()
