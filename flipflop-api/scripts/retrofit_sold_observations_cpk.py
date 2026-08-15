#!/usr/bin/env python3
"""
Retrofit script: populate cpk field for all sold observations that have match_key but cpk = NULL.
Run once to fix the data pipeline, then delete this script.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.gem_radar_sold_observation import GemRadarSoldObservation
from app.models.gem_radar_listing_cpk import GemRadarListingCPK
from app.models.gem_radar_listing_observations import GemRadarListingObservation
from app.gem_radar.benchmarks import _get_cpk_for_match_key


async def retrofit_cpk():
    """Populate cpk for all sold observations with null cpk."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Query all sold observations with cpk = NULL
        result = await db.execute(
            select(GemRadarSoldObservation.id, GemRadarSoldObservation.match_key)
            .where(GemRadarSoldObservation.cpk.is_(None))
            .order_by(GemRadarSoldObservation.id)
        )
        rows = result.fetchall()

        if not rows:
            print("✓ No sold observations with null cpk found. All data is already retrofitted.")
            await engine.dispose()
            return

        print(f"Found {len(rows)} sold observations to retrofit...")

        updated = 0
        for i, (obs_id, match_key) in enumerate(rows, 1):
            cpk = await _get_cpk_for_match_key(db, match_key)

            if cpk:
                await db.execute(
                    update(GemRadarSoldObservation)
                    .where(GemRadarSoldObservation.id == obs_id)
                    .values(cpk=cpk)
                )
                updated += 1

            if i % 100 == 0:
                print(f"  Processed {i}/{len(rows)}...")

        await db.commit()
        print(f"✓ Retrofitted {updated}/{len(rows)} observations with cpk values")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(retrofit_cpk())
