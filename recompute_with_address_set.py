#!/usr/bin/env python3
import csv, json
from pathlib import Path

IN_CSV=Path('bscscan_transactions_with_valuation_and_binance.csv')
TX_CACHE=Path('.cache_txs.json')
OUT_JSON=Path('explicit_address_set_reconciliation.json')
OUT_CSV=Path('explicit_address_set_transactions.csv')

YOU='0x128c33c16ee6d337154d0996220a791d89aa0442'

# BSC addresses from your screenshots
ADDR_SET={
    '0xb6934215b856b03430fc8dc058bd1c668b6a3182',  # USDT on BINANCE
    '0x88e54b8b638d84fed0bce9480ade1702644fa9a9',  # USDT BSC
    '0xae070a43f4142cac9a9bab105e301f500a27ae6c',  # usd bitget
    '0x87c1715176dfd3e3083c68287b339dd0606a56bf',  # BSC Chain Wallet
    '0x8b206a405c11664189cec6673bf5a9b4e0eaf63e',  # StableFund
}

rows=list(csv.DictReader(open(IN_CSV,newline='',encoding='utf-8')))
tx_cache=json.loads(TX_CACHE.read_text()) if TX_CACHE.exists() else {}

hits=[]
in_bnb=in_usd=in_today=0.0
out_bnb=out_usd=out_today=0.0

for r in rows:
    tx=tx_cache.get((r.get('tx_hash') or '').lower()) or {}
    f=(tx.get('from') or '').lower(); t=(tx.get('to') or '').lower()
    if not f or not t:
        continue

    direction='none'
    matched_addr=''
    if f in ADDR_SET and t==YOU:
        direction='set_to_you'
        matched_addr=f
    elif f==YOU and t in ADDR_SET:
        direction='you_to_set'
        matched_addr=t
    else:
        continue

    bnb=float(r.get('value_bnb') or 0)
    usd=float(r.get('usd_at_tx_time') or 0)
    today=float(r.get('usd_at_today_rate') or 0)

    if direction=='set_to_you':
        in_bnb+=bnb; in_usd+=usd; in_today+=today
    else:
        out_bnb+=bnb; out_usd+=usd; out_today+=today

    hits.append({
        'tx_hash':r.get('tx_hash',''),
        'datetime_utc':r.get('datetime_utc',''),
        'direction':direction,
        'matched_counterparty':matched_addr,
        'value_bnb':r.get('value_bnb','0'),
        'usd_at_tx_time':r.get('usd_at_tx_time','0'),
        'usd_at_today_rate':r.get('usd_at_today_rate','0'),
        'from_addr':f,
        'to_addr':t,
    })

with OUT_CSV.open('w',newline='',encoding='utf-8') as f:
    fields=['tx_hash','datetime_utc','direction','matched_counterparty','value_bnb','usd_at_tx_time','usd_at_today_rate','from_addr','to_addr']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(hits)

# per-address totals
per_addr={}
for a in ADDR_SET:
    per_addr[a]={'to_you_usd_then':0.0,'from_you_usd_then':0.0,'to_you_usd_today':0.0,'from_you_usd_today':0.0,'tx_count':0}
for h in hits:
    a=h['matched_counterparty']
    per_addr[a]['tx_count']+=1
    u=float(h['usd_at_tx_time'] or 0)
    ut=float(h['usd_at_today_rate'] or 0)
    if h['direction']=='set_to_you':
        per_addr[a]['to_you_usd_then']+=u
        per_addr[a]['to_you_usd_today']+=ut
    else:
        per_addr[a]['from_you_usd_then']+=u
        per_addr[a]['from_you_usd_today']+=ut

summary={
    'you_wallet':YOU,
    'address_set_size':len(ADDR_SET),
    'matched_transactions':len(hits),
    'set_to_you_bnb':round(in_bnb,8),
    'set_to_you_usd_then':round(in_usd,2),
    'set_to_you_usd_today':round(in_today,2),
    'you_to_set_bnb':round(out_bnb,8),
    'you_to_set_usd_then':round(out_usd,2),
    'you_to_set_usd_today':round(out_today,2),
    'net_usd_then':round(in_usd-out_usd,2),
    'net_usd_today':round(in_today-out_today,2),
    'per_address':{k:{
        'tx_count':v['tx_count'],
        'to_you_usd_then':round(v['to_you_usd_then'],2),
        'from_you_usd_then':round(v['from_you_usd_then'],2),
        'net_usd_then':round(v['to_you_usd_then']-v['from_you_usd_then'],2),
    } for k,v in sorted(per_addr.items())}
}
OUT_JSON.write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
print(f'Wrote: {OUT_CSV}')
print(f'Wrote: {OUT_JSON}')
