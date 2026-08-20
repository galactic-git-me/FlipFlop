"""Generate the approved second batch of three catalogue models."""
from __future__ import annotations
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.api.assets_admin import generate_family_bucket_asset
from app.database import AsyncSessionLocal, engine

TARGETS = (("motherboard", "motherboard_matx"), ("ram", "ram_ddr4"), ("ram", "ram_ddr5"))

async def generate(category: str, family: str) -> None:
    async with AsyncSessionLocal() as db:
        print(f"START {category}/{family}", flush=True)
        try:
            asset = await generate_family_bucket_asset(category, family, SimpleNamespace(email="catalogue-meshy-batch-2"), db)
            print(f"DONE {category}/{family} asset={asset['id']}", flush=True)
        except Exception as exc:
            await db.rollback()
            print(f"FAIL {category}/{family}: {exc}", flush=True)

async def main() -> None:
    await asyncio.gather(*(generate(*target) for target in TARGETS))
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
