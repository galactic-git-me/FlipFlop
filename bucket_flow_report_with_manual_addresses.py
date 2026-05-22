#!/usr/bin/env python3
import csv, json
from collections import defaultdict
from pathlib import Path
import requests

IN_CSV=Path('bscscan_transactions_with_valuation_and_binance.csv')
TX_CACHE=Path('.cache_txs.json')
RECEIPT_CACHE=Path('.cache_tx_receipts.json')
TOKEN_META_CACHE=Path('.cache_token_meta.json')
OUT_CSV=Path('bucket_inflow_outflow_net_with_manual_addresses.csv')
OUT_MD=Path('bucket_inflow_outflow_net_with_manual_addresses.md')

TARGET='0x128c33c16ee6d337154d0996220a791d89aa0442'
BSC_CHAIN_WALLET='0x87c1715176dfd3e3083c68287b339dd0606a56bf'
STABLEFUND_WALLET='0x8b206a405c11664189cec6673bf5a9b4e0eaf63e'
TRANSFER_TOPIC='0xddf252ad'

KNOWN_TOKEN_META={
'0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90':('SAFUU','safuu'),
'0x9321bc6185adc9b9cb503cc211e17cb311c3fa95':('SGO','sgo'),
}
STABLE_KEYWORDS=('stable','usd','usdt','usdc','busd','dai','fdusd','tusd','susd','gusd')

def norm(s): return (s or '').strip().lower()

def parse_addr_topic(t):
    if not t or not t.startswith('0x') or len(t)<42: return ''
    return '0x'+t[-40:].lower()

def usd_gbp_rate(date):
    r=requests.get(f'https://api.frankfurter.app/{date}?from=USD&to=GBP',timeout=20)
    r.raise_for_status()
    return float(r.json()['rates']['GBP'])

rows=list(csv.DictReader(open(IN_CSV,newline='',encoding='utf-8')))
tx_cache=json.loads(TX_CACHE.read_text())
receipt_cache=json.loads(RECEIPT_CACHE.read_text()) if RECEIPT_CACHE.exists() else {}
meta_cache=json.loads(TOKEN_META_CACHE.read_text()) if TOKEN_META_CACHE.exists() else {}

fx_cache={}

def bucket(row,tx,receipt):
    f=norm(tx.get('from')); t=norm(tx.get('to'))
    # explicit override by known wallet addresses
    if {f,t} & {STABLEFUND_WALLET}: return 'stablefund'
    # keep binance special only for inflow/ramp classification rows
    if (row.get('is_binance_inflow') or '0')=='1': return 'binance'

    syms=[]; names=[]
    for lg in receipt.get('logs',[]) if isinstance(receipt,dict) else []:
        topics=lg.get('topics') or []
        if not topics or not (topics[0] or '').lower().startswith(TRANSFER_TOPIC):
            continue
        tf=parse_addr_topic(topics[1]) if len(topics)>1 else ''
        tt=parse_addr_topic(topics[2]) if len(topics)>2 else ''
        if TARGET not in {tf,tt}: continue
        addr=norm(lg.get('address'))
        if addr in KNOWN_TOKEN_META:
            sym,name=KNOWN_TOKEN_META[addr]
        else:
            m=meta_cache.get(addr,{})
            sym=(m.get('symbol') or '').strip().upper()
            name=(m.get('name') or '').strip().lower()
        if sym: syms.append(sym)
        if name: names.append(name)

    s=set(syms)
    names=' '.join(names)
    if 'SGO' in s: return 'sgo'
    if any(x in s for x in ['SAFUU','SFX','SFU']): return 'safuu'
    if any(k in names for k in STABLE_KEYWORDS) or any(any(k in x.lower() for k in STABLE_KEYWORDS) for x in s): return 'stablefund'
    return 'others'

agg=defaultdict(lambda:defaultdict(float))
for r in rows:
    tx=tx_cache.get(norm(r.get('tx_hash'))) or {}
    receipt=receipt_cache.get(norm(r.get('tx_hash'))) or {}
    b=bucket(r,tx,receipt)
    f=norm(tx.get('from')); t=norm(tx.get('to'))
    direction='none'
    if t==TARGET: direction='inflow'
    elif f==TARGET: direction='outflow'

    bnb=float(r.get('value_bnb') or 0)
    usd=float(r.get('usd_at_tx_time') or 0)
    date=(r.get('datetime_utc') or '')[:10]
    if date and date not in fx_cache:
        fx_cache[date]=usd_gbp_rate(date)
    gbp=usd*(fx_cache.get(date,0))

    agg[b]['tx_count']+=1
    if direction=='inflow':
        agg[b]['inflow_bnb']+=bnb; agg[b]['inflow_usd_then']+=usd; agg[b]['inflow_gbp_then']+=gbp
    elif direction=='outflow':
        agg[b]['outflow_bnb']+=bnb; agg[b]['outflow_usd_then']+=usd; agg[b]['outflow_gbp_then']+=gbp

order=['binance','safuu','sgo','stablefund','others']
for b in order:
    d=agg[b]
    d['net_bnb']=d['inflow_bnb']-d['outflow_bnb']
    d['net_usd_then']=d['inflow_usd_then']-d['outflow_usd_then']
    d['net_gbp_then']=d['inflow_gbp_then']-d['outflow_gbp_then']

# totals
tot=defaultdict(float)
for b in order:
    for k,v in agg[b].items(): tot[k]+=v

with open(OUT_CSV,'w',newline='',encoding='utf-8') as f:
    fields=['bucket','tx_count','inflow_usd_then','outflow_usd_then','net_usd_then','inflow_gbp_then','outflow_gbp_then','net_gbp_then']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for b in order+['TOTAL']:
        d=tot if b=='TOTAL' else agg[b]
        w.writerow({
            'bucket':b,
            'tx_count':int(round(d['tx_count'])),
            'inflow_usd_then':round(d['inflow_usd_then'],2),
            'outflow_usd_then':round(d['outflow_usd_then'],2),
            'net_usd_then':round(d['net_usd_then'],2),
            'inflow_gbp_then':round(d['inflow_gbp_then'],2),
            'outflow_gbp_then':round(d['outflow_gbp_then'],2),
            'net_gbp_then':round(d['net_gbp_then'],2),
        })

lines=['# Bucket Flow With Manual Address Overrides','',
'| Bucket | Inflow $ (then) | Outflow $ (then) | Net $ (then) | Inflow £ (then) | Outflow £ (then) | Net £ (then) |',
'|---|---:|---:|---:|---:|---:|---:|']
for b in order+['TOTAL']:
    d=tot if b=='TOTAL' else agg[b]
    lines.append(f"| {b} | ${d['inflow_usd_then']:.2f} | ${d['outflow_usd_then']:.2f} | ${d['net_usd_then']:.2f} | £{d['inflow_gbp_then']:.2f} | £{d['outflow_gbp_then']:.2f} | £{d['net_gbp_then']:.2f} |")
Path(OUT_MD).write_text('\n'.join(lines),encoding='utf-8')

print('Wrote',OUT_CSV)
print('Wrote',OUT_MD)
for b in order+['TOTAL']:
    d=tot if b=='TOTAL' else agg[b]
    print(b,round(d['inflow_usd_then'],2),round(d['outflow_usd_then'],2),round(d['net_usd_then'],2),round(d['inflow_gbp_then'],2),round(d['outflow_gbp_then'],2),round(d['net_gbp_then'],2))
