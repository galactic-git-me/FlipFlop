"""Apply per-listing DEV identity repairs with backups, checks and a receipt."""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.environment import load_application_environment
load_application_environment(Path(__file__).resolve().parents[1])
from app.database import AsyncSessionLocal, engine
from app.config import get_settings
from app.gem_radar.cpk_market import recompute_market_price
from sqlalchemy import text

BASE = Path(__file__).resolve().parents[2] / 'docs/playbook/audits/2026-10-26'


async def main(version='v2', plan_stem=None, output=BASE):
    stem = plan_stem or ('search-matching-v3' if version == 'v3' else 'search-matching')
    import re
    if not re.fullmatch(r'search-matching[-a-z0-9]*', stem):
        raise ValueError('Invalid repair artifact stem')
    plan = json.loads((output / f'{stem}-repair-plan.json').read_text(encoding='utf8'))
    assert get_settings().app_env == 'dev', 'DEV only'
    async with AsyncSessionLocal() as db:
        target = dict((await db.execute(text('SELECT current_database() AS database,current_schema() AS schema'))).mappings().one())
        assert target == {'database': 'pcflipper', 'schema': 'public'}, target
        ids = [r['listing_id'] for r in plan]
        existing_ids = set((await db.execute(text(
            'SELECT listing_id FROM gem_radar_listing_cpk WHERE listing_id=ANY(:ids)'), {'ids': ids})).scalars())
        current = {r['listing_id']: dict(r) for r in (await db.execute(text(
            'SELECT listing_id,cpk,cpk_data,cpk_confidence,updated_at FROM gem_radar_listing_cpk WHERE listing_id=ANY(:ids) FOR UPDATE SKIP LOCKED'), {'ids': ids})).mappings()}
        latest = {r['listing_id']: r['title'] for r in (await db.execute(text('''
            SELECT DISTINCT ON(listing_id) listing_id,title FROM gem_radar_listing_observations
            WHERE listing_id=ANY(:ids) ORDER BY listing_id,observed_at DESC,id DESC
        '''), {'ids': ids})).mappings()}
        best_titles = {r['asin']:r['title'] for r in (await db.execute(text('''
            SELECT DISTINCT ON(asin) asin,title FROM amazon_bestseller_observations
            WHERE asin=ANY(:ids) ORDER BY asin,captured_at DESC,id DESC
        '''), {'ids':[r['listing_id'] for r in plan if r.get('bestseller_anchor')]})).mappings()}
        selected, skipped = [], []
        for row in plan:
            if row['listing_id'] in existing_ids and row['listing_id'] not in current:
                skipped.append(row['listing_id'])
                continue  # The ongoing ingestion owns this row; do not block it.
            saved = current.get(row['listing_id'])
            now_key = saved['cpk'] if saved else None
            observed_title = best_titles.get(row['listing_id']) if row.get('bestseller_anchor') else latest.get(row['listing_id'])
            if observed_title != row['title'] or now_key not in {row['old_cpk'], row['new_cpk']}:
                skipped.append(row['listing_id'])
                continue
            selected.append(row)
        affected = sorted({r['new_cpk'] for r in selected} | {
            current[r['listing_id']]['cpk'] for r in selected if r['listing_id'] in current})
        prices = [dict(r) for r in (await db.execute(text(
            'SELECT * FROM gem_radar_cpk_listing_price WHERE listing_id=ANY(:ids)'),
            {'ids': [r['listing_id'] for r in selected]})).mappings()]
        cache = [dict(r) for r in (await db.execute(text(
            'SELECT * FROM gem_radar_cpk_market_price WHERE cpk=ANY(:cpks)'), {'cpks': affected})).mappings()]
        backup = {'at': datetime.now(timezone.utc).isoformat(), 'database_target': target,
                  'mappings': list(current.values()), 'price_contributions': prices, 'market_cache': cache}
        backup_file = output / (stem + '-backup-' + datetime.now(timezone.utc).strftime('%H%M%S') + '.json')
        backup_file.write_text(json.dumps(backup, default=str), encoding='utf8')
        payload = json.dumps([{'id': r['listing_id'], 'cpk': r['new_cpk'], 'data': r['new_data']} for r in selected])
        await db.execute(text('''
            WITH repair AS (SELECT * FROM jsonb_to_recordset(CAST(:rows AS jsonb)) p(id text,cpk text,data jsonb))
            UPDATE gem_radar_listing_cpk c SET cpk=p.cpk,cpk_data=p.data,cpk_confidence=1,updated_at=CURRENT_TIMESTAMP
            FROM repair p WHERE c.listing_id=p.id
        '''), {'rows': payload})
        await db.execute(text('''
            INSERT INTO gem_radar_listing_cpk(listing_id,cpk,cpk_data,cpk_confidence,updated_at)
            SELECT id,cpk,data,1,CURRENT_TIMESTAMP FROM jsonb_to_recordset(CAST(:rows AS jsonb)) p(id text,cpk text,data jsonb)
            ON CONFLICT(listing_id) DO NOTHING
        '''), {'rows': payload})
        await db.execute(text('''
            UPDATE gem_radar_cpk_listing_price c SET cpk=p.cpk
            FROM jsonb_to_recordset(CAST(:rows AS jsonb)) p(id text,cpk text,data jsonb) WHERE c.listing_id=p.id
        '''), {'rows': payload})
        await db.commit()
        verified = {r['listing_id']: r['cpk'] for r in (await db.execute(text(
            'SELECT listing_id,cpk FROM gem_radar_listing_cpk WHERE listing_id=ANY(:ids)'), {'ids': ids})).mappings()}
        receipt = {'at': datetime.now(timezone.utc).isoformat(), 'database_target': target, 'backup': str(backup_file),
                   'selected': len(selected), 'skipped_concurrent_changes': skipped,
                   'verified_after': verified, 'aggregates_pending': len(affected)}
        receipt_file = output / f'{stem}-apply-receipt.json'
        receipt_file.write_text(json.dumps(receipt, indent=2), encoding='utf8')
        print(json.dumps({'selected': len(selected), 'skipped': len(skipped),
                          'affected_price_aggregates': len(affected), 'backup': str(backup_file)}), flush=True)
        identities = {r['new_cpk']: r['new_data'] for r in selected}
        for index, cpk in enumerate(affected):
            data = identities.get(cpk, {})
            await recompute_market_price(db, cpk, category=data.get('category'), brand=data.get('brand'), model=data.get('model'))
            if (index + 1) % 50 == 0:
                await db.commit()
                print(f'Price aggregates repaired: {index+1}/{len(affected)}', flush=True)
        await db.commit()
        receipt['aggregates_pending'] = 0
        receipt['aggregates_recomputed'] = len(affected)
        receipt_file.write_text(json.dumps(receipt, indent=2), encoding='utf8')
        print('Repair and aggregate recalculation complete.', flush=True)
    await engine.dispose()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', choices=['v2','v3'], default='v2')
    parser.add_argument('--plan-stem', help='Named search-matching audit plan; preserves earlier receipts')
    parser.add_argument('--output',type=Path,default=BASE)
    args = parser.parse_args()
    asyncio.run(main(args.version, args.plan_stem,args.output))
