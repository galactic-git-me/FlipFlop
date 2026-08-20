"""Import the first Meshy batch (CPU AMD/Intel, Motherboard ATX) from review directory
into the component_3d_assets table as MESHY_DRAFT status.

Models are stored locally in assets/3d-models/review/meshy-first-batch/ and need to
be published to the public media directory before being registered in the database.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal, engine
from app.models.component_3d_asset import AssetSubjectType, Component3DAsset, Component3DAssetStatus
from app.services.media_sync import sync_to_public_media


WORKSPACE = Path(__file__).resolve().parents[2]
REVIEW_DIR = WORKSPACE / "assets/3d-models/review/meshy-first-batch"
PUBLIC_MEDIA_ROOT = WORKSPACE.parent / "FlipFlop.shop/public/media"
PUBLIC_MEDIA_URL = "https://theflipflop.shop/media"

# Map review filename (without extension) to (category, family_key, task_id)
FIRST_BATCH = {
    "cpu_amd": ("cpu", "cpu_amd", "01a01c8b-e2d9-7662-8c02-35928fc75fa0"),
    "cpu_intel": ("cpu", "cpu_intel", "01a01c8b-e8ff-7726-ab15-55697bd48630"),
    "motherboard_atx": ("motherboard", "motherboard_atx", "01a01c8b-e68e-7724-9992-1d3381945bdf"),
}


async def main() -> None:
    if not REVIEW_DIR.exists():
        raise FileNotFoundError(f"Review directory not found: {REVIEW_DIR}")
    PUBLIC_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    for family_name, (category, family_key, task_id) in FIRST_BATCH.items():
        glb_path = REVIEW_DIR / f"{family_name}.glb"
        png_path = REVIEW_DIR / f"{family_name}.png"

        if not glb_path.exists():
            print(f"SKIP {family_name}: GLB not found at {glb_path}")
            continue

        # Publish to public media
        glb_filename = f"catalogue-3d-{family_key}-v1.glb"
        glb_public_path = PUBLIC_MEDIA_ROOT / glb_filename
        shutil.copy2(glb_path, glb_public_path)
        if not await sync_to_public_media(glb_public_path):
            print(f"FAIL {family_name}: Could not publish GLB to public media")
            continue

        glb_url = f"{PUBLIC_MEDIA_URL}/{glb_filename}"
        file_size_kb = glb_path.stat().st_size // 1024
        preview_image_ref = None

        if png_path.exists():
            png_filename = f"catalogue-3d-{family_key}-v1.png"
            png_public_path = PUBLIC_MEDIA_ROOT / png_filename
            shutil.copy2(png_path, png_public_path)
            if await sync_to_public_media(png_public_path):
                preview_image_ref = f"{PUBLIC_MEDIA_URL}/{png_filename}"

        # Register in database
        async with AsyncSessionLocal() as db:
            asset = Component3DAsset(
                subject_type=AssetSubjectType.CATEGORY_GENERIC,
                subject_id=None,
                category=category,
                family_key=family_key,
                status=Component3DAssetStatus.MESHY_DRAFT,
                version=1,
                is_active=False,
                glb_ref=glb_url,
                preview_image_ref=preview_image_ref,
                source_image_refs=[],
                file_size_kb=file_size_kb,
                notes=f"Meshy multi-image task {task_id}; first trial batch generated 2026-08-13",
                created_by="batch-import-first",
                provenance_status="original-recreation",
                source_name=f"Meshy AI multi-image recreation (task {task_id})",
                source_url=None,
                commercial_use_approved=False,
                redistribution_approved=False,
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)
            print(f"DONE {family_name}: asset_id={asset.id} glb={glb_url} ({file_size_kb}kb)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
