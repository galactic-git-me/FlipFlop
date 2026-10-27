"""Recover the eight owner-reported DEV Meshy jobs; cache checks precede submission."""
import asyncio,json,sys
from types import SimpleNamespace
from fastapi import BackgroundTasks,HTTPException
from app.database import AsyncSessionLocal,engine
from app.config import get_settings
from app.models.catalogue import CatalogueVariant
from app.api.assets_admin import generate_variant_asset,VariantMeshyGenerate
TARGETS=[30485,12190,31189,53093,33997,33917,33925,34077]
async def job(variant_id,gate):
 async with gate:
  async with AsyncSessionLocal() as db:
   v=await db.get(CatalogueVariant,variant_id)
   generation=(v.asset_media_review or {}).get('generation') or {}
   old_status=generation.get('status')
   print(json.dumps({'event':'starting','variant_id':variant_id,'status':old_status,'resume_existing':bool(generation.get('task_id'))}),flush=True)
   if old_status=='DRAFT_CREATED':return
   tasks=BackgroundTasks()
   try:
    await generate_variant_asset(variant_id,VariantMeshyGenerate(notes='Owner-requested recovery of failed/stalled generation; preserve existing provider task where available.'),tasks,SimpleNamespace(email='operator-requested-recovery'),db)
   except HTTPException as exc:
    print(json.dumps({'event':'blocked','variant_id':variant_id,'detail':exc.detail}),flush=True);return
  await tasks()
  async with AsyncSessionLocal() as db:
   v=await db.get(CatalogueVariant,variant_id)
   g=(v.asset_media_review or {}).get('generation') or {}
   print(json.dumps({'event':'finished','variant_id':variant_id,'status':g.get('status'),'progress':g.get('progress'),'error':g.get('error')}),flush=True)
async def main():
 assert get_settings().app_env=='dev'
 if '--apply' not in sys.argv:
  print('Recovery targets:',TARGETS);return
 gate=asyncio.Semaphore(2)
 await asyncio.gather(*(job(v,gate) for v in TARGETS))
 await engine.dispose()
asyncio.run(main())
