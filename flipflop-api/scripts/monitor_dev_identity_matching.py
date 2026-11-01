"""Read-only matching samples for an already-running DEV scrape; no provider calls."""
import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.environment import load_application_environment
load_application_environment(Path(__file__).resolve().parents[1])
from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from sqlalchemy import text

async def main(since):
    assert get_settings().app_env == 'dev'
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        target = dict((await db.execute(text('SELECT current_database() AS database,current_schema() AS schema'))).mappings().one())
        assert target == {'database':'pcflipper', 'schema':'public'}, target
        rows = [dict(r) for r in (await db.execute(text('''
            SELECT DISTINCT ON(o.listing_id) o.listing_id,o.source,o.title,o.mpn,o.observed_at,
                c.cpk,c.cpk_data,c.updated_at AS identity_updated_at
            FROM gem_radar_listing_observations o LEFT JOIN gem_radar_listing_cpk c USING(listing_id)
            WHERE o.observed_at >= :since ORDER BY o.listing_id,o.observed_at DESC,o.id DESC
        '''), {'since': datetime.fromisoformat(since).replace(tzinfo=None)})).mappings()]
        keys = list({r['cpk'] for r in rows if r['cpk']})
        sources = {r['cpk']: r['sources'] for r in (await db.execute(text('''
            SELECT c.cpk,array_agg(DISTINCT o.source) FILTER(WHERE o.source IS NOT NULL) AS sources
            FROM gem_radar_listing_cpk c JOIN gem_radar_listing_observations o USING(listing_id)
            WHERE c.cpk=ANY(:keys) GROUP BY c.cpk
        '''), {'keys':keys})).mappings()}
    await engine.dispose()
    direct = {'amazon','scan','ebuyer','awd_it','computer_orbit','overclockers','newegg_uk','bargain_hardware'}
    stats = defaultdict(Counter)
    examples = {}
    for row in rows:
        data = row['cpk_data'] or {}
        vendors = sorted(set(sources.get(row['cpk']) or []) & direct)
        counts = stats[row['source']]
        counts['listings'] += 1
        counts['mpn_field'] += bool(row['mpn'])
        counts['cpk'] += bool(row['cpk'])
        counts['validated_v3'] += data.get('identity_validation_version') == 3
        counts['mpn_anchored_identity'] += any(c.get('kind') == 'mpn' for c in data.get('identity_claims',[]))
        counts['linked_2plus_direct_retailers'] += len(vendors) >= 2
        if len(vendors) >= 2:
            examples.setdefault(row['cpk'], {'title':row['title'],'vendors':vendors,'cpk':row['cpk']})
    api = {}
    for endpoint in ['queue-status','pipeline-status']:
        with urllib.request.urlopen('http://127.0.0.1:4311/api/gem-radar/'+endpoint, timeout=15) as response:
            api[endpoint] = json.load(response)
    report = {'sampled_at':now.isoformat(),'since':since,'distinct_observed_listings':len(rows),
              'by_source':dict(stats), 'examples':list(examples.values())[:12],
              'missing_identity_examples':[{k:r[k] for k in ['source','title','mpn']} for r in rows if not r['cpk']][:12],
              'queue':api['queue-status'],'pipeline':api['pipeline-status']}
    out = Path(__file__).resolve().parents[2] / 'docs/playbook/audits/2026-10-26/live-scrape-monitor'
    out.mkdir(exist_ok=True)
    (out / ('sample-'+now.strftime('%H%M%S')+'.json')).write_text(json.dumps(report,default=str,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'pipeline','missing_identity_examples'}},default=str,indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--since',required=True,help='UTC observation cutoff, ISO format')
    asyncio.run(main(parser.parse_args().since))
