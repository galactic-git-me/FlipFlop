"""Bounded Amazon identity discovery for authored requirements absent from drafts.

Search results establish identity only. Exact captures own commercial evidence.
"""
from datetime import datetime, timedelta, timezone
import hashlib
from sqlalchemy import select, text
from app.models.playbook import PlaybookProposal, Playbook
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.services.curated_build_policy import definitions
from app.services.curated_catalogue_range import _matches_requirement
from app.services.bestseller_catalogue_sync import amazon_asin
from app.services.playbook_service import required_parts, _plausible_role_candidate


def requested_specification(definition, role):
    components = definition.get('components') or {}
    if role == 'storage_secondary':
        drives = str(components.get('storage') or '').split('+')
        return drives[1].strip() if len(drives) > 1 else components.get(role)
    return str(components.get(role) or '').split('+')[0].strip()


def requirement_source_gaps(definition, offer):
    """Research missing parts and exact CPU/GPU defaults hidden by substitutions.

    An adequate substitute may still be quoted through the existing approval
    gates. It must not prevent bounded discovery of the authored default.
    """
    selected = {part['role']: part for part in offer.get('components', [])}
    roles = set(required_parts(definition)) - selected.keys()
    # A filled BOM slot is still a sourcing gap when its saved exact offer is
    # stale or explicitly unavailable. Keep retries bounded by the existing
    # per-requirement backoff and verify every discovered product separately.
    for role, part in selected.items():
        source=part.get('source_observation') or {}
        if not role.startswith('os') and source and (source.get('fresh') is False
                or source.get('stock_status')=='unavailable' or source.get('active_listing') is False):
            roles.add(role)
    for role in {'cpu', 'gpu'} & set(required_parts(definition)) & selected.keys():
        specification = requested_specification(definition, role)
        title = selected[role].get('title') or ''
        if specification and not _matches_requirement(role, title, specification):
            roles.add(role)
    return roles


async def discover_missing_requirement_sources(db, limit=6):
    from app.scrapers.amazon_scraper import _search_amazon_term
    from app.services.catalogue_service import compute_display_price
    # Search-only prices are never automatically promoted to supplier evidence.
    if not (await db.execute(text('SELECT pg_try_advisory_xact_lock(61311, 10)'))).scalar():
        return {'attempted':0,'linked':[],'unresolved':[],'status':'already_running','published':False}
    parents = (await db.execute(select(Playbook).where(Playbook.status=='active'))).scalars().all()
    definitions_by_id = {d['id']: d for d in definitions()['builds']}
    proposals = (await db.execute(select(PlaybookProposal).where(PlaybookProposal.action=='UPDATE').order_by(PlaybookProposal.id.desc()))).scalars().all()
    seen, missing = set(), {}
    for proposal in proposals:
        offer = proposal.proposed_data or {}
        cell = offer.get('cell_id')
        if cell not in definitions_by_id or cell in seen: continue
        seen.add(cell)
        definition = definitions_by_id[cell]
        roles = requirement_source_gaps(definition, offer)
        for role in sorted(roles):
            if role.startswith('os'): continue
            specification = requested_specification(definition, role)
            if specification: missing.setdefault((role, specification), []).append(cell)
    listings = (await db.execute(select(Listing).where(Listing.source_name=='amazon'))).scalars().all()
    by_asin = {amazon_asin(row.url): row for row in listings if amazon_asin(row.url)}
    slots = {(row.playbook_id,row.slot_type):row for row in (await db.execute(select(PlaybookSlot))).scalars()}
    report = {'attempted':0,'linked':[],'unresolved':[],'published':False}
    from app.models.commerce_evidence import PriceQuoteSnapshot
    for (role, specification), cells in missing.items():
        if report['attempted'] >= limit: break
        discovery_key = 'playbook-requirement:' + hashlib.sha256(f'v2:{role}:{specification}'.encode()).hexdigest()
        recent = (await db.execute(select(PriceQuoteSnapshot.id).where(
            PriceQuoteSnapshot.product_key==discovery_key,
            PriceQuoteSnapshot.created_at>=datetime.now(timezone.utc)-timedelta(hours=6)).limit(1))).scalar_one_or_none()
        if recent: continue
        report['attempted'] += 1
        print(f'Amazon requirement search: {role} / {specification}', flush=True)
        try:
            import re
            query = re.sub(r'\b(?:build[- ]cache|project|data|datasets?|scratch)\b', '', specification, flags=re.I)
            rows = await _search_amazon_term(query, 0, 20000)
        except Exception as error:
            rows = []
            report['unresolved'].append({'role':role,'specification':specification,'reason':type(error).__name__})
        db.add(PriceQuoteSnapshot(product_key=discovery_key,status='requirement_search',
            created_by_admin_id=0,evidence_json={'role':role,'specification':specification,'source':'amazon_search','result_count':len(rows)},
            decision_json={'published':False,'checkout_changed':False}))
        candidates = [row for row in rows if amazon_asin(row.get('url'))
            and _plausible_role_candidate(role,row.get('title'))
            and _matches_requirement(role,row.get('title') or '',specification)]
        # A processor search must never introduce an entire laptop/mini PC as a CPU.
        if role == 'cpu':
            import re
            candidates = [row for row in candidates if not re.search(r'\b(?:laptop|notebook|mini[- ]?pc|desktop computer|gaming computer)\b',row.get('title') or '',re.I)]
        if not candidates:
            report['unresolved'].append({'role':role,'specification':specification,'cells':cells,'reason':'No exact matching Amazon product identity returned'})
            continue
        row = candidates[0]
        asin = amazon_asin(row['url'])
        listing = by_asin.get(asin)
        if listing and (listing.raw_specs or {}).get('catalogue_deleted'):
            report['unresolved'].append({'role':role,'specification':specification,'reason':'Owner-deleted product remains excluded'})
            continue
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if listing is None:
            listing = Listing(external_id=f'amazon-requirement:{asin}',source_id=0,source_name='amazon',
                source_confidence='requirement_search_identity',title=row['title'],url=f'https://www.amazon.co.uk/dp/{asin}',
                price=row.get('price'),condition='new',listing_type='buy_it_now',status='active',
                image_urls=row.get('image_urls') or [],first_seen_at=now,last_seen_at=now,raw_specs={})
            db.add(listing)
            await db.flush()
            by_asin[asin]=listing
        pin_role = 'storage' if role=='storage_secondary' else role
        listing.raw_specs = {**(listing.raw_specs or {}),'curated_range_pin':{
            'role':pin_role,'reason':'Authored Playbook requirement missing from the normal ranked range',
            'cells':cells,'specification':specification,'asin':asin,'source_url':row['url']},
            'playbook_requirement_discovery':{'observed_at':now.isoformat()+'Z','source':'amazon_search','asin':asin,'commercially_verified':False}}
        roles = ['storage','storage_secondary'] if pin_role=='storage' else [role]
        for parent in parents:
            for linked_role in roles:
                slot=slots.get((parent.id,linked_role))
                if not slot: continue
                variant=(await db.execute(select(CatalogueVariant).where(CatalogueVariant.slot_id==slot.id,CatalogueVariant.listing_id==listing.id))).scalar_one_or_none()
                if variant is None:
                    db.add(CatalogueVariant(listing_id=listing.id,slot_id=slot.id,status='pending_review',
                        display_price=compute_display_price(listing.price or 0),tier='high',curated_for_builds=True,
                        custom_for_builds=False,custom_sale_status='out_of_stock'))
                elif variant.status!='rejected':
                    variant.curated_for_builds=True
        report['linked'].append({'role':role,'specification':specification,'asin':asin,'listing_id':listing.id,'cells':cells})
        await db.flush()
    return report
