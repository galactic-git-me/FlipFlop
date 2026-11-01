"""Link catalogue identities to captured UK supplier offers without provider calls."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import re

from sqlalchemy import bindparam, text
from app.gem_radar.identity import is_full_system_listing


UK_HOSTS = {'amazon.co.uk', 'www.amazon.co.uk', 'scan.co.uk', 'www.scan.co.uk',
            'overclockers.co.uk', 'www.overclockers.co.uk', 'ebuyer.com', 'www.ebuyer.com',
            'computerorbit.com','www.computerorbit.com','awd-it.co.uk','www.awd-it.co.uk','cclonline.com','www.cclonline.com'}


def product_keys(role, title):
    """Exact identities only: a GPU family alone is not a board identity."""
    if is_full_system_listing(title):
        return []
    normalized=re.sub(r'[^a-z0-9]','',title.casefold())
    keys=[('title',normalized)]
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
        # MSI's differently worded vendor titles consistently retain these
        # exact board identifiers; do not merge Ventus with Trio/Suprim or 2X.
        board=re.search(r'\bventus\s*(2x|3x)\b',title,re.I)
        memory=re.search(r'\b(\d{1,2})\s*g(?:b)?\b',title,re.I)
        chip=re.search(r'\brtx\s*(\d{4})(?:\s*(ti|super))?\b',title,re.I)
        if re.search(r'\bmsi\b',title,re.I) and board and memory and chip:
            keys.append(('gpu_board','msi',chip[1],(chip[2] or '').lower(),memory[1],
                         'ventus',board[1].lower(),bool(re.search(r'\boc\b',title,re.I))))
    return keys


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
    return {'observation_id': row['id'], 'listing_id':row['listing_id'],
            'cpk': row['cpk'], 'title': row['title'],
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
              AND o.source IN ('amazon','scan','overclockers','ebuyer','computer_orbit','awd_it','ccl')
          ) SELECT o.id,o.listing_id,c.cpk,c.cpk_data,o.title,o.source,o.item_price,o.mpn,
                   o.commercial_source_evidence,o.observed_at,o.category
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
        index = {}
        for row in rows:
            row={**row,'recorded_product_url':urls.get((row['source'],row['listing_id']))}
            offer = recorded_offer(row)
            if offer:
                index.setdefault(row['cpk'], []).append(offer)
                identity_key=cpk_identity_key(offer.get('cpk_data'))
                if identity_key:
                    index.setdefault(identity_key, []).append(offer)
                # Some supplier observations omit their category even when
                # their linked CPK has a precise category. Use that identity
                # metadata to build safe role-specific indexes (notably exact
                # normalized CPU models across differently worded retailers).
                category = row['category'] or (offer.get('cpk_data') or {}).get('category')
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
    if left_codes and right_codes and left_codes.isdisjoint(right_codes):
        return False
    if left_codes & right_codes:
        left_facts = variant_facts(part['title'], part['role'])
        right_facts = variant_facts(offer['title'], part['role'])
        return all(left_facts[key] == right_facts[key] for key in left_facts.keys() & right_facts.keys())
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
    if set(product_keys(part['role'],part['title'])) & set(product_keys(part['role'],offer['title'])):
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
        r'rog\s*strix', r'tuf\s*gaming', r'prime', r'ventus\s*(?:2x|3x)?',
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
    now=datetime.utcnow()
    def readiness(offer):
        fresh=timedelta(0)<=now-observed(offer)<=timedelta(hours=24)
        return (not (fresh and offer.get('stock_status')=='available'),
                offer.get('condition')!='new')
    return min(choices, key=lambda offer: (*readiness(offer), Decimal(offer['item_gbp']) +
               Decimal(offer.get('delivery_gbp') or 0),-observed(offer).toordinal(),-observed(offer).hour,
               -observed(offer).minute,-observed(offer).second)) if choices else None
