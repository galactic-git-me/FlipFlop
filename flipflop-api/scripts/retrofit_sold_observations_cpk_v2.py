#!/usr/bin/env python3
"""
Retrofit v2: Map sold observations to listing CPKs by comparing match_keys against listing titles.
"""

import asyncio
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


def normalize_match_key(model: str) -> str:
    """Match the normalization in benchmarks.py"""
    return re.sub(r"[^A-Z0-9]", "", model.upper())


async def retrofit_cpk():
    """Map sold observations to listing CPKs by match_key similarity."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("Fetching listings with CPKs...")
        result = await db.execute(text("""
            SELECT glc.cpk, glo.title
            FROM gem_radar_listing_cpk glc
            JOIN gem_radar_listing_observations glo ON glc.listing_id = glo.listing_id
            LIMIT 20000
        """))
        listing_cpks = result.fetchall()

        print(f"Processing {len(listing_cpks)} listings...")

        # Get all distinct match_keys in sold_observations
        result = await db.execute(text("""
            SELECT DISTINCT match_key FROM gem_radar_sold_observations
        """))
        match_keys = set(row[0] for row in result.fetchall())

        print(f"Found {len(match_keys)} distinct match_keys")

        # For each match_key, find a listing title that contains its components
        # Strategy: match_key has no spaces/punctuation, so look for a listing
        # whose normalized title contains the match_key or vice versa
        match_key_to_cpk = {}

        for cpk, title in listing_cpks:
            normalized_title = normalize_match_key(title)

            # Check if any match_key is a substring (or similar) of this title
            for match_key in match_keys:
                if match_key in normalized_title or normalized_title in match_key or \
                   (len(match_key) > 4 and match_key[:4] in normalized_title) or \
                   (len(match_key) > 6 and match_key[:6] in normalized_title):
                    if match_key not in match_key_to_cpk:
                        match_key_to_cpk[match_key] = cpk

        print(f"\nMatched {len(match_key_to_cpk)} match_keys to listing CPKs")
        print(f"Unmatched: {len(match_keys) - len(match_key_to_cpk)}")

        # Update sold observations
        updated = 0
        for i, (match_key, cpk) in enumerate(match_key_to_cpk.items(), 1):
            await db.execute(text(f"""
                UPDATE gem_radar_sold_observations
                SET cpk = '{cpk}'
                WHERE match_key = '{match_key}'
            """))
            updated += 1

            if i % 100 == 0:
                print(f"  Updated {i}...")

        await db.commit()
        print(f"✓ Updated {updated} match_keys with listing CPKs")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(retrofit_cpk())
