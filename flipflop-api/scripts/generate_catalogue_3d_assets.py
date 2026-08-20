"""Generate every missing photo-backed catalogue component model with Meshy."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.assets_admin import generate_family_bucket_asset
from app.database import AsyncSessionLocal, engine
from app.models.component_3d_asset import Component3DAsset, Component3DAssetStatus
from app.services.component_family_classifier import KNOWN_FAMILY_BUCKETS


async def generate_one(semaphore: asyncio.Semaphore, category: str, family_key: str) -> None:
    async with semaphore, AsyncSessionLocal() as db:
        existing = (
            await db.execute(
                select(Component3DAsset.id).where(
                    Component3DAsset.category == category,
                    Component3DAsset.family_key == family_key,
                    Component3DAsset.status != Component3DAssetStatus.REJECTED,
                    Component3DAsset.glb_ref.isnot(None),
                ).limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            print(f"SKIP {category}/{family_key}: asset {existing} already exists", flush=True)
            return
        print(f"START {category}/{family_key}", flush=True)
        try:
            asset = await generate_family_bucket_asset(
                category=category,
                family_key=family_key,
                admin=SimpleNamespace(email="catalogue-meshy-batch"),
                db=db,
            )
            print(f"DONE  {category}/{family_key}: asset {asset['id']}", flush=True)
        except Exception as exc:
            await db.rollback()
            print(f"FAIL  {category}/{family_key}: {exc}", flush=True)


async def main() -> None:
    semaphore = asyncio.Semaphore(3)
    await asyncio.gather(
        *(generate_one(semaphore, category, family_key) for category, family_key in KNOWN_FAMILY_BUCKETS)
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
