#!/usr/bin/env python3
import csv
import json
from collections import defaultdict
from pathlib import Path

IN_CSV = Path('bscscan_transactions_with_valuation.csv')
TX_CACHE = Path('.cache_txs.json')
OUT_CSV = Path('money_by_project_with_valuation.csv')
OUT_MD = Path('money_by_project_with_valuation.md')
OUT_JSON = Path('money_by_project_with_valuation.json')

TARGET = '0x128c33c16ee6d337154d0996220a791d89aa0442'

rows = list(csv.DictReader(IN_CSV.open(newline='', encoding='utf-8')))
tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8')) if TX_CACHE.exists() else {}

agg = defaultdict(lambda: {
    'tx_count': 0,
    'money_into_project_bnb': 0.0,
    'money_out_of_project_bnb': 0.0,
    'net_project_flow_bnb': 0.0,
    'money_into_project_usd_then': 0.0,
    'money_out_of_project_usd_then': 0.0,
    'net_project_flow_usd_then': 0.0,
    'money_into_project_usd_today': 0.0,
    'money_out_of_project_usd_today': 0.0,
    'net_project_flow_usd_today': 0.0,
})

for r in rows:
    txh = (r.get('tx_hash') or '').lower()
    tx = tx_cache.get(txh) or {}
    from_addr = (tx.get('from') or '').lower()
    to_addr = (tx.get('to') or '').lower()

    # wallet perspective direction
    # out: wallet sent value (interpreted as money into project if tx is project-linked)
    # in: wallet received value (money out of project)
    direction = 'other'
    if from_addr == TARGET:
        direction = 'out'
    elif to_addr == TARGET:
        direction = 'in'

    bnb = float((r.get('value_bnb') or '0').strip() or 0)
    usd_then = float((r.get('usd_at_tx_time') or '0').strip() or 0)
    usd_today = float((r.get('usd_at_today_rate') or '0').strip() or 0)

    projects_raw = (r.get('project_hit') or '').strip()
    projects = [p for p in projects_raw.split('|') if p] or ['unclassified']

    # split equally if multi-tag
    w = 1.0 / len(projects)

    for p in projects:
        d = agg[p]
        d['tx_count'] += 1

        if direction == 'out':
            # wallet sent -> into project exposure
            d['money_into_project_bnb'] += bnb * w
            d['money_into_project_usd_then'] += usd_then * w
            d['money_into_project_usd_today'] += usd_today * w
        elif direction == 'in':
            # wallet received -> out of project exposure
            d['money_out_of_project_bnb'] += bnb * w
            d['money_out_of_project_usd_then'] += usd_then * w
            d['money_out_of_project_usd_today'] += usd_today * w

for p, d in agg.items():
    d['net_project_flow_bnb'] = d['money_into_project_bnb'] - d['money_out_of_project_bnb']
    d['net_project_flow_usd_then'] = d['money_into_project_usd_then'] - d['money_out_of_project_usd_then']
    d['net_project_flow_usd_today'] = d['money_into_project_usd_today'] - d['money_out_of_project_usd_today']

fields = [
    'project','tx_count',
    'money_into_project_bnb','money_out_of_project_bnb','net_project_flow_bnb',
    'money_into_project_usd_then','money_out_of_project_usd_then','net_project_flow_usd_then',
    'money_into_project_usd_today','money_out_of_project_usd_today','net_project_flow_usd_today',
]

with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for p in sorted(agg):
        d = agg[p]
        w.writerow({
            'project': p,
            'tx_count': d['tx_count'],
            'money_into_project_bnb': round(d['money_into_project_bnb'], 8),
            'money_out_of_project_bnb': round(d['money_out_of_project_bnb'], 8),
            'net_project_flow_bnb': round(d['net_project_flow_bnb'], 8),
            'money_into_project_usd_then': round(d['money_into_project_usd_then'], 2),
            'money_out_of_project_usd_then': round(d['money_out_of_project_usd_then'], 2),
            'net_project_flow_usd_then': round(d['net_project_flow_usd_then'], 2),
            'money_into_project_usd_today': round(d['money_into_project_usd_today'], 2),
            'money_out_of_project_usd_today': round(d['money_out_of_project_usd_today'], 2),
            'net_project_flow_usd_today': round(d['net_project_flow_usd_today'], 2),
        })

OUT_JSON.write_text(json.dumps(agg, indent=2), encoding='utf-8')

lines = []
lines.append('# Money By Project (With Valuation)')
lines.append('')
lines.append('| Project | Tx Count | Into Project (BNB) | Out Of Project (BNB) | Net (BNB) | Into USD (Then) | Out USD (Then) | Net USD (Then) | Into USD (Today) | Out USD (Today) | Net USD (Today) |')
lines.append('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for p in sorted(agg):
    d = agg[p]
    lines.append(
        f"| {p} | {d['tx_count']} | {d['money_into_project_bnb']:.8f} | {d['money_out_of_project_bnb']:.8f} | {d['net_project_flow_bnb']:.8f} | "
        f"${d['money_into_project_usd_then']:.2f} | ${d['money_out_of_project_usd_then']:.2f} | ${d['net_project_flow_usd_then']:.2f} | "
        f"${d['money_into_project_usd_today']:.2f} | ${d['money_out_of_project_usd_today']:.2f} | ${d['net_project_flow_usd_today']:.2f} |"
    )

OUT_MD.write_text('\n'.join(lines), encoding='utf-8')

print(f'Wrote: {OUT_CSV}')
print(f'Wrote: {OUT_MD}')
print(f'Wrote: {OUT_JSON}')
for p in sorted(agg):
    d=agg[p]
    print(p, round(d['money_into_project_bnb'],8), round(d['money_out_of_project_bnb'],8), round(d['net_project_flow_bnb'],8))
