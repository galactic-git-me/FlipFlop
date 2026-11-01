"""Read-only audit of the canonical 24-cell Playbook against the serving catalogue.

Run from flipflop-api with PYTHONPATH=. Outputs evidence and gaps, never publishes
variants, invents stock, changes selling prices or approves model provenance.
"""
import argparse
import asyncio
import csv
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine
from app.services.curated_build_policy import definitions, _matches_curated_spec, matches_spec
from app.services.playbook_service import (list_playbook_product_engineering_suggestions,
    required_parts)


def approved(asset):
    return bool(asset['is_active'] and asset['status'] == 'FINAL' and asset['glb_ref']
                and asset['commercial_use_approved'] and asset['redistribution_approved'] and asset['scale_validated'])


async def audit(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    async with engine.connect() as db:
        async def rows(query):
            return [dict(row) for row in (await db.execute(text(query))).mappings().all()]
        playbooks = await rows('SELECT id,name,status,pricing_model FROM playbooks ORDER BY id')
        cells = await rows('SELECT id,customer_type,budget_level,is_live,selling_price,proposed_selling_price,approved_upgrades FROM curated_build_segments')
        candidates = await rows('''SELECT v.id,v.status,v.display_price,v.curated_for_builds,s.slot_type,
            s.playbook_id,l.title,l.image_urls,l.price AS supplier_price,l.status::text AS listing_status,
            l.last_seen_at FROM catalogue_variants v JOIN playbook_slots s ON s.id=v.slot_id
            JOIN listings l ON l.id=v.listing_id''')
        assets = await rows('''SELECT id,subject_type::text AS subject_type,subject_id,category,status::text AS status,version,
            is_active,glb_ref,commercial_use_approved,redistribution_approved,scale_validated,review_decision
            FROM component_3d_assets''')
        counts = {}
        for table in ('supplier_offer_evidence','workshop_capacity_evidence','price_quote_snapshots'):
            counts[table] = (await db.execute(text(f'SELECT count(*) FROM {table}'))).scalar_one()
        counts['playbook_motherboard_specs_awaiting_review'] = (await db.execute(text('''
            SELECT count(*) FROM motherboard_specs
            WHERE source='ai_generated' AND reviewed=false
              AND raw_ai_response->>'playbook_source_url' IS NOT NULL
        '''))).scalar_one()
        async with AsyncSessionLocal() as session:
            product_engineering_reviews=await list_playbook_product_engineering_suggestions(session)
        counts['playbook_product_engineering_suggestions_awaiting_review']=len(product_engineering_reviews)
        counts['playbook_product_engineering_suggestions_by_role']=dict(Counter(
            item.get('role','unknown') for item in product_engineering_reviews))
        gamers_outlet_capture = (await db.execute(text('''
            WITH offers AS (
              SELECT DISTINCT ON (external_id)
                title, price, last_seen_at,
                raw_specs->'gamers_outlet' AS supplier,
                raw_specs->'playbook_product_capture' AS capture,
                raw_specs->'playbook_licence_source_review' AS review
              FROM listings
              WHERE source_name='Gamers Outlet'
                AND raw_specs->'gamers_outlet'->>'category' IN ('os','office')
              ORDER BY external_id,last_seen_at DESC NULLS LAST,id DESC
            )
            SELECT
              count(*) FILTER (WHERE supplier->>'category'='os') AS windows_licence_candidates,
              count(*) FILTER (WHERE supplier->>'category'='os' AND title ~* '\\mhome\\M'
                AND capture->>'item_gbp' IS NULL) AS windows_11_unpriced_home,
              count(*) FILTER (WHERE supplier->>'category'='os' AND title ~* '\\mpro\\M'
                AND capture->>'item_gbp' IS NULL) AS windows_11_unpriced_pro,
              count(*) FILTER (WHERE supplier->>'category'='os'
                AND capture->>'status'='captured' AND capture->>'item_gbp' IS NOT NULL) AS priced_windows_offers,
              count(*) FILTER (WHERE supplier->>'category'='office') AS office_candidates,
              count(*) FILTER (WHERE capture->>'status'='captured'
                AND nullif(capture->>'observed_at','')::timestamptz >= now()-interval '24 hours') AS fresh_captured_offers,
              count(*) FILTER (WHERE coalesce(review->>'reviewed','false')='true') AS source_reviewed_offers,
              count(*) FILTER (WHERE coalesce(supplier->>'customer_offering_enabled','false')='true'
                OR coalesce(capture->>'customer_offering_enabled','false')='true') AS customer_enabled_offers
            FROM offers
        '''))).mappings().one()
        counts.update({f'gamers_outlet_{key}':value for key,value in dict(gamers_outlet_capture).items()})
    await engine.dispose()

    async with httpx.AsyncClient(base_url='http://127.0.0.1:4311', timeout=45) as client:
        response = await client.get('/api/public/curated-builds'); response.raise_for_status()
        public_builds = {item['id']:item for item in response.json()}
        response = await client.get('/api/commerce-intelligence/playbook-service/proposals')
        response.raise_for_status()
        generated_proposals = response.json().get('items', [])
        response = await client.get('/api/public/cases'); response.raise_for_status()
        cases = response.json()
        slots_by_build = {}
        semaphore = asyncio.Semaphore(3)
        async def get_slots(build):
            if not build.get('playbook_id'): return
            async with semaphore:
                response=await client.get(f"/api/public/playbooks/{build['playbook_id']}/curated-slots", params={'build_id':build['id']})
                response.raise_for_status(); slots_by_build[build['id']]=response.json()
        await asyncio.gather(*(get_slots(build) for build in public_builds.values()))
        active_models = []
        for asset in assets:
            if not approved(asset): continue
            # GLBs are served by the API's media route, never the storefront
            # development port. Log only the returned status, not signed URLs.
            path=urlsplit(asset['glb_ref']).path
            try:
                result=await client.head(path)
                checked={'asset_id':asset['id'],'subject_type':asset['subject_type'],
                    'subject_id':asset['subject_id'],'api_media_http_status':result.status_code}
                active_models.append(checked)
            except httpx.HTTPError:
                active_models.append({'asset_id':asset['id'],'http_status':None})

    active_playbooks={row['name']:row for row in playbooks if row['status']=='active'}
    proposal_by_cell={row.get('cell_id'):row for row in generated_proposals}
    cell_map={(row['customer_type'],row['budget_level']):row for row in cells}
    asset_map={}
    for asset in assets: asset_map.setdefault((asset['subject_type'],asset['subject_id']),[]).append(asset)
    build_report=[]; part_report=[]
    for definition in definitions()['builds']:
        public=public_builds.get(definition['id'],{})
        cell=cell_map.get((definition['segment'],definition['tier']),{})
        playbook=active_playbooks.get(definition['segment'])
        proposal=proposal_by_cell.get(definition['id'],{})
        proposal_roles=sorted({part.get('role') for part in proposal.get('components',[])
            if part.get('role')})
        missing_proposal_roles=sorted(set(required_parts(definition))-set(proposal_roles))
        delivery_products=proposal.get('delivery_products') or {}
        selected_slots={slot['slot_type']:slot for slot in slots_by_build.get(definition['id'],[])}
        policy=((playbook or {}).get('pricing_model') or {}).get('commercial_cells',{}).get(definition['id'])
        for category,specification in definition['components'].items():
            slot=selected_slots.get(category,{})
            selected_id=slot.get('default_variant_id')
            choices=[item for tier in slot.get('variants_by_tier',{}).values() for item in tier]
            selected=next((item for item in choices if item['id']==selected_id),None)
            matched=[item for item in candidates if item['slot_type']==category
                     and _matches_curated_spec(category,item,specification)] if category!='case' else []
            photo_candidates=[item for item in matched if item['image_urls']]
            model_assets=[asset for item in matched for asset in asset_map.get(('VARIANT',item['id']),[])]
            if category=='case':
                case_matches=[item for item in cases if matches_spec(item['name'],specification)
                              or matches_spec(f"{item['brand']} {item['name']}",specification)]
                photo_candidates=[item for item in case_matches if item['images']]
                model_assets=[asset for item in case_matches for asset in asset_map.get(('CASE',item.get('asset_subject_id') or item['id']),[])]
            usable=[asset for asset in model_assets if approved(asset)]
            part_report.append({'build_id':definition['id'],'build_name':public.get('name',definition['name']),
                'segment':definition['segment'],'tier':definition['tier'],'category':category,'planned_specification':specification,
                'selected_variant_id':selected_id,'selected_title':selected.get('title') if selected else None,
                'selected_display_price_gbp':selected.get('display_price') if selected else None,
                'selected_image_count':len((selected or {}).get('images') or []),
                'catalogue_match_count':len(matched),'matched_image_candidates':len(photo_candidates),
                'approved_exact_models':len(usable),'model_required':category!='os',
                'supplier_stock_verified':False,
                'candidate_variant_ids':','.join(str(item['id']) for item in matched[:10]),
                'blockers':'; '.join(filter(None,[
                    'No matching active Playbook' if not playbook else '',
                    'No selected catalogue part' if category!='case' and not selected else '',
                    'No matching product-photo candidate' if not photo_candidates else '',
                    'No verified supplier-stock evidence' if counts['supplier_offer_evidence']==0 else 'Supplier offer requires per-part verification']))})
        build_report.append({'build_id':definition['id'],'name':public.get('name',definition['name']),
            'segment':definition['segment'],'tier':definition['tier'],'active_playbook_id':(playbook or {}).get('id'),
            'missing_components':public.get('missing_components',list(definition['components'])),
            'public_price_gbp':public.get('price_gbp'),'approved_selling_price_gbp':cell.get('selling_price'),
            'proposed_selling_price_gbp':cell.get('proposed_selling_price'),'published':cell.get('is_live',False),
            'published_upsells':len(public.get('upgrade_options',[])),
            'commercial_policy_present':bool(policy),'checkout_enabled':bool(policy and policy.get('checkout_enabled')),
            'proposal_component_count':len(proposal.get('components') or []),
            'proposal_component_roles':proposal_roles,
            'proposal_missing_required_roles':missing_proposal_roles,
            'proposal_complete_hardware':bool(proposal.get('complete_hardware')),
            'proposal_compatibility_verified':bool((proposal.get('compatibility') or {}).get('verified')),
            'proposal_priced_modes':[mode for mode in ('fast_track','standard','flexible')
                if (delivery_products.get(mode) or {}).get('recommended_price_gbp') is not None],
            'proposal_blocker_count':len(proposal.get('blockers') or []),
            'fully_verified':False})
    summary={'builds':len(build_report),'segments':len({item['segment'] for item in build_report}),
        'part_requirements':len(part_report),'unique_part_specifications':len({(item['category'],item['planned_specification']) for item in part_report}),
        'builds_without_active_playbook':sum(not item['active_playbook_id'] for item in build_report),
        'builds_with_public_price':sum(item['public_price_gbp'] is not None for item in build_report),
        'builds_with_approved_selling_price':sum(item['approved_selling_price_gbp'] is not None for item in build_report),
        'published_upsells':sum(item['published_upsells'] for item in build_report),
        'approved_active_models':len(active_models),'model_http_checks':active_models,
        'hidden_variants':sum(item['status']=='hidden' for item in candidates),**counts}
    reviewable={}
    for proposal in generated_proposals:
        for part in proposal.get('components', []):
            source=part.get('source_observation') or {}
            if part.get('role')=='wireless_adapter':
                continue  # A connectivity extra does not need a catalogue photo or 3D model.
            if (source.get('fresh') and source.get('commercial_capture_verified')
                    and source.get('active_listing') and source.get('condition')=='new'
                    and source.get('listing_type')=='buy_it_now' and source.get('stock_status')=='available'
                    and source.get('stock_evidence') and source.get('postage_verified')
                    and source.get('url','').startswith(('https://www.amazon.co.uk/','https://amazon.co.uk/',
                        'https://www.overclockers.co.uk/','https://overclockers.co.uk/'))):
                reviewable.setdefault(part['listing_id'], part)
    definitions_by_id={item['id']:item for item in definitions()['builds']}
    def missing_required_roles(row):
        definition=definitions_by_id.get(row.get('cell_id'))
        if definition is None:return []
        roles={part.get('role') for part in row.get('components',[])}
        return sorted(set(required_parts(definition))-roles)
    proposal_report=[{'cell_id':row.get('cell_id'),'segment':row.get('segment'),'tier':row.get('tier'),
        'name':row.get('name'),'complete_hardware':row.get('complete_hardware'),
        'component_roles':sorted({part.get('role') for part in row.get('components',[])
            if part.get('role')}),
        'missing_required_roles':missing_required_roles(row),
        'blockers':row.get('blockers',[]),'delivery_products':row.get('delivery_products',{}),
        'compatibility_verified':(row.get('compatibility') or {}).get('verified',False)}
        for row in generated_proposals]
    summary.update({'generated_proposals':len(proposal_report),
        'proposals_ready_for_approval':sum(not row['blockers'] for row in proposal_report),
        'complete_hardware_proposals':sum(bool(row['complete_hardware']) for row in proposal_report),
        'proposals_missing_required_roles':sum(bool(row['missing_required_roles']) for row in proposal_report),
        'compatibility_verified_proposals':sum(row['compatibility_verified'] for row in proposal_report),
        'proposals_with_all_delivery_prices':sum(all((row['delivery_products'].get(mode) or {}).get('recommended_price_gbp') is not None
            for mode in ('fast_track','standard','flexible')) for row in proposal_report),
        'missing_catalogue_os_proposals':sum(any('matching os catalogue product' in blocker for blocker in row['blockers'])
            for row in proposal_report),
        'distinct_supplier_products_ready_for_review':len(reviewable),
        'supplier_component_appearances_ready_for_review':sum(1 for proposal in generated_proposals
            for part in proposal.get('components', []) if part.get('listing_id') in reviewable),
        'proposal_photo_approval_appearances':sum(1 for proposal in generated_proposals
            for part in proposal.get('components', []) if part.get('photo_ready') is False
            and part.get('role')!='wireless_adapter'),
        'distinct_proposal_listings_missing_photo_approval':len({part.get('listing_id')
            for proposal in generated_proposals for part in proposal.get('components', [])
            if part.get('photo_ready') is False and part.get('role')!='wireless_adapter'
            and part.get('listing_id') is not None}),
        'proposal_components_without_final_model':sum(1 for proposal in generated_proposals
            for part in proposal.get('components', []) if part.get('media_ready') is False
            and not str(part.get('role') or '').startswith('os')
            and part.get('role')!='wireless_adapter'),
        'distinct_proposal_products_without_final_model':len({part.get('variant_id')
            for proposal in generated_proposals for part in proposal.get('components', [])
            if part.get('media_ready') is False and not str(part.get('role') or '').startswith('os')
            and part.get('role')!='wireless_adapter' and part.get('variant_id') is not None}),
        'wireless_adapter_builds':sum(any(part.get('role')=='wireless_adapter'
            for part in proposal.get('components', [])) for proposal in generated_proposals),
        'pending_wireless_adapter_variants':len({part.get('variant_id')
            for proposal in generated_proposals for part in proposal.get('components', [])
            if part.get('role')=='wireless_adapter' and not part.get('catalogue_approved')}),
        # Count the role-level automatic-sourcing blockers too. The proposal
        # service reports these as "matching <role> catalogue product"; the
        # older phrase checks missed both authored second drives and dual-OS
        # requirements, making the readiness report falsely show zero gaps.
        'proposals_missing_separate_storage_devices':sum(any(
            'storage_secondary' in blocker or 'storage device separately' in blocker
            for blocker in row['blockers']) for row in proposal_report),
        'proposals_missing_dual_boot_products':sum(any(
            'os_secondary' in blocker or 'Ubuntu and Windows dual-boot' in blocker
            for blocker in row['blockers']) for row in proposal_report)})
    payload={'audited_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'local serving API and local database; no external stock assertions',
        'summary':summary,'builds':build_report,'generated_proposals':proposal_report,'parts':part_report,
        'asset_status_counts':{state:sum(asset['status']==state for asset in assets) for state in sorted({asset['status'] for asset in assets})}}
    (output/'readiness.json').write_text(json.dumps(payload,indent=2,default=str)+'\n',encoding='utf-8')
    unique_parts={}
    for item in part_report:
        key=(item['category'],item['planned_specification'])
        entry=unique_parts.setdefault(key,{'category':key[0],'planned_specification':key[1],
            'used_by_builds':[],'photo_candidate_found':False,'approved_exact_model_found':False,
            'physical_3d_required':item['model_required'],'supplier_stock_verified':False})
        entry['used_by_builds'].append(item['build_id'])
        entry['photo_candidate_found'] |= bool(item['matched_image_candidates'])
        entry['approved_exact_model_found'] |= bool(item['approved_exact_models'])
    for item in unique_parts.values(): item['used_by_builds']=','.join(item['used_by_builds'])
    for name,records in [('builds',build_report),('parts',part_report),('unique-parts',list(unique_parts.values()))]:
        with (output/f'{name}.csv').open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    lines=['# Playbook readiness audit','',f"Audited: {payload['audited_at_utc']}",'',
        'No build is marked verified merely because a planning BOM, photograph or stale listing exists. OS licences do not require physical 3D models.','',
        '## Summary','',*[f'- {key}: {value}' for key,value in summary.items()], '',
        '## Published storefront and generated proposals','',
        'A blank public price means the cell has not been published. Proposal component counts below describe the separate Playbook-generated draft and must not be mistaken for a storefront selection.',
        '', '| Segment | Tier | Build | Published price | Proposal parts | Missing required roles | Complete hardware | Compatible | Priced modes | Proposal blockers |',
        '|---|---|---|---:|---|---|---|---|---:|---:|']
    for item in build_report:
        missing=', '.join(item['proposal_missing_required_roles']) or '—'
        lines.append(f"| {item['segment']} | {item['tier']} | {item['name']} | {item['public_price_gbp'] or 'Not published'} | {item['proposal_component_count']} ({', '.join(item['proposal_component_roles'])}) | {missing} | {'yes' if item['proposal_complete_hardware'] else 'no'} | {'yes' if item['proposal_compatibility_verified'] else 'no'} | {len(item['proposal_priced_modes'])}/3 | {item['proposal_blocker_count']} |")
    lines+=['','## What remains and who acts','',
        'The authenticated review screen is `http://localhost:4312/playbooks/commercial`, with separate Build proposals, Supplier listings, Compatibility, Software licences and Workshop planning areas. Scheduled automation health is shown near the top. Routine source refresh and proposal rebuilds run automatically; use the tabs to review evidence and approve or reject proposals. Automation does not publish products.',
        '', '### Human review and approvals', '',
        f"- Review the {summary['distinct_supplier_products_ready_for_review']} distinct hardware supplier listings in the Supplier listings area (the {summary['supplier_component_appearances_ready_for_review']} proposal appearances reuse those listings). Confirm the exact listing, new condition, stock statement, item price, postage and arrival estimate. This records cost evidence; it does not set a selling price or publish a build.",
        f"- Review {summary['gamers_outlet_windows_licence_candidates']} Windows and {summary['gamers_outlet_office_candidates']} Office offers in the Software licences area. Gamers Outlet captures only establish the seller's current product and pricing claims; they do not establish independent licence entitlement or resale rights.",
        f"- Review the {summary['playbook_motherboard_specs_awaiting_review']} automatically researched motherboard suggestions in the Compatibility area against their linked source evidence. Use “Approve reviewed specs” only for facts the source confirms. Unreviewed suggestions never count as compatibility proof.",
        f"- Review {summary['playbook_product_engineering_suggestions_awaiting_review']} exact-product engineering suggestions in the Compatibility area (by role: {summary['playbook_product_engineering_suggestions_by_role']}). Suggestions use captured listing facts and remain unverified until you approve them.",
        f"- Review photo choices for {summary['distinct_proposal_listings_missing_photo_approval']} exact proposal listings ({summary['proposal_photo_approval_appearances']} build-role appearances) in Admin → PC Builder (`/pc-builder`) → Listing Images. Review generated product models separately in Catalogue → 3D Assets (`/catalogue/3d-assets`); a photo approval alone does not approve a model or publish a product.",
        '', '### Playbook service work after review', '',
        '1. Keep searching the curated/custom catalogues for exact planned parts and current supplier facts. Never fill missing prices, stock or specs by hand, and never treat hidden variants as available stock. A missing exact supplier offer stays blocked until a real catalogue listing can be sourced and reviewed.',
        '2. Resolve every compatibility check with reviewed exact component specifications. A full BOM is not saleable while any required check is unknown or warns of a physical conflict.',
        '3. Get fresh source stock, postage and arrival evidence for every chosen part. The delivery engine must exclude parts whose supplier ETA violates Fast Track, Standard or Flex promises.',
        '4. Calculate all three complete-build prices and estimated profits from the approved cost/margin policy and current catalogue facts; generate compatible, priced upsells through the same service.',
        '5. Complete required exact-product images/models, delivery timing, storefront configurator and exact-configuration checkout verification. Use the Workshop Calendar to plan paid orders; do not set a weekly build count or use one to cap checkout. Publish only after an operator approves the exact proposal.',
        '', '## Generated proposal blockers','',
        'These rows come from the live Playbook-service proposals, separate from the currently empty public storefront. The `generated_proposals` array in readiness.json preserves each exact cell blocker and all three delivery-price results.',
        '',*[f"- {key}: {summary[key]}" for key in ('generated_proposals','proposals_ready_for_approval',
            'complete_hardware_proposals','proposals_missing_required_roles',
            'compatibility_verified_proposals','proposals_with_all_delivery_prices',
            'proposal_photo_approval_appearances','distinct_proposal_listings_missing_photo_approval',
            'proposal_components_without_final_model','distinct_proposal_products_without_final_model',
            'missing_catalogue_os_proposals','distinct_supplier_products_ready_for_review',
            'supplier_component_appearances_ready_for_review','playbook_motherboard_specs_awaiting_review',
            'playbook_product_engineering_suggestions_awaiting_review','playbook_product_engineering_suggestions_by_role',
            'proposals_missing_separate_storage_devices','proposals_missing_dual_boot_products',
            'wireless_adapter_builds','pending_wireless_adapter_variants',
            'gamers_outlet_windows_licence_candidates','gamers_outlet_windows_11_unpriced_home',
            'gamers_outlet_windows_11_unpriced_pro','gamers_outlet_priced_windows_offers',
            'gamers_outlet_office_candidates','gamers_outlet_fresh_captured_offers',
            'gamers_outlet_source_reviewed_offers','gamers_outlet_customer_enabled_offers')],
        '', 'The local media schema repair restored four missing image/video fields and backfilled existing primary images. Unrelated migration history was not stamped or applied. The corresponding migration now tolerates already-present media fields.']
    (output/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,default=str))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    asyncio.run(audit(parser.parse_args().output))
