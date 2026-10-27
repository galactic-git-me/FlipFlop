"""Back up and unlink whole computers from DEV component cohorts, preserving observations."""
import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.environment import load_application_environment
load_application_environment(Path(__file__).resolve().parents[1])
from app.config import get_settings
from app.database import AsyncSessionLocal,engine
from app.gem_radar.identity import is_full_system_listing
from app.gem_radar.cpk_market import recompute_market_price
from sqlalchemy import text

OUT=Path(__file__).resolve().parents[2]/'docs/playbook/audits/2026-10-27'
HARDWARE={'cpu','gpu','ram','ssd','motherboard','psu','case','cooler','fan'}

async def main(apply):
    assert get_settings().app_env=='dev'
    OUT.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%H%M%S')
    async with AsyncSessionLocal() as db:
        target=dict((await db.execute(text('SELECT current_database() AS database,current_schema() AS schema'))).mappings().one())
        assert target=={'database':'pcflipper','schema':'public'},target
        rows=[dict(r) for r in (await db.execute(text('''
            SELECT c.*,o.title,o.source FROM gem_radar_listing_cpk c JOIN LATERAL (
                SELECT title,source FROM gem_radar_listing_observations WHERE listing_id=c.listing_id
                ORDER BY observed_at DESC,id DESC LIMIT 1) o ON TRUE
        '''))).mappings()]
        candidates=[r for r in rows if is_full_system_listing(r['title']) and (r['cpk_data'] or {}).get('category') in HARDWARE]
        (OUT/f'noncomponent-link-plan-{stamp}.json').write_text(json.dumps(candidates,default=str,indent=2))
        result={'at':datetime.now(timezone.utc).isoformat(),'examined':len(rows),'candidates':len(candidates),
                'by_source':dict(Counter(r['source'] for r in candidates)),'applied':False,
                'examples':[{k:r[k] for k in ['source','title','cpk']} for r in candidates][:15]}
        if apply and candidates:
            ids=[r['listing_id'] for r in candidates]
            locked={r['listing_id']:dict(r) for r in (await db.execute(text('''
                SELECT * FROM gem_radar_listing_cpk WHERE listing_id=ANY(:ids) FOR UPDATE SKIP LOCKED
            '''),{'ids':ids})).mappings()}
            latest=dict((await db.execute(text('''SELECT DISTINCT ON(listing_id) listing_id,title
                FROM gem_radar_listing_observations WHERE listing_id=ANY(:ids)
                ORDER BY listing_id,observed_at DESC,id DESC'''),{'ids':ids})).all())
            selected=[r for r in candidates if r['listing_id'] in locked and locked[r['listing_id']]['cpk']==r['cpk']
                      and latest.get(r['listing_id'])==r['title']]
            selected_ids=[r['listing_id'] for r in selected]
            prices=[dict(r) for r in (await db.execute(text('SELECT * FROM gem_radar_cpk_listing_price WHERE listing_id=ANY(:ids)'),{'ids':selected_ids})).mappings()]
            scored=[dict(r) for r in (await db.execute(text('SELECT * FROM gem_radar_scored_listings WHERE listing_id=ANY(:ids)'),{'ids':selected_ids})).mappings()]
            affected=sorted({r['cpk'] for r in selected}|{r['cpk'] for r in prices})
            cache=[dict(r) for r in (await db.execute(text('SELECT * FROM gem_radar_cpk_market_price WHERE cpk=ANY(:cpks)'),{'cpks':affected})).mappings()]
            backup=OUT/f'noncomponent-backup-{stamp}.json'
            backup.write_text(json.dumps({'mappings':selected,'price_contributions':prices,'scored':scored,'market_cache':cache},default=str))
            await db.execute(text('DELETE FROM gem_radar_cpk_listing_price WHERE listing_id=ANY(:ids)'),{'ids':selected_ids})
            await db.execute(text('DELETE FROM gem_radar_listing_cpk WHERE listing_id=ANY(:ids)'),{'ids':selected_ids})
            await db.execute(text('''UPDATE gem_radar_scored_listings SET cpk=NULL,classification='INELIGIBLE',deal_score=0,
                evidence_reason='complete_system_not_component',reasoning_summary='Complete computer; excluded from component matching and pricing.'
                WHERE listing_id=ANY(:ids)'''),{'ids':selected_ids})
            for key in affected:
                await recompute_market_price(db,key)
            await db.commit()
            remaining=(await db.execute(text('SELECT count(*) FROM gem_radar_listing_cpk WHERE listing_id=ANY(:ids)'),{'ids':selected_ids})).scalar_one()
            assert remaining==0,remaining
            result.update(applied=True,unlinked=len(selected),skipped=len(candidates)-len(selected),
                          aggregates_recomputed=len(affected),backup=str(backup),remaining_links=remaining)
        (OUT/f'noncomponent-result-{stamp}.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
    await engine.dispose()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true')
    asyncio.run(main(parser.parse_args().apply))
