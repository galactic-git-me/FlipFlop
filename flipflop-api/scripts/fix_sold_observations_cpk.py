#!/usr/bin/env python3
"""Retroactively link sold observations to CPKs based on matching titles.

This is a one-time migration for existing sold observations that were recorded
before their matching listings had CPKs assigned. The permanent fix is in
cpk_pipeline.py which updates sold observations when NEW listings assign their CPK.
"""
import asyncio
from sqlalchemy import select, text
from app.database import AsyncSessionLocal
from app.models.gem_radar_listing_cpk import GemRadarListingCpk
from app.models.gem_radar_observation import GemRadarListingObservation
from app.gem_radar.benchmarks import normalize_match_key


async def fix_sold_observations():
    async with AsyncSessionLocal() as db:
        print("Starting retroactive sold observation CPK linking...")

        # Get all listings with CPKs
        result = await db.execute(
            select(GemRadarListingCpk.cpk, GemRadarListingObservation.title)
            .join(
                GemRadarListingObservation,
                GemRadarListingCpk.listing_id == GemRadarListingObservation.listing_id,
            )
            .where(GemRadarListingCpk.cpk.isnot(None))
        )
        cpk_title_map = {}
        for cpk, title in result.fetchall():
            if title:
                match_key = normalize_match_key(title)
                if match_key not in cpk_title_map:
                    cpk_title_map[match_key] = cpk

        print(f"Found {len(cpk_title_map)} unique match_keys with CPKs")

        # Get all sold observations with NULL cpk
        result = await db.execute(
            text("""
                SELECT id, match_key FROM gem_radar_sold_observations
                WHERE cpk IS NULL
            """)
        )
        orphan_observations = result.fetchall()
        print(f"Found {len(orphan_observations)} orphan sold observations (cpk=NULL)")

        # Link sold observations to CPKs
        updates = 0
        for obs_id, match_key in orphan_observations:
            if match_key in cpk_title_map:
                cpk = cpk_title_map[match_key]
                await db.execute(
                    text("""
                        UPDATE gem_radar_sold_observations
                        SET cpk = :cpk
                        WHERE id = :id
                    """),
                    {"cpk": cpk, "id": obs_id},
                )
                updates += 1

        await db.commit()
        print(f"Updated {updates} sold observations with CPKs")

        # Verify
        result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN cpk IS NOT NULL THEN 1 ELSE 0 END) as with_cpk,
                    SUM(CASE WHEN cpk IS NULL THEN 1 ELSE 0 END) as without_cpk
                FROM gem_radar_sold_observations
            """)
        )
        total, with_cpk, without_cpk = result.fetchone()
        print(f"\nFinal status:")
        print(f"  Total sold observations: {total}")
        print(f"  With CPK: {with_cpk}")
        print(f"  Without CPK: {without_cpk}")


if __name__ == "__main__":
    asyncio.run(fix_sold_observations())
