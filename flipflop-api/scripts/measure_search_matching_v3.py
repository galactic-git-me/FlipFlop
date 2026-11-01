"""Measure incremental search-only matching against one frozen DEV snapshot."""
import json
import sys
import hashlib
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_search_mpn_matching import prepare, metrics, BASE
from app.gem_radar.search_identity import (
    search_result_identity, last_resort_title_key, unique_title_candidate,
)

DIRECT = {'amazon','awd_it','bargain_hardware','computer_orbit','ebuyer','newegg_uk','overclockers','scan'}


def build_plan(snapshot):
    groups, conflicts, group_conflicts = prepare(snapshot)
    plan = {}
    title_index = defaultdict(list)
    for cpk, group in groups.items():
        for row, result in group:
            data = dict(result['data'])
            data['identity_title_sha256'] = hashlib.sha256(re.sub(r'\s+', ' ', row['title'].casefold()).strip().encode()).hexdigest()
            plan[row['listing_id']] = {'source':row['source'],'listing_id':row['listing_id'],'title':row['title'],
                'old_cpk':row['cpk'],'old_data':row['cpk_data'],'new_cpk':cpk,'new_data':data}
            if key := last_resort_title_key(row['title'], data.get('category'), data):
                title_index[key].append((cpk, data))
    rejected = {r['listing_id'] for r in conflicts} | {listing for g in group_conflicts for listing in g['listings']}
    # Repair weak legacy title assignments only against one evidenced MPN anchor.
    # Existing strong source aliases remain intact when the visible MPN is absent.
    for row in snapshot['rows']:
        if row['listing_id'] in plan or row['listing_id'] in rejected or (row['cpk_data'] or {}).get('identity_claims'):
            continue
        if key := last_resort_title_key(row['title'], row['category']):
            match = unique_title_candidate(row['title'], title_index.get(key, []))
            if match:
                cpk, data = match
                plan[row['listing_id']] = {'source':row['source'],'listing_id':row['listing_id'],'title':row['title'],
                    'old_cpk':row['cpk'],'old_data':row['cpk_data'],'new_cpk':cpk,
                    'new_data':{**data,'identity_source_title':row['title']}}
    identities = {r['listing_id']:r for r in snapshot['amazon_identities']}
    rows_by_id = {r['listing_id']:r for r in snapshot['rows'] if r['source']=='amazon'}
    for bestseller in snapshot['bestsellers']:
        asin = bestseller['asin']
        if asin in plan:
            continue
        old = identities.get(asin, {})
        result = search_result_identity(bestseller['title'], bestseller['category'])
        if result and result['status'] == 'matched':
            cpk, data = result['cpk'], result['data']
        elif result:
            continue
        else:
            key = last_resort_title_key(bestseller['title'], bestseller['category'])
            match = unique_title_candidate(bestseller['title'], title_index.get(key, [])) if key else None
            if not match:
                continue
            cpk, data = match
        plan[asin] = {'source':'amazon','listing_id':asin,'title':bestseller['title'],
            'old_cpk':old.get('cpk'),'old_data':old.get('cpk_data'),'new_cpk':cpk,
            'new_data':{**data,'identity_source_title':bestseller['title']},'bestseller_anchor':True}
    for row in plan.values():
        row['new_data']['identity_title_sha256'] = hashlib.sha256(re.sub(r'\s+', ' ', row['title'].casefold()).strip().encode()).hexdigest()
    return groups, list(plan.values()), conflicts, group_conflicts


def bestseller_coverage(snapshot, mapping):
    before_ids = {r['listing_id']:r['cpk'] for r in snapshot['amazon_identities']}
    offers = defaultdict(list)
    now = datetime.fromisoformat(snapshot['captured_at'])
    for row in snapshot['rows']:
        if (row['source'] not in DIRECT or row['condition_normalised']!='new'
                or row['listing_type']!='buy_it_now' or not row['item_price'] or row['item_price']<=0
                or row['stock_status']=='unavailable'):
            continue
        key = mapping.get(row['listing_id'], row['cpk'])
        if key:
            offers[key].append(row)
    result = []
    for b in snapshot['bestsellers']:
        key = mapping.get(b['asin'],before_ids.get(b['asin']) or b.get('cpk'))
        matched = offers.get(key, [])
        sources = sorted({r['source'] for r in matched if r['source']!='amazon'})
        active = set()
        policy_active = set()
        for row in matched:
            seen = datetime.fromisoformat(row['observed_at'].replace('Z','+00:00'))
            seen = seen.replace(tzinfo=seen.tzinfo or timezone.utc)
            if row['stock_status']!='unavailable' and now-seen <= timedelta(hours=24):
                policy_active.add(row['source'])
            if row['stock_status']!='available':
                continue
            try:
                captured = datetime.fromisoformat((row['capture_observed_at'] or row['observed_at']).replace('Z','+00:00'))
                captured = captured.replace(tzinfo=captured.tzinfo or timezone.utc)
            except (ValueError, TypeError):
                continue
            if now-captured <= timedelta(hours=24):
                active.add(row['source'])
        result.append({'asin':b['asin'],'category':b['bucket'],'title':b['title'],
                       'other_captured_retailers':sources,'verified_available_retailers':sorted(active),
                       'available_under_owner_policy':sorted(policy_active)})
    summary = {'products':len(result),
               'with_another_captured_retailer':sum(bool(r['other_captured_retailers']) for r in result),
               'with_two_explicitly_available_retailers':sum(len(r['verified_available_retailers'])>=2 for r in result),
               'with_an_explicitly_available_non_amazon_retailer':sum(any(v!='amazon' for v in r['verified_available_retailers']) for r in result),
               'with_two_available_retailers_under_owner_policy':sum(len(r['available_under_owner_policy'])>=2 for r in result),
               'with_available_non_amazon_retailer_under_owner_policy':sum(any(v!='amazon' for v in r['available_under_owner_policy']) for r in result)}
    return {'summary':summary,'products':result}


def main():
    snapshot = json.loads((BASE/'search-matching-v3-before-snapshot.json').read_text(encoding='utf8'))
    groups, plan, conflicts, group_conflicts = build_plan(snapshot)
    projected = {r['listing_id']:r['new_cpk'] for r in plan}
    receipt_file = BASE/'search-matching-v3-apply-receipt.json'
    receipt = json.loads(receipt_file.read_text()) if receipt_file.exists() else None
    actual = receipt['verified_after'] if receipt else projected
    after_groups = {key:[({**r,'cpk':actual.get(r['listing_id'],r['cpk'])},x) for r,x in group]
                    for key,group in groups.items()}
    report = {'snapshot_at':snapshot['captured_at'],'total_listings':len(snapshot['rows']),
              'after_is_database_verified':receipt is not None,'mpn_products':len(groups),
              'before':metrics(groups),'after':metrics(after_groups),
              'direct_before':metrics(groups,allowed=DIRECT),'direct_after':metrics(after_groups,allowed=DIRECT),
              'bestsellers_before':bestseller_coverage(snapshot,{}),
              'bestsellers_after':bestseller_coverage(snapshot,actual),
              'title_fallback_planned':sum(r['new_data']['identity_match_rule']=='title_product' for r in plan),
              'mpn_planned':sum(r['new_data']['identity_match_rule']=='manufacturer_mpn' for r in plan),
              'individual_conflicts':len(conflicts),'conflicting_groups':group_conflicts,
              'apply':{k:v for k,v in (receipt or {}).items() if k!='verified_after'}}
    (BASE/'search-matching-v3-repair-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
    (BASE/'search-matching-v3-before-after.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if not k.startswith('bestsellers_') and k not in {'conflicting_groups','apply'}},indent=2))
    print('Top-90 before:',report['bestsellers_before']['summary'])
    print('Top-90 after:',report['bestsellers_after']['summary'])


if __name__ == '__main__':
    main()
