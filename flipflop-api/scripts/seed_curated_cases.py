"""Seed the ten launch cases for the Curated Builds configurator.

The dimensions and clearances are manufacturer-published specifications.
Prices are launch catalogue guide prices and remain editable in the admin;
they are not supplier quotations. Safe to run repeatedly.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.catalogue import CaseCatalogue
from app.models.component_3d_asset import Component3DAsset, AssetSubjectType, Component3DAssetStatus


CASES = [
    dict(name="O11 Vision Compact", brand="Lian Li", rrp_gbp=109.00,
         depth_mm=447.5, width_mm=287.5, height_mm=446.4, max_gpu_length_mm=408, max_cooler_height_mm=167,
         radiator_support={"top": [240, 280, 360], "side": [240, 360], "bottom": [240, 360]},
         style_tags=["showcase", "dual-chamber", "premium"], rgb_zones=0,
         source="https://lian-li.com/product/o11-vision-compact/"),
    dict(name="North", brand="Fractal Design", rrp_gbp=129.99,
         depth_mm=447, width_mm=215, height_mm=469, max_gpu_length_mm=355, max_cooler_height_mm=170,
         radiator_support={"front": [240, 280, 360], "top": [240], "rear": [120]},
         style_tags=["wood", "minimal", "airflow"], rgb_zones=0,
         source="https://www.fractal-design.com/products/cases/north/north/"),
    dict(name="H6 Flow", brand="NZXT", rrp_gbp=99.99,
         depth_mm=435, width_mm=287, height_mm=415, max_gpu_length_mm=365, max_cooler_height_mm=163,
         radiator_support={"top": [240, 280, 360], "rear": [120]},
         style_tags=["panoramic", "compact", "airflow"], rgb_zones=0,
         source="https://nzxt.com/product/h6-flow"),
    dict(name="3500X", brand="Corsair", rrp_gbp=89.99,
         depth_mm=460, width_mm=240, height_mm=506, max_gpu_length_mm=425, max_cooler_height_mm=170,
         radiator_support={"top": [240, 280, 360], "side": [240, 280, 360], "rear": [120]},
         style_tags=["panoramic", "showcase", "back-connect"], rgb_zones=0,
         source="https://www.corsair.com/uk/en/p/pc-cases/cc-9011276-ww/3500x-mid-tower-pc-case-cc-9011276-ww"),
    dict(name="XT View", brand="Phanteks", rrp_gbp=79.99,
         depth_mm=440, width_mm=230, height_mm=500, max_gpu_length_mm=415, max_cooler_height_mm=184,
         radiator_support={"top": [360], "side": [240], "rear": [120]},
         style_tags=["panoramic", "value", "airflow"], rgb_zones=1,
         source="https://phanteks.com/product/xt-view-black/"),
    dict(name="KING 95 PRO", brand="Montech", rrp_gbp=129.99,
         depth_mm=475, width_mm=300, height_mm=442, max_gpu_length_mm=420, max_cooler_height_mm=175,
         radiator_support={"top": [240, 280, 360], "side": [240, 280], "bottom": [240, 280, 360], "rear": [120]},
         style_tags=["panoramic", "rgb", "dual-chamber"], rgb_zones=6,
         source="https://www.montechpc.com/king-95-pro"),
    dict(name="Light Base 600 LX", brand="be quiet!", rrp_gbp=159.99,
         depth_mm=450, width_mm=305, height_mm=455, max_gpu_length_mm=400, max_cooler_height_mm=170,
         radiator_support={"top": [120, 240, 360], "side": [120, 240], "bottom": [120, 240, 360], "rear": [120]},
         style_tags=["panoramic", "rgb", "invertible"], rgb_zones=5,
         source="https://www.bequiet.com/en/case/5294"),
    dict(name="Y60", brand="HYTE", rrp_gbp=179.99,
         depth_mm=456, width_mm=285, height_mm=462, max_gpu_length_mm=375, max_cooler_height_mm=160,
         radiator_support={"top": [120, 240, 280, 360], "side": [120, 140, 240, 280], "rear": [120]},
         style_tags=["panoramic", "premium", "vertical-gpu"], rgb_zones=0,
         source="https://hyte.com/store/y60/cs-hyte-y60"),
    dict(name="Pop 2 Air", brand="Fractal Design", rrp_gbp=79.99,
         depth_mm=481, width_mm=215, height_mm=462, max_gpu_length_mm=416, max_cooler_height_mm=170,
         radiator_support={"top": [120, 240, 360], "rear": [120]},
         style_tags=["airflow", "value", "minimal"], rgb_zones=0,
         source="https://www.fractal-design.com/products/cases/pop/pop-2-air/"),
    dict(name="MasterBox TD500 Mesh V2", brand="Cooler Master", rrp_gbp=99.99,
         depth_mm=499, width_mm=210, height_mm=500, max_gpu_length_mm=410, max_cooler_height_mm=165,
         radiator_support={"front": [120, 140, 240, 280, 360], "top": [120, 140, 240, 280, 360], "rear": [120]},
         style_tags=["airflow", "rgb", "mesh"], rgb_zones=3,
         source="https://www.coolermaster.com/en-global/products/masterbox-td500-mesh-v2/"),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for item in CASES:
            source = item["source"]
            result = await db.execute(select(CaseCatalogue).where(
                CaseCatalogue.brand == item["brand"], CaseCatalogue.name == item["name"]
            ))
            case = result.scalar_one_or_none()
            if case is None and item["name"] == "O11 Vision Compact":
                alias_result = await db.execute(select(CaseCatalogue).where(
                    CaseCatalogue.name == "Lian Li O11 Vision Compact"
                ))
                case = alias_result.scalar_one_or_none()
            if case is None:
                case = CaseCatalogue(brand=item["brand"], name=item["name"], form_factor="atx", rrp_gbp=item["rrp_gbp"])
                db.add(case)
            for key, value in item.items():
                if key == "source":
                    continue
                setattr(case, key, value)
            case.status = "active"
            case.is_transparent_panel = True
            case.notes = f"Launch Curated Build case. Manufacturer specifications: {source}"
            await db.flush()
            asset_result = await db.execute(select(Component3DAsset).where(
                Component3DAsset.subject_type == AssetSubjectType.CASE,
                Component3DAsset.subject_id == case.id,
            ))
            asset = asset_result.scalar_one_or_none()
            if asset is None:
                asset = Component3DAsset(
                    subject_type=AssetSubjectType.CASE,
                    subject_id=case.id,
                    status=Component3DAssetStatus.MISSING,
                )
                db.add(asset)
            asset.dimensions_mm = {"w": case.width_mm, "h": case.height_mm, "d": case.depth_mm}
            asset.source_name = case.brand
            asset.source_url = source
            asset.notes = "Queued for image-to-3D generation after source-image and commercial-use review."
        await db.commit()
        print(f"Seeded {len(CASES)} curated cases")


if __name__ == "__main__":
    asyncio.run(main())
