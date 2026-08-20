"""Retry only the two failed first-batch catalogue models."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.assets_admin import generate_family_bucket_asset
from app.database import AsyncSessionLocal, engine


async def generate(category: str, family_key: str) -> None:
    async with AsyncSessionLocal() as db:
        print(f"START {category}/{family_key}", flush=True)
        try:
            asset = await generate_family_bucket_asset(
                category=category,
                family_key=family_key,
                admin=SimpleNamespace(email="catalogue-meshy-retry"),
                db=db,
            )
            print(f"DONE {category}/{family_key} asset={asset['id']}", flush=True)
        except Exception as exc:
            await db.rollback()
            print(f"FAIL {category}/{family_key}: {exc}", flush=True)


async def main() -> None:
    await asyncio.gather(
        generate("cpu", "cpu_intel"),
        generate("motherboard", "motherboard_atx"),
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
