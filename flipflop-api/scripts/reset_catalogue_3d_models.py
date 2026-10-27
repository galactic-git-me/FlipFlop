"""Reset DEV catalogue models, preserving all pre-built model references and photos."""
import asyncio,json,os,shutil
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,unquote
from sqlalchemy import select,delete
from app.config import get_settings
from app.database import AsyncSessionLocal,engine
from app.models.component_3d_asset import Component3DAsset
from app.models.manual_build import ManualBuild
from app.models.product import Product
from app.models.case import Case
from app.models.catalogue import CatalogueVariant

def refs(value):
 if isinstance(value,str):
  return {value} if urlsplit(value).path.lower().endswith(('.glb','.gltf')) else set()
 if isinstance(value,dict):return set().union(*(refs(v) for v in value.values())) if value else set()
 if isinstance(value,list):return set().union(*(refs(v) for v in value)) if value else set()
 return set()
def name(url):return Path(unquote(urlsplit(url).path)).name

def snapshot(row):
 return {c.name:getattr(row,c.name) for c in row.__table__.columns}
def encode(value):
 if hasattr(value,'value'):return value.value
 if hasattr(value,'isoformat'):return value.isoformat()
 raise TypeError(type(value).__name__)

async def main(apply=False):
 assert get_settings().app_env=='dev','DEV only'
 workspace=Path(__file__).resolve().parents[2]
 roots=[workspace/'flipflop-api/data/3d-media',workspace/'FlipFlop.shop/public/media',workspace.parent/'FlipFlop.shop/public/media']
 roots=[p.resolve() for p in roots if p.is_dir()]
 async with AsyncSessionLocal() as db:
  builds=list((await db.execute(select(ManualBuild))).scalars())
  products=list((await db.execute(select(Product))).scalars())
  preserved=set().union(*(refs(b.model_3d_url)|refs(b.model_3d_assets) for b in builds),*(refs(p.model_3d_url) for p in products))
  protected_names={name(url) for url in preserved}
  assert preserved,'No pre-built model found; stop before deletion'
  assets=list((await db.execute(select(Component3DAsset).with_for_update())).scalars())
  removed=[a for a in assets if not (refs(a.glb_ref)&preserved) and name(a.glb_ref or '') not in protected_names]
  cases=list((await db.execute(select(Case).where(Case.model_3d_url.is_not(None)).with_for_update())).scalars())
  cleared=[c for c in cases if c.model_3d_url not in preserved and name(c.model_3d_url) not in protected_names]
  variants=list((await db.execute(select(CatalogueVariant).where(CatalogueVariant.asset_media_review.is_not(None)).with_for_update())).scalars())
  active={'QUEUED','PREPARING','STARTING','RESUMING','SUBMITTED','PENDING','IN_PROGRESS','PUBLISHING'}
  assert not any((v.asset_media_review or {}).get('generation',{}).get('status') in active for v in variants),'Active generation exists; stop rather than race the worker'
  reset=[v for v in variants if any(k in (v.asset_media_review or {}) for k in ('generation','media_preparation','generation_input_image_urls','generation_input_basis'))]
  names={name(a.glb_ref) for a in removed if a.glb_ref}|{name(c.model_3d_url) for c in cleared}
  files=[]
  for root in roots:
   for path in root.rglob('*.glb'):
    resolved=path.resolve()
    if resolved.is_relative_to(root) and path.name in names and path.name not in protected_names:files.append(resolved)
  print(json.dumps({'registry_rows_to_remove':len(removed),'registered_models':sum(bool(a.glb_ref) for a in removed),'case_links_to_clear':len(cleared),'generation_states_to_reset':len(reset),'local_files_to_remove':len(files),'prebuilt_models_preserved':len(preserved)}))
  if not apply:return
  backup=(Path(os.environ['LOCALAPPDATA'])/'FlipFlop/recovery'/('model-reset-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
  backup.mkdir(parents=True,exist_ok=False)
  data={'assets':[snapshot(a) for a in removed],'cases':[snapshot(c) for c in cleared],'reviews':[{'id':v.id,'asset_media_review':v.asset_media_review} for v in reset],'preserved_urls':sorted(preserved),'files':[]}
  for index,path in enumerate(files):data['files'].append({'source':str(path),'backup':str(backup/f'{index}-{path.name}')})
  (backup/'recovery.json').write_text(json.dumps(data,default=encode),encoding='utf-8')
  moved=[]
  try:
   for item in data['files']:
    src,dst=Path(item['source']),Path(item['backup'])
    assert any(src.is_relative_to(root) for root in roots) and dst.is_relative_to(backup)
    shutil.move(str(src),str(dst));moved.append((src,dst))
   for case in cleared:
    case.has_3d_model=False
    for field in ('model_3d_url','model_3d_source','model_3d_creator','model_3d_license','model_3d_quality','model_3d_vertices','model_3d_polygons','model_3d_file_size'):setattr(case,field,None)
   for v in reset:v.asset_media_review={k:value for k,value in v.asset_media_review.items() if k not in {'generation','media_preparation','generation_input_image_urls','generation_input_basis'}}
   await db.execute(delete(Component3DAsset).where(Component3DAsset.id.in_([a.id for a in removed])))
   await db.flush()
   assert all(b.model_3d_url in preserved for b in builds if b.model_3d_url)
   await db.commit()
  except BaseException:
   await db.rollback()
   for src,dst in reversed(moved):
    if dst.is_file():shutil.move(str(dst),str(src))
   raise
  print('APPLIED; recovery backup:',backup)
 await engine.dispose()
if __name__=='__main__':
 import sys
 asyncio.run(main('--apply' in sys.argv))
