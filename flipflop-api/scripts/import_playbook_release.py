"""Import an owner-reviewed release bundle with identity remapping and rollback by default.

Only catalogue/Playbook tables are touched. Customer, order and payment data are
never imported. Run against a restored staging database before production.
"""
import asyncio
from copy import deepcopy
from datetime import datetime
import json
import sys
from pathlib import Path
from sqlalchemy import MetaData, Table, select, text
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import AsyncSessionLocal, engine
import app.models
from app.database import Base

MAPS = {}
JSON_ID_KEYS = {'variant_id':'variants','target_variant_id':'variants','base_variant_id':'variants',
    'from_variant_id':'variants','to_variant_id':'variants','listing_db_id':'listings',
    'slot_id':'slots','playbook_slot_id':'slots','playbook_id':'parents',
    'case_catalogue_id':'cases','case_id':'cases'}

def remap(value):
    if isinstance(value,list):return [remap(v) for v in value]
    if not isinstance(value,dict):return value
    result={}
    for key,item in value.items():
        if key in JSON_ID_KEYS and isinstance(item,int):item=MAPS[JSON_ID_KEYS[key]].get(item,item)
        elif key=='listing_id' and isinstance(item,int):item=MAPS['listings'].get(item,item)
        elif key in {'recommended_component_variant_ids','delivery_eligible_variant_ids'}:
            if isinstance(item,list):item=[MAPS['variants'].get(v,v) for v in item]
            elif isinstance(item,dict):item={m:[MAPS['variants'].get(v,v) for v in rows] for m,rows in item.items()}
        elif key=='components' and isinstance(item,dict) and all(isinstance(v,int) for v in item.values()):
            item={r:MAPS['variants'].get(v,v) for r,v in item.items()}
        else:item=remap(item)
        result[key]=item
    return result

def values(table,row):
    result={}
    for key,value in row.items():
        if key not in table.c or key=='id':continue
        col=table.c[key]
        if value is not None and isinstance(col.type, __import__('sqlalchemy').DateTime) and isinstance(value,str):
            value=datetime.fromisoformat(value.replace('Z','+00:00'))
        if value is not None and isinstance(col.type, __import__('sqlalchemy').Enum):
            cls=col.type.enum_class
            if cls:
                value=next((m.name if not col.type.values_callable else m.value for m in cls if value in {m.name,m.value}),value)
        def public_media(item):
            if isinstance(item,str):return item.replace('http://127.0.0.1:4311/api/3d-media/','https://www.theflipflop.shop/api/3d-media/').replace('http://127.0.0.1:4311/api/uploads/','https://www.theflipflop.shop/api/uploads/')
            if isinstance(item,list):return [public_media(v) for v in item]
            if isinstance(item,dict):return {k:public_media(v) for k,v in item.items()}
            return item
        result[key]=public_media(value)
    return result

async def upsert(db,table,row,identity):
    data=values(table,row)
    query=select(table.c.id)
    for key in identity:query=query.where(table.c[key]==data[key])
    found=(await db.execute(query.order_by(table.c.id.desc()).limit(1))).scalar_one_or_none()
    if found is None:
        return (await db.execute(table.insert().values(**data).returning(table.c.id))).scalar_one()
    await db.execute(table.update().where(table.c.id==found).values(**data))
    return found

async def main(bundle_path,apply=False):
    bundle=json.loads(Path(bundle_path).read_text(encoding='utf8'))
    assert bundle['schema_version']==1 and len(bundle['proposals'])==24
    assert engine.url.database in {'pcflipper','flipflop_release_20261027_test'}
    assert engine.url.host in {'postgres','127.0.0.1','localhost'}
    async with AsyncSessionLocal() as db:
        await db.execute(text('SELECT pg_advisory_xact_lock(61311,1)'))
        tables=Base.metadata.tables
        for group,table_name,identity in [('parents','playbooks',['name']),('slots','playbook_slots',['playbook_id','slot_type']),
            ('cases','case_catalogue',['name']),('listings','listings',['external_id']),('variants','catalogue_variants',['slot_id','listing_id'])]:
            MAPS[group]={}
            for original in bundle[group]:
                row=deepcopy(original)
                if group=='parents':
                    row['pricing_model']={**(row.get('pricing_model') or {}),'managed_offers':{},'commercial_cells':{},'mvp_autonomy':{**((row.get('pricing_model') or {}).get('mvp_autonomy') or {}),'enabled':False}}
                    row['packaging_playbook_id']=None
                if group=='slots':row['playbook_id']=MAPS['parents'][row['playbook_id']]
                if group=='listings' and row.get('case_catalogue_id'):row['case_catalogue_id']=MAPS['cases'][row['case_catalogue_id']]
                if group=='variants':
                    row['slot_id']=MAPS['slots'][row['slot_id']];row['listing_id']=MAPS['listings'][row['listing_id']]
                MAPS[group][original['id']]=await upsert(db,tables[table_name],row,identity)
            print(group,len(MAPS[group]),flush=True)
        for original in bundle['assets']:
            row=deepcopy(original)
            if row['subject_type']=='variant':row['subject_id']=MAPS['variants'].get(row['subject_id'])
            elif row['subject_type']=='case':row['subject_id']=MAPS['cases'].get(row['subject_id'])
            if row['subject_type'] in {'variant','case'} and row['subject_id'] is None:continue
            for key in ('glb_ref','preview_image_ref'):
                if isinstance(row.get(key),str):row[key]=row[key].replace('http://127.0.0.1:4311','https://www.theflipflop.shop')
            await upsert(db,tables['component_3d_assets'],row,['subject_type','subject_id','category','family_key','version','glb_ref'])
        for original in bundle['supplier_evidence']:
            row=deepcopy(original);kind,old=row['part_key'].split(':',1)
            mapping=MAPS['variants' if kind=='variant' else 'cases'];row['part_key']=f'{kind}:{mapping[int(old)]}'
            await upsert(db,tables['supplier_offer_evidence'],row,['part_key','evidence_source','evidence_ref'])
        for row in bundle['benchmarks']:
            await upsert(db,tables['hardware_benchmarks'],row,['component_type','normalized_model','model','benchmark_source'])
        from app.models.playbook import PlaybookProposal
        from app.services.playbook_service import fingerprint
        from app.services.playbook_mvp import commercial_revision_payload
        for original in bundle['proposals']:
            row=deepcopy(original);offer=remap(row['proposed_data'])
            offer['revision_sha256']=fingerprint(commercial_revision_payload(offer))
            row.update(playbook_id=MAPS['parents'][row['playbook_id']],proposed_data=offer,status='pending',resolved_at=None,resolved_by=None)
            old=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.playbook_id==row['playbook_id'],PlaybookProposal.status=='pending'))).scalars().all()
            target=next((p for p in old if (p.proposed_data or {}).get('cell_id')==offer['cell_id']),None)
            if target:
                target.proposed_data=offer;target.demand_signals=row['demand_signals']
            else:db.add(PlaybookProposal(**values(tables['playbook_proposals'],row)))
        await db.flush()
        print('24 remapped proposals; customer/order/payment tables untouched',flush=True)
        if apply:await db.commit();print('COMMITTED',flush=True)
        else:await db.rollback();print('DRY RUN ROLLED BACK',flush=True)
    await engine.dispose()

if __name__=='__main__':asyncio.run(main(sys.argv[1],'--apply' in sys.argv))
