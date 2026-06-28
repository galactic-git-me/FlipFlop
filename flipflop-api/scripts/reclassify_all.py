"""
Re-score every listing through the updated classifier.
Run with: docker exec flipflop-backend python scripts/reclassify_all.py
"""
import asyncio
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://flipper:flipper@db:5432/pcflipper")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
from app.models.listing import Listing, Classification
from app.services.classifier import score_listing
from app.config import get_settings


async def main():
    s = get_settings()
    engine = create_async_engine(s.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(select(Listing))
        listings = result.scalars().all()
        print(f"Re-scoring {len(listings)} listings...")

        updated = changed = 0
        component_purged = 0

        for l in listings:
            sr = score_listing(
                title=l.title or "",
                price=l.price or 0,
                estimated_profit=l.estimated_profit,
                cpu=l.cpu,
                ram_gb=l.ram_gb,
                ram_type=l.ram_type,
                storage_gb=l.storage_gb,
                gpu=l.gpu,
                has_psu=l.has_psu if l.has_psu is not None else True,
                location=l.location,
                profit_low=l.resale_low - (l.price or 0) - (l.estimated_upgrade_cost or 0) if l.resale_low else None,
                profit_high=l.resale_high - (l.price or 0) - (l.estimated_upgrade_cost or 0) if l.resale_high else None,
            )

            # If LLM already judged this listing, don't override the classification
            # unless it's a component-only (those should always be purged)
            if l.claude_judged_at and sr.classification != Classification.overpriced:
                continue

            old_class = l.classification
            l.gem_score = sr.score
            l.gem_signals = sr.signals
            l.classification = sr.classification

            if sr.classification == Classification.overpriced and old_class != Classification.overpriced:
                component_purged += 1

            if old_class != l.classification:
                changed += 1

            updated += 1

        await db.commit()
        print(f"Done. Updated {updated} listings, {changed} classification changes, {component_purged} newly marked as component-only/overpriced.")


asyncio.run(main())
