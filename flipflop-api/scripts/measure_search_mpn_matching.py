"""Frozen before/after measurement. No provider calls or database writes."""
import json,sys,hashlib,re
from pathlib import Path
from collections import defaultdict,Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.gem_radar.search_identity import search_result_identity
BASE=Path(__file__).resolve().parents[2]/'docs/playbook/audits/2026-10-26'

def prepare(snapshot):
    groups=defaultdict(list);conflicts=[]
    for row in snapshot['rows']:
        result=search_result_identity(row['title'],row['category'],mpn=row['mpn'])
        if result and result['status']=='matched':groups[result['cpk']].append((row,result))
        elif result:conflicts.append({'source':row['source'],'listing_id':row['listing_id'],'title':row['title'],**result})
    accepted={};group_conflicts=[]
    for key,group in groups.items():
        facts=defaultdict(set)
        for row,result in group:
            for field,value in result['data']['variant_facts'].items():
                if field!='family':facts[field].add(value)
        bad={k:sorted(v,key=str) for k,v in facts.items() if len(v)>1}
        if bad:group_conflicts.append({'cpk':key,'mpn':group[0][1]['data']['model'],'fields':bad,'listings':[r['listing_id'] for r,x in group]})
        else:accepted[key]=group
    return accepted,conflicts,group_conflicts

def metrics(groups,after=False,allowed=None):
    products=fully=listing_count=pairs=amazon_products=0
    for group in groups.values():
        rows=[r for r,x in group if allowed is None or r['source'] in allowed]
        sources={r['source'] for r in rows}
        if len(sources)<2:continue
        partitions=defaultdict(list)
        for row in rows:
            key='new' if after else row['cpk']
            if key:partitions[key].append(row)
        linked=[rs for rs in partitions.values() if len({r['source'] for r in rs})>1]
        if linked:products+=1
        if any({r['source'] for r in rs}==sources for rs in linked):fully+=1
        if any('amazon' in {r['source'] for r in rs} for rs in linked):amazon_products+=1
        listing_count+=sum(len(rs) for rs in linked)
        for rs in linked:
            c=Counter(r['source'] for r in rs);n=list(c.values())
            pairs+=sum(n[a]*n[b] for a in range(len(n)) for b in range(a+1,len(n)))
    return {'products_with_cross_source_links':products,'products_with_all_observed_sources_linked':fully,
            'listings_in_cross_source_groups':listing_count,'cross_source_listing_pairs':pairs,
            'amazon_products_linked_to_another_source':amazon_products}

def main():
    snapshot=json.loads((BASE/'search-matching-before-snapshot.json').read_text(encoding='utf8'))
    groups,conflicts,group_conflicts=prepare(snapshot)
    plan=[]
    for key,group in groups.items():
        for row,result in group:
            data=dict(result['data']);data['identity_title_sha256']=hashlib.sha256(re.sub(r'\s+',' ',row['title'].casefold()).strip().encode()).hexdigest()
            plan.append({'source':row['source'],'listing_id':row['listing_id'],'title':row['title'],'old_cpk':row['cpk'],'old_data':row['cpk_data'],
                         'new_cpk':key,'new_data':data})
    direct={'amazon','awd_it','bargain_hardware','computer_orbit','ebuyer','newegg_uk','overclockers','scan'}
    report={'snapshot_at':snapshot['captured_at'],'database_target':snapshot['database_target'],
            'measurement':'Same frozen captures, exact manufacturer+MPN only; no detail-page data or new network captures. After is replay until a separate apply receipt exists.',
            'total_listings':len(snapshot['rows']),'mpn_eligible_listings':len(plan),'mpn_products':len(groups),
            'listings_flagged_individually':len(conflicts),'conflicting_mpn_groups_excluded':len(group_conflicts),
            'before':metrics(groups),'after_replay':metrics(groups,True),
            'direct_retailers_before':metrics(groups,allowed=direct),'direct_retailers_after_replay':metrics(groups,True,allowed=direct),
            'per_source':dict(Counter(r['source'] for r in plan)),
            'limitations':['MPN equality and variant consistency are the measurement evidence; this is not a manual precision audit.',
                'Title-only fallback links are retained but not counted as new confirmed MPN links.',
                'Existing captured titles often omit MPNs; extension improvements need a new results-page scan to measure their additional capture gain.',
                'No historical CPK is redirected wholesale: only individual evidenced source listings are planned.'],
            'conflicts':conflicts,'group_conflicts':group_conflicts}
    (BASE/'search-matching-repair-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
    (BASE/'search-matching-before-after.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    lines=['# Search-page MPN matching: before and after','',report['measurement'],'',f"Frozen sample: {report['total_listings']:,} listings. {len(plan):,} eligible listings across {len(groups):,} manufacturer+MPN products.",'',
        '| Metric | Before | After replay | Change |','|---|---:|---:|---:|']
    for key,before in report['before'].items():
        after=report['after_replay'][key];lines.append(f"| {key} | {before} | {after} | {after-before:+} |")
    lines+=['','Direct retailer-only comparison (excludes eBay and Google Shopping):','',
        '| Metric | Before | After replay |','|---|---:|---:|']
    for key,before in report['direct_retailers_before'].items():lines.append(f"| {key} | {before} | {report['direct_retailers_after_replay'][key]} |")
    lines+=['','## Limits','']+['- '+text for text in report['limitations']]
    lines+=[f"- {len(conflicts)} individual conflicts and {len(group_conflicts)} conflicting part-code groups were excluded from reassignment."]
    (BASE/'search-matching-before-after.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'conflicts','group_conflicts','limitations','per_source'}},indent=2))
if __name__=='__main__':main()
