"""Seed the Lian Li O11 Vision Compact case template (PRD reference build,
flipflop-3d-builder-claude-prd.md §6).

Geometry/mount layout here is an ORIGINAL RECREATION authored from published
envelope dimensions only (447.5 D x 287.5 W x 446.4 H mm, per Lian Li's public
spec sheet) — NOT derived from Lian Li's CAD archive, which the PRD's asset
register (§12) explicitly flags as requiring written licence permission before
any use. Mount point coordinates below are placeholder/approximate, laid out
to be dimensionally plausible within the real envelope — they are NOT
calibrated against the actual product and must be refined once a real
approved model (or calibration pass, PRD §6) exists. Safe to re-run.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.catalogue import CaseCatalogue
from app.models.component_3d_asset import Component3DAsset, AssetSubjectType, Component3DAssetStatus

CASE_NAME = "Lian Li O11 Vision Compact"

# PRD §6 envelope + clearance limits.
ENVELOPE_MM = (447.5, 287.5, 446.4)  # depth, width, height
MAX_GPU_LENGTH_MM = 408.0
MAX_COOLER_HEIGHT_MM = 167.0
MAX_PSU_LENGTH_MM = 220.0

# Approximate, non-calibrated mount layout — see module docstring.
MOUNTS = [
    {
        "id": "mobo-tray",
        "category": "Motherboard",
        "position_mm": (30.0, 0.0, 0.0),
        "rotation_deg": (0.0, 0.0, 0.0),
        "supported_formats": ["atx", "matx", "itx"],
    },
    {
        "id": "gpu-horizontal",
        "category": "GPU",
        "position_mm": (60.0, -40.0, 90.0),
        "rotation_deg": (0.0, 0.0, 0.0),
        "max_dimensions_mm": (MAX_GPU_LENGTH_MM, 150.0, 70.0),
    },
    {
        "id": "psu-chamber",
        "category": "PSU",
        "position_mm": (-180.0, 0.0, -150.0),
        "rotation_deg": (0.0, 0.0, 0.0),
        "max_dimensions_mm": (MAX_PSU_LENGTH_MM, 150.0, 86.0),
    },
    {
        "id": "cpu-cooler",
        "category": "CPUCooler",
        "position_mm": (30.0, 0.0, 20.0),
        "rotation_deg": (0.0, 0.0, 0.0),
        "max_dimensions_mm": (167.0, 167.0, MAX_COOLER_HEIGHT_MM),
    },
    {
        "id": "fan-top-1", "category": "CaseFan",
        "position_mm": (60.0, -60.0, 220.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-top-2", "category": "CaseFan",
        "position_mm": (60.0, 0.0, 220.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-top-3", "category": "CaseFan",
        "position_mm": (60.0, 60.0, 220.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-side-1", "category": "CaseFan",
        "position_mm": (60.0, 140.0, 60.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-side-2", "category": "CaseFan",
        "position_mm": (60.0, 140.0, 0.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-side-3", "category": "CaseFan",
        "position_mm": (60.0, 140.0, -60.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-bottom-1", "category": "CaseFan",
        "position_mm": (60.0, -60.0, -220.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-bottom-2", "category": "CaseFan",
        "position_mm": (60.0, 0.0, -220.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-bottom-3", "category": "CaseFan",
        "position_mm": (60.0, 60.0, -220.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-rear-1", "category": "CaseFan",
        "position_mm": (-220.0, -30.0, 90.0), "fan_size_mm": 120,
    },
    {
        "id": "fan-rear-2", "category": "CaseFan",
        "position_mm": (-220.0, 30.0, 90.0), "fan_size_mm": 120,
    },
]


async def main():
    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(CaseCatalogue).where(CaseCatalogue.name == CASE_NAME))
        ).scalar_one_or_none()

        depth, width, height = ENVELOPE_MM
        if existing:
            case = existing
            print(f"Updating existing case row id={case.id}")
        else:
            case = CaseCatalogue(
                name=CASE_NAME,
                brand="Lian Li",
                form_factor="atx",
                rrp_gbp=109.00,
                is_transparent_panel=True,
                status="active",
            )
            db.add(case)
            print("Creating new case row")

        case.depth_mm = depth
        case.width_mm = width
        case.height_mm = height
        case.max_gpu_length_mm = MAX_GPU_LENGTH_MM
        case.max_cooler_height_mm = MAX_COOLER_HEIGHT_MM
        case.colour = "black"
        case.style_tags = ["premium", "showcase", "compact-atx"]
        await db.flush()

        manifest = {
            "case_envelope_mm": list(ENVELOPE_MM),
            "max_gpu_length_mm": MAX_GPU_LENGTH_MM,
            "max_cooler_height_mm": MAX_COOLER_HEIGHT_MM,
            "max_psu_length_mm": MAX_PSU_LENGTH_MM,
            "mounts": MOUNTS,
        }

        existing_asset = (
            await db.execute(
                select(Component3DAsset).where(
                    Component3DAsset.subject_type == AssetSubjectType.CASE,
                    Component3DAsset.subject_id == case.id,
                )
            )
        ).scalar_one_or_none()

        if existing_asset:
            asset = existing_asset
            print(f"Updating existing Component3DAsset id={asset.id}")
        else:
            asset = Component3DAsset(
                subject_type=AssetSubjectType.CASE,
                subject_id=case.id,
                status=Component3DAssetStatus.MISSING,  # no GLB yet — mount data only
            )
            db.add(asset)
            print("Creating new Component3DAsset row (mount data only, no GLB yet)")

        asset.anchor_manifest_json = manifest
        asset.dimensions_mm = {"w": width, "h": height, "d": depth}
        # Original recreation from published dimensions only — not derived
        # from Lian Li's CAD archive, so no external licence approval is
        # needed for this data; it's an in-house layout, not a copy.
        asset.provenance_status = "dimensionally-accurate-proxy"
        asset.source_name = "flipflop original recreation from published Lian Li spec sheet"
        asset.source_url = "https://lian-li.com/product/o11-vision-compact/"
        asset.commercial_use_approved = True
        asset.redistribution_approved = True
        asset.notes = (
            "Mount coordinates are an approximate, non-calibrated original layout — "
            "see docs/3d-asset-pipeline.md calibration mode before treating as exact."
        )

        await db.commit()
        print(f"Done. case_id={case.id} asset_id={asset.id}")


if __name__ == "__main__":
    asyncio.run(main())
