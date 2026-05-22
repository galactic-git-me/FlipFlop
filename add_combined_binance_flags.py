#!/usr/bin/env python3
import csv, json
from pathlib import Path

IN_CSV = Path('bscscan_transactions_with_valuation_and_binance.csv')
TX_CACHE = Path('.cache_txs.json')
OUT_CSV = Path('bscscan_transactions_with_combined_binance_flags.csv')
OUT_SUMMARY = Path('combined_binance_flags_summary.json')

YOU = '0x128c33c16ee6d337154d0996220a791d89aa0442'

# Binance-related addresses you provided (BSC)
USER_BINANCE_ADDRS = {
    '0xb6934215b856b03430fc8dc058bd1c668b6a3182',
    '0x88e54b8b638d84fed0bce9480ade1702644fa9a9',
    '0xae070a43f4142cac9a9bab105e301f500a27ae6c',
}

rows = list(csv.DictReader(IN_CSV.open(newline='', encoding='utf-8')))
tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8')) if TX_CACHE.exists() else {}

counts = {
    'total_rows': len(rows),
    'binance_linked_rows': 0,
    'by_address_rule': 0,
    'by_label_rule': 0,
    'inflows_to_you': 0,
    'outflows_from_you': 0,
}

sum_in_usd_then = sum_out_usd_then = 0.0
sum_in_usd_today = sum_out_usd_today = 0.0

for r in rows:
    txh = (r.get('tx_hash') or '').lower()
    tx = tx_cache.get(txh) or {}

    f = (tx.get('from') or '').lower()
    t = (tx.get('to') or '').lower()

    from_label = (r.get('from') or '').lower()
    to_label = (r.get('to') or '').lower()
    from_url = (r.get('from_url') or '').lower()
    to_url = (r.get('to_url') or '').lower()

    by_address = (f in USER_BINANCE_ADDRS) or (t in USER_BINANCE_ADDRS)
    by_label = any('binance' in s for s in [from_label, to_label, from_url, to_url])

    is_binance_linked = by_address or by_label

    reasons = []
    if by_address:
        reasons.append('user_binance_address_match')
    if by_label:
        reasons.append('friendly_tag_or_url_contains_binance')

    direction = 'other'
    if t == YOU:
        direction = 'inflow_to_you'
    elif f == YOU:
        direction = 'outflow_from_you'

    usd_then = float((r.get('usd_at_tx_time') or '0').strip() or 0)
    usd_today = float((r.get('usd_at_today_rate') or '0').strip() or 0)

    if is_binance_linked:
        counts['binance_linked_rows'] += 1
        if by_address:
            counts['by_address_rule'] += 1
        if by_label:
            counts['by_label_rule'] += 1

        if direction == 'inflow_to_you':
            counts['inflows_to_you'] += 1
            sum_in_usd_then += usd_then
            sum_in_usd_today += usd_today
        elif direction == 'outflow_from_you':
            counts['outflows_from_you'] += 1
            sum_out_usd_then += usd_then
            sum_out_usd_today += usd_today

    r['is_binance_linked_combined'] = '1' if is_binance_linked else '0'
    r['binance_link_reason_combined'] = '|'.join(reasons)
    r['binance_link_direction_vs_you'] = direction

with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
    w.writeheader()
    w.writerows(rows)

summary = {
    **counts,
    'inflow_usd_then': round(sum_in_usd_then, 2),
    'outflow_usd_then': round(sum_out_usd_then, 2),
    'net_usd_then': round(sum_in_usd_then - sum_out_usd_then, 2),
    'inflow_usd_today': round(sum_in_usd_today, 2),
    'outflow_usd_today': round(sum_out_usd_today, 2),
    'net_usd_today': round(sum_in_usd_today - sum_out_usd_today, 2),
    'user_binance_addresses_used': sorted(USER_BINANCE_ADDRS),
}
OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding='utf-8')

print(json.dumps(summary, indent=2))
print(f'Wrote: {OUT_CSV}')
print(f'Wrote: {OUT_SUMMARY}')
