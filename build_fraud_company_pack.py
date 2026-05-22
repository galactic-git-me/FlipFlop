#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

IN_TX = Path('bscscan_transactions_with_combined_binance_flags.csv')
TX_CACHE = Path('.cache_txs.json')
RECEIPT_CACHE = Path('.cache_tx_receipts.json')
TOKEN_META_CACHE = Path('.cache_token_meta.json')

OUT_REPORT = Path('fraud_company_report.md')
OUT_TIMELINE = Path('fraud_company_timeline_monthly.csv')
OUT_USD = Path('fraud_company_summary_usd.csv')
OUT_GBP = Path('fraud_company_summary_gbp.csv')
OUT_TOKEN = Path('fraud_company_token_loss_estimates.csv')
OUT_RAW = Path('fraud_company_raw_data_dump.csv')

YOU = '0x128c33c16ee6d337154d0996220a791d89aa0442'
TRANSFER_TOPIC = '0xddf252ad'

TOKENS_REQUESTED = ['SAFUU','SAFUUX','SGO','VUL','VITRUVEO','SFU','SFX','VTRX']

KNOWN = {
    '0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90': ('SAFUU', 'Safuu'),
    '0x9321bc6185adc9b9cb503cc211e17cb311c3fa95': ('SGO', 'SafuuGo'),
    '0x936e203701c6f8b619fcf8bcba8ec0d4157f02a5': ('PYR', 'Vulcan'),
    '0xd7f7827507c49235a2a6c13ce07bac75ab183ea8': ('VUL', 'Vulcan'),
    '0xb08504d245713ca9692c8fa605e76a0a11ed4955': ('VTRU', 'Vitruveo'),
}

GROUP_RULES = {
    'binance': {'binance'},
    'safuu': {'safuu','safuux','sfu','sfx'},
    'sgo': {'sgo'},
    'stablecoin': {'stablecoin','stablefund_stablecoin','stablefund'},
    'other': {'other','others','unclassified'},
}



def norm(s: str) -> str:
    return (s or '').strip().lower()


def usd_to_gbp(date: str, cache: dict) -> float:
    if date in cache:
        return cache[date]
    r = requests.get(f'https://api.frankfurter.app/{date}?from=USD&to=GBP', timeout=20)
    r.raise_for_status()
    rate = float(r.json()['rates']['GBP'])
    cache[date] = rate
    return rate


def parse_addr_topic(topic_hex: str) -> str:
    if not topic_hex or not topic_hex.startswith('0x') or len(topic_hex) < 42:
        return ''
    return '0x' + topic_hex[-40:].lower()


def symbol_for(addr: str, meta_cache: dict) -> str:
    a = norm(addr)
    if a in KNOWN:
        return KNOWN[a][0]
    m = meta_cache.get(a, {})
    sym = (m.get('symbol') or '').strip().upper()
    return sym if sym else a


def map_symbol_to_requested_bucket(sym: str) -> str:
    s = sym.upper()
    if s == 'SAFUU': return 'SAFUU'
    if s == 'SGO': return 'SGO'
    if s in ('VUL','PYR'): return 'VUL'
    if s in ('VTRU','VTRX'): return 'VTRX'
    if s in ('SFX',): return 'SFX'
    if s in ('SFU',): return 'SFU'
    return ''

rows = list(csv.DictReader(IN_TX.open(newline='', encoding='utf-8')))
tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8'))
receipt_cache = json.loads(RECEIPT_CACHE.read_text(encoding='utf-8')) if RECEIPT_CACHE.exists() else {}
meta_cache = json.loads(TOKEN_META_CACHE.read_text(encoding='utf-8')) if TOKEN_META_CACHE.exists() else {}

# raw dump
shutil.copyfile(IN_TX, OUT_RAW)

# date boundaries
dts = sorted([r['datetime_utc'] for r in rows if r.get('datetime_utc')])
start_dt = dts[0] if dts else ''
end_dt = dts[-1] if dts else ''

# timeline: money paid in (binance inflow combined) by month + token outflows by month
monthly_paid_in = defaultdict(float)
monthly_tokens = defaultdict(lambda: defaultdict(float))
fx_cache = {}

# summary buckets with today+then in USD and then GBP
bucket = defaultdict(lambda: defaultdict(float))

# token loss estimates + transfer detection
token_flow = defaultdict(lambda: {'into_usd':0.0,'out_usd':0.0,'into_gbp':0.0,'out_gbp':0.0,'into_today':0.0,'out_today':0.0,'tx_count':0})
transfer_overlap = defaultdict(float)  # usd value where token appears in conversion tx containing >=2 project tokens

for r in rows:
    txh = norm(r.get('tx_hash'))
    tx = tx_cache.get(txh) or {}
    rc = receipt_cache.get(txh) or {}

    f = norm(tx.get('from'))
    t = norm(tx.get('to'))
    usd_then = float((r.get('usd_at_tx_time') or '0') or 0)
    usd_today = float((r.get('usd_at_today_rate') or '0') or 0)
    date = (r.get('datetime_utc') or '')[:10]
    month = (r.get('datetime_utc') or '')[:7]
    gbp_then = usd_then * (usd_to_gbp(date, fx_cache) if date else 0)

    direction = 'other'
    if t == YOU:
        direction = 'in'
    elif f == YOU:
        direction = 'out'

    # bucket classification
    b = 'other'
    if (r.get('is_binance_linked_combined') or '0') == '1':
        b = 'binance'
    # token hints override for project buckets
    tl = (r.get('to') or '').lower() + ' ' + (r.get('from') or '').lower()
    if 'safuugo' in tl or ' sgo' in tl:
        b = 'sgo'
    elif 'safuu' in tl or 'safuux' in tl:
        b = 'safuu'
    elif 'stable' in tl or 'usdt' in tl or 'usdc' in tl or 'busd' in tl:
        if b != 'binance':
            b = 'stablecoin'

    if direction == 'in':
        bucket[b]['in_usd_then'] += usd_then
        bucket[b]['in_usd_today'] += usd_today
        bucket[b]['in_gbp_then'] += gbp_then
    elif direction == 'out':
        bucket[b]['out_usd_then'] += usd_then
        bucket[b]['out_usd_today'] += usd_today
        bucket[b]['out_gbp_then'] += gbp_then

    # monthly paid in from binance inflow only
    if direction == 'in' and (r.get('is_binance_linked_combined') or '0') == '1':
        monthly_paid_in[month] += gbp_then

    # token-level flows using logs touching wallet
    symbols_touch = set()
    for lg in rc.get('logs', []) if isinstance(rc, dict) else []:
        topics = lg.get('topics') or []
        if not topics or not (topics[0] or '').lower().startswith(TRANSFER_TOPIC):
            continue
        if len(topics) < 3:
            continue
        lf = parse_addr_topic(topics[1])
        lt = parse_addr_topic(topics[2])
        if YOU not in {lf, lt}:
            continue
        sym = symbol_for(norm(lg.get('address')), meta_cache)
        bucket_sym = map_symbol_to_requested_bucket(sym)
        if not bucket_sym:
            continue
        symbols_touch.add(bucket_sym)

    if symbols_touch:
        w = 1.0 / len(symbols_touch)
        for sym in symbols_touch:
            token_flow[sym]['tx_count'] += 1
            if direction == 'out':
                token_flow[sym]['into_usd'] += usd_then * w
                token_flow[sym]['into_gbp'] += gbp_then * w
                token_flow[sym]['into_today'] += usd_today * w
                monthly_tokens[month][sym] += gbp_then * w
            elif direction == 'in':
                token_flow[sym]['out_usd'] += usd_then * w
                token_flow[sym]['out_gbp'] += gbp_then * w
                token_flow[sym]['out_today'] += usd_today * w

        # conversion marker: multiple tracked symbols in one tx (likely transfer/reallocation)
        if len(symbols_touch) >= 2:
            for sym in symbols_touch:
                transfer_overlap[sym] += usd_then / len(symbols_touch)

# finalise buckets
for b in ['binance','safuu','sgo','stablecoin','other']:
    d = bucket[b]
    d['net_usd_then'] = d['in_usd_then'] - d['out_usd_then']
    d['net_usd_today'] = d['in_usd_today'] - d['out_usd_today']
    d['net_gbp_then'] = d['in_gbp_then'] - d['out_gbp_then']

# totals
total = defaultdict(float)
for b in ['binance','safuu','sgo','stablecoin','other']:
    for k,v in bucket[b].items():
        total[k]+=v

# write USD and GBP summary tables as csv
with OUT_USD.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['group','in_usd_then','out_usd_then','net_usd_then','in_usd_today','out_usd_today','net_usd_today'])
    w.writeheader()
    for g in ['binance','safuu','sgo','stablecoin','other']:
        d=bucket[g]
        w.writerow({'group':g, 'in_usd_then':round(d['in_usd_then'],2),'out_usd_then':round(d['out_usd_then'],2),'net_usd_then':round(d['net_usd_then'],2),'in_usd_today':round(d['in_usd_today'],2),'out_usd_today':round(d['out_usd_today'],2),'net_usd_today':round(d['net_usd_today'],2)})
    w.writerow({'group':'TOTAL','in_usd_then':round(total['in_usd_then'],2),'out_usd_then':round(total['out_usd_then'],2),'net_usd_then':round(total['net_usd_then'],2),'in_usd_today':round(total['in_usd_today'],2),'out_usd_today':round(total['out_usd_today'],2),'net_usd_today':round(total['net_usd_today'],2)})

with OUT_GBP.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['group','in_gbp_then','out_gbp_then','net_gbp_then'])
    w.writeheader()
    for g in ['binance','safuu','sgo','stablecoin','other']:
        d=bucket[g]
        w.writerow({'group':g,'in_gbp_then':round(d['in_gbp_then'],2),'out_gbp_then':round(d['out_gbp_then'],2),'net_gbp_then':round(d['net_gbp_then'],2)})
    w.writerow({'group':'TOTAL','in_gbp_then':round(total['in_gbp_then'],2),'out_gbp_then':round(total['out_gbp_then'],2),'net_gbp_then':round(total['net_gbp_then'],2)})

# token loss estimates
with OUT_TOKEN.open('w', newline='', encoding='utf-8') as f:
    fields=['token','money_into_usd_then','money_out_usd_then','net_usd_then','money_into_gbp_then','money_out_gbp_then','net_gbp_then','money_into_usd_today','money_out_usd_today','net_usd_today','estimated_internal_transfer_usd','estimated_new_money_into_usd']
    w=csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for tkn in TOKENS_REQUESTED:
        d=token_flow[tkn]
        net_usd = d['into_usd']-d['out_usd']
        net_gbp = d['into_gbp']-d['out_gbp']
        net_today = d['into_today']-d['out_today']
        transfer_usd = transfer_overlap[tkn]
        new_money_into = max(0.0, d['into_usd']-transfer_usd)
        w.writerow({
            'token':tkn,
            'money_into_usd_then':round(d['into_usd'],2),
            'money_out_usd_then':round(d['out_usd'],2),
            'net_usd_then':round(net_usd,2),
            'money_into_gbp_then':round(d['into_gbp'],2),
            'money_out_gbp_then':round(d['out_gbp'],2),
            'net_gbp_then':round(net_gbp,2),
            'money_into_usd_today':round(d['into_today'],2),
            'money_out_usd_today':round(d['out_today'],2),
            'net_usd_today':round(net_today,2),
            'estimated_internal_transfer_usd':round(transfer_usd,2),
            'estimated_new_money_into_usd':round(new_money_into,2),
        })

# timeline csv
with OUT_TIMELINE.open('w', newline='', encoding='utf-8') as f:
    headers=['month','paid_in_gbp_from_binance'] + TOKENS_REQUESTED
    w=csv.DictWriter(f, fieldnames=headers)
    w.writeheader()
    for m in sorted(set(list(monthly_paid_in.keys())+list(monthly_tokens.keys()))):
        row={'month':m,'paid_in_gbp_from_binance':round(monthly_paid_in[m],2)}
        for tkn in TOKENS_REQUESTED:
            row[tkn]=round(monthly_tokens[m].get(tkn,0.0),2)
        w.writerow(row)

# markdown report
usd_rows=[]
with OUT_USD.open(newline='',encoding='utf-8') as f:
    usd_rows=list(csv.DictReader(f))
gbp_rows=[]
with OUT_GBP.open(newline='',encoding='utf-8') as f:
    gbp_rows=list(csv.DictReader(f))
token_rows=[]
with OUT_TOKEN.open(newline='',encoding='utf-8') as f:
    token_rows=list(csv.DictReader(f))

report=[]
report.append('# Fraud Analysis Report')
report.append('')
report.append('## Background')
report.append('- This wallet analysis indicates a pattern of repeated onboarding through exchange-linked wallets followed by high-frequency project interactions.')
report.append('- Prior to Safuu, the same actor appears to have operated fraudulently under a different name. Detailed pre-Safuu project naming has been intentionally omitted per request.')
report.append(f'- Analysis window: `{start_dt}` to `{end_dt}` (UTC).')
report.append('')
report.append('## Timeline (Visual)')
report.append('- Monthly paid-in from exchange-linked inflows is in `fraud_company_timeline_monthly.csv`.')
report.append('- Exact boundary dates are listed above.')
report.append('')
report.append('```mermaid')
report.append('timeline')
report.append('    title Scam Evolution (High-Level)')
report.append('    2022 : Wallet funded and activity begins')
report.append('    2023 : Safuu activity intensifies')
report.append('    2023 : Migration/conversion activity into SGO')
report.append('    2024 : Reduced direct Safuu/SGO labeled activity')
report.append('    2025 : Residual on-chain activity')
report.append('```')
report.append('')
report.append('## Evolution Narrative')
report.append('- The data supports a migration pattern where funds attributed to Safuu-related flows are later seen in SGO-related flows.')
report.append('- These are not always fresh cash injections; many rows represent reallocation/conversion events (e.g., Safuu to SGO) rather than new external money.')
report.append('- Evidence for explicit Vulcan/Vitruveo token-touch in this wallet is limited in the available transactions; where present it is much smaller than Safuu/SGO flow.')
report.append('')
report.append('## Lite Nodes')
report.append('- A distinct on-chain label for "Lite Nodes" was not found in the scraped rows.')
report.append('- Your stated estimate (about £1,500 total for 5 Lite Nodes) should be treated as user-supplied evidence pending supporting receipts/invoices or contract-level decode evidence.')
report.append('')
report.append('## Documentary Reference')
report.append('- Coffeezilla video (Safuu investigation): [Scammer BEGGED Me Not to Investigate](https://www.youtube.com/watch?v=38RBRPwODUk)')
report.append('- Transcript summary: Not provided in this workspace. Add the transcript text and this section can be replaced with a structured summary with key claims and timestamps.')
report.append('')
report.append('## Summary Table (USD)')
report.append('| Group | Money In (USD then) | Money Out (USD then) | Net (USD then) | Money In (USD today) | Money Out (USD today) | Net (USD today) |')
report.append('|---|---:|---:|---:|---:|---:|---:|')
for r in usd_rows:
    report.append(f"| {r['group']} | ${float(r['in_usd_then']):,.2f} | ${float(r['out_usd_then']):,.2f} | ${float(r['net_usd_then']):,.2f} | ${float(r['in_usd_today']):,.2f} | ${float(r['out_usd_today']):,.2f} | ${float(r['net_usd_today']):,.2f} |")
report.append('')
report.append('## Summary Table (GBP)')
report.append('| Group | Money In (GBP then) | Money Out (GBP then) | Net (GBP then) |')
report.append('|---|---:|---:|---:|')
for r in gbp_rows:
    report.append(f"| {r['group']} | £{float(r['in_gbp_then']):,.2f} | £{float(r['out_gbp_then']):,.2f} | £{float(r['net_gbp_then']):,.2f} |")
report.append('')
report.append('## Token-Level Scam Exposure (Requested Token List)')
report.append('| Token | Into USD (then) | Out USD (then) | Net USD (then) | Internal Transfer USD (est) | New Money Into USD (est) |')
report.append('|---|---:|---:|---:|---:|---:|')
for r in token_rows:
    report.append(f"| {r['token']} | ${float(r['money_into_usd_then']):,.2f} | ${float(r['money_out_usd_then']):,.2f} | ${float(r['net_usd_then']):,.2f} | ${float(r['estimated_internal_transfer_usd']):,.2f} | ${float(r['estimated_new_money_into_usd']):,.2f} |")
report.append('')
report.append('## Interpretation Guidance')
report.append('- `Money Into Token` can include internal conversions. It is not always new external capital.')
report.append('- `Estimated Internal Transfer` flags probable reallocation chains (e.g., Safuu->SGO).')
report.append('- `Estimated New Money Into` attempts to isolate fresh capital exposure per token by subtracting overlap.')
report.append('')
report.append('## Raw Data Dump')
report.append(f'- Full CSV with detailed fields: `{OUT_RAW.name}`')

OUT_REPORT.write_text('\n'.join(report), encoding='utf-8')

print('Wrote:', OUT_REPORT)
print('Wrote:', OUT_TIMELINE)
print('Wrote:', OUT_USD)
print('Wrote:', OUT_GBP)
print('Wrote:', OUT_TOKEN)
print('Wrote:', OUT_RAW)
