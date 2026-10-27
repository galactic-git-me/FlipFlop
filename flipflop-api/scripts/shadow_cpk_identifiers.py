"""Read-only exact-identifier clustering of captured listings; never reassign CPKs."""
import asyncio
from collections import defaultdict
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.environment import load_application_environment
load_application_environment(Path(__file__).resolve().parents[1])
from sqlalchemy import text
from app.database import AsyncSessionLocal,engine
from app.gem_radar.product_identity_registry import identifier_claims
from app.gem_radar.product_identifiers import identity_conflicts,extract_asin,variant_facts

async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        target=dict((await db.execute(text("SELECT current_database() AS database, current_schema() AS schema, current_setting('search_path') AS search_path"))).mappings().one())
        rows=[dict(row) for row in (await db.execute(text('''
          SELECT DISTINCT ON(o.source,o.listing_id) o.source,o.listing_id,o.title,o.gtin,o.mpn,o.category,
            o.commercial_source_evidence->>'url' AS url,c.cpk,c.cpk_data
          FROM gem_radar_listing_observations o LEFT JOIN gem_radar_listing_cpk c ON c.listing_id=o.listing_id
          WHERE o.observed_at>=now()-interval '14 days'
            AND o.source IN ('amazon','scan','awd_it','overclockers','ebuyer','computer_orbit')
          ORDER BY o.source,o.listing_id,o.observed_at DESC,o.id DESC
        '''))).mappings()]
        # Product-detail titles may be more complete than Amazon result-card alt text.
        amazon_titles={}
        for row in (await db.execute(text('SELECT url,title FROM listings WHERE status=\'active\''))).mappings():
            if (asin:=extract_asin(row['url'])) and ('.amazon.co.uk/' in row['url'] or '//amazon.co.uk/' in row['url']):
                if len(row['title'])>len(amazon_titles.get(asin,'')): amazon_titles[asin]=row['title']
        await db.rollback()
    groups=defaultdict(list); conflicts=[]; output=[]
    for row in rows:
        if row['source']=='amazon' and row['listing_id'] in amazon_titles:
            row['title']=amazon_titles[row['listing_id']]
        data=row.pop('cpk_data') or {}
        category=row['category'] or data.get('category')
        row['conflicts']=identity_conflicts(row['title'],data,category) if data else []
        row['claims']=identifier_claims(title=row['title'],gtin=row['gtin'],mpn=row['mpn'],source_url=row['url'])
        row['variant_facts']=variant_facts(row['title'],category)
        output.append(row)
        if row['conflicts']: conflicts.append(row)
        for claim in row['claims']:
            if claim['kind'] in {'gtin','mpn'}: groups[(claim['kind'],claim['namespace'],claim['value'])].append(row)
    splits=[]
    for claim,members in groups.items():
        keys=sorted({r['cpk'] for r in members if r['cpk']})
        if len(keys)>1:
            contradictions=[]
            for a in members:
                for b in members:
                    contradictions.extend(k for k in a['variant_facts'].keys() & b['variant_facts'].keys()
                        if a['variant_facts'][k]!=b['variant_facts'][k])
            splits.append({'identifier':list(claim),'old_cpks':keys,'sources':sorted({r['source'] for r in members}),
                'status':'needs_conflict_review' if contradictions else 'exact_identifier_reconciliation_candidate',
                'conflicted_fields':sorted(set(contradictions)),'members':members})
    report={'observed_at':datetime.now(timezone.utc).isoformat(),'read_only':True,'database_target':target,
        'summary':{'listings':len(rows),'with_strong_identifier':sum(any(c['kind'] in {'gtin','mpn'} for c in r['claims']) for r in output),
            'contradictory_cached_identities':len(conflicts),'split_identifier_groups':len(splits),
            'cross_vendor_split_groups':sum(len(r['sources'])>1 for r in splits)},
        'split_groups':splits,'conflicting_assignments':conflicts}
    out=Path(__file__).resolve().parents[2]/'docs/playbook/audits/2026-10-26';out.mkdir(parents=True,exist_ok=True)
    (out/'cpk-shadow-assignment-report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
    lines=['# CPK identifier shadow report','',report['observed_at'],'','No saved identities were changed. Candidate clusters require per-listing reconciliation; old collided CPKs cannot be redirected wholesale.','',
        '| Identifier | Sources | Existing CPKs | Proposed disposition |','|---|---|---|---|']
    for group in splits:
        lines.append('| '+' / '.join(group['identifier'])+' | '+', '.join(group['sources'])+' | '+', '.join(group['old_cpks'])+' | '+group['status']+' |')
    lines.extend(['','Summary: `'+json.dumps(report['summary'])+'`'])
    (out/'cpk-shadow-assignment-report.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps(report['summary'],indent=2))
    await engine.dispose()

if __name__=='__main__':asyncio.run(main())
