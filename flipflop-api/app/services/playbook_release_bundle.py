"""Materialise reviewed supplier selections without changing canonical products."""
from copy import deepcopy
from hashlib import sha256
import json


def materialize_reviewed_sources(original):
    bundle = deepcopy(original)
    listings = {row['id']: row for row in bundle['listings']}
    variants = {row['id']: row for row in bundle['variants']}
    supplier_listings = {}
    selected_sources = {}
    exact_cases = {row['name']:row for row in bundle['cases']}
    for proposal in bundle['proposals']:
        for part in proposal['proposed_data']['components']:
            if part['role'].startswith('os'):
                continue  # Preserve the original software supplier and its licence review.
            source = part.get('source_observation') or {}
            if not (part.get('catalogue_approved') and source.get('commercial_capture_verified')
                    and source.get('observed_at') and source.get('url')
                    and source.get('condition') == 'new' and source.get('stock_status') == 'available'):
                raise ValueError(f"Selected supplier evidence is incomplete: {part['role']}")
            variant = variants[part['variant_id']]
            previous = selected_sources.setdefault(variant['id'], source['url'])
            if previous != source['url']:
                raise ValueError('One reviewed variant has conflicting supplier selections')
            if variant['status'] not in {'active', 'hidden'} or (
                    variant['status'] == 'hidden' and not str(variant.get('reject_reason') or '').startswith('freshness:')):
                raise ValueError('A selected variant requires an explicit catalogue review')
            anchor = listings[part['listing_id']]
            if part['role']=='case' and not anchor.get('case_catalogue_id'):
                case=exact_cases.get(part['title'])
                if case is None:
                    facts={**(part.get('engineering')or{}),**(part.get('manufacturer_facts')or{})}
                    case={'id':-len(exact_cases)-1,'name':part['title'],
                        'rrp_gbp':float(source['item_gbp']),'status':'active',
                        'brand':str((part.get('cpk_data')or{}).get('brand')or 'Unspecified'),
                        'form_factor':'unknown','images':part.get('images')or[],
                        'notes':json.dumps({'configurator':facts,'supplier_url':source['url']})}
                    exact_cases[part['title']]=case
                    bundle['cases'].append(case)
                anchor['case_catalogue_id']=case['id']
                part['case_catalogue_id']=case['id']
            key = (anchor['id'], source['url'])
            if key not in supplier_listings:
                row = deepcopy(anchor)
                row['id'] = -len(supplier_listings) - 1
                row['external_id'] = 'reviewed-supplier:' + sha256(source['url'].encode()).hexdigest()
                row.update(url=source['url'], source_name=source.get('source') or anchor['source_name'],
                           price=float(source['item_gbp']), condition=source['condition'], status='active')
                raw = dict(row.get('raw_specs') or {})
                raw['playbook_product_capture'] = {
                    **source, 'status': 'captured', 'merchant_name': source.get('source'),
                    'title': part['title'], 'reviewed_release_source': original.get('source'),
                    'original_capture_fingerprint': source.get('fingerprint'),
                }
                engineering = part.get('engineering') or {}
                if engineering.get('reviewed') is True:
                    raw['configurator'] = {**deepcopy(engineering),
                        'reviewed_product_title': part['title'],
                        'source_reference_kind': 'owner_reviewed_exact_product',
                        'origin_reviewed_by': engineering.get('reviewed_by'),
                        'reviewed_by': 'owner:approved-release-supplier'}
                row['raw_specs'] = raw
                supplier_listings[key] = row
                bundle['listings'].append(row)
            row = supplier_listings[key]
            part['listing_id'] = row['id']
            variant.update(listing_id=row['id'], status='active', consecutive_misses=0,
                           reject_reason=None, reviewed_by='owner:approved-release-supplier')
    return bundle
