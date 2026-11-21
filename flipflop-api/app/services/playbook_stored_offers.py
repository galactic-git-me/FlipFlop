"""Link catalogue identities to captured UK supplier offers without provider calls."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import re

from sqlalchemy import bindparam, select, text
from app.gem_radar.identity import is_full_system_listing


UK_HOSTS = {'amazon.co.uk', 'www.amazon.co.uk', 'scan.co.uk', 'www.scan.co.uk',
            'overclockers.co.uk', 'www.overclockers.co.uk', 'ebuyer.com', 'www.ebuyer.com',
            'computerorbit.com','www.computerorbit.com','awd-it.co.uk','www.awd-it.co.uk',
            'cclonline.com','www.cclonline.com','corsair.com','www.corsair.com',
            'hardvance.co.uk','www.hardvance.co.uk','senetic.co.uk','www.senetic.co.uk'}


def product_keys(role, title, product_evidence=None):
    """Exact identities only: a GPU family alone is not a board identity."""
    if is_full_system_listing(title):
        return []
    normalized=re.sub(r'[^a-z0-9]','',title.casefold())
    keys=[('title',normalized)]
    if model_key := supplier_model_key(role, title, product_evidence):
        keys.append(model_key)
    from app.gem_radar.search_identity import last_resort_title_key
    if title_key := last_resort_title_key(title, role):
        keys.append(title_key)
    from app.gem_radar.search_identity import manufacturer_part
    part = manufacturer_part(title)
    if part and part['status'] == 'identified':
        keys.append(('manufacturer_part', part['manufacturer'], part['mpn']))
    if role == 'cpu':
        # Retailer titles often add socket, cache, generation or "retail"
        # wording. Index by the normalized exact CPU model too, so a current
        # new offer can replace a used capture for the same processor without
        # substituting a different CPU into the authored build.
        from app.services.benchmark_normaliser import normalise_cpu
        model = normalise_cpu(title)
        if model:
            keys.append(('cpu_model', model))
    if role=='gpu':
        if model_key := _gpu_board_model_key(role, title):
            keys.append(model_key)
        # MSI's differently worded vendor titles consistently retain these
        # exact board identifiers; do not merge Ventus with Trio/Suprim or 2X.
        board=re.search(r'\bventus\s*(2x|3x)\b',title,re.I)
        memory=re.search(r'\b(\d{1,2})\s*g(?:b)?\b',title,re.I)
        chip=re.search(r'\brtx\s*(\d{4})(?:\s*(ti|super))?\b',title,re.I)
        if re.search(r'\bmsi\b',title,re.I) and board and memory and chip:
            keys.append(('gpu_board','msi',chip[1],(chip[2] or '').lower(),memory[1],
                         'ventus',board[1].lower(),bool(re.search(r'\boc\b',title,re.I))))
        # PNY's RTX 6000 Ada name is stable across the OEM SKU and concise
        # catalogue title; the Ada suffix distinguishes it from RTX 6000
        # families with different architectures.
        pny_rtx_6000_ada=bool(re.search(r'\bpny\b',title,re.I)
            and re.search(r'\brtx\s*6000\s*ada\b',title,re.I))
        if pny_rtx_6000_ada:
            keys.append(('gpu_model','pny','rtx6000','ada'))
    if role in {'storage','storage_secondary','ssd'}:
        # Retailer titles often omit a precise 2280 form-factor even when the
        # catalogue identity names it. Model family + capacity + heatsink
        # state still distinguish the sellable SSD variants without letting a
        # 1TB offer replace a 2TB part.
        from app.gem_radar.product_identifiers import title_brand,variant_facts
        brand=title_brand(title)
        facts=variant_facts(title,'ssd')
        family=re.search(r'\b(?:990\s*(?:pro|evo(?:\s*plus)?)|980\s*pro|nv[123]|sn850x|p310|p510)\b',title,re.I)
        if brand and family and isinstance(facts.get('capacity_gb'),int):
            heatsink=('without' if re.search(r'\bwithout\s+(?:a\s+)?heat\s*sink\b',title,re.I)
                else 'with' if re.search(r'\bheat\s*sink\b',title,re.I) else 'unspecified')
            keys.append(('ssd_model_capacity',brand,re.sub(r'\s+','',family[0].casefold()),
                facts['capacity_gb'],heatsink))
    return keys


def supplier_model_key(role, title, product_evidence=None):
    """Extract precise board/PSU names shared by catalogue and retailer titles.

    Retailer captures often add socket/chipset/interface text or use a CPK
    model with a different punctuation suffix. These keys keep the explicit
    manufacturer model (including Wi-Fi and PSU revision markers) stable.
    """
    if role not in {'motherboard', 'psu'} or not title:
        return None
    from app.gem_radar.product_identifiers import title_brand
    brand = title_brand(title)
    if role=='psu' and not brand and re.search(r'\bseasonic\b',title,re.I):
        brand='seasonic'
    if not brand:
        return None
    value = re.sub(r'^\s*quick\s*view\s*', '', str(title), flags=re.I)
    if role == 'motherboard':
        brand_match = re.search(r'\b' + re.escape(brand).replace(r'\ ', r'[\s_-]+') + r'\b', value, re.I)
        if not brand_match:
            return None
        model = value[brand_match.end():]
        model = re.split(
            r'[,(|]|\b(?:motherboard|mainboard|socket|am[345]|lga\s*\d{4,5}|'
            r'ddr\s*[345]|pcie|micro[-\s]?atx|m[-\s]?atx|atx|amd|intel|supports)\b',
            model, maxsplit=1, flags=re.I,
        )[0]
        model = re.sub(r'[^a-z0-9]+', '', model.casefold())
        # Some catalogue imports prepend chipset noise to the actual board
        # model (e.g. "MSI B550 00 - B550M PRO-VDH WIFI - AMD Motherboard").
        # A current product-page capture can carry an explicit structured
        # "Model:" field and manufacturer part number in its description.
        # Prefer that exact model evidence over the noisy title tokens.
        evidence = product_evidence if isinstance(product_evidence, dict) else {}
        capture = evidence.get('playbook_product_capture') or evidence.get('product_capture') or evidence
        description = str(capture.get('product_description') or '') if isinstance(capture, dict) else ''
        explicit = re.search(r'(?:^|[•*\r\n])\s*model\s*:\s*([^•*\r\n]+)', description, re.I)
        if explicit:
            captured_model = re.split(
                r'\b(?:motherboard|mainboard|socket|am[345]|lga\s*\d{4,5}|'
                r'ddr\s*[345]|pcie|micro[-\s]?atx|m[-\s]?atx|atx|amd|intel|supports)\b',
                explicit.group(1), maxsplit=1, flags=re.I,
            )[0]
            captured_model = re.sub(r'[^a-z0-9]+', '', captured_model.casefold())
            mpn = str(capture.get('mpn') or capture.get('manufacturer_part_number') or '')
            if not mpn:
                mpn_match = re.search(r'\bmodel\s+number\s*:\s*([a-z0-9-]{5,})', description, re.I)
                mpn = mpn_match.group(1) if mpn_match else ''
            ean_match = re.search(r'\b(?:ean|gtin)\s*:\s*(\d{8,14})\b', description, re.I)
            # Require explicit product model plus manufacturer/GTIN evidence;
            # free-form marketing copy alone must not override title identity.
            if captured_model and (mpn or ean_match):
                model = captured_model
        # A numeric chipset/model token is required; brand plus generic board
        # family words such as "gaming motherboard" are not an identity.
        if not re.search(r'\d{3,4}', model):
            return None
        return ('supplier_model', role, brand, model)

    # Corsair's current HXi PSU titles vary between "HX1500i" and
    # "HXi Series 1500W". Use the explicit HX model and retain the 2025
    # revision marker where the source exposes it.
    corsair_model = re.search(r'\bhx\s*(\d{3,4})\s*i\b', value, re.I) if brand == 'corsair' else None
    if corsair_model:
        revision = '2025' if re.search(r'\b2025\b', value, re.I) else ''
        return ('supplier_model', role, brand, f"hx{corsair_model[1]}i", revision)
    corsair_sf = re.search(r'\bsf\s*(\d{3,4})\b', value, re.I) if brand == 'corsair' else None
    if corsair_sf and (re.search(r'\b2024\b',value,re.I)
            or re.search(r'\batx\s*3\.1\b',value,re.I)
            and re.search(r'\bpcie\s*5\.1\b',value,re.I)):
        return ('supplier_model',role,brand,f"sf{corsair_sf[1]}",'2024')
    if brand == 'bequiet':
        system_power=re.search(r'\bsystem\s+power\s*(\d+)\b.*?\b(\d{3,4})\s*w\b',value,re.I)
        if system_power:
            return ('supplier_model',role,brand,
                f"systempower{system_power[1]}",f"{system_power[2]}w")
    if brand == 'seasonic':
        core_bc=re.search(r'\bcore\s*bc[-\s]*(\d{3,4})\b',value,re.I)
        if core_bc:
            return ('supplier_model',role,brand,f"corebc{core_bc[1]}",f"{core_bc[1]}w")
    return None


def cpk_identity_key(data):
    """Index a validated CPK identity independently of its hash encoding."""
    if not isinstance(data, dict):
        return None
    category = {'storage': 'ssd', 'cooling': 'cooler', 'graphics_card': 'gpu'}.get(
        str(data.get('category') or '').casefold(), str(data.get('category') or '').casefold()
    )
    normalise = lambda value: re.sub(r'[^a-z0-9]', '', str(value or '').casefold())
    brand, model = normalise(data.get('brand')), normalise(data.get('model'))
    if not category or not brand or not model or model in {'unknown', 'undefined', 'component', 'product', 'chassis'}:
        return None
    return ('cpk_identity', category, brand, model)


def _gpu_board_model_key(role, title):
    """Key an exact add-in-board SKU across retailer title variations.

    GPU chipset alone is too broad: a catalogue part for ASUS Dual must not
    join an ASUS TUF or another board maker. Require the board family and VRAM
    in addition to the exact chip. Explicit colour and OC variants stay apart.
    """
    if role != 'gpu' or not title:
        return None
    from app.gem_radar.product_identifiers import title_brand
    brand=title_brand(title)
    chip=re.search(r'\b(?:rtx|gtx|rx|arc)\s*(\d{3,4})(?:\s*(ti|super|xtx|xt|gre))?\b',title,re.I)
    vram=re.search(r'\b(\d{1,2})\s*gb\b',title,re.I)
    board=_gpu_board_family(title)
    if not brand or not chip or not vram or not board:
        return None
    suffix=(chip[2] or '').casefold()
    colour=next((name for name in ('white','black','silver','grey','gray')
                 if re.search(rf'\b{name}\b',title,re.I)),None)
    if colour == 'gray':
        colour='grey'
    overclocked=bool(re.search(r'\b(?:oc|overclocked)\b',title,re.I))
    return ('gpu_board_model',brand,f"{chip[1]}{suffix}",int(vram[1]),board,colour,overclocked)


def offers_for_part(part, index):
    choices=index.get(part.get('cpk'),[])
    identity_key=cpk_identity_key(part.get('cpk_data'))
    if identity_key:
        choices=[*choices,*index.get(identity_key,[])]
    for key in product_keys(part['role'],part['title']):
        matches=index.get(key,[])
        if key[0]=='title_product':
            strong={offer.get('cpk') for offer in matches if (offer.get('cpk_data') or {}).get('identity_claims')}
            if len(strong)>1:
                continue
        choices=[*choices,*matches]
    return [{**row,'match_basis':'exact_cpk_and_product' if part.get('cpk') and row.get('cpk')==part['cpk']
             else 'exact_product_identity'} for row in {row['observation_id']:row for row in choices}.values()]


def recorded_offer(row):
    if is_full_system_listing(row.get('title') or ''):
        return None
    capture = row.get('commercial_source_evidence') or {}
    from app.services.commercial_source import search_listing_availability
    stock, stock_evidence, assumed = search_listing_availability(
        capture.get('stock_status'), capture.get('stock_evidence'))
    url = capture.get('url') or row.get('recorded_product_url') or ''
    if urlsplit(url).hostname not in UK_HOSTS or stock == 'unavailable':
        return None
    try:
        price = Decimal(str(capture.get('item_gbp', row['item_price'])))
        delivery = Decimal(str(capture['delivery_gbp'])) if capture.get('postage_verified') is True else None
    except (InvalidOperation, ValueError, TypeError, KeyError):
        return None
    if not price.is_finite() or price <= 0 or delivery is not None and (not delivery.is_finite() or delivery < 0):
        return None
    observed_at=row['observed_at']
    if observed_at.tzinfo is None:
        observed_at=observed_at.replace(tzinfo=timezone.utc)
    title=str(row['title'] or '')
    for marker in ('\ufffd','\u00ae','\u2122'):
        title=title.replace(marker,' ')
    title=re.sub(r'\s+',' ',title).strip()
    return {'observation_id': row['id'], 'listing_id':row['listing_id'],
            'cpk': row['cpk'], 'title': title,
            'cpk_data': row.get('cpk_data'),
            'source': row['source'], 'url': url, 'item_gbp': str(price), 'mpn': row.get('mpn'),
            'delivery_gbp': str(delivery) if delivery is not None else None,
            'observed_at': observed_at.isoformat(), 'match_basis': 'exact_cpk',
            'stock_status':stock, 'availability_assumed':assumed,
            'stock_evidence':stock_evidence,
            'condition':'new','listing_type':'buy_it_now',
            'commercial_capture_verified':bool(capture.get('url')==url and capture.get('item_gbp') is not None),
            'delivery_working_days':capture.get('delivery_working_days'),
            'delivery_estimate_source':capture.get('delivery_estimate_source'),
            'prime_eligible':capture.get('prime_eligible'),
            'url_basis':'current_capture' if capture.get('url') else 'same_listing_recorded_url',
            'postage_verified': delivery is not None}


def _apply_exact_product_page_capture(row, listing, preview):
    """Let a newer exact retailer-page capture supersede its older search observation."""
    from app.services.commercial_readiness import same_listing_product
    capture=(listing.raw_specs or {}).get('playbook_product_capture') or {}
    if (preview.get('identity_source')!='exact_retailer_product_page'
            or preview.get('commercial_capture_verified') is not True
            or preview.get('fresh') is not True
            or preview.get('condition')!='new'
            or preview.get('listing_type')!='buy_it_now'
            or not same_listing_product(preview.get('url'),listing.url)
            or not same_listing_product(preview.get('url'),row.get('recorded_product_url')
                or (row.get('commercial_source_evidence') or {}).get('url'))):
        return row
    try:
        page_time=datetime.fromisoformat(str(preview['observed_at']).replace('Z','+00:00'))
        row_time=row['observed_at']
        if row_time.tzinfo is None:
            row_time=row_time.replace(tzinfo=timezone.utc)
        if page_time.tzinfo is None or page_time<row_time.astimezone(page_time.tzinfo):
            return row
        price=Decimal(str(preview['item_gbp']))
        if not price.is_finite() or price<=0:
            return row
    except (KeyError,TypeError,ValueError,ArithmeticError):
        return row
    product_identity={key:capture.get(key) for key in (
        'title','sku','mpn','product_brand','product_description','product_properties')
        if capture.get(key) is not None}
    updated={**row,'observed_at':page_time,'item_price':price,
        'title':capture.get('title') or row.get('title'),
        'mpn':capture.get('mpn') or row.get('mpn'),
        'listing_db_id':listing.id,'playbook_product_capture':product_identity,
        'commercial_source_evidence':{
            'url':preview.get('url'),'item_gbp':str(price),
            'delivery_gbp':preview.get('delivery_gbp'),
            'postage_verified':preview.get('postage_verified') is True,
            'observed_at':page_time.isoformat(),
            'stock_status':preview.get('stock_status'),
            'stock_evidence':preview.get('stock_evidence'),
            'delivery_working_days':preview.get('delivery_working_days'),
            'delivery_estimate_source':preview.get('delivery_estimate_source'),
            'prime_eligible':preview.get('prime_eligible'),
        }}
    return updated


async def stored_offers(db, cpks):
    """Latest capture per listing, never an old low price from that listing's history."""
    if 'simple_playbook_supplier_offers' not in db.info:
        rows = (await db.execute(text('''
          WITH ranked_ids AS (
            SELECT o.id, ROW_NUMBER() OVER (
              PARTITION BY o.listing_id ORDER BY o.observed_at DESC,o.id DESC
            ) AS listing_rank
            FROM gem_radar_listing_observations o
            WHERE o.observed_at >= :since
              AND o.source IN ('amazon','scan','overclockers','ebuyer','computer_orbit','awd_it','ccl','corsair','hardvance','senetic')
          ) SELECT o.id,o.listing_id,c.cpk,c.cpk_data,o.title,o.source,o.item_price,o.mpn,
                   o.commercial_source_evidence,o.observed_at,o.category,o.search_tags
            FROM ranked_ids ids JOIN gem_radar_listing_observations o ON o.id=ids.id
            LEFT JOIN gem_radar_listing_cpk c ON c.listing_id=o.listing_id
            WHERE ids.listing_rank=1 AND o.condition_normalised='new' AND o.listing_type='buy_it_now'
              AND COALESCE(c.cpk_data->>'identity_status','') <> 'conflict'
          '''), {'since': datetime.utcnow()-timedelta(days=30)})).mappings().all()
        # Recover URLs only for relevant current listings, not by sorting the
        # entire history's large JSON capture payloads on every book rebuild.
        missing=[row['listing_id'] for row in rows if not (row['commercial_source_evidence'] or {}).get('url')
                 and (row['cpk'] in cpks or row['category']=='gpu')]
        urls={}
        if missing:
            prior_query=text('''
              WITH ranked_urls AS (
              SELECT source,listing_id,
                     commercial_source_evidence->>'url' AS url
                     ,ROW_NUMBER() OVER (PARTITION BY source,listing_id ORDER BY observed_at DESC,id DESC) AS row_rank
              FROM gem_radar_listing_observations
              WHERE listing_id IN :ids AND observed_at>=:since
                AND commercial_source_evidence->>'url' IS NOT NULL
              ) SELECT source,listing_id,url FROM ranked_urls WHERE row_rank=1
            ''').bindparams(bindparam('ids', expanding=True))
            prior=(await db.execute(prior_query,{'ids':missing,'since':datetime.utcnow()-timedelta(days=30)})).all()
            urls={(row.source,row.listing_id):row.url for row in prior}
        # Some extension/import observations keep the exact retailer product
        # URL on the canonical listing instead of duplicating it into every
        # observation's evidence JSON. Recover that URL for the link only;
        # recorded_offer still marks the capture unverified and stock unknown
        # unless a product-page capture provides those facts.
        canonical_query=text('''
          SELECT external_id,url
          FROM listings
          WHERE external_id IN :ids AND status='active' AND url IS NOT NULL
        ''').bindparams(bindparam('ids', expanding=True))
        canonical=(await db.execute(canonical_query,{'ids':missing})).all()
        canonical_urls={listing_id:url for listing_id,url in canonical
            if urlsplit(url).hostname in UK_HOSTS}
        for row in rows:
            listing_id=row['listing_id']
            key=(row['source'],listing_id)
            if listing_id in canonical_urls and not urls.get(key):
                urls[key]=canonical_urls[listing_id]
        # Product-page refreshes are persisted on the exact retailer Listing.
        # They must supersede an older Gem Radar card/observation so captured
        # stock, price, postage and delivery time are available to pace quotes.
        row_urls={}
        for row in rows:
            key=(row['source'],row['listing_id'])
            capture=row.get('commercial_source_evidence') or {}
            url=capture.get('url') or urls.get(key)
            if url and urlsplit(url).hostname in UK_HOSTS:
                row_urls[key]=url
        from app.models.listing import Listing
        page_listings=(await db.execute(select(Listing).where(
            Listing.url.in_(set(row_urls.values())),Listing.status=='active'
        ))).scalars().all() if row_urls else []
        from app.services.commercial_readiness import source_preview_many
        page_previews=await source_preview_many(db,page_listings) if page_listings else {}
        listings_by_url={listing.url:listing for listing in page_listings}
        previews_by_url={listing.url:page_previews.get(listing.id) for listing in page_listings}
        index = {}
        for row in rows:
            key=(row['source'],row['listing_id'])
            row={**row,'recorded_product_url':urls.get(key)}
            page_url=(row.get('commercial_source_evidence') or {}).get('url') or row_urls.get(key)
            listing=listings_by_url.get(page_url)
            page=previews_by_url.get(page_url)
            if listing and page:
                row=_apply_exact_product_page_capture(row,listing,page)
            offer = recorded_offer(row)
            if offer:
                if row.get('listing_db_id'):
                    offer['listing_db_id']=row['listing_db_id']
                if row.get('playbook_product_capture'):
                    offer['playbook_product_capture']=row['playbook_product_capture']
                index.setdefault(row['cpk'], []).append(offer)
                identity_key=cpk_identity_key(offer.get('cpk_data'))
                if identity_key:
                    index.setdefault(identity_key, []).append(offer)
                # Some supplier observations omit their category even when
                # their linked CPK has a precise category. Use that identity
                # metadata to build safe role-specific indexes (notably exact
                # normalized CPU models across differently worded retailers).
                category = row['category'] or (offer.get('cpk_data') or {}).get('category')
                if not category:
                    tags=row.get('search_tags') or []
                    category=next((tag.split(':',1)[1].casefold() for tag in tags
                        if isinstance(tag,str) and tag.casefold().startswith('role:')),None)
                role={'graphics_card':'gpu'}.get(category,category)
                for key in product_keys(role,row['title']):
                    index.setdefault(key,[]).append(offer)
        db.info['simple_playbook_supplier_offers'] = index
    index = db.info['simple_playbook_supplier_offers']
    return index


def same_product(part, offer):
    """A CPK is a join candidate; a corrupt/generic key cannot replace product identity."""
    if is_full_system_listing(offer['title']):
        return False
    from app.services.playbook_service import _plausible_role_candidate
    if not _plausible_role_candidate(part['role'], offer['title']):
        return False
    from app.gem_radar.product_identifiers import title_part_numbers, variant_facts
    left_codes, right_codes = title_part_numbers(part['title']), title_part_numbers(offer['title'])
    product_evidence = offer.get('playbook_product_capture') or offer.get('product_capture')
    if not product_evidence and offer.get('raw_specs'):
        product_evidence = (offer.get('raw_specs') or {}).get('playbook_product_capture')
    if not product_evidence and offer.get('product_description'):
        product_evidence = offer
    shared_model_keys = set(product_keys(part['role'], part['title'])) & set(
        product_keys(part['role'], offer['title'], product_evidence))
    if any(key[0] == 'supplier_model' for key in shared_model_keys):
        left_facts = variant_facts(part['title'], part['role'])
        right_facts = variant_facts(offer['title'], part['role'])
        if all(left_facts[key] == right_facts[key] for key in left_facts.keys() & right_facts.keys()):
            return True
    if left_codes and right_codes and left_codes.isdisjoint(right_codes):
        # A retailer may expose a complete MPN where the source catalogue
        # title was truncated. Permit that difference only when the shared
        # CPK identity also validates both exact titles and their product
        # family/variant facts.
        if (part.get('cpk') and part.get('cpk') == offer.get('cpk')
                and part.get('cpk_data') and offer.get('cpk_data')
                and _same_specific_cpk_product(part, offer)):
            return True
        return False
    if part['role'] in {'storage', 'storage_secondary'}:
        # SSD captures commonly omit the manufacturer's full part number from
        # the title and append retailer-only wording. Match the explicit model
        # family only when the brand and capacity also agree; reject conflicts
        # in interface or heatsink state when both titles state them.
        from app.gem_radar.product_identifiers import title_brand
        def storage_brand(title):
            brand=title_brand(title)
            if brand:
                return brand
            if re.search(r'\b(?:western\s+digital|wd)\b',str(title or ''),re.I):
                return 'western_digital'
            return None
        left_brand=storage_brand(part['title'])
        right_brand=storage_brand(offer['title'])
        if (left_brand and right_brand and left_brand==right_brand
                and _same_storage_family(part['title'],offer['title'])):
            left_facts=_variant_facts(part['role'],part['title'])
            right_facts=_variant_facts(part['role'],offer['title'])
            if any(left_facts.get(key)!=right_facts.get(key)
                    for key in ('capacity_gb',) if key in left_facts and key in right_facts):
                return False
            def storage_detail(title):
                value=str(title or '').casefold()
                interface=('nvme' if re.search(r'\b(?:nvme|pcie)\b',value) else
                    'sata' if re.search(r'\bsata\b',value) else None)
                heatsink=('without' if re.search(r'\bwithout\s+(?:a\s+)?heat\s*sink\b',value) else
                    'with' if re.search(r'\bheat\s*sink\b',value) else None)
                return interface,heatsink
            left_detail=storage_detail(part['title'])
            right_detail=storage_detail(offer['title'])
            if any(a and b and a!=b for a,b in zip(left_detail,right_detail)):
                return False
            return True
    if left_codes & right_codes:
        left_facts = variant_facts(part['title'], part['role'])
        right_facts = variant_facts(offer['title'], part['role'])
        return all(left_facts[key] == right_facts[key] for key in left_facts.keys() & right_facts.keys())
    if part.get('cpk') and part.get('cpk')==offer.get('cpk') and part.get('cpk_data') and offer.get('cpk_data'):
        # Catalogue titles are sometimes truncated in the middle of an MPN.
        # A manufacturer MPN that continues that exact trailing prefix can
        # bridge the cut only when the shared CPK's detailed product-family
        # and variant facts also agree.
        trailing_code=re.search(r'\(([A-Z0-9-]{5,})\s*$',str(part.get('title') or ''),re.I)
        source_mpn=re.sub(r'[^a-z0-9]','',str(offer.get('mpn') or '').casefold())
        if (trailing_code and source_mpn.startswith(
                re.sub(r'[^a-z0-9]','',trailing_code.group(1).casefold()))
                and _same_specific_cpk_product(part,offer)):
            return True
    normalize = lambda value: re.sub(r'[^a-z0-9]', '', str(value or '').casefold())
    left, right = normalize(part['title']), normalize(offer['title'])
    if left == right:
        return True
    if part.get('cpk') and part.get('cpk')==offer.get('cpk') and offer.get('cpk_data'):
        # A shared key only establishes the join candidate. Require the
        # supplier's structured identity to describe both exact titles and
        # retain the same product/variant checks used for reviewed CPKs.
        from app.services.catalogue_cpk import identity_is_usable
        data=offer.get('cpk_data') or {}
        if (identity_is_usable(part['title'],data,{part['role']})
                and identity_is_usable(offer['title'],data,{part['role']})
                and _same_specific_cpk_product({**part,'cpk_data':data},offer)):
            return True
    if shared_model_keys:
        return True
    if part.get('cpk_data') and offer.get('cpk_data'):
        if _same_specific_cpk_product(part, offer):
            return True
    mpn = normalize(offer.get('mpn'))
    if len(mpn) >= 6 and any(c.isdigit() for c in mpn) and mpn in left:
        return True
    if part['role'] == 'cpu':
        from app.services.benchmark_normaliser import normalise_cpu
        model = normalise_cpu(part['title'])
        return bool(model and model == normalise_cpu(offer['title']))
    return False


def _same_specific_cpk_product(part, offer):
    """Use CPK metadata to bridge retailer title wording safely.

    The CPK hash is a join key, not proof by itself: broad GPU-family and
    placeholder identities are deliberately rejected. Capacity, memory and
    colour differences are checked when titles expose them.
    """
    left = part.get('cpk_data') or {}
    right = offer.get('cpk_data') or {}
    category = lambda value: {'storage': 'ssd', 'cooling': 'cooler',
                              'graphics_card': 'gpu'}.get(str(value or '').casefold(),
                                                           str(value or '').casefold())
    norm = lambda value: re.sub(r'[^a-z0-9]', '', str(value or '').casefold())
    left_category, right_category = category(left.get('category')), category(right.get('category'))
    left_brand, right_brand = norm(left.get('brand')), norm(right.get('brand'))
    left_model, right_model = norm(left.get('model')), norm(right.get('model'))
    if not (left_category and left_category == right_category
            and left_brand and left_brand == right_brand
            and left_model and left_model == right_model
            and left_model not in {'unknown', 'undefined', 'component', 'chassis', 'product'}):
        return False
    role = part.get('role')
    left_title, right_title = part.get('title') or '', offer.get('title') or ''
    if role == 'cpu':
        from app.services.benchmark_normaliser import normalise_cpu
        if normalise_cpu(left_title) != normalise_cpu(right_title):
            return False
    if role == 'gpu':
        # A chip family alone cannot match different add-in-board models.
        if re.fullmatch(r'(?:rtx|gtx|rx|arc)\d{3,4}(?:ti|super)?', left_model):
            return False
        if _gpu_board_family(left_title) != _gpu_board_family(right_title):
            return False
    if role == 'case':
        # Case CPKs generated from weak titles have sometimes put a model name
        # in the brand field and "mid tower case" in the model field. Never
        # let that category-level identity join prices from a different case.
        generic = {'atx', 'case', 'chassis', 'computer', 'full', 'gaming', 'itx',
                   'matx', 'mid', 'mini', 'pc', 'tower', 'white', 'black', 'rgb',
                   'argb', 'glass'}
        model_tokens = [token for token in norm(left.get('model')).split('-') if token not in generic]
        if not model_tokens:
            return False
        left_key, right_key = norm(left_title), norm(right_title)
        if not all(token in left_key and token in right_key for token in model_tokens):
            return False
    if role == 'ram' and not _same_product_family(left_title, right_title, _RAM_FAMILIES):
        return False
    if role in {'storage', 'storage_secondary'} and not _same_storage_family(left_title, right_title):
        return False
    if role == 'psu' and not _same_product_family(left_title, right_title, _PSU_FAMILIES):
        return False
    facts = lambda title: _variant_facts(role, title)
    a, b = facts(left_title), facts(right_title)
    for key in a.keys() & b.keys():
        if a[key] != b[key]:
            return False
    return True


_RAM_FAMILIES = (
    r'vengeance\s*(?:lpx|rgb(?:\s*pro|\s*rs)?)?', r'dominator(?:\s*titanium)?',
    r'fury\s*(?:beast|renegade|impact)', r'viper\s*(?:steel|venom|elite)',
    r'ripjaws\s*[sv]?', r'crucial\s*pro', r'xpg\s*lancer', r't[- ]force\s*delta',
)
_PSU_FAMILIES = (
    r'\brm\d{3,4}x\b', r'\brm\d{3,4}e\b', r'\brm\d{3,4}\b',
    r'\bsf\d{3,4}\b', r'\bhx\d{3,4}\b', r'\bcx\d{3,4}\b',
    r'\bfocus\b', r'\bprime\b', r'\bpure\s*power\s*\d{1,2}\b',
    r'\bdark\s*power\s*\d{1,2}\b', r'\bhydro\s*ptm\b', r'\bsupernova\b',
)


def _same_product_family(left, right, patterns):
    def family(value):
        text = value.casefold()
        return next((re.sub(r'\s+', '', match.group(0)) for pattern in patterns
                     if (match := re.search(pattern, text, re.I))), None)
    a, b = family(left), family(right)
    return bool(a and b and a == b)


def _gpu_board_family(title):
    text = title.casefold()
    patterns = (
        r'rog\s*strix', r'tuf\s*gaming', r'prime', r'dual', r'ventus\s*(?:2x|3x)?',
        r'suprim\s*x?', r'trio\s*x?', r'gaming\s*oc', r'eagle\s*oc?',
        r'windforce', r'aorus\s*(?:master|elite)?', r'phoenix(?:-s)?',
        r'nitro\+?', r'pulse', r'hellhound', r'red\s*devil', r'fighter',
        r'challenger', r'arc\s*b\d{3}\s*(?:titan|guardian|limited)',
    )
    return next((re.sub(r'\s+', '', match.group(0)) for pattern in patterns
                 if (match := re.search(pattern, text, re.I))), None)


def _same_storage_family(left, right):
    patterns = (
        r'\bsn\d{3,4}[a-z]?\b', r'\bsnv\d[a-z0-9/]*\b', r'\bnv\d(?:\s*\d{3,4})?\b',
        r'\bkc\d{3,4}\b', r'\b(?:bx|mx)\d{3}\b', r'\bp\d{1,3}\b',
        r'\ba\d{3,4}\b', r'\b\d{3}\s*(?:pro|evo|evo\s*plus|qvo)\b',
        r'\b(?:gm|nv)\d{1,4}\b', r'\bmodel\s*\w+\b',
    )
    return _same_product_family(left, right, patterns)


def _variant_facts(role, title):
    value = str(title or '').casefold()
    facts = {}
    if role in {'storage', 'storage_secondary'}:
        capacities = re.findall(r'\b(\d+(?:\.\d+)?)\s*(tb|gb)\b', value)
        if capacities:
            facts['capacity_gb'] = sorted({int(float(amount) * (1000 if unit == 'tb' else 1))
                                           for amount, unit in capacities})
    if role == 'ram':
        package = re.search(r'\b(\d+)\s*gb\b', value)
        if package:
            facts['capacity_gb'] = package.group(1)
    if role == 'ram':
        ddr = re.search(r'\bddr\s*([345])\b', value)
        speed = re.search(r'\b(\d{4,5})\s*mhz\b', value)
        sticks = re.search(r'\((\d+)\s*x\s*(\d+)\s*gb\)', value)
        latency = re.search(r'\bcl\s*(\d{1,2})\b', value)
        if ddr: facts['ddr'] = ddr.group(1)
        if speed: facts['speed'] = speed.group(1)
        if sticks: facts['sticks'] = (sticks.group(1), sticks.group(2))
        if latency: facts['latency'] = latency.group(1)
    if role == 'gpu':
        chip = re.search(r'\b(?:rtx|gtx|rx|arc)\s*(\d{3,4})\s*(ti|super)?\b', value)
        if chip: facts['chip'] = (chip.group(1), (chip.group(2) or '').strip())
        vram = re.search(r'\b(\d{1,2})\s*g(?:b)?\b', value)
        if vram: facts['vram_gb'] = vram.group(1)
    if role == 'cooling':
        radiator = re.search(r'\b(120|140|240|280|360|420)\s*mm\b', value)
        if radiator: facts['radiator'] = radiator.group(1)
    if role == 'case':
        colours = {'black', 'white', 'grey', 'gray', 'silver', 'red'}
        found = colours.intersection(re.findall(r'\b[a-z]+\b', value))
        if found: facts['colour'] = sorted(found)
    if role == 'psu':
        wattage = re.search(r'\b(\d{3,4})\s*(?:w(?:att)?s?)\b', value)
        if wattage: facts['wattage'] = wattage.group(1)
    return facts


def suggested_offer(part, offers):
    """Unknown delivery remains visible; it is never presented as delivered cost."""
    from app.services.commercial_readiness import same_listing_product
    source=part.get('source_observation') or {}
    original = {'url': part.get('source_url'), 'title': part['title'],
                'item_gbp': part.get('listing_price_gbp'),
                'delivery_gbp': part.get('supplier_postage_gbp'),
                'observed_at': part.get('price_observed_at'), 'match_basis': 'catalogue_identity',
                'stock_status':source.get('stock_status'),'stock_evidence':source.get('stock_evidence'),
                'condition':source.get('condition'),'listing_type':source.get('listing_type'),
                'commercial_capture_verified':source.get('commercial_capture_verified'),
                'delivery_working_days':source.get('delivery_working_days'),
                'delivery_estimate_source':source.get('delivery_estimate_source'),
                'prime_eligible':source.get('prime_eligible'),
                'licence_source_reviewed':source.get('licence_source_reviewed') is True,
                'licence_review_fingerprint':source.get('licence_review_fingerprint'),
                'postage_verified':source.get('postage_verified'),
                'postage_assumption':('captured' if source.get('postage_verified') is True
                    else 'owner-approved-zero-fallback'),
                'source':source.get('source')}
    matches=[row for row in offers if same_product(part,row)]
    def observed(offer):
        try:return datetime.fromisoformat(str(offer.get('observed_at')).replace('Z','+00:00')).replace(tzinfo=None)
        except (ValueError,TypeError):return datetime.min
    # Resolve one latest observation for the exact same supplier product. A
    # newer catalogue-page capture must supersede an older low supplier quote,
    # and a newer supplier quote must supersede that page capture. Previously
    # we only removed the page capture when the stored quote was newer, leaving
    # old low prices selectable after the exact page had already changed.
    same_product_matches=[row for row in matches if row.get('url') and original.get('url')
        and same_listing_product(row['url'],original['url'])]
    current_capture=bool(source.get('fresh') and source.get('commercial_capture_verified'))
    original_time=observed(original)
    latest_match=max(same_product_matches,key=observed) if same_product_matches else None
    keep_original=True
    if latest_match and current_capture:
        if original_time>=observed(latest_match):
            matches=[row for row in matches if row not in same_product_matches]
        else:
            keep_original=False
            matches=[row for row in matches if row not in same_product_matches or row is latest_match]
    choices = []
    for offer in [*([original] if keep_original else []), *matches]:
        if offer.get('item_gbp') is None:
            continue
        verified=offer.get('postage_verified') is True
        choices.append({**offer,
            'delivery_gbp':offer.get('delivery_gbp') if verified else '0.00',
            'postage_verified':verified,
            'postage_assumption':('captured' if verified else 'owner-approved-zero-fallback')})
    # The proposal's default BOM is assembled for Standard delivery. If its
    # catalogue page misses that ETA but an exact matched retailer offer for
    # the same product meets it, select that source before ranking price.
    # This keeps product identity fixed while allowing supplier substitution.
    from app.services.commerce_pricing import PLAYBOOK_SUPPLIER_ARRIVAL_LIMITS
    standard_limit=PLAYBOOK_SUPPLIER_ARRIVAL_LIMITS.get('standard',6)
    standard_choices=[]
    for offer in choices:
        if (offer.get('stock_status') not in {'available','in_stock'}
                or offer.get('condition')!='new'
                or offer.get('commercial_capture_verified') is not True):
            continue
        try:
            days=offer.get('delivery_working_days')
            if days is None:
                from app.services.commerce_pricing import estimate_delivery_working_days
                days,_=estimate_delivery_working_days(str(offer.get('source') or 'retail'),None,
                    offer.get('prime_eligible'))
            if (not isinstance(days,int) or isinstance(days,bool) or days<0 or days>standard_limit
                    or (offer.get('url') and urlsplit(offer['url']).hostname
                        in {'ebay.co.uk','www.ebay.co.uk','ebay.com','www.ebay.com','vinted.co.uk','www.vinted.co.uk'})):
                continue
            landed=Decimal(str(offer['item_gbp']))+Decimal(str(offer.get('delivery_gbp') or 0))
            seen=observed(offer)
            standard_choices.append((landed,days,-seen.toordinal(),-seen.hour,-seen.minute,-seen.second,offer))
        except (ValueError,TypeError,KeyError,ArithmeticError,OverflowError):
            continue
    if standard_choices:
        return min(standard_choices,key=lambda row:row[:-1])[-1]
    now=datetime.utcnow()
    def readiness(offer):
        fresh=timedelta(0)<=now-observed(offer)<=timedelta(hours=24)
        return (not (fresh and offer.get('stock_status')=='available'),
                offer.get('condition')!='new')
    return min(choices, key=lambda offer: (*readiness(offer), Decimal(offer['item_gbp']) +
               Decimal(offer.get('delivery_gbp') or 0),-observed(offer).toordinal(),-observed(offer).hour,
               -observed(offer).minute,-observed(offer).second)) if choices else None
