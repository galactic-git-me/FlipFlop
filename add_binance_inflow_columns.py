#!/usr/bin/env python3
import csv
import json
from pathlib import Path

IN_CSV = Path('bscscan_transactions_with_valuation.csv')
OUT_CSV = Path('bscscan_transactions_with_valuation_and_binance.csv')
TX_CACHE = Path('.cache_txs.json')

TARGET = '0x128c33c16ee6d337154d0996220a791d89aa0442'

rows = list(csv.DictReader(IN_CSV.open(newline='', encoding='utf-8')))
tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8')) if TX_CACHE.exists() else {}

count = 0
sum_bnb = 0.0
sum_then = 0.0
sum_today = 0.0

for r in rows:
    txh = (r.get('tx_hash') or '').lower()
    tx = tx_cache.get(txh) or {}

    to_addr = (tx.get('to') or '').lower()
    from_label = (r.get('from') or '').lower()

    is_binance_inflow = (to_addr == TARGET) and ('binance' in from_label)

    bnb = float((r.get('value_bnb') or '0').strip() or 0)
    usd_then = float((r.get('usd_at_tx_time') or '0').strip() or 0)
    usd_today = float((r.get('usd_at_today_rate') or '0').strip() or 0)

    r['is_binance_inflow'] = '1' if is_binance_inflow else '0'
    r['binance_inflow_bnb'] = f'{bnb:.12f}'.rstrip('0').rstrip('.') if is_binance_inflow else '0'
    r['binance_inflow_usd_then'] = f'{usd_then:.2f}' if is_binance_inflow else '0.00'
    r['binance_inflow_usd_today'] = f'{usd_today:.2f}' if is_binance_inflow else '0.00'

    if is_binance_inflow:
        count += 1
        sum_bnb += bnb
        sum_then += usd_then
        sum_today += usd_today

with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
    w.writeheader()
    w.writerows(rows)

print(f'Wrote: {OUT_CSV}')
print(f'binance_inflow_tx_count={count}')
print(f'binance_inflow_bnb={sum_bnb:.8f}')
print(f'binance_inflow_usd_then={sum_then:.2f}')
print(f'binance_inflow_usd_today={sum_today:.2f}')
