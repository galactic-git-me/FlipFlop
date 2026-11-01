"""Identifier-first resolution. One immutable product CPK, multiple evidenced aliases.

No provider calls. Callers own the transaction and observation persistence.
Legacy title resolution remains available when no strong identifier was captured.
"""
from datetime import datetime, timezone
import json
from uuid import uuid4
from sqlalchemy import text
from app.gem_radar.product_identifiers import (
    extract_asin, normalise_gtin, normalise_brand, normalise_mpn,
    title_part_numbers, title_brand, variant_facts, identity_conflicts,
)

VERSION = 1

def identifier_claims(*, title, brand=None, gtin=None, mpn=None, source_url=None):
    from app.gem_radar.search_identity import manufacturer_part
    part = manufacturer_part(title, brand, mpn)
    claims=[]
    if part and part['status'] == 'identified':
        claims.append({'kind':'mpn','namespace':part['manufacturer'],'value':part['mpn']})
    if code:=normalise_gtin(gtin): claims.append({'kind':'gtin','namespace':'gs1','value':code})
    # ASIN aliases must originate in an actual Amazon product URL, not a
    # similarly shaped arbitrary source SKU or search tag.
    from urllib.parse import urlsplit
    host=(urlsplit(source_url or '').hostname or '').lower()
    if (host=='amazon.co.uk' or host.endswith('.amazon.co.uk')) and (asin:=extract_asin(source_url)):
        claims.append({'kind':'asin','namespace':'amazon.co.uk','value':asin})
    return claims

async def registry_available(db):
    if 'component_identity_registry_available' not in db.info:
        db.info['component_identity_registry_available']=bool((await db.execute(text(
            "SELECT to_regclass('canonical_component_identifiers') IS NOT NULL"))).scalar())
    return db.info['component_identity_registry_available']

async def resolve_identifiers(db, *, title, category=None, brand=None, gtin=None, mpn=None,
                              source_url=None, observation_id=None, persist=True):
    """Return matched/new/conflict, or None for the legacy fallback.

    persist=False is a read-only shadow lookup. Unknown identifiers return
    proposed_new with no database writes and no allocated random key.
    """
    from app.gem_radar.search_identity import search_result_identity
    search_identity = search_result_identity(title, category, brand, mpn)
    if search_identity and search_identity['status'] == 'conflict':
        return {**search_identity, 'fields':['manufacturer_part_number'],'claims':[],'cpks':[]}
    captured_brand=title_brand(title)
    if brand and captured_brand and normalise_brand(brand)!=captured_brand:
        return {'status':'conflict','reason':'manufacturer_disagrees','fields':['brand'],'claims':[],'cpks':[]}
    claims=identifier_claims(title=title,brand=brand,gtin=gtin,mpn=mpn,source_url=source_url)
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
            await db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,61026))'),
                {'key':json.dumps(claim,sort_keys=True)})
    rows=(await db.execute(text('''
        SELECT p.cpk,p.identity,i.kind,i.namespace,i.value
        FROM canonical_component_identifiers i
        JOIN canonical_component_products p ON p.cpk=i.cpk
        JOIN jsonb_to_recordset(CAST(:claims AS jsonb)) c(kind text,namespace text,value text)
          ON i.kind=c.kind AND i.namespace=c.namespace AND i.value=c.value
    '''),{'claims':json.dumps(claims)})).mappings().all()
    cpks={row['cpk'] for row in rows}
    if len(cpks)>1:
        return {'status':'conflict','reason':'strong_identifiers_disagree','claims':claims,'cpks':sorted(cpks)}
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
        cpk=search_identity['cpk'] if search_identity else uuid4().hex
        from app.gem_radar.identity import resolve_identity
        parsed=resolve_identity(title)
        facts=variant_facts(title,category or parsed.category)
        data={'cpk':cpk,'category':category or parsed.category,
              'brand':brand or title_brand(title) or parsed.brand,
              'model':normalise_mpn(mpn) or (next(iter(title_part_numbers(title))) if len(title_part_numbers(title))==1 else parsed.model),
              'specs':{'capacity_gb':facts.get('capacity_gb'),'module_count':facts.get('modules'),
                       'speed_mhz':facts.get('speed'),'type':f"ddr{facts['ddr']}" if facts.get('ddr') else None},
              'variant_facts':facts,'resolver_version':VERSION,'extraction_method':'identifier_registry'}
        await db.execute(text('INSERT INTO canonical_component_products(cpk,identity) VALUES(:cpk,CAST(:identity AS jsonb))'),
            {'cpk':cpk,'identity':json.dumps(data)})
        status='new'
    rule=next((kind for kind in ['mpn','gtin','asin'] if any(r['kind']==kind for r in rows)),claims[0]['kind'])
    if persist:
        evidence={'source_url':source_url,'observation_id':observation_id,
                  'observed_at':datetime.now(timezone.utc).isoformat(),'resolver_version':VERSION}
        for claim in claims:
            await db.execute(text('''INSERT INTO canonical_component_identifiers(kind,namespace,value,cpk,evidence)
                VALUES(:kind,:namespace,:value,:cpk,CAST(:evidence AS jsonb))
                ON CONFLICT(kind,namespace,value) DO NOTHING'''),
                {**claim,'cpk':cpk,'evidence':json.dumps(evidence)})
    return {'status':status,'cpk':cpk,'data':{**data,'identity_match_rule':rule,'resolver_version':VERSION},'claims':claims}
