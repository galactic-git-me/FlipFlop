"""Regenerate first Meshy batch with textures enabled."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

from sqlalchemy import select, delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.assets_admin import generate_family_bucket_asset
from app.database import AsyncSessionLocal, engine
from app.models.component_3d_asset import Component3DAsset


async def regenerate() -> None:
    """Delete old textured-less models and regenerate with textures."""
    families = [
        ("cpu", "cpu_amd"),
        ("cpu", "cpu_intel"),
        ("motherboard", "motherboard_atx"),
    ]

    async with AsyncSessionLocal() as db:
        # Delete old models so they'll be regenerated
        for category, family_key in families:
            await db.execute(
                delete(Component3DAsset).where(
                    Component3DAsset.category == category,
                    Component3DAsset.family_key == family_key,
                )
            )
            await db.commit()
            print(f"DELETED {category}/{family_key}", flush=True)

    # Regenerate with textures
    semaphore = asyncio.Semaphore(1)  # One at a time to avoid API limits
    async with AsyncSessionLocal() as db:
        for category, family_key in families:
            async with semaphore:
                print(f"REGENERATING {category}/{family_key}", flush=True)
                try:
                    asset = await generate_family_bucket_asset(
                        category=category,
                        family_key=family_key,
                        admin=SimpleNamespace(email="regenerate-with-textures"),
                        db=db,
                    )
                    print(f"DONE {category}/{family_key}: asset {asset['id']}", flush=True)
                except Exception as exc:
                    await db.rollback()
                    print(f"FAIL {category}/{family_key}: {exc}", flush=True)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(regenerate())
