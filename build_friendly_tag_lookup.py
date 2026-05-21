#!/usr/bin/env python3
import csv
import json
import re
from collections import defaultdict
from urllib.parse import urlparse

IN_CSV = 'bscscan_transactions_2021_to_today.csv'
OUT_LOOKUP_CSV = 'friendly_tag_lookup.csv'
OUT_LOOKUP_JSON = 'friendly_tag_lookup.json'
OUT_ENRICHED = 'bscscan_transactions_2021_to_today.enriched.csv'

HEX40 = re.compile(r'^0x[a-fA-F0-9]{40}$')
TRUNC_ADDR = re.compile(r'^0x[a-fA-F0-9]{6,}\.\.\.[a-fA-F0-9]{4,}$')

def extract_address_from_url(url: str) -> str:
    if not url:
        return ''
    p = urlparse(url)
    parts = [x for x in p.path.split('/') if x]
    if len(parts) >= 2 and parts[0] == 'address' and HEX40.match(parts[1]):
        return parts[1]
    return ''

def looks_like_friendly(s: str) -> bool:
    if not s:
        return False
    t = s.strip()
    if HEX40.match(t) or TRUNC_ADDR.match(t):
        return False
    return True

rows = []
with open(IN_CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# tag -> set(address)
tag_to_addresses = defaultdict(set)
# address -> most common tag
address_to_tag_counts = defaultdict(lambda: defaultdict(int))

for r in rows:
    for side in ('from', 'to'):
        label = (r.get(side) or '').strip()
        addr = extract_address_from_url((r.get(f'{side}_url') or '').strip())
        if looks_like_friendly(label) and addr:
            tag_to_addresses[label].add(addr)
            address_to_tag_counts[addr][label] += 1

lookup_records = []
for tag, addrs in sorted(tag_to_addresses.items(), key=lambda kv: kv[0].lower()):
    for addr in sorted(addrs):
        lookup_records.append({'friendly_tag': tag, 'address': addr})

with open(OUT_LOOKUP_CSV, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['friendly_tag', 'address'])
    w.writeheader()
    w.writerows(lookup_records)

with open(OUT_LOOKUP_JSON, 'w', encoding='utf-8') as f:
    json.dump(lookup_records, f, indent=2)

# Choose most frequent tag per address for enrichment
best_tag_by_address = {}
for addr, counts in address_to_tag_counts.items():
    best_tag = max(counts.items(), key=lambda x: x[1])[0]
    best_tag_by_address[addr] = best_tag

# Add normalized addr/tag columns to transaction rows
for r in rows:
    from_addr = extract_address_from_url((r.get('from_url') or '').strip())
    to_addr = extract_address_from_url((r.get('to_url') or '').strip())
    r['from_address'] = from_addr
    r['to_address'] = to_addr
    r['from_friendly_tag_lookup'] = best_tag_by_address.get(from_addr, '')
    r['to_friendly_tag_lookup'] = best_tag_by_address.get(to_addr, '')

fieldnames = list(rows[0].keys()) if rows else []
with open(OUT_ENRICHED, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f'Lookup rows: {len(lookup_records)}')
print(f'Unique friendly tags: {len(tag_to_addresses)}')
print(f'Unique tagged addresses: {len(best_tag_by_address)}')
print(f'Wrote: {OUT_LOOKUP_CSV}')
print(f'Wrote: {OUT_LOOKUP_JSON}')
print(f'Wrote: {OUT_ENRICHED}')
