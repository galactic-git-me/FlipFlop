#!/usr/bin/env python3
import csv
import json
import re
from pathlib import Path

IN_CSV = Path('bscscan_transactions_2021_to_today.project_attributed.aggressive.csv')
OUT_CSV = Path('bscscan_transactions_with_valuation.csv')
OUT_SUMMARY = Path('bscscan_transactions_with_valuation.summary.json')

# Verified today: 2026-05-21
BNB_USD_TODAY = 658.81
BNB_PRICE_DATE = '2026-05-21'

VAL_RE = re.compile(r'([-+]?[0-9]*\.?[0-9]+)\s*BNB')
USD_RE = re.compile(r'\$\s*([-+]?[0-9,]*\.?[0-9]+)')


def to_float(s: str) -> float:
    try:
        return float(s.replace(',', '').strip())
    except Exception:
        return 0.0


def parse_value_field(v: str):
    s = (v or '').strip()
    bnb = 0.0
    usd_then = 0.0

    m = VAL_RE.search(s)
    if m:
        bnb = to_float(m.group(1))

    u = USD_RE.search(s)
    if u:
        usd_then = to_float(u.group(1))

    return bnb, usd_then

rows = []
with IN_CSV.open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

for r in rows:
    bnb, usd_then = parse_value_field(r.get('value', ''))
    usd_today = bnb * BNB_USD_TODAY
    delta = usd_today - usd_then

    r['value_bnb'] = f"{bnb:.12f}".rstrip('0').rstrip('.') if bnb else '0'
    r['usd_at_tx_time'] = f"{usd_then:.2f}"
    r['usd_at_today_rate'] = f"{usd_today:.2f}"
    r['valuation_delta_today_minus_then'] = f"{delta:.2f}"
    r['bnb_usd_today_rate_used'] = f"{BNB_USD_TODAY:.2f}"
    r['bnb_usd_today_rate_date'] = BNB_PRICE_DATE

with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
    fieldnames = list(rows[0].keys()) if rows else []
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

summary = {
    'rows': len(rows),
    'bnb_usd_today_rate_used': BNB_USD_TODAY,
    'bnb_usd_today_rate_date': BNB_PRICE_DATE,
    'sum_usd_at_tx_time': round(sum(float(r['usd_at_tx_time']) for r in rows), 2),
    'sum_usd_at_today_rate': round(sum(float(r['usd_at_today_rate']) for r in rows), 2),
}
OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding='utf-8')

print(json.dumps(summary, indent=2))
print(f'Wrote: {OUT_CSV}')
print(f'Wrote: {OUT_SUMMARY}')
