#!/usr/bin/env python3
import csv
import json
from pathlib import Path

BASE_LOOKUP = Path('friendly_tag_lookup.csv')
BASE_DATASET = Path('bscscan_transactions_2021_to_today.enriched.csv')

OUT_LOOKUP_CSV = Path('friendly_tag_lookup.extended.csv')
OUT_LOOKUP_JSON = Path('friendly_tag_lookup.extended.json')
OUT_DATASET = Path('bscscan_transactions_2021_to_today.enriched.with_external_tags.csv')

# High-confidence public mappings found from BscScan / official project docs.
EXTERNAL_MAPPINGS = [
    {
        'friendly_tag': 'Safuu: SAFUU Token',
        'address': '0xE5bA47fD94CB645ba4119222e34fB33F59C7CD90',
        'source': 'https://bscscan.com/address/0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90',
        'query_term': 'Safuu / SFU / SFX',
    },
    {
        'friendly_tag': 'Safuu: Deployer',
        'address': '0xc38511A85d8FBF2C859e0bCE7E831AFd4b569939',
        'source': 'https://bscscan.com/address/0xc38511a85d8fbf2c859e0bce7e831afd4b569939',
        'query_term': 'Safuu',
    },
    {
        'friendly_tag': 'SafuuGO: SGO Token',
        'address': '0x9321bc6185AdC9B9Cb503cc211E17Cb311c3FA95',
        'source': 'https://bscscan.com/token/0x9321bc6185adc9b9cb503cc211e17cb311c3fa95',
        'query_term': 'SafuuGo / SGO',
    },
    {
        'friendly_tag': 'Vulcan Forged PYR (PYR)',
        'address': '0x936E203701C6f8b619fcf8BCbA8Ec0D4157f02A5',
        'source': 'https://bscscan.com/token/0x936e203701c6f8b619fcf8bcba8ec0d4157f02a5',
        'query_term': 'Vulcan / VUL',
    },
    {
        'friendly_tag': 'VulcanSwap: Vulcan Token (VULCAN)',
        'address': '0xd7F7827507c49235A2a6C13cE07BaC75ab183eA8',
        'source': 'https://vulcanswap.gitbook.io/vulcanswap/tokenomics/vulcanswap-token-vulcan',
        'query_term': 'VUL',
    },
    {
        'friendly_tag': 'Vitruveo Bridged VTRU (VTRU)',
        'address': '0xb08504D245713Ca9692C8fA605E76A0A11Ed4955',
        'source': 'https://bscscan.com/token/0xb08504d245713ca9692c8fa605e76a0a11ed4955',
        'query_term': 'Vitruveo / VTRX',
    },
]


def norm_addr(a: str) -> str:
    return (a or '').strip().lower()

# Load current lookup
lookup_rows = []
if BASE_LOOKUP.exists():
    with BASE_LOOKUP.open(newline='', encoding='utf-8') as f:
        lookup_rows = list(csv.DictReader(f))

# Build index from existing lookup
addr_to_tag = {}
for r in lookup_rows:
    a = norm_addr(r.get('address', ''))
    t = (r.get('friendly_tag', '') or '').strip()
    if a and t:
        addr_to_tag[a] = t

# Inject external mappings (external mappings override if same address)
external_rows = []
for m in EXTERNAL_MAPPINGS:
    a = norm_addr(m['address'])
    addr_to_tag[a] = m['friendly_tag']
    external_rows.append({
        'friendly_tag': m['friendly_tag'],
        'address': m['address'],
        'source': m['source'],
        'query_term': m['query_term'],
    })

# Write extended lookup csv (simple)
extended_lookup_simple = [
    {'friendly_tag': tag, 'address': addr}
    for addr, tag in sorted(addr_to_tag.items(), key=lambda kv: kv[1].lower())
]
with OUT_LOOKUP_CSV.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['friendly_tag', 'address'])
    w.writeheader()
    w.writerows(extended_lookup_simple)

# Write richer JSON with sources for external additions
payload = {
    'lookup': extended_lookup_simple,
    'external_additions': external_rows,
}
with OUT_LOOKUP_JSON.open('w', encoding='utf-8') as f:
    json.dump(payload, f, indent=2)

# Re-enrich dataset using extended lookup
if BASE_DATASET.exists():
    with BASE_DATASET.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        fa = norm_addr(r.get('from_address', ''))
        ta = norm_addr(r.get('to_address', ''))

        # Preserve old columns and add external-aware columns
        r['from_friendly_tag_final'] = addr_to_tag.get(fa, r.get('from_friendly_tag_lookup', '') or '')
        r['to_friendly_tag_final'] = addr_to_tag.get(ta, r.get('to_friendly_tag_lookup', '') or '')

    fieldnames = list(rows[0].keys()) if rows else []
    with OUT_DATASET.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    tagged_from = sum(1 for r in rows if (r.get('from_friendly_tag_final') or '').strip())
    tagged_to = sum(1 for r in rows if (r.get('to_friendly_tag_final') or '').strip())
    print(f'Extended lookup entries: {len(extended_lookup_simple)}')
    print(f'Rows in dataset: {len(rows)}')
    print(f'Rows with from_friendly_tag_final: {tagged_from}')
    print(f'Rows with to_friendly_tag_final: {tagged_to}')
    print(f'Wrote: {OUT_LOOKUP_CSV}')
    print(f'Wrote: {OUT_LOOKUP_JSON}')
    print(f'Wrote: {OUT_DATASET}')
else:
    print('Base dataset not found; wrote lookup files only.')

