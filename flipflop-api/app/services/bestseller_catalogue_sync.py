"""Reconcile the single Curated range from ranked hardware and authored exceptions.

Ranks/prices are retained with their source. Membership is not stock approval;
new products stay pending until the Playbook approval workflow validates them.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal,InvalidOperation
import re
from urllib.parse import urlsplit
from sqlalchemy import select, text, func
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.models.catalogue import CatalogueVariant, PlaybookSlot, CaseCatalogue
from app.models.listing import Listing
from app.models.playbook import Playbook
from app.services.amazon_bestsellers import bestseller_item_matches_category
from app.services.catalogue_service import infer_slot_type, compute_display_price

FREE_SOFTWARE_SOURCE_NAME='Ubuntu official download'


async def _sync_ubuntu_downloads(db, parents, by_slot, pairs):
    """Link authored Ubuntu dual-boot requirements to official free downloads.

    Ubuntu is not physical supplier stock or a paid licence. Keep its exact
    authored major release in the catalogue at a zero licence cost, and verify
    that Canonical's official release index currently exposes an amd64 desktop
    installer before representing it as available.
    """
    from app.services.curated_build_policy import definitions
    versions=set()
    versions_by_segment={}
    for build in definitions().get('builds',[]):
        operating_system=str((build.get('components') or {}).get('os') or '')
        if 'ubuntu' not in operating_system.casefold() or 'windows' not in operating_system.casefold():
            continue
        match=re.search(r'ubuntu\s+(\d{2}\.\d{2})',operating_system,re.I)
        if match:
            version=match.group(1)
            versions.add(version)
            versions_by_segment.setdefault(build['segment'],set()).add(version)
    if not versions:
        return {'versions':0,'available':0,'created_listings':0,'created_variants':0}

    import httpx
    checked={}
    async with httpx.AsyncClient(timeout=15,follow_redirects=True,headers={'User-Agent':'FlipFlop Playbook Catalogue/1.0'}) as client:
        for version in sorted(versions):
            index_url=f'https://releases.ubuntu.com/{version}/'
            try:
                response=await client.get(index_url)
                response.raise_for_status()
                pattern=rf'href=[\"\']([^\"\']*ubuntu-{re.escape(version)}(?:\.\d+)*-desktop-amd64\.iso)[\"\']'
                match=re.search(pattern,response.text,re.I)
                download_url=(f'https://releases.ubuntu.com/{version}/'+match.group(1).lstrip('/')) if match else None
                checked[version]={'index_url':index_url,'download_url':download_url,
                    'available':bool(download_url),'observed_at':datetime.utcnow().isoformat()+'Z'}
            except (httpx.HTTPError,ValueError):
                checked[version]={'index_url':index_url,'download_url':None,'available':False,
                    'observed_at':datetime.utcnow().isoformat()+'Z'}

    created_listings=created_variants=0
    for version,release in checked.items():
        external_id=f'playbook-free-software:ubuntu-{version}'
        listing=(await db.execute(select(Listing).where(Listing.external_id==external_id)
            .with_for_update())).scalar_one_or_none()
        if listing is None:
            listing=Listing(external_id=external_id,source_id=0,
                source_name=FREE_SOFTWARE_SOURCE_NAME,source_confidence='official_source',
                title=f'Ubuntu {version} LTS Desktop (official free download)',
                description='Free, unmodified desktop installer from Ubuntu releases.',
                price=0.0,url=release['index_url'],image_urls=[],
                condition='new',listing_type='software_download',status='active',
                first_seen_at=datetime.utcnow(),last_seen_at=datetime.utcnow(),
                raw_specs={'playbook_free_software':{'kind':'official_free_os_download',
                    'distribution':'Ubuntu','authored_release':version,**release}})
            db.add(listing);created_listings+=1
        else:
            listing.title=f'Ubuntu {version} LTS Desktop (official free download)'
            listing.description='Free, unmodified desktop installer from Ubuntu releases.'
            listing.price=0.0
            listing.url=release['index_url']
            listing.status='active'
            listing.last_seen_at=datetime.utcnow()
            listing.raw_specs={**(listing.raw_specs or {}),'playbook_free_software':{
                'kind':'official_free_os_download','distribution':'Ubuntu','authored_release':version,**release}}
        # The row needs its database identity before CatalogueVariant rows are
        # built for each segment slot.
        await db.flush()
        for parent in parents:
            slot=by_slot.get((parent.id,'os_secondary'))
            if slot is None or version not in versions_by_segment.get(parent.name,set()):
                if slot is not None:
                    stale_variant=pairs.get((listing.id,slot.id))
                    if stale_variant and stale_variant.status!='rejected':
                        stale_variant.status='hidden'
                        stale_variant.custom_for_builds=False
                continue
            variant=pairs.get((listing.id,slot.id))
            if variant is None:
                variant=CatalogueVariant(listing_id=listing.id,slot_id=slot.id,status='active',
                    display_price=0.0,tier='mid',curated_for_builds=True,custom_for_builds=False,
                    custom_sale_status='out_of_stock',reviewed_at=release['observed_at'],
                    reviewed_by='official_source_sync')
                db.add(variant);pairs[listing.id,slot.id]=variant;created_variants+=1
            elif variant.status!='rejected':
                variant.status='active'
                variant.display_price=0.0
                variant.custom_for_builds=False
                variant.reviewed_at=release['observed_at']
                variant.reviewed_by='official_source_sync'
    await db.flush()
    return {'versions':len(checked),'available':sum(value['available'] for value in checked.values()),
        'created_listings':created_listings,'created_variants':created_variants}

HARDWARE_ROLES=('cpu','motherboard','ram','gpu','storage','psu','cooling','case')
CATALOGUE_ROLES=(*HARDWARE_ROLES,'storage_secondary','os','os_secondary','wireless_adapter')


def _importable_bestseller_observation(row):
    """Use Amazon Bestseller input for hardware; software costs have a separate source."""
    if not row.image_url or amazon_asin(row.url)!=str(row.asin or '').upper():
        return False
    if row.category=='os':
        # OS licence costs are sourced from the selected specialist key catalogue,
        # never from conventional Amazon retail listings. Amazon ranks may still
        # exist as demand observations, but must not become Playbook inventory.
        return False
    return bool((row.price is None or row.price>0) and bestseller_item_matches_category(row.title,row.category))


def _observation_catalogue_price(row):
    """Return a price only for hardware; Amazon OS records are demand evidence."""
    if row.category=='os':
        return None
    fallback=float(row.price) if row.price and row.price>0 else None
    return fallback


def _case_catalogue_price(listing):
    """A hidden case candidate needs a real captured item price before creation."""
    price=listing.price
    return float(price) if price is not None and float(price)>0 else None


def amazon_asin(url):
    try:
        parsed=urlsplit(url or '')
        host=(parsed.hostname or '').casefold()
        if parsed.scheme!='https' or parsed.username or parsed.password or not (host=='amazon.co.uk' or host.endswith('.amazon.co.uk')):
            return None
        matched=re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)',parsed.path,re.I)
        return matched.group(1).upper() if matched else None
    except ValueError:
        return None


def _historical_target_identities(history,current,targets):
    from app.services.benchmark_normaliser import normalise_cpu,normalise_gpu
    from types import SimpleNamespace
    recovered=[]
    seen=set(current)
    for row in history:
        if row.category not in {'cpu','gpu'}:continue
        normalise=normalise_cpu if row.category=='cpu' else normalise_gpu
        identity=normalise(row.title)
        if ((row.category,row.asin) in seen or not identity or identity not in targets[row.category]
                or not _importable_bestseller_observation(row)):
            continue
        seen.add((row.category,row.asin))
        recovered.append(SimpleNamespace(**{key:getattr(row,key) for key in
            ('id','category','asin','title','url','image_url','cpk','captured_at','list_name')},
            price=None,rank=None,historical_identity_only=True))
    return recovered


def _historical_offer_is_current(listing):
    capture=(listing.raw_specs or {}).get('playbook_product_capture') or {}
    if capture.get('status')!='captured' or capture.get('url')!=listing.url:return False
    try:
        observed=datetime.fromisoformat(capture['observed_at'].replace('Z','+00:00'))
        price=Decimal(str(capture['item_gbp']))
        age=(datetime.now(timezone.utc)-observed).total_seconds()
        return 0<=age<=86400 and price.is_finite() and price>0 and price==Decimal(str(listing.price))
    except (KeyError,ValueError,TypeError,InvalidOperation):
        return False


def _historical_required_identities(history, current, builds):
    """Recover exact authored hardware requirements, never historical offers."""
    from types import SimpleNamespace
    from app.services.curated_catalogue_range import _matches_requirement, authored_requirements
    seen = set(current)
    recovered = []
    for row in history:
        role = infer_slot_type(row.title, row.category)
        if not role or (row.category, row.asin) in seen or not _importable_bestseller_observation(row):
            continue
        requirements = [specification for build in builds for required_role, specification in authored_requirements(build)
            if required_role == role or (role == 'storage' and required_role == 'storage_secondary')]
        if not any(_matches_requirement(role, row.title, requirement) for requirement in requirements):
            continue
        seen.add((row.category, row.asin))
        recovered.append(SimpleNamespace(**{key:getattr(row,key) for key in
            ('id','category','asin','title','url','image_url','cpk','captured_at','list_name')},
            price=None,rank=None,historical_identity_only=True))
    return recovered


async def sync_bestseller_catalogues(db, *, check_free_software=True):
    # The scheduled source refresh, manual rebuild, and Amazon scraper can all
    # reconcile the same newly captured ASINs. Serialize the lookup-and-create
    # section so two sessions cannot both miss the same listing and violate
    # the unique external_id constraint.
    await db.execute(text('SELECT pg_advisory_xact_lock(61311, 3)'))
    observations=(await db.execute(select(AmazonBestsellerObservation).where(
        AmazonBestsellerObservation.captured_at >= datetime.utcnow()-timedelta(hours=24),
        AmazonBestsellerObservation.captured_at <= datetime.utcnow(),
    ).order_by(AmazonBestsellerObservation.category,AmazonBestsellerObservation.asin,
               AmazonBestsellerObservation.captured_at.desc(),AmazonBestsellerObservation.id.desc())
      .distinct(AmazonBestsellerObservation.category,AmazonBestsellerObservation.asin))).scalars().all()
    # Captures are inserted together per category. Discard identities left over
    # from an earlier run in the 24h window when a later list replaced it.
    latest = {}
    for row in observations:
        latest[row.category] = max(latest.get(row.category, row.captured_at), row.captured_at)
    observations = [row for row in observations if
        (latest[row.category] - row.captured_at).total_seconds() < 60]
    refreshed_categories = set(latest)
    from app.services.playbook_service import _plausible_role_candidate
    observations=[row for row in observations if _importable_bestseller_observation(row)
        and _plausible_role_candidate(infer_slot_type(row.title, row.category), row.title)]
    # Recover authored requirements from captured history as identity only;
    # historical rank and price are never current demand/cost facts.
    from app.services.curated_build_policy import definitions
    history=(await db.execute(select(AmazonBestsellerObservation).where(
        AmazonBestsellerObservation.category.in_(('cpu','gpu','motherboard','ram','storage','psu','cooler','case')),
        AmazonBestsellerObservation.captured_at>=datetime.utcnow()-timedelta(days=30),
        AmazonBestsellerObservation.captured_at<datetime.utcnow()-timedelta(hours=24),
    ).order_by(AmazonBestsellerObservation.category,AmazonBestsellerObservation.asin,
        AmazonBestsellerObservation.captured_at.desc(),AmazonBestsellerObservation.id.desc())
      .distinct(AmazonBestsellerObservation.category,AmazonBestsellerObservation.asin))).scalars().all()
    current={(row.category,row.asin) for row in observations}
    historical=_historical_required_identities(history,current,definitions()['builds'])
    observations.extend(historical)
    from app.services.curated_catalogue_range import select_curated_range
    observations, range_reasons = select_curated_range(observations, definitions()['builds'])
    curated_keys = set(range_reasons)
    reviews={(row.category,row.cpk):row.status for row in
        (await db.execute(text('SELECT category,cpk,status FROM curated_bestseller_reviews'))).all()}
    parents=(await db.execute(select(Playbook).where(Playbook.status=='active'))).scalars().all()
    slots=(await db.execute(select(PlaybookSlot).where(PlaybookSlot.playbook_id.in_([p.id for p in parents])))).scalars().all()
    by_slot={(row.playbook_id,row.slot_type):row for row in slots}
    for parent in parents:
        for role in CATALOGUE_ROLES:
            if (parent.id,role) not in by_slot:
                slot=PlaybookSlot(playbook_id=parent.id,slot_type=role)
                db.add(slot);by_slot[parent.id,role]=slot
    await db.flush()
    pairs={(row.listing_id,row.slot_id):row for row in (await db.execute(select(CatalogueVariant).where(
        CatalogueVariant.slot_id.in_([s.id for s in by_slot.values()]),
    ))).scalars().all()}
    # Finish the remote official-download check before locking hardware rows.
    free_software_sync=(await _sync_ubuntu_downloads(db,parents,by_slot,pairs)
        if check_free_software else {'versions':0,'available':0,'created_listings':0,
            'created_variants':0,'skipped':'already checked earlier in this refresh'})
    urls={row.url.split('?')[0] for row in observations}
    external_ids={value for row in observations for value in (row.asin,f'amazon-bestseller:{row.asin}')}
    listings=(await db.execute(select(Listing).where(
        (func.split_part(Listing.url,'?',1).in_(urls)) | (Listing.external_id.in_(external_ids))
        | func.substring(Listing.url,r'/(?:dp|gp/product)/([A-Za-z0-9]{10})').in_([row.asin for row in observations]),
    ).order_by(Listing.id).with_for_update().execution_options(populate_existing=True))).scalars().all() if observations else []
    by_url={row.url.split('?')[0]:row for row in listings}
    by_external={row.external_id:row for row in listings}
    by_asin={}
    for listing in listings:
        asin=amazon_asin(listing.url)
        if asin:
            by_asin.setdefault(asin,listing)
    prepared=[];case_links=[];created_listings=created_variants=0
    cases={row.name.casefold():row for row in (await db.execute(select(CaseCatalogue))).scalars().all()}
    for row in observations:
        role=infer_slot_type(row.title,row.category)
        if not role:
            continue
        key=row.cpk or f'asin:{row.asin}'
        review=reviews.get((row.category,key),'pending')
        if review=='rejected':
            continue
        url=row.url.split('?')[0]
        listing=by_asin.get(row.asin.upper()) or by_url.get(url) or by_external.get(row.asin) or by_external.get(f'amazon-bestseller:{row.asin}')
        catalogue_price=_observation_catalogue_price(row)
        source={'observation_id':row.id,'asin':row.asin,'cpk':key,'category':row.category,
            'rank':row.rank,'rank_current':not getattr(row,'historical_identity_only',False),
            'list_name':row.list_name,'price_gbp':str(row.price) if row.price is not None else None,
            'captured_at':row.captured_at.isoformat(),'review_status':review,'url':url}
        product_capture=None
        if listing is None:
            listing=Listing(external_id=f'amazon-bestseller:{row.asin}',source_id=0,source_name='amazon',
                source_confidence='bestseller_capture',title=row.title,url=url,price=catalogue_price,
                image_urls=[row.image_url],condition='new',listing_type='buy_it_now',status='active',
                first_seen_at=row.captured_at,last_seen_at=row.captured_at,
                raw_specs={'gem_radar_category':row.category,'bestseller':source,
                    **({'playbook_product_capture':product_capture} if product_capture else {})})
            db.add(listing);by_url[url]=listing;by_external[listing.external_id]=listing;by_asin[row.asin.upper()]=listing;created_listings+=1
        else:
            if (listing.raw_specs or {}).get('catalogue_deleted'):
                continue
            listing.raw_specs={**(listing.raw_specs or {}),'bestseller':source}
            # Do not overwrite newer product-detail evidence with an older list.
            if listing.last_seen_at is None or row.captured_at>=listing.last_seen_at.replace(tzinfo=None):
                if row.price and row.price>0:
                    listing.price=row.price
                elif listing.price is None:
                    listing.price=catalogue_price
                listing.last_seen_at=row.captured_at
        listing.raw_specs={**(listing.raw_specs or {}), 'curated_range': range_reasons[(row.category,row.asin)]}
        prepared.append((row,role,listing))
        if role=='case' and not listing.case_catalogue_id:
            case_price=_case_catalogue_price(listing)
            # Bestseller rank pages often omit price. Keep the observation and
            # listing available for exact product-page capture, then materialise
            # a case only once its own listing has a current price.
            if case_price is None:
                continue
            case=cases.get(row.title.casefold())
            if case is None:
                case=CaseCatalogue(name=row.title,brand=row.title.split()[0],form_factor='unknown',
                    rrp_gbp=case_price,status='hidden',images=[row.image_url],
                    notes=f'Automatically linked to Amazon bestseller ASIN {row.asin}; product facts await source collection')
                db.add(case);cases[row.title.casefold()]=case
            case_links.append((listing,case))
    await db.flush()
    for listing,case in case_links:
        listing.case_catalogue_id=case.id
    for row,role,listing in prepared:
        # Bestseller-linked source products are materialised only for priced hardware.
        # Identity/photo review is possible before a supplier price is captured.
        # Zero display price is never availability or publication approval.
        # Historical captures establish identity for photo review only. Current
        # source, cost and compatibility gates still own every sales decision.
        linked_roles=[role]
        if role=='storage': linked_roles.append('storage_secondary')
        if role=='os': linked_roles.append('os_secondary')
        for parent in parents:
            for linked_role in linked_roles:
                slot=by_slot[parent.id,linked_role]
                variant=pairs.get((listing.id,slot.id))
                if variant is None:
                    variant=CatalogueVariant(listing_id=listing.id,slot_id=slot.id,status='pending_review',
                        display_price=compute_display_price(listing.price or 0),tier='budget',
                        last_seen_at=listing.last_seen_at.isoformat(),curated_for_builds=(row.category,row.asin) in curated_keys,
                        custom_for_builds=False,custom_sale_status='out_of_stock')
                    db.add(variant);pairs[listing.id,slot.id]=variant;created_variants+=1
                elif variant.status!='rejected':
                    variant.curated_for_builds=(row.category,row.asin) in curated_keys
                    variant.custom_for_builds=False
    # Reconcile rather than accumulate membership. Preserve all rows, media and
    # historic orders; products can return without paying for another model.
    included = {listing.id: role for _, role, listing in prepared}
    all_rows = (await db.execute(select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id))).all()
    removed = 0
    for variant, listing, slot in all_rows:
        variant.custom_for_builds = False  # Deprecated membership; both journeys use Curated.
        if slot.slot_type=='wireless_adapter':
            # This is an authored connectivity extra sourced from its exact
            # retailer product page, not a bestseller category.
            continue
        if slot.slot_type.startswith('os'):
            if variant.status != 'rejected' and not (listing.raw_specs or {}).get('catalogue_deleted'):
                variant.curated_for_builds = True
            continue
        category = (listing.raw_specs or {}).get('bestseller', {}).get('category')
        # A failed/stale source category preserves its last known range, never
        # substitutes a fabricated new ranking. Fresh categories reconcile fully.
        from app.services.curated_catalogue_range import pinned_catalogue_role
        pinned_role = pinned_catalogue_role(listing.raw_specs)
        if category not in refreshed_categories and category and not pinned_role:
            continue
        role = pinned_role or included.get(listing.id)
        allowed_roles = {'storage', 'storage_secondary'} if role == 'storage' else {role}
        allowed = role is not None and slot.slot_type in allowed_roles and variant.status != 'rejected' and not (listing.raw_specs or {}).get('catalogue_deleted')
        if variant.curated_for_builds and not allowed:
            removed += 1
        variant.curated_for_builds = allowed
    await db.flush()
    from app.services.component_media_identity import inherit_family_media_reviews
    await inherit_family_media_reviews(db)
    return {'source_products':len(prepared), 'removed_memberships':removed,
            'range_policy':'all-cases-top10-other-categories-with-playbook-exceptions', 'created_listings':created_listings,
            'historical_source_identities':len(historical),
            'created_variants':created_variants,'new_products_published':0,
            'free_software_sync':free_software_sync}
