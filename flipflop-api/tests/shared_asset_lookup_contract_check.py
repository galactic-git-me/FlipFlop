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
    variants=[SimpleNamespace(id=i,status='active',asset_media_review={}) for i in (1,2,3)]
    found=await final_assets_by_variant(Database(),variants)
    assert set(found)=={1,2} and found[1] is found[2] is asset
    columns=list(queries[0].selected_columns)
    assert len(columns)==5, 'Family lookup fetches complete ORM catalogue rows'
    assert not any(str(column)=='listings.raw_specs' for column in columns)
    assert 'AS BOOLEAN' not in str(queries[0]), 'Deletion metadata is an object, not a SQL boolean'
    print('PASS: shared FINAL identity, deleted product exclusion, bounded column projection')


if __name__=='__main__':
    asyncio.run(check())
