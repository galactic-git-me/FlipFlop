"""Fill genuine Playbook range gaps from existing UK retailer captures."""
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import re
from urllib.parse import urlsplit

from sqlalchemy import select, text
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.services.curated_build_policy import definitions, _capacity_gb
from app.services.curated_catalogue_range import _matches_requirement

HOSTS = {'amazon.co.uk','scan.co.uk','overclockers.co.uk','awd-it.co.uk',
         'computerorbit.com','ebuyer.com','cclonline.com'}


def matches_requirement(role, title, specification):
    from app.services.playbook_service import _plausible_role_candidate
    if not _plausible_role_candidate(role,title):
        return False
    if role in {'storage','storage_secondary'} and re.search(r'\bexternal\b|\bportable\b|\bUSB\b',title,re.I):
        return False
    if role in {'storage','storage_secondary'} and not re.search(r'\bnvme\b|\bsata\b|\bm\.2\b|\bpcie\b',title,re.I):
        return False
    if role=='gpu':
        from app.services.playbook_component_facts import manufacturer_facts
        from app.services.benchmark_normaliser import normalise_gpu
        facts=manufacturer_facts(role,title)
        if facts and normalise_gpu(title)==normalise_gpu(specification):
            return facts.get('vram_gb',0)>=(_capacity_gb(specification) or 0)
    if role=='psu':
        wanted=re.search(r'\b(\d{3,4})\s*w\b',specification,re.I)
        actual=re.search(r'\b(\d{3,4})\s*w\b',title,re.I)
        return bool(wanted and actual and int(actual[1])>=int(wanted[1]))
    if role=='ram':
        generation=re.search(r'\bDDR[345]\b',specification,re.I)
        rdimm=bool(re.search(r'\bRDIMM\b',specification,re.I))
        if rdimm != bool(re.search(r'\bRDIMM\b|registered',title,re.I)):
            return False
        if re.search(r'SO[- ]?DIMM|SODIMM|laptop',title,re.I):
            return False
        if generation and not re.search(r'\b'+generation.group()+r'\b',title,re.I):
            return False
        capacity=_capacity_gb(title) or 0
        minimum=_capacity_gb(specification) or 0
        # Eight identical single RDIMMs are eight separately costed units.
        return capacity>=minimum or bool(rdimm and capacity and minimum%capacity==0
            and minimum/capacity<=8 and re.search(r'\b1\s*x\s*\d+\s*GB\b',title,re.I))
    if _matches_requirement(role,title,specification):
        return True
    if role in {'case','motherboard','cooling'}:
        tokens=lambda value:set(re.findall(r'[a-z]+|\d+',value.casefold()))
        wanted=tokens(specification)-{'case','motherboard','cooler','cpu','gaming'}
        return len(wanted)>=3 and wanted.issubset(tokens(title))
    return False


async def link_missing_requirements(db, offers):
    from app.services.playbook_service import required_parts,_plausible_role_candidate
    # Retract only our own accidentally matched accessory/B-grade inclusions.
    for listing in (await db.execute(select(Listing).where(
            Listing.raw_specs['playbook_requirement_source'].is_not(None)))).scalars():
        raw=dict(listing.raw_specs or {})
        pin=raw.get('curated_range_pin') or {}
        if not raw.get('playbook_requirement_source') or not pin.get('role'):
            continue
        role=pin['role']
        valid=_plausible_role_candidate(role,listing.title)
        if role=='storage':
            valid=valid and bool(re.search(r'\bnvme\b|\bsata\b|\bm\.2\b|\bpcie\b',listing.title,re.I))
            valid=valid and not re.search(r'\bexternal\b|\bportable\b|\bUSB\b',listing.title,re.I)
        if not valid:
            raw.pop('curated_range_pin',None)
            listing.raw_specs=raw
            for variant in (await db.execute(select(CatalogueVariant).where(CatalogueVariant.listing_id==listing.id))).scalars():
                variant.curated_for_builds=False
    definitions_by_id={row['id']:row for row in definitions()['builds']}
    needs=[]
    for offer in offers:
        definition=definitions_by_id[offer['cell_id']]
        selected={part['role'] for part in offer['components']
                  if part.get('listing_price_gbp') is not None}
        missing=set(required_parts(definition))-selected
        # Compare the required GPU model across stored board/vendor offers,
        # even when an expensive bestseller already fills the slot.
        if definition['components'].get('gpu'):
            missing.add('gpu')
        # A priced oversized kit must not hide a missing right-sized RAM
        # option. Revisit workstation memory too so equivalent arrangements
        # are compared by their full required quantity, not one DIMM's price.
        memory=next((part for part in offer['components'] if part['role']=='ram'),None)
        minimum=_capacity_gb(definition['components'].get('ram','')) or 0
        if memory and minimum:
            from app.services.playbook_service import _candidate_capacity
            if _candidate_capacity(memory)>minimum or re.search(r'\bRDIMM\b',memory['title'],re.I):
                missing.add('ram')
        # A workstation socket needs its actual cooler and EEB chassis, even
        # when a generic desktop product happened to fill those slots.
        if 'threadripper' in definition['components'].get('cpu','').casefold():
            missing.update(('case','cooling'))
        for role in missing:
            specification=definition['components'].get(role)
            if role=='storage_secondary':
                specification=definition['components']['storage'].split('+',1)[1].strip()
            if specification and not role.startswith('os'):
                needs.append((offer['playbook_id'],role,specification,offer['cell_id']))
    if not needs:
        return {'linked':0,'unresolved':[]}
    rows=(await db.execute(text('''
      SELECT * FROM (
        SELECT DISTINCT ON (o.listing_id) o.listing_id,o.title,o.source,o.item_price,
          o.postage_price,o.observed_at,o.commercial_source_evidence,o.image_urls,
          o.condition_normalised,o.listing_type,c.cpk
        FROM gem_radar_listing_observations o
        LEFT JOIN gem_radar_listing_cpk c USING (listing_id)
        WHERE o.observed_at>=:since AND o.source IN
          ('amazon','scan','overclockers','awd_it','computer_orbit','ebuyer','ccl')
        ORDER BY o.listing_id,o.observed_at DESC,o.id DESC
      ) latest WHERE condition_normalised='new' AND listing_type='buy_it_now'
        AND item_price>0 AND item_price<'Infinity'::float8
    '''),{'since':datetime.utcnow()-timedelta(days=30)})).mappings().all()
    valid=[]
    for row in rows:
        capture=row['commercial_source_evidence'] or {}
        url=capture.get('url') or ''
        host=(urlsplit(url).hostname or '').removeprefix('www.')
        if host not in HOSTS:
            continue
        valid.append((row,url,capture))
    slots={(slot.playbook_id,slot.slot_type):slot for slot in (await db.execute(select(PlaybookSlot))).scalars()}
    linked=0;unresolved=[]
    for parent_id,role,specification,cell_id in needs:
        candidates=[value for value in valid if matches_requirement(role,value[0]['title'],specification)]
        if not candidates:
            unresolved.append({'cell_id':cell_id,'role':role,'requirement':specification})
            continue
        def requirement_cost(value):
            row,_,capture=value
            quantity=1
            if role=='ram':
                minimum=_capacity_gb(specification) or 0
                capacity=_capacity_gb(row['title']) or 0
                if capacity and capacity<minimum:
                    quantity=int(minimum//capacity)
            return Decimal(str(row['item_price']))*quantity
        row,url,capture=min(candidates,key=lambda value:(value[2].get('stock_status') not in {'available','in_stock'},
                                                       abs((_capacity_gb(value[0]['title']) or 0)-(_capacity_gb(specification) or 0)) if role=='ram' and not re.search(r'\bRDIMM\b',specification,re.I) else 0,
                                                       requirement_cost(value),
                                                       -value[0]['observed_at'].timestamp(),value[0]['listing_id']))
        listing=(await db.execute(select(Listing).where(Listing.url==url).order_by(Listing.id).limit(1))).scalar_one_or_none()
        if listing is None:
            source_identity=str(row['listing_id'])
            identity_hash=hashlib.sha256(source_identity.encode('utf-8')).hexdigest()
            external_id=f"captured:{row['source']}:{identity_hash}"
            listing=(await db.execute(select(Listing).where(Listing.external_id==external_id))).scalar_one_or_none()
        if listing is None:
            listing=Listing(external_id=external_id,source_id=0,source_name=row['source'],
                source_confidence='stored_retail_capture',title=row['title'],url=url,
                price=row['item_price'],condition='new',listing_type='buy_it_now',status='active',
                image_urls=row['image_urls'] or [],first_seen_at=row['observed_at'],last_seen_at=row['observed_at'],raw_specs={})
            db.add(listing)
            await db.flush()
        raw=dict(listing.raw_specs or {})
        if raw.get('catalogue_deleted'):
            unresolved.append({'cell_id':cell_id,'role':role,'requirement':specification,'reason':'operator_deleted'})
            continue
        if listing.price is None:
            listing.price=row['item_price']
        raw.update(curated_range_pin={'role':'storage' if role=='storage_secondary' else role,
                    'reason':f'{cell_id}: required {specification}; existing UK retailer capture'},
                   playbook_requirement_source={'listing_id':row['listing_id'],'cpk':row['cpk'],
                    'observed_at':row['observed_at'].isoformat(),'url':url,
                    'item_gbp':str(row['item_price']), 'delivery_gbp':capture.get('delivery_gbp'),
                    'postage_verified':capture.get('postage_verified') is True,
                    'stock_status':capture.get('stock_status'),'product_properties':capture.get('product_properties') or {}},
                   gem_radar_category='storage' if role=='storage_secondary' else role)
        listing.raw_specs=raw
        slot=slots[parent_id,role]
        variant=(await db.execute(select(CatalogueVariant).where(
            CatalogueVariant.listing_id==listing.id,CatalogueVariant.slot_id==slot.id))).scalar_one_or_none()
        if variant is None:
            db.add(CatalogueVariant(listing_id=listing.id,slot_id=slot.id,status='pending_review',
                display_price=row['item_price'],tier='budget',curated_for_builds=True,
                custom_for_builds=False,custom_sale_status='out_of_stock',last_seen_at=row['observed_at'].isoformat()))
            linked+=1
        elif variant.status!='rejected' and not variant.curated_for_builds:
            variant.curated_for_builds=True
            linked+=1
    await db.flush()
    return {'linked':linked,'unresolved':unresolved}
