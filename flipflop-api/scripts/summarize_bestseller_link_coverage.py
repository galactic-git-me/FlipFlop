"""Report fixed-cohort supplier links from a snapshot and verified repair receipt."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.gem_radar.identity import is_full_system_listing
from app.services.playbook_stored_offers import same_product
from measure_search_mpn_matching import prepare,metrics
from measure_search_matching_v3 import DIRECT

ORDER=['cpu','motherboard','gpu','ram','nvme','sata','psu','cooling','case']
LABEL={'cpu':'CPU','motherboard':'Motherboard','gpu':'Graphics card','ram':'RAM','nvme':'NVMe SSD','sata':'SATA SSD','psu':'Power supply','cooling':'CPU cooler','case':'Case'}

def main(args):
    snapshot=json.loads(args.snapshot.read_text(encoding='utf8'))
    receipt=json.loads(args.receipt.read_text(encoding='utf8'))
    plan=json.loads(args.snapshot.with_name(args.snapshot.name.replace('-before-snapshot','-repair-plan')).read_text(encoding='utf8'))
    mapping=receipt['verified_after']
    assert all(mapping.get(r['listing_id'])==r['new_cpk'] for r in plan), 'Not all repairs verified'
    assert receipt['aggregates_pending']==0
    new_data={r['listing_id']:r['new_data'] for r in plan}
    rows=[{**r,'cpk':mapping.get(r['listing_id'],r['cpk']),
           'cpk_data':new_data.get(r['listing_id'],r['cpk_data'])} for r in snapshot['rows']]
    before_groups,_,_=prepare(snapshot)
    groups,_,_=prepare({**snapshot,'rows':rows})
    index=defaultdict(list)
    by_id={r['listing_id']:r for r in rows}
    for r in rows:
        if r['cpk'] and r['source'] in DIRECT and not is_full_system_listing(r['title']):
            index[r['cpk']].append(r)
    identities={r['listing_id']:r for r in snapshot['amazon_identities']}
    products=[]
    for b in snapshot['bestsellers']:
        identity=identities.get(b['asin'],{})
        key=mapping.get(b['asin'],identity.get('cpk') or b.get('cpk'))
        data=new_data.get(b['asin'],identity.get('cpk_data'))
        role={'nvme':'storage','sata':'storage_secondary','cooling':'cooling'}.get(b['bucket'],b['bucket'])
        part={'title':b['title'],'role':role,'cpk':key,'cpk_data':data}
        matches=[r for r in index.get(key,[]) if same_product(part,r)] if key else []
        vendors={r['source'] for r in matches}
        captured=by_id.get(b['asin'])
        exact=bool(captured and captured['source']=='amazon')
        cpk_amazon='amazon' in vendors
        if exact:vendors.add('amazon')
        products.append({'asin':b['asin'],'title':b['title'],'category':b['bucket'],'cpk':key,
                         'amazon_exact_asin_captured':exact,'amazon_cpk_link':cpk_amazon,
                         'vendors':sorted(vendors),'other_vendor':any(v!='amazon' for v in vendors)})
    summaries=[]
    for category in ORDER+['TOTAL']:
        cohort=products if category=='TOTAL' else [r for r in products if r['category']==category]
        n=len(cohort)
        summaries.append({'category':category,'products':n,
            'amazon_exact_asin':sum(r['amazon_exact_asin_captured'] for r in cohort),
            'amazon_cpk_links':sum(r['amazon_cpk_link'] for r in cohort),
            'other_vendor_links':sum(r['other_vendor'] for r in cohort),
            'average_vendors':round(sum(len(r['vendors']) for r in cohort)/n,2) if n else 0})
    report={'snapshot_at':snapshot['captured_at'],'listings':len(rows),'identity_changes_applied':receipt['selected'],
        'mpn_before':metrics(before_groups),'mpn_after_verified':metrics(groups),
        'direct_mpn_before':metrics(before_groups,allowed=DIRECT),'direct_mpn_after_verified':metrics(groups,allowed=DIRECT),
        'summary':summaries,'products':products}
    args.output.mkdir(exist_ok=True,parents=True)
    (args.output/'bestseller-link-coverage.json').write_text(json.dumps(report,indent=2))
    lines=['# Bestseller supplier-link coverage','','Snapshot: '+snapshot['captured_at']+'. Same 90 ASINs as the previous top-ten report. Captured listing links across all saved ages/conditions, not current purchasable-offer counts. eBay and Google Shopping excluded. Other-vendor links must pass the actual Playbook same-product check. Whole computers are excluded. Average includes Amazon where its exact ASIN was captured.','','Amazon ASIN capture and a resolved Amazon CPK join are reported separately: an ASIN seen in the bestseller feed alone does not count as a captured supplier listing.','','| Type | Products | Amazon exact ASIN captured | Amazon CPK linked | Other vendor linked | Average vendors |','|---|---:|---:|---:|---:|---:|']
    for r in summaries:
        n=r['products'];pct=lambda k:f"{r[k]}/{n} ({r[k]/n:.0%})" if n else '0'
        lines.append(f"| {LABEL.get(r['category'],r['category'])} | {n} | {pct('amazon_exact_asin')} | {pct('amazon_cpk_links')} | {pct('other_vendor_links')} | {r['average_vendors']:.2f} |")
    lines+=['','Verified repair on this frozen sample: direct-retailer MPN products '+str(report['direct_mpn_before']['products_with_cross_source_links'])+' → '+str(report['direct_mpn_after_verified']['products_with_cross_source_links'])+'. Earlier published raw-CPK counts did not apply this same-product validation, so they are not a direct precision comparison. The scrape is still in progress; this is an interim snapshot.']
    (args.output/'bestseller-link-coverage.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('\n'.join(lines))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8',errors='replace')
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args())
