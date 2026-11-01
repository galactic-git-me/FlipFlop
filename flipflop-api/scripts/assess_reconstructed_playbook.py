"""Read-only exact-offer assessment of the dated reconstructed draft.

Does not replace runtime definitions, persist proposals, approve or publish.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select,text
from app.database import AsyncSessionLocal,engine
from app.models.playbook import Playbook
from app.models.app_settings import AppSettings
from app.services.curated_build_policy import definitions
from app.services.playbook_service import _catalogue_candidates,build_cell_offer
from app.services.hardware_performance import load_benchmark_context

ROOT=Path(__file__).resolve().parents[2]/'docs/playbook/specifications/2026-10-22'
async def main():
 spec=json.loads((ROOT/'specifications.json').read_text(encoding='utf-8'))
 active={row['id']:row for row in definitions()['builds']}
 result={'observed_at':datetime.now(timezone.utc).isoformat(),'specification_version':spec['specification_version'],
         'runtime_modified':False,'published':False,'cells':[]}
 try:
  async with AsyncSessionLocal() as db:
   await db.execute(text('SET TRANSACTION READ ONLY'))
   parents={p.name:p for p in (await db.execute(select(Playbook).where(Playbook.status=='active'))).scalars()}
   settings=await db.get(AppSettings,1)
   benchmarks,_=await load_benchmark_context(db)
   pools={};cache={}
   for cell in spec['cells']:
    if cell['lifecycle']=='withheld':
     result['cells'].append({'cell_id':cell['id'],'disposition':'withheld','owner_scope_approved':True})
     continue
    if cell['lifecycle']=='shared_offer':
     result['cells'].append({'cell_id':cell['id'],'disposition':'shared_offer','shared_with':'FF-HPG-01','owner_scope_approved':True})
     continue
    parent=parents[cell['segment']]
    if parent.id not in pools:pools[parent.id]=await _catalogue_candidates(db,parent.id,'curated',cache)
    definition=deepcopy(active[cell['id']])
    definition['components']={role:product['recommended'] for role,product in cell['products'].items()}
    definition['constraints']=cell['constraints']
    definition['description']=cell['tier_benefit']
    definition['use']='; '.join(cell['workloads'])
    offer=await build_cell_offer(db,definition,parent,settings,pools[parent.id],benchmarks)
    offer['capability_profile']=cell['capability_tier']
    offer['legacy_tier']=definition['tier']
    offer['workload_acceptance_verified']=False
    offer['blockers'].append('Named workload acceptance tests have not been measured on the exact assembled build')
    result['cells'].append(offer)
    print(json.dumps({'cell':cell['id'],'parts':len(offer['components']),'blockers':len(offer['blockers'])}),flush=True)
  target=ROOT/'release'/('reconstructed-readiness-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
  target.write_text(json.dumps(result,default=str,indent=2)+'\n',encoding='utf-8')
  print('REPORT '+str(target),flush=True)
 finally:await engine.dispose()
if __name__=='__main__':asyncio.run(main())
