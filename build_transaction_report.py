#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import requests

TARGET = '0x128c33c16ee6d337154d0996220a791d89aa0442'
TARGET_PREFIX = TARGET[:10]  # 0x + first 8 hex
TARGET_SUFFIX = TARGET[-8:]
IN_CSV = Path('bscscan_transactions_2021_to_today.project_attributed.aggressive.csv')
OUT_MD = Path('transaction_report.md')
OUT_MONTHLY = Path('transaction_timeline_monthly.csv')
OUT_SUMMARY_JSON = Path('transaction_report_summary.json')
TX_CACHE = Path('.cache_txs.json')
RPC_URL = 'https://bsc-dataseed.binance.org'

# from web finance tool fetched today (UTC 2026-05-21)
CURRENT_BNB_USD = 651.22

VAL_RE = re.compile(r'([-+]?[0-9]*\.?[0-9]+)\s*BNB')
USD_RE = re.compile(r'\$\s*([-+]?[0-9,]*\.?[0-9]+)')


def to_float(s: str) -> float:
    try:
        return float(s.replace(',', '').strip())
    except Exception:
        return 0.0


def parse_value_bnb_usd(value_field: str) -> tuple[float, float]:
    s = (value_field or '').strip()
    bnb = 0.0
    usd = 0.0
    m = VAL_RE.search(s)
    if m:
        bnb = to_float(m.group(1))
    u = USD_RE.search(s)
    if u:
        usd = to_float(u.group(1))
    return bnb, usd


def looks_like_target_display(s: str) -> bool:
    t = (s or '').lower().replace(' ', '')
    return TARGET_PREFIX in t and TARGET_SUFFIX in t

rows = []
with IN_CSV.open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

tx_cache = {}
if TX_CACHE.exists():
    tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8'))


def rpc_tx(tx_hash: str):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionByHash", "params": [tx_hash]}
    try:
        r = requests.post(RPC_URL, json=payload, timeout=30)
        r.raise_for_status()
        j = r.json()
        return j.get('result')
    except Exception:
        return None

if not rows:
    raise SystemExit('No rows found')

# Sort chronologically
rows.sort(key=lambda r: r.get('datetime_utc', ''))
first_dt = rows[0]['datetime_utc']
last_dt = rows[-1]['datetime_utc']

monthly = defaultdict(lambda: {
    'tx_count': 0,
    'project_match_count': 0,
    'in_bnb': 0.0,
    'out_bnb': 0.0,
    'in_usd_then': 0.0,
    'out_usd_then': 0.0,
})

sum_in_bnb = sum_out_bnb = 0.0
sum_in_usd_then = sum_out_usd_then = 0.0
proj_rows = 0

for r in rows:
    dt = r.get('datetime_utc', '')
    month = dt[:7] if len(dt) >= 7 else 'unknown'

    from_addr = (r.get('from_address') or '').lower()
    to_addr = (r.get('to_address') or '').lower()

    txh = (r.get('tx_hash') or '').lower()
    tx = tx_cache.get(txh)
    if tx is None and txh:
        tx = rpc_tx(txh)
        if tx:
            tx_cache[txh] = tx

    if tx:
        from_addr = ((tx.get('from') or from_addr) or '').lower()
        to_addr = ((tx.get('to') or to_addr) or '').lower()

    bnb, usd_then = parse_value_bnb_usd(r.get('value', ''))

    direction = 'other'
    if from_addr == TARGET or looks_like_target_display(r.get('from', '')):
        direction = 'out'
    elif to_addr == TARGET or looks_like_target_display(r.get('to', '')):
        direction = 'in'

    monthly[month]['tx_count'] += 1
    if (r.get('project_hit') or '').strip():
        monthly[month]['project_match_count'] += 1
        proj_rows += 1

    if direction == 'in':
        monthly[month]['in_bnb'] += bnb
        monthly[month]['in_usd_then'] += usd_then
        sum_in_bnb += bnb
        sum_in_usd_then += usd_then
    elif direction == 'out':
        monthly[month]['out_bnb'] += bnb
        monthly[month]['out_usd_then'] += usd_then
        sum_out_bnb += bnb
        sum_out_usd_then += usd_then

sum_in_usd_today = sum_in_bnb * CURRENT_BNB_USD
sum_out_usd_today = sum_out_bnb * CURRENT_BNB_USD
net_bnb = sum_in_bnb - sum_out_bnb
net_usd_then = sum_in_usd_then - sum_out_usd_then
net_usd_today = sum_in_usd_today - sum_out_usd_today

# Write monthly CSV
with OUT_MONTHLY.open('w', newline='', encoding='utf-8') as f:
    fieldnames = [
        'month', 'tx_count', 'project_match_count',
        'in_bnb', 'out_bnb', 'net_bnb',
        'in_usd_then', 'out_usd_then', 'net_usd_then',
        'in_usd_today_est', 'out_usd_today_est', 'net_usd_today_est'
    ]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for m in sorted(monthly.keys()):
        d = monthly[m]
        in_today = d['in_bnb'] * CURRENT_BNB_USD
        out_today = d['out_bnb'] * CURRENT_BNB_USD
        w.writerow({
            'month': m,
            'tx_count': d['tx_count'],
            'project_match_count': d['project_match_count'],
            'in_bnb': round(d['in_bnb'], 8),
            'out_bnb': round(d['out_bnb'], 8),
            'net_bnb': round(d['in_bnb'] - d['out_bnb'], 8),
            'in_usd_then': round(d['in_usd_then'], 2),
            'out_usd_then': round(d['out_usd_then'], 2),
            'net_usd_then': round(d['in_usd_then'] - d['out_usd_then'], 2),
            'in_usd_today_est': round(in_today, 2),
            'out_usd_today_est': round(out_today, 2),
            'net_usd_today_est': round(in_today - out_today, 2),
        })

# Build markdown
lines = []
lines.append('# Transaction Analysis Report')
lines.append('')
lines.append(f'- Address: `{TARGET}`')
lines.append(f'- Transactions analyzed: `{len(rows)}`')
lines.append(f'- Project-attributed rows (aggressive): `{proj_rows}`')
lines.append(f'- First transaction (exact UTC): `{first_dt}`')
lines.append(f'- Last transaction (exact UTC): `{last_dt}`')
lines.append(f'- Current BNB price used for "today" estimate: `${CURRENT_BNB_USD:,.2f}` (as of 2026-05-21 UTC)')
lines.append('')
lines.append('## Money In/Out Summary')
lines.append('')
lines.append('| Metric | BNB | USD at tx time | USD at today price (est.) |')
lines.append('|---|---:|---:|---:|')
lines.append(f'| Money In | {sum_in_bnb:,.8f} | ${sum_in_usd_then:,.2f} | ${sum_in_usd_today:,.2f} |')
lines.append(f'| Money Out | {sum_out_bnb:,.8f} | ${sum_out_usd_then:,.2f} | ${sum_out_usd_today:,.2f} |')
lines.append(f'| Net (In-Out) | {net_bnb:,.8f} | ${net_usd_then:,.2f} | ${net_usd_today:,.2f} |')
lines.append('')
lines.append('## Monthly Timeline (month-level)')
lines.append('')
lines.append('| Month | Tx Count | Project Matches | In (BNB) | Out (BNB) | Net (BNB) |')
lines.append('|---|---:|---:|---:|---:|---:|')
for m in sorted(monthly.keys()):
    d = monthly[m]
    lines.append(
        f"| {m} | {d['tx_count']} | {d['project_match_count']} | "
        f"{d['in_bnb']:.8f} | {d['out_bnb']:.8f} | {(d['in_bnb']-d['out_bnb']):.8f} |"
    )

lines.append('')
lines.append('## Notes')
lines.append('')
lines.append('- This report uses BscScan tx list `Amount` values (BNB-denominated).')
lines.append('- Token-side USD values for non-BNB assets are not present in this dataset; calculations here are BNB flow based.')
lines.append('- `USD at tx time` is parsed from BscScan row value when present.')

OUT_MD.write_text('\n'.join(lines), encoding='utf-8')

summary = {
    'address': TARGET,
    'transactions_analyzed': len(rows),
    'project_attributed_rows': proj_rows,
    'first_transaction_utc': first_dt,
    'last_transaction_utc': last_dt,
    'current_bnb_usd': CURRENT_BNB_USD,
    'money_in_bnb': round(sum_in_bnb, 8),
    'money_out_bnb': round(sum_out_bnb, 8),
    'net_bnb': round(net_bnb, 8),
    'money_in_usd_then': round(sum_in_usd_then, 2),
    'money_out_usd_then': round(sum_out_usd_then, 2),
    'net_usd_then': round(net_usd_then, 2),
    'money_in_usd_today_est': round(sum_in_usd_today, 2),
    'money_out_usd_today_est': round(sum_out_usd_today, 2),
    'net_usd_today_est': round(net_usd_today, 2),
}
OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding='utf-8')
TX_CACHE.write_text(json.dumps(tx_cache, indent=2), encoding='utf-8')

print(json.dumps(summary, indent=2))
print(f'Wrote: {OUT_MD}')
print(f'Wrote: {OUT_MONTHLY}')
print(f'Wrote: {OUT_SUMMARY_JSON}')
