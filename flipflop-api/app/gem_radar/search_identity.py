"""Search-page identity only: exact manufacturer code before legacy title inference.

Pure functions shared by ingestion and the frozen before/after audit. No detail
requests, provider lookups, or model calls. Retailer IDs remain source aliases.
"""
import hashlib
import re
from app.gem_radar.product_identifiers import (
    normalise_brand, normalise_mpn, normalise_gtin, title_brand,
    title_part_numbers, variant_facts,
)

SEARCH_IDENTITY_VERSION = 3


def part_variant_facts(code):
    """Decode only explicit, established memory/storage part-code segments."""
    facts = {}
    if m := re.fullmatch(r'CM[KWHDT](\d+)GX([345])M(\d)[A-Z]*(\d{4,5})[CZ](\d+)[A-Z]*', code):
        facts.update(capacity_gb=int(m[1]), ddr=int(m[2]), modules=int(m[3]), speed=int(m[4]), cl=int(m[5]))
    elif m := re.fullmatch(r'KF([345])(\d{2})C(\d+)[A-Z]+(?:K(\d))?-(\d+)', code):
        facts.update(ddr=int(m[1]), speed=int(m[2])*100, cl=int(m[3]), modules=int(m[4] or 1), capacity_gb=int(m[5]))
    elif m := re.match(r'^C[TP](?:(\d)K)?(\d+)G', code):
        modules=int(m[1] or 1)
        facts.update(modules=modules, capacity_gb=modules*int(m[2]))
        if generation := re.match(r'^C[TP](?:\dK)?\d+G([345])(?=[A-Z])', code):
            facts['ddr']=int(generation[1])
        if ddr5 := re.search(r'G(\d{2})C(\d{2})[A-Z]*5',code):
            facts.update(ddr=5,speed=int(ddr5[1])*100,cl=int(ddr5[2]))
    elif m := re.fullmatch(r'SNV\d(S|SM3)/(\d+)(G|T0)', code):
        facts.update(capacity_gb=int(m[2])*(1000 if m[3]=='T0' else 1), form_factor='2230' if m[1]=='SM3' else '2280')
    elif m := re.search(r'^MZ-.*?(\d+)T0', code):
        facts['capacity_gb']=int(m[1])*1000
    elif m := re.fullmatch(r'PVV5(\d+)G(\d{2,3})C(\d{2})K?',code):
        facts.update(ddr=5,capacity_gb=int(m[1]),speed=int(m[2])*(10 if len(m[2])==3 else 100),cl=int(m[3]))
    elif m := re.match(r'^CC-H\d{2}F([BW])-',code):
        facts.update(colour='black' if m[1]=='B' else 'white',rgb=bool(re.search(r'-R\d$',code)))
    return facts


def manufacturer_part(title, brand=None, mpn=None):
    """Return one evidenced manufacturer+MPN, or an explicit conflict/unknown."""
    manufacturer = normalise_brand(brand or title_brand(title))
    codes = title_part_numbers(title)
    explicit = normalise_mpn(mpn)
    # Real sites put their own SKU or a barcode in the mpn field. Preserve raw
    # capture elsewhere; never promote those values into manufacturer identity.
    if explicit and (normalise_gtin(explicit) or re.match(r'^(?:STO-|ITM\d|LN\d|WINDOWS|OFFICE)', explicit)
                     or re.fullmatch(r'(?:RTX|GTX|RX|ARC)\d{3,4}(?:TI|SUPER|XT|XTX)?', explicit)):
        explicit = None
    if explicit and codes and explicit not in codes:
        return {'status': 'conflict', 'reason': 'manufacturer_part_number'}
    if len(codes) > 1:
        return {'status': 'conflict', 'reason': 'multiple_manufacturer_parts'}
    code = explicit or (next(iter(codes)) if codes else None)
    # Manufacturer formats are stronger than a chip vendor or compatibility
    # brand elsewhere in marketing text (e.g. AMD-compatible Corsair RAM).
    if code:
        for pattern, owner in [(r'^SNV|^KF\d|^SA400','kingston'),(r'^MZ-','samsung'),
                (r'^CM[KWHDT]|^CP-902|^CC-901','corsair'),(r'^C[TP]\d','crucial'),
                (r'^WDS\d','wd'),(r'^F[45]-','gskill'),(r'^100-1000','amd'),
                (r'^BX807','intel'),(r'^FD-C-','fractaldesign'),(r'^GV-','gigabyte'),
                (r'^ZT-','zotac'),(r'^90(?:YV|MB)|^(?:DUAL|PRIME|TUF|ROG)-RTX','asus'),
                (r'^CC-H','nzxt'),(r'^ACFRE','arctic'),(r'^PV[VSRP]|^P210S','patriot'),(r'^LD[45]','lexar')]:
            if re.match(pattern, code):
                manufacturer = owner
                break
    if not manufacturer or not code:
        return None
    return {'status': 'identified', 'manufacturer': manufacturer, 'mpn': code}


def search_result_identity(title, category=None, brand=None, mpn=None):
    from app.gem_radar.identity import is_full_system_listing, resolve_identity
    from app.gem_radar.opportunity_scoring import identity_gates
    if is_full_system_listing(title):
        return None
    part = manufacturer_part(title, brand, mpn)
    if not part or part['status'] == 'conflict':
        return part
    # This key is independent of seller wording, price, source and optional
    # category extraction. The exact manufacturer suffix is intentionally kept.
    cpk = hashlib.sha256(f"mpn|{part['manufacturer']}|{part['mpn']}".encode()).hexdigest()[:32]
    parsed = resolve_identity(title)
    category = {'storage': 'ssd', 'storage_secondary': 'ssd', 'cooling': 'cooler'}.get(category, category)
    category = category or parsed.category
    code = part['mpn']
    if re.match(r'^(?:CM[KWHDT]|KF\d|C[TP](?:\dK)?\d+G|F[45]-|M393|M378|M471|MTA|HMA|PV[VSRP]|LD[45])', code):
        category = 'ram'
    elif re.match(r'^(?:SNV\d|MZ-|WDS\d|SSD\dCS|SA400|P210S)', code):
        category = 'ssd'
    elif re.match(r'^(?:100-1000|BX807)', code):
        category = 'cpu'
    elif code.startswith('CC-H'):
        category = 'case'
    elif code.startswith('ACFRE'):
        category = 'cooler'
    elif re.match(r'^(?:DUAL|PRIME|TUF|ROG)-RTX', code):
        category = 'gpu'
    if any(flag in {'accessory_or_parts_listing', 'bundle_listing'} for flag in
           identity_gates(title, {'category': category, 'brand': part['manufacturer'], 'model': part['mpn']})):
        return None
    facts = variant_facts(title, category)
    encoded = part_variant_facts(part['mpn'])
    conflicts = [key for key in encoded.keys() & facts.keys() if encoded[key] != facts[key]]
    if conflicts:
        return {'status':'conflict', 'reason':'part_code_variant_disagrees', 'fields':conflicts}
    facts.update(encoded)
    data = {'cpk': cpk, 'category': category, 'brand': part['manufacturer'],
            'model': part['mpn'], 'variant_facts': facts,
            'specs': {k:v for k,v in {'capacity_gb':facts.get('capacity_gb'),
                'module_count':facts.get('modules'),'speed_mhz':facts.get('speed'),
                'cas_latency':facts.get('cl'),'type':f"ddr{facts['ddr']}" if facts.get('ddr') else None}.items() if v is not None},
            'extraction_method': 'search_manufacturer_mpn',
            'identity_match_rule': 'manufacturer_mpn', 'resolver_version': SEARCH_IDENTITY_VERSION,
            'identity_validation_version': SEARCH_IDENTITY_VERSION,
            'identity_source_title': title,
            'identity_claims': [{'kind': 'mpn', 'namespace': part['manufacturer'], 'value': part['mpn']}]}
    return {'status': 'matched', 'cpk': cpk, 'data': data, 'claims': data['identity_claims']}


def preferred_search_query(title, data=None, role=None):
    """Prefer evidenced search-capture MPNs, including ones absent from titles."""
    data = data or {}
    part = manufacturer_part(title)
    if not part:
        claims = [c for c in data.get('identity_claims', []) if c.get('kind') == 'mpn']
        if len(claims) == 1 and data.get('extraction_method') in {'search_manufacturer_mpn','search_title_fallback'}:
            part = manufacturer_part(title, data.get('brand'), claims[0].get('value'))
    if part and part['status'] == 'identified':
        return f"{part['manufacturer']} {part['mpn']}"
    return re.sub(r'\s+', ' ', re.split(r'[,|]', title, maxsplit=1)[0]).strip()


def last_resort_title_key(title, category, identity=None):
    """Exact product-name/spec key, never arbitrary fuzzy string similarity."""
    from app.gem_radar.identity import is_full_system_listing, resolve_identity
    if is_full_system_listing(title):
        return None
    brand = title_brand(title)
    if not brand:
        return None
    category = {'storage':'ssd','storage_secondary':'ssd','cooling':'cooler'}.get(category, category) or resolve_identity(title).category
    if category == 'cpu':
        from app.services.benchmark_normaliser import normalise_cpu
        model = normalise_cpu(re.sub(r'\bryzensets\b','Ryzen',title,flags=re.I))
        return ('title_product','cpu',brand,model) if model else None
    facts = variant_facts(title, category)
    if identity and identity.get('identity_claims'):
        for key,value in (identity.get('variant_facts') or {}).items():
            facts.setdefault(key,value)
    if category == 'ram':
        required = {'family','capacity_gb','modules','ddr','speed','cl'}
        if required <= facts.keys():
            colour = re.search(r'\b(black|white|grey|gray|silver|red)\b',title,re.I)
            return ('title_product','ram',brand,*[facts[k] for k in sorted(required)],
                    (colour[1].casefold().replace('gray','grey') if colour else 'unknown_colour'),
                    bool(re.search(r'\b(?:a?rgb)\b',title,re.I)))
    if category == 'ssd' and {'capacity_gb','form_factor'} <= facts.keys():
        family = re.search(r'\b(?:990\s*(?:pro|evo(?:\s*plus)?)|980\s*pro|nv[123]|sn850x|p310|p510)\b',title,re.I)
        if family:
            heatsink = ('without' if re.search(r'\bwithout\s+(?:a\s+)?heat\s*sink\b',title,re.I)
                        else 'with' if re.search(r'\bheat\s*sink\b',title,re.I) else 'unspecified')
            return ('title_product','ssd',brand,re.sub(r'\s+','',family[0].casefold()),
                    facts['capacity_gb'],facts['form_factor'],heatsink)
    if category == 'case' and brand == 'nzxt':
        model = re.search(r'\bH\d{1,3}i?\s*Flow\b',title,re.I)
        colour = re.search(r'\b(black|white)\b',title,re.I)
        colour = colour[1].casefold() if colour else facts.get('colour')
        if model and colour:
            year = re.search(r'\b(20\d{2})\b',title)
            return ('title_product','case',brand,re.sub(r'\s+','',model[0].casefold()),colour,
                    facts.get('rgb',bool(re.search(r'\brgb\b',title,re.I))),year[1] if year else 'unknown_year')
    return None


def unique_title_candidate(title, candidates):
    """A title fallback cannot choose between distinct evidenced manufacturer SKUs."""
    from app.gem_radar.product_identifiers import identity_conflicts
    eligible = [(cpk,data) for cpk,data in candidates if not identity_conflicts(title,data)]
    strong = [(cpk,data) for cpk,data in eligible if data.get('identity_claims')]
    eligible = strong or eligible
    keys = {cpk for cpk,data in eligible}
    if len(keys) != 1:
        return None
    cpk, data = eligible[0]
    return cpk, {**data, 'identity_match_rule':'title_product',
                 'extraction_method':'search_title_fallback', 'identity_anchor_cpk':cpk}
