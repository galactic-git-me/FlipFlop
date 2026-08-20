"""Idempotently register the user-supplied Geometric Future M5 web model."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import shutil
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal, engine
from app.models.catalogue import CaseCatalogue
from app.models.component_3d_asset import AssetSubjectType, Component3DAsset, Component3DAssetStatus
from app.services.media_sync import sync_to_public_media


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "assets/3d-models/chassis/geometric-future/model-5-geo-m5-bny-black-green-web.glb"
PUBLIC_DIR = WORKSPACE.parent / "FlipFlop.shop/public/media"
PUBLIC_NAME = "case-geometric-future-model-5-geo-m5-bny-black-green.glb"
PUBLIC_URL = f"https://theflipflop.shop/media/{PUBLIC_NAME}"
AMAZON_URL = "https://www.amazon.co.uk/dp/B0DF7RVRW2"


async def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    public_path = PUBLIC_DIR / PUBLIC_NAME
    shutil.copy2(SOURCE, public_path)
    if not await sync_to_public_media(public_path):
        raise RuntimeError("Could not publish the chassis GLB")

    async with AsyncSessionLocal() as db:
        case = (
            await db.execute(select(CaseCatalogue).where(CaseCatalogue.name == "Model 5 Black/Green"))
        ).scalar_one_or_none()
        if not case:
            now = datetime.utcnow().isoformat()
            case = CaseCatalogue(
                name="Model 5 Black/Green",
                brand="Geometric Future",
                form_factor="atx",
                images=[],
                rrp_gbp=109.99,
                is_transparent_panel=True,
                status="active",
                notes=(
                    "GEO-M5-BNY; Amazon UK ASIN B0DF7RVRW2. Supplier offer is eligible only when "
                    "Prime next-day delivery is confirmed for TW12 1JQ. " + AMAZON_URL
                ),
                height_mm=440,
                width_mm=242,
                depth_mm=480,
                max_gpu_length_mm=460,
                max_cooler_height_mm=180,
                radiator_support={"top": [360, 420], "bottom": [360], "rear": [120, 140]},
                style_tags=["showcase", "dual-chamber", "black", "green"],
                colour="black/green",
                created_at=now,
                updated_at=now,
            )
            db.add(case)
            await db.flush()

        asset = (
            await db.execute(
                select(Component3DAsset).where(
                    Component3DAsset.subject_type == AssetSubjectType.CASE,
                    Component3DAsset.subject_id == case.id,
                    Component3DAsset.glb_ref == PUBLIC_URL,
                )
            )
        ).scalar_one_or_none()
        if not asset:
            asset = Component3DAsset(
                subject_type=AssetSubjectType.CASE,
                subject_id=case.id,
                status=Component3DAssetStatus.CLEANED,
                version=1,
                is_active=False,
                glb_ref=PUBLIC_URL,
                file_size_kb=max(1, public_path.stat().st_size // 1024),
                notes="User-supplied textured Meshy model; web-optimised. Scale/orientation review still required.",
                created_by="user-supplied-import",
                provenance_status="original-recreation",
                source_name="User-supplied Meshy textured GLB",
                source_url=AMAZON_URL,
                commercial_use_approved=False,
                redistribution_approved=False,
            )
            db.add(asset)
        await db.commit()
        print(f"case_id={case.id} asset_id={asset.id} glb={PUBLIC_URL}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
