#!/usr/bin/env python3
import csv
import json
from collections import defaultdict
from pathlib import Path

IN_CSV = Path('bscscan_transactions_2021_to_today.project_attributed.aggressive.csv')
TX_CACHE = Path('.cache_txs.json')
OUT_CSV = Path('money_by_project.csv')
OUT_MD = Path('money_by_project.md')
OUT_JSON = Path('money_by_project.json')

TARGET = '0x128c33c16ee6d337154d0996220a791d89aa0442'
CURRENT_BNB_USD = 651.22


def parse_value(v: str):
    # e.g. "0.0015 BNB $0.97"
    v = (v or '').strip()
    bnb = 0.0
    usd = 0.0
    parts = v.split('BNB')
    if parts and parts[0].strip():
        try:
            bnb = float(parts[0].strip().replace(',', ''))
        except Exception:
            bnb = 0.0
    if '$' in v:
        try:
            usd = float(v.split('$')[-1].strip().replace(',', ''))
        except Exception:
            usd = 0.0
    return bnb, usd

rows = list(csv.DictReader(IN_CSV.open(newline='', encoding='utf-8')))
tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8')) if TX_CACHE.exists() else {}

agg = defaultdict(lambda: {
    'tx_count': 0,
    'money_in_bnb': 0.0,
    'money_out_bnb': 0.0,
    'net_bnb': 0.0,
    'money_in_usd_then': 0.0,
    'money_out_usd_then': 0.0,
    'net_usd_then': 0.0,
    'money_in_usd_today_est': 0.0,
    'money_out_usd_today_est': 0.0,
    'net_usd_today_est': 0.0,
})

for r in rows:
    txh = (r.get('tx_hash') or '').lower()
    tx = tx_cache.get(txh) or {}
    from_addr = (tx.get('from') or '').lower()
    to_addr = (tx.get('to') or '').lower()

    direction = 'other'
    if from_addr == TARGET:
        direction = 'out'
    elif to_addr == TARGET:
        direction = 'in'

    bnb, usd_then = parse_value(r.get('value', ''))
    projects_raw = (r.get('project_hit') or '').strip()
    projects = [p for p in projects_raw.split('|') if p] or ['unclassified']

    # split equally if multi-project hit
    w = 1.0 / len(projects)

    for p in projects:
        d = agg[p]
        d['tx_count'] += 1
        if direction == 'in':
            d['money_in_bnb'] += bnb * w
            d['money_in_usd_then'] += usd_then * w
        elif direction == 'out':
            d['money_out_bnb'] += bnb * w
            d['money_out_usd_then'] += usd_then * w

for p, d in agg.items():
    d['net_bnb'] = d['money_in_bnb'] - d['money_out_bnb']
    d['money_in_usd_today_est'] = d['money_in_bnb'] * CURRENT_BNB_USD
    d['money_out_usd_today_est'] = d['money_out_bnb'] * CURRENT_BNB_USD
    d['net_usd_today_est'] = d['money_in_usd_today_est'] - d['money_out_usd_today_est']
    d['net_usd_then'] = d['money_in_usd_then'] - d['money_out_usd_then']

# write csv
fields = [
    'project','tx_count','money_in_bnb','money_out_bnb','net_bnb',
    'money_in_usd_then','money_out_usd_then','net_usd_then',
    'money_in_usd_today_est','money_out_usd_today_est','net_usd_today_est'
]
with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for p in sorted(agg):
        d = agg[p]
        w.writerow({
            'project': p,
            'tx_count': d['tx_count'],
            'money_in_bnb': round(d['money_in_bnb'], 8),
            'money_out_bnb': round(d['money_out_bnb'], 8),
            'net_bnb': round(d['net_bnb'], 8),
            'money_in_usd_then': round(d['money_in_usd_then'], 2),
            'money_out_usd_then': round(d['money_out_usd_then'], 2),
            'net_usd_then': round(d['net_usd_then'], 2),
            'money_in_usd_today_est': round(d['money_in_usd_today_est'], 2),
            'money_out_usd_today_est': round(d['money_out_usd_today_est'], 2),
            'net_usd_today_est': round(d['net_usd_today_est'], 2),
        })

OUT_JSON.write_text(json.dumps(agg, indent=2), encoding='utf-8')

lines = ['# Money Split By Project','',f'- Current BNB used: ${CURRENT_BNB_USD:,.2f}','',
         '| Project | Tx Count | In (BNB) | Out (BNB) | Net (BNB) | In USD (then) | Out USD (then) | Net USD (then) |',
         '|---|---:|---:|---:|---:|---:|---:|---:|']
for p in sorted(agg):
    d = agg[p]
    lines.append(f"| {p} | {d['tx_count']} | {d['money_in_bnb']:.8f} | {d['money_out_bnb']:.8f} | {d['net_bnb']:.8f} | ${d['money_in_usd_then']:.2f} | ${d['money_out_usd_then']:.2f} | ${d['net_usd_then']:.2f} |")
OUT_MD.write_text('\n'.join(lines), encoding='utf-8')

print(f'Wrote: {OUT_CSV}')
print(f'Wrote: {OUT_MD}')
print(f'Wrote: {OUT_JSON}')
for p in sorted(agg):
    d=agg[p]
    print(p, d['money_in_bnb'], d['money_out_bnb'], d['net_bnb'])
