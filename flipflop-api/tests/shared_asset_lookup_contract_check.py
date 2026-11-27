"""Family asset lookup retains identities without loading catalogue payloads."""
import asyncio
from types import SimpleNamespace
from app.models.component_3d_asset import AssetSubjectType
from app.services.shared_variant_assets import final_assets_by_variant


async def check():
    asset=SimpleNamespace(id=77,subject_type=AssetSubjectType.CATEGORY_GENERIC,
        category='cpu',family_key='cpu_amd',source_image_refs=[])
    queries=[]
    class Database:
        async def execute(self,query):
            queries.append(query)
            if len(queries)==1:
                return SimpleNamespace(all=lambda:[
                    (1,11,'AMD Ryzen 5 9600X','cpu',False),
                    (2,12,'AMD Ryzen 9 9950X','cpu',None),
                    (3,13,'AMD Ryzen 7 9700X','cpu',{'at':'2026-10-21','by':'owner'})])
            return SimpleNamespace(scalars=lambda:SimpleNamespace(all=lambda:[asset]))
    variants=[SimpleNamespace(id=i,status=status,asset_media_review={})
        for i,status in ((1,'active'),(2,'pending_review'),(3,'active'))]
    found=await final_assets_by_variant(Database(),variants)
    assert set(found)=={1} and found[1] is asset
    found=await final_assets_by_variant(Database(),variants,allow_pending_review=True)
    assert set(found)=={1,2} and all(row is asset for row in found.values())
    columns=list(queries[0].selected_columns)
    assert len(columns)==5, 'Family lookup fetches complete ORM catalogue rows'
    assert not any(str(column)=='listings.raw_specs' for column in columns)
    assert 'AS BOOLEAN' not in str(queries[0]), 'Deletion metadata is an object, not a SQL boolean'
    print('PASS: shared FINAL identity, deleted product exclusion, bounded column projection')


if __name__=='__main__':
    asyncio.run(check())
