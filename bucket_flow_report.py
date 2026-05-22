#!/usr/bin/env python3
import csv
import json
from collections import defaultdict
from pathlib import Path

IN_CSV = Path('bscscan_transactions_with_valuation_and_binance.csv')
TX_CACHE = Path('.cache_txs.json')
RECEIPT_CACHE = Path('.cache_tx_receipts.json')
TOKEN_META_CACHE = Path('.cache_token_meta.json')
OUT_CSV = Path('bucket_inflow_outflow_net.csv')
OUT_MD = Path('bucket_inflow_outflow_net.md')

TARGET = '0x128c33c16ee6d337154d0996220a791d89aa0442'
TRANSFER_TOPIC = '0xddf252ad'

KNOWN_TOKEN_META = {
    '0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90': ('SAFUU', 'Safuu: SAFUU Token'),
    '0x9321bc6185adc9b9cb503cc211e17cb311c3fa95': ('SGO', 'SafuuGO: SGO Token'),
}
STABLE_KEYWORDS = ('stable', 'usd', 'usdt', 'usdc', 'busd', 'dai', 'fdusd', 'tusd', 'susd', 'gusd')


def norm(s):
    return (s or '').strip().lower()


def parse_addr_topic(topic_hex):
    if not topic_hex or not topic_hex.startswith('0x') or len(topic_hex) < 42:
        return ''
    return '0x' + topic_hex[-40:].lower()


def bucket_from_tx(row, tx, receipt, token_meta_cache):
    # binance inflow bucket is explicit
    if (row.get('is_binance_inflow') or '0') == '1':
        return 'binance'

    symbols = set()
    for lg in receipt.get('logs', []) if isinstance(receipt, dict) else []:
        topics = lg.get('topics') or []
        if not topics or not (topics[0] or '').lower().startswith(TRANSFER_TOPIC):
            continue

        from_t = parse_addr_topic(topics[1]) if len(topics) > 1 else ''
        to_t = parse_addr_topic(topics[2]) if len(topics) > 2 else ''
        if TARGET not in {from_t, to_t}:
            continue

        token_addr = norm(lg.get('address'))
        if token_addr in KNOWN_TOKEN_META:
            sym, name = KNOWN_TOKEN_META[token_addr]
        else:
            meta = token_meta_cache.get(token_addr, {})
            sym = (meta.get('symbol') or '').strip().upper()
            name = (meta.get('name') or '').strip().lower()
            if not sym:
                sym = token_addr

        symbols.add((sym, name))

    # priority bucketing
    syms = {s for s, _ in symbols}
    names = ' '.join(n for _, n in symbols)

    if 'SGO' in syms:
        return 'sgo'
    if 'SAFUU' in syms or 'SFX' in syms or 'SFU' in syms:
        return 'safuu'
    if any(k in names for k in STABLE_KEYWORDS) or any(any(k in s.lower() for k in STABLE_KEYWORDS) for s in syms):
        return 'stablefund'
    return 'others'

rows = list(csv.DictReader(IN_CSV.open(newline='', encoding='utf-8')))
tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8')) if TX_CACHE.exists() else {}
receipt_cache = json.loads(RECEIPT_CACHE.read_text(encoding='utf-8')) if RECEIPT_CACHE.exists() else {}
token_meta_cache = json.loads(TOKEN_META_CACHE.read_text(encoding='utf-8')) if TOKEN_META_CACHE.exists() else {}

agg = defaultdict(lambda: {
    'inflow_bnb': 0.0,
    'outflow_bnb': 0.0,
    'net_bnb': 0.0,
    'inflow_usd_then': 0.0,
    'outflow_usd_then': 0.0,
    'net_usd_then': 0.0,
    'inflow_usd_today': 0.0,
    'outflow_usd_today': 0.0,
    'net_usd_today': 0.0,
    'tx_count': 0,
})

for r in rows:
    txh = norm(r.get('tx_hash'))
    tx = tx_cache.get(txh) or {}
    receipt = receipt_cache.get(txh) or {}

    bucket = bucket_from_tx(r, tx, receipt, token_meta_cache)

    from_addr = norm(tx.get('from'))
    to_addr = norm(tx.get('to'))

    direction = 'none'
    if to_addr == TARGET:
        direction = 'inflow'
    elif from_addr == TARGET:
        direction = 'outflow'

    bnb = float((r.get('value_bnb') or '0') or 0)
    usd_then = float((r.get('usd_at_tx_time') or '0') or 0)
    usd_today = float((r.get('usd_at_today_rate') or '0') or 0)

    d = agg[bucket]
    d['tx_count'] += 1
    if direction == 'inflow':
        d['inflow_bnb'] += bnb
        d['inflow_usd_then'] += usd_then
        d['inflow_usd_today'] += usd_today
    elif direction == 'outflow':
        d['outflow_bnb'] += bnb
        d['outflow_usd_then'] += usd_then
        d['outflow_usd_today'] += usd_today

for b, d in agg.items():
    d['net_bnb'] = d['inflow_bnb'] - d['outflow_bnb']
    d['net_usd_then'] = d['inflow_usd_then'] - d['outflow_usd_then']
    d['net_usd_today'] = d['inflow_usd_today'] - d['outflow_usd_today']

order = ['binance', 'safuu', 'sgo', 'stablefund', 'others']

with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
    fields = ['bucket','tx_count','inflow_bnb','outflow_bnb','net_bnb','inflow_usd_then','outflow_usd_then','net_usd_then','inflow_usd_today','outflow_usd_today','net_usd_today']
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for b in order:
        d = agg[b]
        w.writerow({
            'bucket': b,
            'tx_count': d['tx_count'],
            'inflow_bnb': round(d['inflow_bnb'],8),
            'outflow_bnb': round(d['outflow_bnb'],8),
            'net_bnb': round(d['net_bnb'],8),
            'inflow_usd_then': round(d['inflow_usd_then'],2),
            'outflow_usd_then': round(d['outflow_usd_then'],2),
            'net_usd_then': round(d['net_usd_then'],2),
            'inflow_usd_today': round(d['inflow_usd_today'],2),
            'outflow_usd_today': round(d['outflow_usd_today'],2),
            'net_usd_today': round(d['net_usd_today'],2),
        })

lines = ['# Bucket Inflow/Outflow/Net','',
'| Bucket | Inflow USD (Then) | Outflow USD (Then) | Net USD (Then) | Inflow USD (Today) | Outflow USD (Today) | Net USD (Today) |',
'|---|---:|---:|---:|---:|---:|---:|']
for b in order:
    d = agg[b]
    lines.append(f"| {b} | ${d['inflow_usd_then']:.2f} | ${d['outflow_usd_then']:.2f} | ${d['net_usd_then']:.2f} | ${d['inflow_usd_today']:.2f} | ${d['outflow_usd_today']:.2f} | ${d['net_usd_today']:.2f} |")
OUT_MD.write_text('\n'.join(lines), encoding='utf-8')

for b in order:
    d = agg[b]
    print(b, round(d['inflow_usd_then'],2), round(d['outflow_usd_then'],2), round(d['net_usd_then'],2), round(d['inflow_usd_today'],2), round(d['outflow_usd_today'],2), round(d['net_usd_today'],2))
print(f'Wrote: {OUT_CSV}')
print(f'Wrote: {OUT_MD}')
