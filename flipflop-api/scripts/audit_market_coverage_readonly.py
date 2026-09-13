"""Read-only market coverage snapshot; writes only a local JSON report."""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import engine
from sqlalchemy import text
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from app.gem_radar.opportunity_scoring import load_opportunity_policy, SoldComparable, robust_sold_market
from app.gem_radar.cpk_market import robust_active_market

QUERIES = {
    'active_summary': "SELECT count(*) total, count(*) FILTER(WHERE cpk IS NOT NULL) cpk, count(*) FILTER(WHERE market_sample_size>0) market, count(*) FILTER(WHERE classification='INSUFFICIENT_DATA') insufficient FROM gem_radar_scored_listings WHERE listing_id IN (SELECT listing_id FROM gem_radar_listing_observations WHERE observed_at>=now()-interval '24 hours')",
    'active_categories': "SELECT category,count(*) n,count(*) FILTER(WHERE cpk IS NOT NULL) cpk,count(*) FILTER(WHERE market_sample_size>0) market FROM gem_radar_scored_listings WHERE listing_id IN (SELECT listing_id FROM gem_radar_listing_observations WHERE observed_at>=now()-interval '24 hours') GROUP BY 1 ORDER BY n DESC",
    'active_classifications': "SELECT classification,evidence_status,count(*) n FROM gem_radar_scored_listings WHERE listing_id IN (SELECT listing_id FROM gem_radar_listing_observations WHERE observed_at>=now()-interval '24 hours') GROUP BY 1,2 ORDER BY n DESC",
    'sold_duplicates': "SELECT count(*) n,count(DISTINCT split_part(source_url,'?',1)) urls,count(*) FILTER(WHERE source_url IS NULL) missing_url FROM gem_radar_sold_observations",
    'active_price_health': "SELECT count(*) n,count(*) FILTER(WHERE updated_at>=now()-interval '14 days') fresh, max(updated_at) latest FROM gem_radar_cpk_listing_price",
    'identity_examples': "SELECT s.title,s.classification,s.reasoning_summary FROM gem_radar_scored_listings s WHERE s.classification='IDENTITY_FAILED' AND listing_id IN (SELECT listing_id FROM gem_radar_listing_observations WHERE observed_at>=now()-interval '24 hours') ORDER BY md5(listing_id) LIMIT 20",
    'fragmented_models': "SELECT cpk_data->>'category' category,cpk_data->>'brand' brand,cpk_data->>'model' model,count(DISTINCT cpk) keys,count(*) listings FROM gem_radar_listing_cpk GROUP BY 1,2,3 HAVING count(DISTINCT cpk)>1 ORDER BY listings DESC LIMIT 20",
    'snapshot': "SELECT count(*) total, max(scored_at) latest_score, count(*) FILTER(WHERE cpk IS NOT NULL) with_cpk, count(*) FILTER(WHERE market_sample_size > 0) with_market FROM gem_radar_scored_listings",
    'classification': "SELECT classification, evidence_status, count(*) n FROM gem_radar_scored_listings GROUP BY 1,2 ORDER BY n DESC",
    'categories': "SELECT category, count(*) n, count(*) FILTER(WHERE cpk IS NOT NULL) cpk, count(*) FILTER(WHERE market_sample_size > 0) market, count(*) FILTER(WHERE classification='INSUFFICIENT_DATA') insufficient FROM gem_radar_scored_listings GROUP BY 1 ORDER BY n DESC",
    'sold': "SELECT count(*) n, count(*) FILTER(WHERE cpk IS NOT NULL) mapped, count(DISTINCT cpk) cpks, count(DISTINCT match_key) keys, min(observed_at), max(observed_at), count(*) FILTER(WHERE observed_at >= now()-interval '90 days') fresh FROM gem_radar_sold_observations",
    'sold_keys': "SELECT match_key, condition, count(*) n, count(*) FILTER(WHERE cpk IS NOT NULL) mapped FROM gem_radar_sold_observations GROUP BY 1,2 ORDER BY n DESC LIMIT 35",
    'flags': "SELECT flag, count(*) n FROM gem_radar_scored_listings, jsonb_array_elements_text(scoring_explanation::jsonb->'risk_flags') flag GROUP BY 1 ORDER BY n DESC",
    'samples': "SELECT title, category, condition, cpk, classification, evidence_status, scoring_explanation FROM (SELECT *, row_number() OVER(PARTITION BY evidence_status ORDER BY listing_id) rn FROM gem_radar_scored_listings) t WHERE rn<=5",
    'tables': "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (table_name LIKE '%cpk%' OR table_name LIKE '%queue%')",
}

async def main():
    output = {}
    async with engine.connect() as conn:
        await conn.execute(text('SET TRANSACTION READ ONLY'))
        for name, sql in QUERIES.items():
            output[name] = [dict(r) for r in (await conn.execute(text(sql))).mappings()]
        policy = await load_opportunity_policy(AsyncSession(bind=conn))
        output['policy'] = vars(policy)
        listings = (await conn.execute(text("""SELECT DISTINCT ON(o.listing_id) o.listing_id,o.title,o.condition_normalised,o.delivered_price,o.source,o.observed_at,c.cpk,c.cpk_data,p.updated_at price_updated,p.price stored_price FROM gem_radar_listing_observations o LEFT JOIN gem_radar_listing_cpk c USING(listing_id) LEFT JOIN gem_radar_cpk_listing_price p USING(listing_id) ORDER BY o.listing_id,o.observed_at DESC,o.id DESC"""))).mappings().all()
        sold = (await conn.execute(text("SELECT cpk,condition,price,postage,source_url,match_key FROM gem_radar_sold_observations WHERE observed_at>=now()-interval '90 days' AND price>0"))).mappings().all()
        identities = (await conn.execute(text('SELECT DISTINCT cpk,cpk_data::text FROM gem_radar_listing_cpk'))).all()
        import re
        from datetime import datetime, timedelta, timezone
        norm = lambda x: re.sub('[^A-Z0-9]', '', x.upper())
        aliases = defaultdict(set)
        for cpk, raw in identities:
            d=json.loads(raw)
            for key in (d.get('model') or '', (d.get('brand') or '')+(d.get('model') or '')):
                if key: aliases[norm(key)].add(cpk)
        cohorts=defaultdict(list)
        repaired_sold=defaultdict(list)
        recoverable=ambiguous=unmatched=0
        for r in sold:
            comp=SoldComparable(r['price'],r['postage'] or 0,r['source_url'])
            if r['cpk']: cohorts[(r['cpk'],r['condition'])].append(comp)
            key=r['cpk']
            if not key:
                options=aliases[r['match_key']]
                if len(options)==1: key=next(iter(options)); recoverable+=1
                elif options: ambiguous+=1
                else: unmatched+=1
            if key: repaired_sold[(key,r['condition'])].append(comp)
        current=defaultdict(list); refreshed=defaultdict(list)
        now=datetime.now(timezone.utc).replace(tzinfo=None); stale_live=missing_live=changed_live=0
        output['audit_context']={'captured_at_utc':now.isoformat(),'database_host':engine.url.host,'database_name':engine.url.database,'active_definition':'observed within 24 hours'}
        for r in listings:
            if not r['cpk']: continue
            condition='new' if r['condition_normalised']=='new' and not re.search(r'\b(b[ -]?grade|open[ -]?box|refurbished|renewed)\b',r['title'].lower()) else 'used'
            key=(r['cpk'],condition)
            url=f"{r['source']}://{r['listing_id']}"
            if r['price_updated'] and r['price_updated']>=now-timedelta(days=14): current[key].append(SoldComparable(r['stored_price'],source_url=url))
            if r['observed_at']>=now-timedelta(days=14) and r['delivered_price']>0: refreshed[key].append(SoldComparable(r['delivered_price'],source_url=url))
            if r['observed_at']>=now-timedelta(hours=24):
                missing_live+=int(r['price_updated'] is None)
                stale_live+=int(r['price_updated'] is not None and r['price_updated']<now-timedelta(days=14))
                changed_live+=int(r['stored_price'] is not None and abs(r['stored_price']-r['delivered_price'])>=.01)
        counts=defaultdict(int); examples=[]
        for r in listings:
            if not r['cpk'] or r['observed_at']<now-timedelta(hours=24): continue
            condition='new' if r['condition_normalised']=='new' and not re.search(r'\b(b[ -]?grade|open[ -]?box|refurbished|renewed)\b',r['title'].lower()) else 'used'
            key=(r['cpk'],condition); lid=r['listing_id']
            sm=robust_sold_market(cohorts[key],subject_listing_id=lid,policy=policy)
            old=sm or robust_active_market(current[key],subject_listing_id=lid,condition=condition,policy=policy)
            fixed=sm or robust_active_market(refreshed[key],subject_listing_id=lid,condition=condition,policy=policy)
            both=robust_sold_market(repaired_sold[key],subject_listing_id=lid,policy=policy) or fixed
            counts['known_active']+=1
            counts['current_market']+=int(old is not None)
            counts['refreshed_market']+=int(fixed is not None)
            counts['refreshed_plus_unique_alias_market']+=int(both is not None)
            counts['current_market_at_least_3']+=int(old is not None and old.sample_size>=3)
            counts['refreshed_market_at_least_3']+=int(fixed is not None and fixed.sample_size>=3)
            if old is None and fixed is not None and len(examples)<12: examples.append({'title':r['title'],'basis':fixed.basis,'n':fixed.sample_size})
        output['repair_simulation']={'counts':dict(counts),'active_stale_price_rows':stale_live,'active_missing_price_rows':missing_live,'active_changed_price_rows':changed_live,'unmapped_unique_alias_rows':recoverable,'unmapped_ambiguous_rows':ambiguous,'unmapped_no_alias_rows':unmatched,'examples':examples}
        ambiguous_keys=defaultdict(int)
        for r in sold:
            if not r['cpk'] and len(aliases[r['match_key']])>1: ambiguous_keys[r['match_key']]+=1
        output['ambiguous_alias_examples']=[{'match_key':key,'unmapped_rows':n,'identities':[{'cpk':cpk,'data':json.loads(raw)} for cpk,raw in identities if cpk in aliases[key]][:8]} for key,n in sorted(ambiguous_keys.items(),key=lambda x:-x[1])[:6]]
    await engine.dispose()
    dest = Path(__file__).resolve().parents[2] / 'tmp/market-coverage-audit.json'
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(output, indent=2, default=str), encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k not in ('samples','tables')}, indent=2, default=str))

if __name__ == '__main__':
    asyncio.run(main())
