#!/usr/bin/env python3
import csv, json
from pathlib import Path

IN_CSV=Path('bscscan_transactions_with_valuation_and_binance.csv')
TX_CACHE=Path('.cache_txs.json')
OUT_JSON=Path('binance_explicit_wallet_reconciliation.json')
OUT_CSV=Path('binance_explicit_wallet_transactions.csv')

YOU='0x128c33c16ee6d337154d0996220a791d89aa0442'
BIN='0xb6934215b856b03430fc8dc058bd1c668b6a3182'

rows=list(csv.DictReader(open(IN_CSV,newline='',encoding='utf-8')))
tx_cache=json.loads(TX_CACHE.read_text()) if TX_CACHE.exists() else {}

hits=[]
in_usd=in_today=in_bnb=0.0
out_usd=out_today=out_bnb=0.0

for r in rows:
    tx=tx_cache.get((r.get('tx_hash') or '').lower()) or {}
    f=(tx.get('from') or '').lower(); t=(tx.get('to') or '').lower()
    if {f,t}!={YOU,BIN} and not (f==YOU and t==BIN) and not (f==BIN and t==YOU):
        continue

    bnb=float(r.get('value_bnb') or 0)
    usd=float(r.get('usd_at_tx_time') or 0)
    today=float(r.get('usd_at_today_rate') or 0)
    direction='binance_to_you' if (f==BIN and t==YOU) else ('you_to_binance' if (f==YOU and t==BIN) else 'other')

    if direction=='binance_to_you':
        in_bnb+=bnb; in_usd+=usd; in_today+=today
    elif direction=='you_to_binance':
        out_bnb+=bnb; out_usd+=usd; out_today+=today

    hits.append({
        'tx_hash':r.get('tx_hash',''),'datetime_utc':r.get('datetime_utc',''),'direction':direction,
        'value_bnb':r.get('value_bnb','0'),'usd_at_tx_time':r.get('usd_at_tx_time','0'),'usd_at_today_rate':r.get('usd_at_today_rate','0'),
        'from_addr':f,'to_addr':t
    })

with OUT_CSV.open('w',newline='',encoding='utf-8') as f:
    if hits:
        w=csv.DictWriter(f,fieldnames=list(hits[0].keys()));w.writeheader();w.writerows(hits)
    else:
        w=csv.DictWriter(f,fieldnames=['tx_hash','datetime_utc','direction','value_bnb','usd_at_tx_time','usd_at_today_rate','from_addr','to_addr']);w.writeheader()

summary={
    'you_wallet':YOU,
    'binance_wallet':BIN,
    'matched_transactions':len(hits),
    'binance_to_you_bnb':round(in_bnb,8),
    'binance_to_you_usd_then':round(in_usd,2),
    'binance_to_you_usd_today':round(in_today,2),
    'you_to_binance_bnb':round(out_bnb,8),
    'you_to_binance_usd_then':round(out_usd,2),
    'you_to_binance_usd_today':round(out_today,2),
    'net_usd_then':round(in_usd-out_usd,2),
    'net_usd_today':round(in_today-out_today,2),
}
OUT_JSON.write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
print(f'Wrote: {OUT_CSV}')
print(f'Wrote: {OUT_JSON}')
