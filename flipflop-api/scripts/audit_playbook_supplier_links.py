"""Read-only BOM -> bestseller -> ASIN/CPK -> supplier-price audit.

Run from flipflop-api. Writes inspectable JSON/CSV; never changes catalogue data.
"""
import asyncio
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select, text
from app.database import AsyncSessionLocal, engine
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.models.playbook import PlaybookProposal
from app.services.bestseller_catalogue_sync import _importable_bestseller_observation, amazon_asin
from app.services.curated_catalogue_range import select_curated_range
from app.services.playbook_service import _plausible_role_candidate
from app.services.playbook_stored_offers import stored_offers, offers_for_part, same_product
from app.services.curated_build_policy import definitions

OUT = Path(__file__).resolve().parents[2] / 'docs/playbook/audits/2026-10-26'
HARDWARE = {'cpu','gpu','motherboard','ram','storage','storage_secondary','psu','cooling','case'}
NOW = datetime.now(timezone.utc)
NAMES = {row['id']:row['name'] for row in definitions()['builds']}

def dt(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)

def money(value):
    try: return Decimal(str(value))
    except Exception: return None

def eligible(offer):
    return bool(offer.get('commercial_capture_verified') and offer.get('condition') == 'new'
        and offer.get('stock_status') in {'available','in_stock'}
        and timedelta(0) <= NOW-dt(offer.get('observed_at')) <= timedelta(hours=24)
        and money(offer.get('item_gbp')) is not None and money(offer['item_gbp']) > 0)

def total(offer):
    item = money(offer.get('item_gbp'))
    delivery = money(offer.get('delivery_gbp')) if offer.get('postage_verified') else Decimal(0)
    return item + (delivery or Decimal(0)) if item is not None else None

def urlkey(offer):
    parsed = urlsplit(offer.get('url') or '')
    return (parsed.hostname, amazon_asin(offer.get('url')) or parsed.path.rstrip('/'))

async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        proposals = (await db.execute(select(PlaybookProposal).where(
            PlaybookProposal.action=='UPDATE', PlaybookProposal.status=='pending')
            .order_by(PlaybookProposal.id.desc()))).scalars().all()
        cells = {}
        for proposal in proposals:
            offer = proposal.proposed_data or {}
            if offer.get('cell_id') and offer['cell_id'] not in cells:
                cells[offer['cell_id']] = {'proposal_id':proposal.id, 'proposed_at':proposal.proposed_at,
                    'offer':offer}
        listings = {row['id']:dict(row) for row in (await db.execute(text(
            'SELECT id,external_id,title,url,raw_specs,status FROM listings'))).mappings()}
        identities = [dict(row) for row in (await db.execute(text(
            'SELECT listing_id,cpk,cpk_data FROM gem_radar_listing_cpk'))).mappings()]
        registry = {row['listing_id']:row for row in identities}
        data_by_cpk = defaultdict(list)
        for row in identities:
            data_by_cpk[row['cpk']].append(row['cpk_data'] or {})
        history = (await db.execute(select(AmazonBestsellerObservation).where(
            AmazonBestsellerObservation.captured_at >= NOW.replace(tzinfo=None)-timedelta(days=30))
            .order_by(AmazonBestsellerObservation.captured_at.desc(),AmazonBestsellerObservation.id.desc()))).scalars().all()
        batch_times = {}
        for row in history:
            batch_times[row.category] = max(batch_times.get(row.category, row.captured_at),row.captured_at)
        current = [row for row in history if (batch_times[row.category]-row.captured_at).total_seconds()<60
            and _importable_bestseller_observation(row)
            and _plausible_role_candidate({'cooler':'cooling'}.get(row.category,row.category),row.title)]
        current = list({(row.category,row.asin):row for row in reversed(current)}.values())
        allowed, _ = select_curated_range(current, [])
        allowed_keys = {(row.category,row.asin) for row in allowed}
        by_asin = defaultdict(list)
        by_cpk = defaultdict(list)
        history_asins = {row.asin for row in history}
        for row in current:
            by_asin[row.asin].append(row)
            cpk = row.cpk or (registry.get(row.asin) or registry.get(f'amazon-bestseller:{row.asin}') or {}).get('cpk')
            if cpk: by_cpk[cpk].append(row)
        all_parts = [part for cell in cells.values() for part in cell['offer'].get('components',[])]
        index = await stored_offers(db,{part.get('cpk') for part in all_parts})
        rows=[]
        for cell_id, cell in cells.items():
            offer=cell['offer']
            for part in offer.get('components',[]):
                listing=listings.get(part.get('listing_id'),{})
                raw=listing.get('raw_specs') or {}
                anchor_asin=part.get('asin') or (raw.get('bestseller') or {}).get('asin') or amazon_asin(listing.get('url'))
                cpk=part.get('cpk') or (registry.get(listing.get('external_id')) or {}).get('cpk')
                probe={**part,'cpk':cpk}
                anchors=by_asin.get(anchor_asin,[]) if anchor_asin else []
                basis='asin' if anchors else None
                if not anchors and cpk:
                    for candidate in by_cpk.get(cpk,[]):
                        data=next(iter(data_by_cpk.get(cpk,[])),{})
                        if same_product(probe,{'title':candidate.title,'cpk':cpk,'cpk_data':data}):
                            anchors.append(candidate)
                    if anchors: basis='validated_cpk'
                allowed_anchors=[row for row in anchors if (row.category,row.asin) in allowed_keys]
                scope=('software_or_extra' if part['role'] not in HARDWARE else
                    'allowed_current_range' if allowed_anchors else 'current_list_outside_top_range' if anchors else
                    'historical_bestseller_only' if anchor_asin in history_asins else 'no_bestseller_link')
                selected=dict(part.get('suggested_supplier_offer') or {})
                quantity=int(part.get('quantity') or 1)
                selected_unit={**selected}
                for key in ('item_gbp','delivery_gbp'):
                    if money(selected.get(key)) is not None:
                        selected_unit[key]=str(money(selected[key])/quantity)
                matches=[row for row in offers_for_part(probe,index) if same_product(probe,row)]
                latest={}
                for candidate in [selected_unit,*matches]:
                    if not candidate.get('url') or money(candidate.get('item_gbp')) is None: continue
                    key=urlkey(candidate)
                    if key not in latest or dt(candidate.get('observed_at'))>dt(latest[key].get('observed_at')):
                        latest[key]=candidate
                choices=[row for row in latest.values() if eligible(row)]
                cheapest=min(choices,key=total) if choices else None
                selected_total=total(selected_unit)
                cheapest_total=total(cheapest) if cheapest else None
                saving=max(Decimal(0),(selected_total-cheapest_total)*quantity) if selected_total is not None and cheapest_total is not None else None
                vendor_matches=[row for row in latest.values() if 'amazon.co.uk' not in (urlsplit(row.get('url') or '').hostname or '')]
                rows.append({'cell_id':cell_id,'build_name':NAMES.get(cell_id,cell_id),
                    'proposal_id':cell['proposal_id'],'role':part['role'],'title':part['title'],
                    'listing_id':part.get('listing_id'),'variant_id':part.get('variant_id'),
                    'range_kind':(raw.get('curated_range') or {}).get('kind'),
                    'scope':scope,'anchor_asin':anchor_asin,'anchor_match_basis':basis,
                    'current_anchor_asins':sorted({row.asin for row in anchors}),
                    'amazon_listing_url':part.get('amazon_listing_url') or (f'https://www.amazon.co.uk/dp/{anchor_asin}' if anchor_asin else None),
                    'cpk':cpk,'quantity':quantity,'matched_vendor_links':len(vendor_matches),
                    'matched_vendor_sources':sorted({row.get('source') or '' for row in vendor_matches}),
                    'eligible_vendor_links':sum(eligible(row) for row in vendor_matches),
                    'selected_url':selected.get('url'),'selected_source':selected.get('source'),
                    'selected_total_gbp':str(selected_total*quantity) if selected_total is not None else None,
                    'selected_eligible':eligible(selected_unit),
                    'cheapest_eligible_url':cheapest.get('url') if cheapest else None,
                    'cheapest_eligible_total_gbp':str(cheapest_total*quantity) if cheapest_total is not None else None,
                    'possible_saving_gbp':str(saving) if saving is not None else None,
                    'supplier_offers':list(latest.values())})
        live=(await db.execute(text('SELECT count(*) FROM curated_build_segments WHERE is_live=true'))).scalar()
        jobs=[dict(row) for row in (await db.execute(text('SELECT job_id,mode,status,phase,started_at,completed_at FROM playbook_refresh_runs ORDER BY started_at DESC LIMIT 5'))).mappings()]
        current_counts=dict(Counter(row.category for row in current))
        allowed_counts=dict(Counter(row.category for row in allowed))
        await db.rollback()
    hardware=[row for row in rows if row['role'] in HARDWARE]
    report={'observed_at':NOW,'database_snapshot':'repeatable-read, read-only',
        'current_category_batch_times':batch_times,'current_list_counts':current_counts,
        'allowed_range_counts':allowed_counts,
        'summary':{'builds':len(cells),'live_builds':live,'hardware_occurrences':len(hardware),
            'unique_hardware_listings':len({row['listing_id'] for row in hardware}),
            'hardware_scope':dict(Counter(row['scope'] for row in hardware)),
            'hardware_with_cpk':sum(bool(row['cpk']) for row in hardware),
            'hardware_with_vendor_links':sum(row['matched_vendor_links']>0 for row in hardware),
            'hardware_with_eligible_vendor_links':sum(row['eligible_vendor_links']>0 for row in hardware),
            'hardware_selected_eligible':sum(row['selected_eligible'] for row in hardware),
            'hardware_with_cheaper_eligible_offer':sum((money(row['possible_saving_gbp']) or 0)>0 for row in hardware)},
        'cells':[{**{k:v for k,v in cell.items() if k!='offer'},'cell_id':key,
            'name':NAMES.get(key,key),'blockers':cell['offer'].get('blockers'),
            'compatibility_review':cell['offer'].get('compatibility_review'),
            'delivery_products':cell['offer'].get('delivery_products'),
            'complete_hardware':cell['offer'].get('complete_hardware')} for key,cell in cells.items()],
        'components':rows,'recent_jobs':jobs}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'supplier-link-audit.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    flat=[{key:value for key,value in row.items() if key!='supplier_offers'} for row in rows]
    with (OUT/'supplier-link-components.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    print(json.dumps(report['summary'],indent=2))
    print('Evidence:',OUT)
    await engine.dispose()

if __name__=='__main__': asyncio.run(main())
