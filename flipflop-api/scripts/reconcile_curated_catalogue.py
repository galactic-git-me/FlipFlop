"""Read-only reconciliation of workbook definitions against database catalogue."""
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import AsyncSessionLocal,engine
from app.api.public_catalogue import public_curated_builds,public_list_cases
from app.services.curated_build_policy import definitions,matches_spec
async def main():
    try:
        async with AsyncSessionLocal() as db:
            builds=await public_curated_builds(db)
            cases=await public_list_cases(db)
            unmatched=[c['name'] for c in definitions()['cases'] if not any(matches_spec(d['name'],c['name']) for d in cases)]
            print(json.dumps({'builds':[{'id':b['id'],'name':b['name'],'price_gbp':b['price_gbp'],'missing_components':b['missing_components']} for b in builds], 'available_database_cases':len(cases),'unmatched_workbook_cases':unmatched},indent=2))
    finally:
        await engine.dispose()
if __name__=='__main__':
    asyncio.run(main())
