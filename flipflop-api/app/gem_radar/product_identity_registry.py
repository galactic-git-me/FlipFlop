"""Identifier-first resolution. One immutable product CPK, multiple evidenced aliases.

No provider calls. Callers own the transaction and observation persistence.
Legacy title resolution remains available when no strong identifier was captured.
"""
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4
from sqlalchemy import text
from app.gem_radar.product_identifiers import (
    extract_asin, normalise_gtin, normalise_brand, normalise_mpn,
    title_part_numbers, title_brand, variant_facts, identity_conflicts,
)

VERSION = 2

def identifier_claims(*, title, category=None, brand=None, gtin=None, mpn=None,
                      model_number=None, epid=None, vendor_product_id=None,
                      source_url=None, include_title_alias=True,
                      include_manufacturer_part=True):
    from app.gem_radar.search_identity import manufacturer_part
    part = manufacturer_part(title, brand, mpn) if include_manufacturer_part else None
    claims=[]
    if part and part['status'] == 'identified':
        claims.append({'kind':'mpn','namespace':part['manufacturer'],'value':part['mpn']})
    if code:=normalise_gtin(gtin): claims.append({'kind':'gtin','namespace':'gs1','value':code})
    model_brand=normalise_brand(brand or title_brand(title))
    if code:=normalise_mpn(model_number):
        if model_brand: claims.append({'kind':'model_number','namespace':model_brand,'value':code})
    if epid and str(epid).strip():
        claims.append({'kind':'epid','namespace':'ebay','value':str(epid).strip().upper()})
    # ASIN aliases must originate in an actual Amazon product URL, not a
    # similarly shaped arbitrary source SKU or search tag.
    from urllib.parse import urlsplit
    host=(urlsplit(source_url or '').hostname or '').lower().removeprefix('www.')
    if vendor_product_id and host and len(host)<=100:
        value=str(vendor_product_id).strip()
        if value and len(value)<=255:
            claims.append({'kind':'vendor_product_id','namespace':host,'value':value})
    if (host=='amazon.co.uk' or host.endswith('.amazon.co.uk')) and (asin:=extract_asin(source_url)):
        claims.append({'kind':'asin','namespace':'amazon.co.uk','value':asin})
    # A category-aware normalized title is an alias bridge between different
    # identifier types. It is deliberately available only where the existing
    # resolver can form an exact product/variant key (not fuzzy title text).
    from app.gem_radar.search_identity import last_resort_title_key
    from app.gem_radar.identity import resolve_identity
    resolved_category = category or resolve_identity(title).category
    title_key = last_resort_title_key(title, resolved_category) if include_title_alias else None
    if title_key:
        value=json.dumps(title_key[2:],separators=(',',':'),ensure_ascii=True)
        if len(value)<=255:
            claims.append({'kind':'title_product','namespace':str(title_key[1]),'value':value})
    return claims

async def registry_available(db):
    if 'component_identity_registry_available' not in db.info:
        db.info['component_identity_registry_available']=bool((await db.execute(text(
            "SELECT to_regclass('canonical_component_identifiers') IS NOT NULL"))).scalar())
    return db.info['component_identity_registry_available']

async def resolve_identifiers(db, *, title, category=None, brand=None, gtin=None, mpn=None,
                              model_number=None, epid=None, vendor_product_id=None,
                              source_url=None, observation_id=None, persist=True,
                              existing_cpk=None, existing_data=None,
                              include_title_alias=True, include_manufacturer_part=True,
                              use_search_identity=True):
    """Return matched/new/conflict, or None for the legacy fallback.

    persist=False is a read-only shadow lookup. Unknown identifiers return
    proposed_new with no database writes and no allocated random key.
    """
    from app.gem_radar.search_identity import search_result_identity
    from app.gem_radar.identity import is_full_system_listing
    if is_full_system_listing(title):
        return None
    search_identity = search_result_identity(title, category, brand, mpn) if use_search_identity else None
    if search_identity and search_identity['status'] == 'conflict':
        return {**search_identity, 'fields':['manufacturer_part_number'],'claims':[],'cpks':[]}
    captured_brand=title_brand(title)
    if brand and captured_brand and normalise_brand(brand)!=captured_brand:
        return {'status':'conflict','reason':'manufacturer_disagrees','fields':['brand'],'claims':[],'cpks':[]}
    claims=identifier_claims(title=title,category=category,brand=brand,gtin=gtin,mpn=mpn,
                             model_number=model_number,epid=epid,
                             vendor_product_id=vendor_product_id,source_url=source_url,
                             include_title_alias=include_title_alias,
                             include_manufacturer_part=include_manufacturer_part)
    # Search-page MPN linking works against the existing CPK table too; it
    # must not silently depend on an unapplied optional registry migration.
    if not claims or not await registry_available(db):
        if search_identity and search_identity['status'] == 'matched':
            peers = (await db.execute(text('SELECT cpk_data FROM gem_radar_listing_cpk WHERE cpk=:cpk'),
                                     {'cpk': search_identity['cpk']})).scalars().all()
            fields = set()
            for peer in peers:
                if peer and peer.get('identity_status') != 'conflict':
                    fields.update(identity_conflicts(title, peer, search_identity['data']['category']))
            if fields:
                return {'status':'conflict','reason':'same_mpn_variant_disagrees',
                        'fields':sorted(fields),'claims':claims,'cpks':[search_identity['cpk']]}
        return search_identity
    if persist:
        # All workers acquire identifier locks in the same order. Unique keys
        # then prevent duplicate identities during concurrent first sightings.
        for claim in sorted(claims,key=lambda c:(c['kind'],c['namespace'],c['value'])):
            locked=(await db.execute(text('SELECT pg_try_advisory_xact_lock(hashtextextended(:key,61026))'),
                {'key':json.dumps(claim,sort_keys=True)})).scalar()
            if not locked:
                return {'status':'deferred','reason':'identifier_busy','claims':claims}
    rows=(await db.execute(text('''
        SELECT p.cpk,p.identity,i.kind,i.namespace,i.value
        FROM canonical_component_identifiers i
        JOIN canonical_component_products p ON p.cpk=i.cpk
        JOIN jsonb_to_recordset(CAST(:claims AS jsonb)) c(kind text,namespace text,value text)
          ON i.kind=c.kind AND i.namespace=c.namespace AND i.value=c.value
    '''),{'claims':json.dumps(claims)})).mappings().all()
    cpks={row['cpk'] for row in rows}
    if len(cpks)>1:
        # A normalized title is a bridge alias, weaker than an exact product
        # identifier. If the exact IDs agree with each other, use them and
        # leave a conflicting title alias untouched for review.
        strong_cpks={row['cpk'] for row in rows if row['kind']!='title_product'}
        if len(strong_cpks)==1:
            rows=[row for row in rows if row['cpk'] in strong_cpks]
            cpks=strong_cpks
        else:
            return {'status':'conflict','reason':'strong_identifiers_disagree','claims':claims,'cpks':sorted(cpks)}
    if existing_cpk and cpks and cpks != {existing_cpk}:
        return {'status':'conflict','reason':'existing_identity_disagrees','claims':claims,
                'cpks':sorted(cpks | {existing_cpk})}
    if rows:
        cpk=rows[0]['cpk'];data=dict(rows[0]['identity'])
        conflicts=identity_conflicts(title,data,category)
        registered=(await db.execute(text('SELECT kind,namespace,value FROM canonical_component_identifiers WHERE cpk=:cpk'),{'cpk':cpk})).mappings().all()
        prior_mpns={(r['namespace'],r['value']) for r in registered if r['kind']=='mpn'}
        new_mpns={(r['namespace'],r['value']) for r in claims if r['kind']=='mpn'}
        if prior_mpns and new_mpns and prior_mpns.isdisjoint(new_mpns): conflicts.append('manufacturer_part_number')
        if conflicts:
            return {'status':'conflict','reason':'identity_facts_disagree','fields':sorted(set(conflicts)),'claims':claims,'cpks':[cpk]}
        status='matched'
    else:
        if not persist:return {'status':'proposed_new','claims':claims}
        # Seed the immutable key from the strongest available evidence. Later
        # aliases (including normalized title) resolve back to this same key.
        priority = {'gtin':0,'mpn':1,'model_number':2,'epid':3,'asin':4,
                    'vendor_product_id':5,'title_product':6}
        strongest = min(claims,key=lambda claim:priority.get(claim['kind'],99)) if claims else None
        if existing_cpk and existing_data:
            # Preserve an already validated listing identity while backfilling
            # registry aliases on resighting; never rotate a live CPK just
            # because the registry migration/alias was introduced later.
            cpk=existing_cpk
            data={**existing_data,'cpk':existing_cpk}
            await db.execute(text('''INSERT INTO canonical_component_products(cpk,identity)
                VALUES(:cpk,CAST(:identity AS jsonb)) ON CONFLICT(cpk) DO NOTHING'''),
                {'cpk':cpk,'identity':json.dumps(data)})
            status='matched'
        else:
            if strongest:
                seed=f"{strongest['kind']}|{strongest['namespace']}|{strongest['value']}"
                cpk=hashlib.sha256(seed.encode()).hexdigest()[:32]
            else:
                cpk=uuid4().hex
            prior_product=(await db.execute(text(
                'SELECT identity FROM canonical_component_products WHERE cpk=:cpk'),{'cpk':cpk})).scalar_one_or_none()
            if prior_product:
                data=dict(prior_product)
                conflicts=identity_conflicts(title,data,category)
                if conflicts:
                    return {'status':'conflict','reason':'seed_cpk_identity_disagrees',
                            'fields':sorted(set(conflicts)),'claims':claims,'cpks':[cpk]}
                status='matched'
            else:
                from app.gem_radar.identity import resolve_identity
                parsed=resolve_identity(title)
                facts=variant_facts(title,category or parsed.category)
                data={'cpk':cpk,'category':category or parsed.category,
                      'brand':brand or title_brand(title) or parsed.brand,
                      'model':normalise_mpn(mpn) or normalise_mpn(model_number) or (next(iter(title_part_numbers(title))) if len(title_part_numbers(title))==1 else parsed.model),
                      'specs':{'capacity_gb':facts.get('capacity_gb'),'module_count':facts.get('modules'),
                               'speed_mhz':facts.get('speed'),'type':f"ddr{facts['ddr']}" if facts.get('ddr') else None},
                      'variant_facts':facts,'resolver_version':VERSION,'extraction_method':'identifier_registry'}
                await db.execute(text('INSERT INTO canonical_component_products(cpk,identity) VALUES(:cpk,CAST(:identity AS jsonb))'),
                    {'cpk':cpk,'identity':json.dumps(data)})
                status='new'
    rule=next((kind for kind in ['gtin','mpn','model_number','epid','asin','vendor_product_id','title_product']
               if any(r['kind']==kind for r in rows)),
              min(claims,key=lambda claim:{'gtin':0,'mpn':1,'model_number':2,'epid':3,'asin':4,
                  'vendor_product_id':5,'title_product':6}.get(claim['kind'],99))['kind'])
    if persist:
        evidence={'source_url':source_url,'observation_id':observation_id,
                  'observed_at':datetime.now(timezone.utc).isoformat(),'resolver_version':VERSION}
        for claim in claims:
            await db.execute(text('''INSERT INTO canonical_component_identifiers(kind,namespace,value,cpk,evidence)
                VALUES(:kind,:namespace,:value,:cpk,CAST(:evidence AS jsonb))
                ON CONFLICT(kind,namespace,value) DO NOTHING'''),
                {**claim,'cpk':cpk,'evidence':json.dumps(evidence)})
    return {'status':status,'cpk':cpk,'data':{**data,'identity_match_rule':rule,'resolver_version':VERSION},'claims':claims}
