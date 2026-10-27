"""Playbook-owned discovery searches and unapproved browser market captures."""
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import select
from app.models.playbook import Playbook, PlaybookProposal
from app.models.commerce_evidence import PriceQuoteSnapshot
from app.services.curated_build_policy import definitions
from app.services.playbook_market import bom_hash, search_query, candidate, core_spec_blockers, key, latest
from app.services.commercial_readiness import cell_context

VENDORS = ['ebay','amazon','overclockers','scan','awd_it','computer_orbit','bargain_hardware','newegg_uk','ebuyer','google_shopping']
HOSTS = {'amazon':('amazon.co.uk',), 'overclockers':('overclockers.co.uk',), 'scan':('scan.co.uk',),
    'awd_it':('awd-it.co.uk',), 'computer_orbit':('computerorbit.com',),
    'bargain_hardware':('bargainhardware.co.uk',), 'newegg_uk':('newegg.com',),
    'ebuyer':('ebuyer.com',), 'google_shopping':('google.com','google.co.uk')}


def selected_parts(definition,parent,proposals):
    offer=next((p.proposed_data for p in proposals if p.playbook_id==parent.id
        and (p.proposed_data or {}).get('cell_id')==definition['id']),None)
    offer=offer or ((parent.pricing_model or {}).get('managed_offers') or {}).get(definition['id'])
    parts={p['role']:p for p in (offer or {}).get('components',[])}
    return parts or {role:{'title':title} for role,title in definition['components'].items()}


async def context(db,parent_id,cell_id,lock=False):
    parent,definition=await cell_context(db,parent_id,cell_id,lock=lock)
    if lock:await db.refresh(parent)
    proposals=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.playbook_id==parent_id,
        PlaybookProposal.status=='pending',PlaybookProposal.action=='UPDATE')
        .order_by(PlaybookProposal.id.desc()).execution_options(populate_existing=True))).scalars().all()
    return parent,definition,selected_parts(definition,parent,proposals)


def target(definition, parent, parts):
    query = search_query(parts)
    # Motherboard is useful when listed; keep the broad CPU/GPU/RAM/storage
    # query too because many complete-PC titles omit the board model.
    motherboard = (parts.get('motherboard') or {}).get('title')
    tags = [f"Playbook:{definition['id']}", 'Complete-build-market']
    identities = {}
    for role, part in parts.items():
        identity = {name:str(part[name]) for name in ('asin','cpk') if part.get(name)}
        identities[role] = identity
        tags.extend(f'{name.upper()}:{role}:{value}' for name,value in identity.items() if len(f'{name}:{role}:{value}') <= 80)
    return {'id':f"playbook-market-{definition['id']}", 'label':f"{definition['name']} · {definition['segment']} · {definition['tier']}",
        'query':query, 'preciseQuery':f'{motherboard} {query}' if motherboard else query,
        'tags':tags, 'marketplaces':VENDORS, 'listingMode':'both',
        'playbookTarget':{'playbookId':parent.id,'cellId':definition['id'],'bomSha256':bom_hash(definition,parts)},
        'componentIdentities':identities}


async def searches(db):
    parents=(await db.execute(select(Playbook).where(Playbook.status=='active'))).scalars().all()
    proposals=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.status=='pending',
        PlaybookProposal.action=='UPDATE').order_by(PlaybookProposal.id.desc()))).scalars().all()
    items=[]
    for definition in definitions()['builds']:
        parent=next((p for p in parents if p.name==definition['segment']),None)
        if not parent:continue
        parts=selected_parts(definition,parent,proposals)
        items.append(target(definition,parent,parts))
    component_items=await component_searches(db,proposals)
    return {'items':items,'count':len(items),'componentItems':component_items,
            'componentCount':len(component_items)}


async def ingest(db, body):
    parent,definition,parts=await context(db,body.playbook_id,body.cell_id,lock=True)
    if bom_hash(definition,parts)!=body.bom_sha256:
        raise HTTPException(409,'Playbook selection changed; sync the extension searches before collecting again')
    if body.vendor not in VENDORS or body.kind=='sold' and body.vendor!='ebay':
        raise HTTPException(422,'Only eBay supports completed-sale capture')
    source=urlsplit(body.source_url)
    if source.scheme!='https' or source.username or source.password:
        raise HTTPException(422,'A public HTTPS search source is required')
    if body.kind=='sold' and not (source.hostname or '').endswith('.ebay.co.uk'):
        raise HTTPException(422,'Sold evidence must originate from eBay')
    from urllib.parse import parse_qs
    if body.kind=='sold' and parse_qs(source.query).get('LH_Sold')!=['1']:
        raise HTTPException(422,'The source must be a sold-results search')
    previous=await latest(db,parent.id,definition['id'])
    prior=(previous.evidence_json or {}) if previous else {}
    now=datetime.now(timezone.utc)
    # Avoid merging old cohorts into a fresh capture or another build revision.
    retained=prior.get('candidates',[]) if prior.get('bom_sha256')==body.bom_sha256 else []
    retained=[row for row in retained if row.get('observed_at') and
        (now-datetime.fromisoformat(row['observed_at'])).total_seconds()<86400]
    rows={row['id']:row for row in retained}
    for i,item in enumerate(body.listings):
        parsed=urlsplit(item.url)
        allowed=body.vendor=='ebay' or any(parsed.hostname==h or (parsed.hostname or '').endswith('.'+h) for h in HOSTS.get(body.vendor,()))
        raw={'title':item.title,'url':item.url,'price':item.item_price,
             'postage':item.postage_price if item.delivery_cost_known else None,
             'condition':item.condition_normalised,'sold_at':item.sold_date_text}
        row=candidate(raw,body.kind,'new',i)
        if body.vendor!='ebay':
            identity=hashlib.sha256((parsed.hostname or '').encode()+parsed.path.encode()).hexdigest()[:24]
            row['id']=f'active:{body.vendor}:{identity}'
            if allowed and parsed.scheme=='https' and not parsed.username and not parsed.password:
                row['url']=item.url
                row['blockers']=[b for b in row['blockers'] if b!='Exact eBay listing URL missing']
        row['blockers'].extend(core_spec_blockers(item.title,parts))
        if not allowed:row['blockers'].append('Listing host does not match the vendor')
        if item.currency!='GBP':row['blockers'].append('GBP price required')
        if item.price_is_range:row['blockers'].append('Configurable price range is not one verified configuration price')
        if body.kind=='sold' and not item.sold_confirmed:row['blockers'].append('Sold marker not captured')
        if body.kind=='sold' and item.best_offer_enabled:row['blockers'].append('Accepted best-offer sale price is not verified')
        row.update(vendor=body.vendor,observed_at=now.isoformat(),source_url=body.source_url)
        rows[row['id']]=row
    snapshot=PriceQuoteSnapshot(product_key=key(parent.id,definition['id']),status='market_candidates',
        created_by_admin_id=0,evidence_json={'bom_sha256':body.bom_sha256,'condition':'new',
            'observed_at':min((row['observed_at'] for row in rows.values()),default=now.isoformat()),
            'components':{role:p['title'] for role,p in parts.items()},'candidates':list(rows.values())[-300:],
            'errors':[],'source':'extension_browser','search_id':body.search_id},decision_json={'purchasable':False})
    db.add(snapshot);await db.commit()
    return {'captured':len(body.listings),'batch_id':snapshot.id,'approved':False}


async def component_searches(db, proposals):
    """Current active curated identities, shared across segments; no provider calls."""
    from sqlalchemy import text
    from app.services.catalogue_cpk import identity_is_usable
    selected={part.get('listing_id') for proposal in proposals
        for part in (proposal.proposed_data or {}).get('components',[])}
    attention={part.get('listing_id') for proposal in proposals
        for part in (proposal.proposed_data or {}).get('components',[])
        if not ((part.get('source_observation') or {}).get('fresh')
            and (part.get('source_observation') or {}).get('active_listing')
            and (part.get('source_observation') or {}).get('stock_status')=='available'
            and (part.get('source_observation') or {}).get('condition')=='new')}
    rows=(await db.execute(text("""
      SELECT DISTINCT l.id,l.title,l.external_id,s.slot_type AS role,c.cpk,c.cpk_data
      FROM catalogue_variants v
      JOIN listings l ON l.id=v.listing_id
      JOIN playbook_slots s ON s.id=v.slot_id
      LEFT JOIN gem_radar_listing_cpk c ON c.listing_id=l.external_id
      WHERE v.curated_for_builds IS TRUE AND v.status='active'
        AND l.status='active' AND s.slot_type NOT IN ('os','os_secondary')
      ORDER BY l.id,s.slot_type
    """))).mappings().all()
    import re
    categories={'cpu':'164','gpu':'27386','motherboard':'1244','ram':'170083',
        'storage':'175669','psu':'42017','cooling':'131486','case':'42014'}
    grouped={}
    for row in rows:
        role='storage' if row['role']=='storage_secondary' else row['role']
        if role not in categories:continue
        data=row['cpk_data'] or {}
        from app.gem_radar.product_identifiers import normalise_brand, title_brand
        normalized=lambda value:re.sub(r'[^a-z0-9]','',str(value).casefold())
        brand=normalise_brand(data.get('brand'))
        cpk=row['cpk'] if (row['cpk'] and brand and (brand==title_brand(row['title']) or brand in normalized(row['title']))
            and identity_is_usable(row['title'],data,{role})) else None
        # Capacity-only RAM identities cannot merge different product families.
        if role=='ram' and not data.get('identity_claims') and not any(word in str(data.get('model') or '').casefold()
                for word in ('vengeance','fury','dominator','trident','ripjaws','proart','lancer')):
            cpk=None
        asin_match=re.search(r'(?:amazon-bestseller:)?\b(B0[A-Z0-9]{8})\b',row['external_id'] or '',re.I)
        asin=asin_match[1].upper() if asin_match else None
        identity=asin or cpk or str(row['id'])
        group=grouped.setdefault((role,identity),{'row':row,'cpk':cpk,'asin':asin,'used':False,'attention':False})
        group['used'] |= row['id'] in selected
        group['attention'] |= row['id'] in attention
    items=[]
    for (role,identity),g in grouped.items():
        row=g['row'];digest=hashlib.sha256(f'{role}:{identity}'.encode()).hexdigest()[:20]
        data=row['cpk_data'] or {}
        tags=['curated','Managed-catalogue',f'Role:{role}']
        if g['cpk']:tags.append(f"CPK:{g['cpk']}")
        if g['asin']:tags.append(f"ASIN:{g['asin']}")
        # Supplier marketing after commas/bars is not part of product identity.
        query=re.sub(r'\s+',' ',re.split(r'[,|]',row['title'],maxsplit=1)[0]).strip()
        if g['cpk'] and role in {'cpu','motherboard','psu','cooling'}:
            query=f"{data.get('brand','')} {str(data.get('model') or '').replace('-',' ')}".strip()
        from app.gem_radar.search_identity import preferred_search_query
        query = preferred_search_query(row['title'], data, role)
        items.append({'id':f'catalogue-component-{digest}','label':query,'query':query,
            'tags':tags,'marketplaces':[v for v in VENDORS if v!='bargain_hardware'],
            'ebayCategory':categories[role],'priority':0 if g['attention'] else 1 if g['used'] else 2,
            'intervalMinutes':180 if g['used'] else 1440})
    return sorted(items,key=lambda item:(item['priority'],item['label'].casefold()))
