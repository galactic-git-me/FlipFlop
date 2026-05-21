#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple

IN_CSV = Path('bscscan_transactions_with_valuation.csv')
TX_CACHE = Path('.cache_txs.json')
RECEIPT_CACHE = Path('.cache_tx_receipts.json')
TOKEN_META_CACHE = Path('.cache_token_meta.json')

OUT_TOKEN_CSV = Path('money_by_token_with_valuation.csv')
OUT_TOKEN_MD = Path('money_by_token_with_valuation.md')
OUT_TOKEN_JSON = Path('money_by_token_with_valuation.json')
OUT_TOKEN_MONTHLY = Path('money_by_token_monthly.csv')

TARGET = '0x128c33c16ee6d337154d0996220a791d89aa0442'
BNB_USD_TODAY = 658.81

TRANSFER_TOPIC = '0xddf252ad'

TARGET_SYMBOLS = {
    'SAFUU', 'SGO', 'VUL', 'SFX', 'SFU', 'VTRX', 'VTRU', 'PYR'
}

KNOWN_TOKEN_MAP = {
    '0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90': ('SAFUU', 'Safuu: SAFUU Token'),
    '0x9321bc6185adc9b9cb503cc211e17cb311c3fa95': ('SGO', 'SafuuGO: SGO Token'),
    '0x936e203701c6f8b619fcf8bcba8ec0d4157f02a5': ('PYR', 'Vulcan Forged PYR'),
    '0xd7f7827507c49235a2a6c13ce07bac75ab183ea8': ('VUL', 'VulcanSwap: VULCAN'),
    '0xb08504d245713ca9692c8fa605e76a0a11ed4955': ('VTRU', 'Vitruveo Bridged VTRU'),
}


def norm(s: str) -> str:
    return (s or '').strip().lower()


def load_json(path: Path, default):
    if path.exists():
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    return default


def parse_addr_topic(topic_hex: str) -> str:
    # topic is 32-byte hex, address is last 20 bytes
    if not topic_hex or not topic_hex.startswith('0x') or len(topic_hex) < 42:
        return ''
    return '0x' + topic_hex[-40:].lower()


def token_meta_for(addr: str, token_meta_cache: Dict[str, dict]) -> Tuple[str, str]:
    a = norm(addr)
    if a in KNOWN_TOKEN_MAP:
        return KNOWN_TOKEN_MAP[a]

    meta = token_meta_cache.get(a, {})
    symbol = (meta.get('symbol') or '').strip().upper()
    name = (meta.get('name') or '').strip()
    return symbol, name


def value_bnb(row: dict) -> float:
    try:
        return float((row.get('value_bnb') or '0').strip() or 0)
    except Exception:
        return 0.0


def usd_then(row: dict) -> float:
    try:
        return float((row.get('usd_at_tx_time') or '0').strip() or 0)
    except Exception:
        return 0.0

rows = []
with IN_CSV.open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

tx_cache = load_json(TX_CACHE, {})
receipt_cache = load_json(RECEIPT_CACHE, {})
token_meta_cache = load_json(TOKEN_META_CACHE, {})

agg = defaultdict(lambda: {
    'tx_count': 0,
    'money_into_token_bnb': 0.0,
    'money_out_of_token_bnb': 0.0,
    'net_token_flow_bnb': 0.0,
    'money_into_token_usd_then': 0.0,
    'money_out_of_token_usd_then': 0.0,
    'net_token_flow_usd_then': 0.0,
    'money_into_token_usd_today': 0.0,
    'money_out_of_token_usd_today': 0.0,
    'net_token_flow_usd_today': 0.0,
})

monthly = defaultdict(lambda: {
    'tx_count': 0,
    'money_into_token_bnb': 0.0,
    'money_out_of_token_bnb': 0.0,
    'money_into_token_usd_then': 0.0,
    'money_out_of_token_usd_then': 0.0,
    'money_into_token_usd_today': 0.0,
    'money_out_of_token_usd_today': 0.0,
})

for r in rows:
    txh = norm(r.get('tx_hash'))
    if not txh:
        continue

    tx = tx_cache.get(txh) or {}
    receipt = receipt_cache.get(txh) or {}

    from_addr = norm(tx.get('from'))
    to_addr = norm(tx.get('to'))

    direction = 'other'
    if from_addr == TARGET:
        direction = 'into_token'      # wallet sent funds into token-related tx
    elif to_addr == TARGET:
        direction = 'out_of_token'    # wallet received funds back

    # find token symbols touched by this tx via Transfer logs involving wallet
    token_symbols_touched = set()
    token_labels = {}

    for lg in receipt.get('logs', []) if isinstance(receipt, dict) else []:
        topics = lg.get('topics') or []
        if not topics:
            continue
        topic0 = (topics[0] or '').lower()
        if not topic0.startswith(TRANSFER_TOPIC):
            continue

        token_addr = norm(lg.get('address'))
        if not token_addr:
            continue

        # require wallet involvement in transfer for attribution quality
        from_t = parse_addr_topic(topics[1]) if len(topics) > 1 else ''
        to_t = parse_addr_topic(topics[2]) if len(topics) > 2 else ''
        if TARGET not in {from_t, to_t}:
            continue

        sym, name = token_meta_for(token_addr, token_meta_cache)
        if sym in TARGET_SYMBOLS:
            token_symbols_touched.add(sym)
            token_labels[sym] = name or token_addr

    if not token_symbols_touched:
        continue

    bnb = value_bnb(r)
    then_usd = usd_then(r)
    today_usd = bnb * BNB_USD_TODAY

    # split evenly if multiple target tokens in same tx
    w = 1.0 / len(token_symbols_touched)
    month = (r.get('datetime_utc') or '')[:7]

    for sym in sorted(token_symbols_touched):
        d = agg[sym]
        d['tx_count'] += 1

        mkey = (month, sym)
        m = monthly[mkey]
        m['tx_count'] += 1

        if direction == 'into_token':
            d['money_into_token_bnb'] += bnb * w
            d['money_into_token_usd_then'] += then_usd * w
            d['money_into_token_usd_today'] += today_usd * w

            m['money_into_token_bnb'] += bnb * w
            m['money_into_token_usd_then'] += then_usd * w
            m['money_into_token_usd_today'] += today_usd * w

        elif direction == 'out_of_token':
            d['money_out_of_token_bnb'] += bnb * w
            d['money_out_of_token_usd_then'] += then_usd * w
            d['money_out_of_token_usd_today'] += today_usd * w

            m['money_out_of_token_bnb'] += bnb * w
            m['money_out_of_token_usd_then'] += then_usd * w
            m['money_out_of_token_usd_today'] += today_usd * w

for sym, d in agg.items():
    d['net_token_flow_bnb'] = d['money_into_token_bnb'] - d['money_out_of_token_bnb']
    d['net_token_flow_usd_then'] = d['money_into_token_usd_then'] - d['money_out_of_token_usd_then']
    d['net_token_flow_usd_today'] = d['money_into_token_usd_today'] - d['money_out_of_token_usd_today']

# write token csv
fields = [
    'token_symbol','tx_count',
    'money_into_token_bnb','money_out_of_token_bnb','net_token_flow_bnb',
    'money_into_token_usd_then','money_out_of_token_usd_then','net_token_flow_usd_then',
    'money_into_token_usd_today','money_out_of_token_usd_today','net_token_flow_usd_today',
]
with OUT_TOKEN_CSV.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for sym in sorted(agg.keys()):
        d = agg[sym]
        w.writerow({
            'token_symbol': sym,
            'tx_count': d['tx_count'],
            'money_into_token_bnb': round(d['money_into_token_bnb'], 8),
            'money_out_of_token_bnb': round(d['money_out_of_token_bnb'], 8),
            'net_token_flow_bnb': round(d['net_token_flow_bnb'], 8),
            'money_into_token_usd_then': round(d['money_into_token_usd_then'], 2),
            'money_out_of_token_usd_then': round(d['money_out_of_token_usd_then'], 2),
            'net_token_flow_usd_then': round(d['net_token_flow_usd_then'], 2),
            'money_into_token_usd_today': round(d['money_into_token_usd_today'], 2),
            'money_out_of_token_usd_today': round(d['money_out_of_token_usd_today'], 2),
            'net_token_flow_usd_today': round(d['net_token_flow_usd_today'], 2),
        })

# write monthly token matrix
monthly_fields = [
    'month','token_symbol','tx_count',
    'money_into_token_bnb','money_out_of_token_bnb','net_token_flow_bnb',
    'money_into_token_usd_then','money_out_of_token_usd_then','net_token_flow_usd_then',
    'money_into_token_usd_today','money_out_of_token_usd_today','net_token_flow_usd_today',
]
with OUT_TOKEN_MONTHLY.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=monthly_fields)
    w.writeheader()
    for (month, sym) in sorted(monthly.keys()):
        d = monthly[(month, sym)]
        w.writerow({
            'month': month,
            'token_symbol': sym,
            'tx_count': d['tx_count'],
            'money_into_token_bnb': round(d['money_into_token_bnb'], 8),
            'money_out_of_token_bnb': round(d['money_out_of_token_bnb'], 8),
            'net_token_flow_bnb': round(d['money_into_token_bnb'] - d['money_out_of_token_bnb'], 8),
            'money_into_token_usd_then': round(d['money_into_token_usd_then'], 2),
            'money_out_of_token_usd_then': round(d['money_out_of_token_usd_then'], 2),
            'net_token_flow_usd_then': round(d['money_into_token_usd_then'] - d['money_out_of_token_usd_then'], 2),
            'money_into_token_usd_today': round(d['money_into_token_usd_today'], 2),
            'money_out_of_token_usd_today': round(d['money_out_of_token_usd_today'], 2),
            'net_token_flow_usd_today': round(d['money_into_token_usd_today'] - d['money_out_of_token_usd_today'], 2),
        })

# markdown + json
lines = []
lines.append('# Money By Token (Token-Level)')
lines.append('')
lines.append('| Token | Tx Count | Into (BNB) | Out (BNB) | Net (BNB) | Into USD (Then) | Out USD (Then) | Net USD (Then) | Into USD (Today) | Out USD (Today) | Net USD (Today) |')
lines.append('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for sym in sorted(agg.keys()):
    d = agg[sym]
    lines.append(
        f"| {sym} | {d['tx_count']} | {d['money_into_token_bnb']:.8f} | {d['money_out_of_token_bnb']:.8f} | {d['net_token_flow_bnb']:.8f} | "
        f"${d['money_into_token_usd_then']:.2f} | ${d['money_out_of_token_usd_then']:.2f} | ${d['net_token_flow_usd_then']:.2f} | "
        f"${d['money_into_token_usd_today']:.2f} | ${d['money_out_of_token_usd_today']:.2f} | ${d['net_token_flow_usd_today']:.2f} |"
    )
OUT_TOKEN_MD.write_text('\n'.join(lines), encoding='utf-8')
OUT_TOKEN_JSON.write_text(json.dumps(agg, indent=2), encoding='utf-8')

print(f'Wrote: {OUT_TOKEN_CSV}')
print(f'Wrote: {OUT_TOKEN_MD}')
print(f'Wrote: {OUT_TOKEN_JSON}')
print(f'Wrote: {OUT_TOKEN_MONTHLY}')
for sym in sorted(agg.keys()):
    d = agg[sym]
    print(sym, round(d['money_into_token_bnb'],8), round(d['money_out_of_token_bnb'],8), round(d['net_token_flow_bnb'],8), 'tx', d['tx_count'])
