"""Focused family-media contract checks. No provider calls; database writes roll back."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from app.services.component_media_identity import media_key, group_media_inventory, media_members, inherit_family_media_reviews
from app.services.shared_variant_assets import final_assets_by_variant
from app.models.component_3d_asset import Component3DAsset, Component3DAssetStatus, AssetSubjectType
from app.models.catalogue import CatalogueVariant
from app.database import engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

def check_identity():
    assert media_key('cpu','AMD Ryzen 5 9600X',1)==media_key('cpu','AMD Ryzen 9 9950X',2)
    assert media_key('cpu','Intel Core i5-14400',3)!=media_key('cpu','AMD Ryzen 5 9600X',1)
    assert media_key('case','Case',1)!=media_key('case','Case',2)
    assert media_key('storage','M.2 SATA SSD',1)!=media_key('storage_secondary','PCIe NVMe SSD',2)
    assert media_key('motherboard','ASUS M-ATX motherboard',1)[1]=='motherboard_asus'
    assert media_key('cooling','CPU cooler 120mm fan',1)[1]=='cooling_air_tower'
    rows=[dict(category='cpu',title=t,listing_id=i,variant_id=i,variant_ids=[i]) for i,t in enumerate(['AMD Ryzen 5','AMD Ryzen 9','Intel Core i5'],1)]
    grouped=group_media_inventory(rows)
    assert len(grouped)==2 and next(r for r in grouped if r['media_family_key']=='cpu_amd')['product_count']==2
    print('PASS: family identity, storage separation, cooler/board classification, grouping')

async def check_db():
    from app.config import get_settings
    assert get_settings().app_env=='dev'
    async with engine.connect() as conn:
        tx=await conn.begin()
        async with AsyncSession(bind=conn,expire_on_commit=False,join_transaction_mode='create_savepoint') as db:
            owner=(await db.execute(select(CatalogueVariant).where(CatalogueVariant.curated_for_builds.is_(True)).order_by(CatalogueVariant.id))).scalars().first()
            # Find a classified family with different physical catalogue listings.
            for candidate in (await db.execute(select(CatalogueVariant).where(CatalogueVariant.curated_for_builds.is_(True)))).scalars():
                category,family,members=await media_members(db,candidate)
                by_listing={v.listing_id:v for v in members if v.curated_for_builds}
                if category=='cpu' and not family.endswith('_unclassified') and len(by_listing)>1:
                    owner,other=list(by_listing.values())[:2];break
            else: raise AssertionError('Need two CPU products for DEV rollback check')
            photo='https://example.invalid/family-hardware.jpg'
            owner.asset_media_review={'status':'approved','media_scope':'family','media_family_key':family,'main_photo_approved_by':'contract-check','main_photo_approved_url':photo,'image_urls':[photo],'model_image_urls':[photo]}
            other.asset_media_review=None
            await inherit_family_media_reviews(db)
            assert other.asset_media_review['main_photo_approved_url']==photo
            owner.status=other.status='active'
            asset=Component3DAsset(subject_type=AssetSubjectType.CATEGORY_GENERIC,category=category,family_key=family,status=Component3DAssetStatus.FINAL,is_active=True,version=999999,glb_ref='https://example.invalid/shared.glb',source_image_refs=[photo])
            db.add(asset);await db.flush()
            found=await final_assets_by_variant(db,[owner,other])
            assert found[owner.id].id==found[other.id].id==asset.id
            # A family job queued through another SKU must block duplicate submission.
            for v in members:
                v.asset_media_review={**owner.asset_media_review,'generation':{'status':'STARTING','updated_at':__import__('datetime').datetime.utcnow().isoformat()}}
            await db.flush()
            from app.api.assets_admin import generate_variant_asset, VariantMeshyGenerate
            from fastapi import BackgroundTasks, HTTPException
            tasks=BackgroundTasks()
            try: await generate_variant_asset(other.id,VariantMeshyGenerate(),tasks,SimpleNamespace(email='contract-check'),db)
            except HTTPException as exc: assert exc.status_code==409
            else: raise AssertionError('Duplicate job allowed')
            assert not tasks.tasks
            print('PASS: cross-product photo inheritance, one FINAL family model, duplicate job guard')
        await tx.rollback()
    await engine.dispose()

if __name__=='__main__':
    check_identity();asyncio.run(check_db())
