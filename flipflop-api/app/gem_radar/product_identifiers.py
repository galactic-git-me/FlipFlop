"""Shared marketplace identifiers used to link the same product across sources."""
from __future__ import annotations

import re
from urllib.parse import unquote


_ASIN_RE = re.compile(
    r"/(?:dp|gp/product|gp/aw/d|exec/obidos/ASIN)/([A-Z0-9]{10})(?:[/?#]|$)",
    re.IGNORECASE,
)


def extract_asin(value: str | None) -> str | None:
    """Extract an Amazon ASIN from a product URL or a standalone listing ID."""
    if not value:
        return None
    match = _ASIN_RE.search(unquote(value))
    if match:
        return match.group(1).upper()
    # Amazon scrapes commonly use the ASIN itself as listing_id. Do not infer
    # an ASIN from arbitrary descriptive text or a larger vendor identifier.
    if re.fullmatch(r"[A-Z0-9]{10}", value.strip(), re.IGNORECASE):
        return value.strip().upper()
    return None


def categories_compatible(expected: str | None, actual: str | None) -> bool:
    if not expected or not actual:
        return True
    aliases = {
        "storage": {"storage", "ssd"},
        "ssd": {"storage", "ssd"},
        "cooler": {"cooler", "cooling"},
        "cooling": {"cooler", "cooling"},
    }
    return actual.strip().lower() in aliases.get(expected.strip().lower(), {expected.strip().lower()})


def normalise_gtin(value: str | None) -> str | None:
    """Validate GTIN-8/12/13/14 and return its internal 14-digit comparison key."""
    raw = re.sub(r'[\s-]', '', str(value or ''))
    if len(raw) not in {8, 12, 13, 14} or not raw.isascii() or not raw.isdigit() or set(raw) == {'0'}:
        return None
    check = (10 - sum(int(digit) * (3 if index % 2 == 0 else 1)
                      for index, digit in enumerate(reversed(raw[:-1]))) % 10) % 10
    return raw.zfill(14) if check == int(raw[-1]) else None


def normalise_brand(value: str | None) -> str:
    key = re.sub(r'[^a-z0-9]', '', str(value or '').casefold())
    return {'westerndigital': 'wd', 'wdblack': 'wd', 'westerndigitaltechnologiesinc': 'wd',
            'hewlettpackard': 'hp', 'kingstontechnology': 'kingston', 'kingstonfury': 'kingston',
            'corsairmemory': 'corsair', 'corsairmemoryinc': 'corsair', 'crucialtechnology': 'crucial',
            'asustek': 'asus', 'asustekcomputer': 'asus', 'asustekcomputerinc': 'asus',
            'gigabytetechnology': 'gigabyte', 'microstarinternational': 'msi',
            'microstar': 'msi', 'pnytechnologies': 'pny'}.get(key, key)


def normalise_mpn(value: str | None) -> str | None:
    """Conservative manufacturer-code normalization; suffixes and separators survive."""
    raw = re.sub(r'\s+', '', str(value or '')).upper()
    if len(raw) < 5 or len(raw) > 100 or raw in {'UNKNOWN', 'UNDEFINED', 'NONE', 'N/A', 'DOESNOTAPPLY'}:
        return None
    return raw if re.fullmatch(r'[A-Z0-9][A-Z0-9./_-]*', raw) and any(c.isdigit() for c in raw) else None


def title_part_numbers(title: str) -> set[str]:
    """Recognise manufacturer formats; arbitrary merchant SKUs are never inferred."""
    patterns = (
        r'\bSNV\d[A-Z0-9]*/[A-Z0-9]+\b',  # Kingston incl. distinct 2230/2280 variants
        r'\bMZ-[A-Z0-9]{6,}(?:/[A-Z0-9]+)?\b',
        r'\bCM[KWHDT][A-Z0-9]{8,}(?:-[A-Z0-9]+)*\b',  # Corsair memory part codes
        r'\bCT\d+[A-Z0-9]{5,}(?:-[A-Z0-9]+)*\b',
        r'\bWDS\d[A-Z0-9]{5,}(?:-[A-Z0-9]+)?\b',
        r'\bSSD\dCS\d+[A-Z0-9-]+\b',
        r'\bKF\d{3,}[A-Z0-9]+(?:[-/][A-Z0-9]+)*\b',  # Kingston Fury kits
        r'\bF[45]-[A-Z0-9]{6,}(?:-[A-Z0-9]+)+\b',  # G.Skill exact kit codes
        r'\b100-1000\d{5,}[A-Z]*\b',  # AMD boxed/tray product codes
        r'\bBX807\d+[A-Z0-9]+\b',  # Intel boxed CPUs
        r'\b(?:CP-902|CC-901)\d+[A-Z0-9-]*\b',  # Corsair PSU/case codes
        r'\bFD-C-[A-Z0-9]+(?:-[A-Z0-9]+)+\b',  # Fractal case variants
        r'\bGV-[A-Z0-9]+(?:-[A-Z0-9]+)+\b',  # Gigabyte graphics board SKU
        r'\bZT-[A-Z0-9]+(?:-[A-Z0-9]+)+\b',  # Zotac graphics board SKU
        r'\b90(?:YV|MB)[A-Z0-9]+(?:-[A-Z0-9]+)+\b',  # ASUS board/card codes
        r'\bM(?:393|378|471)[A-Z0-9]+-[A-Z0-9]+\b',  # Samsung RAM
        r'\bMTA[A-Z0-9]+-[A-Z0-9]+\b',  # Micron RAM
        r'\bHMA[A-Z0-9]+-[A-Z0-9]+\b',  # SK Hynix RAM
        r'(?<=\()\d{2}[A-Z]{2}\d{3}(?=\))',  # Explicit Lenovo part in parentheses
        r'\bCC-H[A-Z0-9]+(?:-[A-Z0-9]+)+\b',  # NZXT case SKU, colour/revision retained
        r'\bACFRE\d{5}[A-Z0-9]*\b',  # Arctic cooler product code
        r'\bCP(?:\dK)?\d+G[A-Z0-9]+(?:-[A-Z0-9]+)*\b',  # Crucial Pro kits
        r'\bPV[VSRP]\d[A-Z0-9]+(?:-[A-Z0-9]+)*\b',  # Patriot Viper kits
        r'\bLD[45][A-Z0-9]+(?:-[A-Z0-9]+)+\b',  # Lexar exact memory kit code
        r'\bSA400(?:S37|M8)/\d+G\b',  # Kingston SATA part, capacity retained
        r'\bP210S\d+G25\b',  # Patriot SATA SSD
        r'\b(?:DUAL|PRIME|TUF|ROG)-RTX[A-Z0-9]+(?:-[A-Z0-9]+)+\b',  # ASUS full board model code
    )
    return {code for pattern in patterns for value in re.findall(pattern, title.upper())
            if (code := normalise_mpn(value))}


def title_brand(title: str) -> str | None:
    title = re.sub(r'^\s*quick\s*view\s*', '', title, flags=re.I)
    brands = ('corsair', 'kingston', 'samsung', 'crucial', 'thermalright', 'noctua',
              'lian li', 'kolink', 'gigabyte', 'asrock', 'asus', 'msi', 'patriot',
              'lexar', 'silicon power', 'fractal design', 'be quiet', 'nzxt', 'fsp',
              'g.skill', 'zotac', 'pny', 'western digital', 'wd black', 'adata',
              'intel', 'amd', 'lenovo', 'micron', 'sk hynix', 'hp', 'hpe',
              'arctic', 'asustek computer', 'micro-star international', 'micro star', 'deepcool')
    matches = [(match.start(), normalise_brand(brand)) for brand in brands
               if (match := re.search(r'\b' + re.escape(brand).replace(r'\ ', r'[\s_-]+') + r'\b', title, re.I))]
    return min(matches)[1] if matches else None


def variant_facts(title: str, category: str | None) -> dict:
    """Only explicit identity fields. Unknown fields remain absent."""
    value = title.casefold()
    category = {'storage': 'ssd', 'storage_secondary': 'ssd', 'cooling': 'cooler'}.get(category, category)
    facts = {}
    if category in {'ram', 'ssd'}:
        kit = re.search(r'\b(\d+)\s*[x×]\s*(\d+)\s*gb\b', value)
        capacity = re.search(r'\b(\d+(?:\.\d+)?)\s*(tb|gb)\b', value)
        if category == 'ram' and kit:
            facts.update(capacity_gb=int(kit[1])*int(kit[2]), modules=int(kit[1]), module_gb=int(kit[2]))
        elif capacity:
            facts['capacity_gb'] = int(float(capacity[1])*(1000 if capacity[2]=='tb' else 1))
    if category == 'ram':
        for key, pattern in [('ddr',r'\bddr\s*([345])\b'), ('speed',r'\b(\d{4,5})\s*(?:mhz|mt/s)\b'),
                             ('cl',r'\b(?:cl|c)\s*(\d{2})\b')]:
            if match := re.search(pattern,value): facts[key] = int(match[1])
        for family in (r'vengeance\s*rgb\s*pro\s*sl',r'vengeance\s*rgb\s*pro',r'vengeance\s*rgb\s*rs',r'vengeance\s*lpx',
                       r'vengeance\s*rgb',r'vengeance',r'dominator\s*titanium',r'fury\s*beast',r'viper\s*venom'):
            if match := re.search(family,value):
                facts['family']=re.sub(r'\s+','',match[0]); break
    if category == 'ssd':
        if match := re.search(r'\b(2230|2242|2260|2280|22110)\b',value): facts['form_factor']=match[1]
    return facts


def identity_conflicts(title: str, data: dict | None, category: str | None = None) -> list[str]:
    """Reject cached metadata which contradicts explicit current source facts."""
    data = data or {}
    conflicts = []
    if data.get('identity_status') == 'conflict': return ['quarantined']
    if not categories_compatible(category, data.get('category')): conflicts.append('category')
    actual_brand = title_brand(title)
    if actual_brand and data.get('brand') and actual_brand != normalise_brand(data['brand']): conflicts.append('brand')
    actual = variant_facts(title, category or data.get('category'))
    specs = data.get('specs') or {}
    expected = variant_facts(str(data.get('model') or '').replace('-', ' '), category or data.get('category'))
    expected.update(data.get('variant_facts') or {})
    if (category or data.get('category')) == 'cpu':
        from app.services.benchmark_normaliser import normalise_cpu
        model = str(data.get('model') or '').replace('-',' ')
        if data.get('identity_claims') and data.get('identity_source_title'):
            model = data['identity_source_title']
        clean = lambda text: re.sub(r'\bryzensets\b','Ryzen',text,flags=re.I)
        left,right=normalise_cpu(clean(title)),normalise_cpu(clean(model))
        known = r'ryzen|core|xeon|epyc|threadripper|pentium|celeron|athlon'
        if left and right and re.search(known,left) and re.search(known,right) and left!=right:
            conflicts.append('cpu_model')
    for target, aliases in {'capacity_gb':('capacity_gb',),'modules':('modules','module_count','sticks'),
                            'speed':('speed_mhz',),'cl':('cl','cas_latency')}.items():
        for alias in aliases:
            if specs.get(alias) is not None:
                try: expected[target] = int(specs[alias])
                except (ValueError, TypeError): pass
                break
    if str(specs.get('type') or '').lower() in {'ddr3','ddr4','ddr5'}: expected['ddr']=int(specs['type'][-1])
    for key in actual.keys() & expected.keys():
        if key == 'family' and title_part_numbers(title) & title_part_numbers(str(data.get('model') or '')):
            continue  # A shortened marketing family is not a different exact MPN.
        # Old SSD metadata uses both decimal GB and binary GiB for a marketed TB.
        if key=='capacity_gb' and (category or data.get('category')) in {'ssd','storage','storage_secondary'}:
            a,b=actual[key],expected[key]
            if a%1000==0 and b==a//1000*1024: continue
        if actual[key] != expected[key]: conflicts.append(key)
    return sorted(set(conflicts))


def identity_has_variant_evidence(title: str, data: dict) -> bool:
    """A family-only alias cannot establish an exact RAM kit or SSD variant."""
    category = data.get('category')
    if category not in {'ram', 'ssd', 'storage', 'storage_secondary'}:
        return True
    title_codes = title_part_numbers(title)
    model_codes = title_part_numbers(str(data.get('model') or ''))
    model_codes.update(claim.get('value') for claim in data.get('identity_claims', [])
                       if claim.get('kind') == 'mpn' and claim.get('value'))
    if title_codes and model_codes and title_codes == model_codes:
        return True
    actual = variant_facts(title, category)
    expected = variant_facts(str(data.get('model') or '').replace('-', ' '), category)
    expected.update(data.get('variant_facts') or {})
    specs = data.get('specs') or {}
    for key, field in {'capacity_gb':'capacity_gb', 'modules':'module_count',
                       'speed':'speed_mhz', 'cl':'cas_latency'}.items():
        if specs.get(field) is not None:
            expected[key] = specs[field]
    if str(specs.get('type') or '').casefold() in {'ddr3','ddr4','ddr5'}:
        expected['ddr'] = int(str(specs['type'])[-1])
    return bool(actual) and all(key in expected for key in actual)
