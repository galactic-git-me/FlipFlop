"""Plan the shared search-identity repair over every saved DEV listing, offline."""
import asyncio
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.environment import load_application_environment
load_application_environment(Path(__file__).resolve().parents[1])
from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from sqlalchemy import text
from measure_search_matching_v3 import build_plan, DIRECT
from measure_search_mpn_matching import BASE, metrics, prepare

STEM = 'search-matching-all-history'

async def main(stem=STEM, output=BASE, cohort=None):
    if not re.fullmatch(r'search-matching[-a-z0-9]*',stem):
        raise ValueError('Invalid repair artifact stem')
    output.mkdir(parents=True,exist_ok=True)
    bestsellers=json.loads(cohort.read_text(encoding='utf8'))['bestsellers'] if cohort else []
    assert get_settings().app_env == 'dev', 'DEV only'
    async with AsyncSessionLocal() as db:
        await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        target = dict((await db.execute(text('SELECT current_database() AS database,current_schema() AS schema'))).mappings().one())
        assert target == {'database': 'pcflipper', 'schema': 'public'}, target
        rows = [dict(r) for r in (await db.execute(text('''
            SELECT o.*, c.cpk, c.cpk_data FROM (
                SELECT DISTINCT ON(listing_id) listing_id,title,category,source,mpn,
                    condition_normalised,listing_type,item_price,observed_at
                FROM gem_radar_listing_observations
                ORDER BY listing_id,observed_at DESC,id DESC
            ) o LEFT JOIN gem_radar_listing_cpk c USING(listing_id)
        '''))).mappings()]
        identities=[dict(r) for r in (await db.execute(text('SELECT listing_id,cpk,cpk_data FROM gem_radar_listing_cpk WHERE listing_id=ANY(:ids)'),
            {'ids':[b['asin'] for b in bestsellers]})).mappings()] if bestsellers else []
    await engine.dispose()
    snapshot = {'captured_at': datetime.now(timezone.utc).isoformat(), 'database_target': target,
                'rows': rows, 'bestsellers': bestsellers, 'amazon_identities': identities}
    (output / f'{stem}-before-snapshot.json').write_text(json.dumps(snapshot, default=str), encoding='utf8')
    groups, candidates, conflicts, group_conflicts = build_plan(snapshot)
    plan = [r for r in candidates if r['old_cpk'] != r['new_cpk']]
    mapping = {r['listing_id']: r['new_cpk'] for r in plan}
    after_snapshot = {**snapshot, 'rows': [{**r, 'cpk': mapping.get(r['listing_id'], r['cpk'])} for r in rows]}
    after_groups, _, _ = prepare(after_snapshot)
    report = {'snapshot_at': snapshot['captured_at'], 'total_listings': len(rows),
              'eligible_candidates': len(candidates), 'additional_identity_changes': len(plan),
              'individual_conflicts': len(conflicts), 'conflicting_groups': len(group_conflicts),
              'before': metrics(groups), 'after_planned': metrics(after_groups),
              'direct_before': metrics(groups, allowed=DIRECT),
              'direct_after_planned': metrics(after_groups, allowed=DIRECT)}
    (output / f'{stem}-repair-plan.json').write_text(json.dumps(plan, default=str), encoding='utf8')
    (output / f'{stem}-before-after.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stem',default=STEM)
    parser.add_argument('--output',type=Path,default=BASE)
    parser.add_argument('--cohort',type=Path,help='Keep the previous bestseller cohort fixed for comparison')
    args=parser.parse_args()
    asyncio.run(main(args.stem,args.output,args.cohort))
