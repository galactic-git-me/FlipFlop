#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

IN_CSV = Path('bscscan_transactions_with_valuation_and_binance.csv')
RECEIPT_CACHE = Path('.cache_tx_receipts.json')
TOKEN_META_CACHE = Path('.cache_token_meta.json')
TX_CACHE = Path('.cache_txs.json')

OUT_SUMMARY_JSON = Path('paid_in_summary_usd_gbp.json')
OUT_TOKEN_SPLIT_CSV = Path('token_destination_split_with_groups.csv')
OUT_TOKEN_SPLIT_MD = Path('token_destination_split_with_groups.md')

TARGET = '0x128c33c16ee6d337154d0996220a791d89aa0442'
TRANSFER_TOPIC = '0xddf252ad'

# Explicit project token map (token-level)
PROJECT_TOKEN_GROUP = {
    'SAFUU': 'SAFUU_PROJECTS',
    'SGO': 'SAFUU_PROJECTS',
    'SFX': 'SAFUU_PROJECTS',
    'SFU': 'SAFUU_PROJECTS',
    'VUL': 'VULCAN_PROJECTS',
    'PYR': 'VULCAN_PROJECTS',
    'VTRX': 'VITRUVEO_PROJECTS',
    'VTRU': 'VITRUVEO_PROJECTS',
}

KNOWN_TOKEN_META = {
    '0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90': ('SAFUU', 'Safuu: SAFUU Token'),
    '0x9321bc6185adc9b9cb503cc211e17cb311c3fa95': ('SGO', 'SafuuGO: SGO Token'),
    '0x936e203701c6f8b619fcf8bcba8ec0d4157f02a5': ('PYR', 'Vulcan Forged PYR'),
    '0xd7f7827507c49235a2a6c13ce07bac75ab183ea8': ('VUL', 'VulcanSwap: VULCAN'),
    '0xb08504d245713ca9692c8fa605e76a0a11ed4955': ('VTRU', 'Vitruveo Bridged VTRU'),
}

STABLE_KEYWORDS = (
    'stable', 'usd', 'usdt', 'usdc', 'busd', 'dai', 'fdusd', 'usde', 'tusd', 'susd', 'gusd'
)


def norm(s: str) -> str:
    return (s or '').strip().lower()


def parse_addr_topic(topic_hex: str) -> str:
    if not topic_hex or not topic_hex.startswith('0x') or len(topic_hex) < 42:
        return ''
    return '0x' + topic_hex[-40:].lower()


def usd_to_gbp_rate(date_str: str) -> float:
    # date_str: YYYY-MM-DD
    url = f'https://api.frankfurter.app/{date_str}?from=USD&to=GBP'
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    rates = data.get('rates', {})
    if 'GBP' not in rates:
        raise RuntimeError(f'No GBP rate for {date_str}')
    return float(rates['GBP'])


def classify_group(symbol: str, name: str) -> str:
    s = (symbol or '').upper()
    n = (name or '').lower()

    if s in PROJECT_TOKEN_GROUP:
        return PROJECT_TOKEN_GROUP[s]

    stable_hit = any(k in n for k in STABLE_KEYWORDS) or any(k in s.lower() for k in STABLE_KEYWORDS)
    if stable_hit:
        return 'STABLEFUND_STABLECOIN'

    return 'OTHER'


def main() -> int:
    rows = list(csv.DictReader(IN_CSV.open(newline='', encoding='utf-8')))
    receipt_cache = json.loads(RECEIPT_CACHE.read_text(encoding='utf-8')) if RECEIPT_CACHE.exists() else {}
    token_meta_cache = json.loads(TOKEN_META_CACHE.read_text(encoding='utf-8')) if TOKEN_META_CACHE.exists() else {}
    tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8')) if TX_CACHE.exists() else {}

    # 1) Paid in from Binance inflows (USD + historical GBP)
    binance_rows = [r for r in rows if (r.get('is_binance_inflow') or '0') == '1']

    # cache FX per date
    fx_cache = {}
    total_paid_usd = 0.0
    total_paid_gbp = 0.0

    for r in binance_rows:
        usd = float((r.get('binance_inflow_usd_then') or '0').strip() or 0)
        dt = (r.get('datetime_utc') or '')
        date = dt[:10]
        if date not in fx_cache:
            fx_cache[date] = usd_to_gbp_rate(date)
        gbp = usd * fx_cache[date]
        r['binance_inflow_gbp_then'] = f'{gbp:.2f}'
        total_paid_usd += usd
        total_paid_gbp += gbp

    # 2) Destination split by token for all wallet-out transactions
    token_agg = defaultdict(lambda: {
        'grouping': 'OTHER',
        'token_name': '',
        'tx_count': 0,
        'money_into_token_bnb': 0.0,
        'money_into_token_usd_then': 0.0,
        'money_into_token_gbp_then': 0.0,
    })

    for r in rows:
        txh = norm(r.get('tx_hash'))
        tx = tx_cache.get(txh) or {}
        from_addr = norm(tx.get('from'))
        if from_addr != TARGET:
            continue  # only where money went out from your wallet

        bnb = float((r.get('value_bnb') or '0').strip() or 0)
        usd_then = float((r.get('usd_at_tx_time') or '0').strip() or 0)
        date = (r.get('datetime_utc') or '')[:10]
        if date not in fx_cache:
            fx_cache[date] = usd_to_gbp_rate(date)
        gbp_then = usd_then * fx_cache[date]

        receipt = receipt_cache.get(txh) or {}
        token_hits = {}

        for lg in receipt.get('logs', []) if isinstance(receipt, dict) else []:
            topics = lg.get('topics') or []
            if not topics:
                continue
            if not (topics[0] or '').lower().startswith(TRANSFER_TOPIC):
                continue

            token_addr = norm(lg.get('address'))
            if not token_addr:
                continue

            # wallet-involved transfer to improve precision
            from_t = parse_addr_topic(topics[1]) if len(topics) > 1 else ''
            to_t = parse_addr_topic(topics[2]) if len(topics) > 2 else ''
            if TARGET not in {from_t, to_t}:
                continue

            if token_addr in KNOWN_TOKEN_META:
                sym, name = KNOWN_TOKEN_META[token_addr]
            else:
                meta = token_meta_cache.get(token_addr, {})
                sym = (meta.get('symbol') or '').strip().upper() or token_addr
                name = (meta.get('name') or '').strip()

            group = classify_group(sym, name)
            token_hits[sym] = (name, group)

        if not token_hits:
            token_hits['NO_TOKEN_LOG'] = ('No token transfer log attributed', 'OTHER')

        w = 1.0 / len(token_hits)
        for sym, (name, group) in token_hits.items():
            d = token_agg[sym]
            d['grouping'] = group
            d['token_name'] = name
            d['tx_count'] += 1
            d['money_into_token_bnb'] += bnb * w
            d['money_into_token_usd_then'] += usd_then * w
            d['money_into_token_gbp_then'] += gbp_then * w

    # write token split csv
    with OUT_TOKEN_SPLIT_CSV.open('w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'grouping', 'token_symbol', 'token_name', 'tx_count',
            'money_into_token_bnb', 'money_into_token_usd_then', 'money_into_token_gbp_then'
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for sym in sorted(token_agg.keys()):
            d = token_agg[sym]
            w.writerow({
                'grouping': d['grouping'],
                'token_symbol': sym,
                'token_name': d['token_name'],
                'tx_count': d['tx_count'],
                'money_into_token_bnb': round(d['money_into_token_bnb'], 8),
                'money_into_token_usd_then': round(d['money_into_token_usd_then'], 2),
                'money_into_token_gbp_then': round(d['money_into_token_gbp_then'], 2),
            })

    # group totals
    group_totals = defaultdict(lambda: {'bnb': 0.0, 'usd_then': 0.0, 'gbp_then': 0.0})
    for sym, d in token_agg.items():
        g = d['grouping']
        group_totals[g]['bnb'] += d['money_into_token_bnb']
        group_totals[g]['usd_then'] += d['money_into_token_usd_then']
        group_totals[g]['gbp_then'] += d['money_into_token_gbp_then']

    summary = {
        'assumption': 'All Binance inflows are treated as your money paid in via Binance.',
        'binance_inflow_tx_count': len(binance_rows),
        'total_paid_in_usd_then': round(total_paid_usd, 2),
        'total_paid_in_gbp_then': round(total_paid_gbp, 2),
        'group_totals_money_into_tokens': {
            g: {
                'bnb': round(v['bnb'], 8),
                'usd_then': round(v['usd_then'], 2),
                'gbp_then': round(v['gbp_then'], 2),
            }
            for g, v in sorted(group_totals.items())
        },
    }
    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding='utf-8')

    # markdown
    lines = []
    lines.append('# Paid-In And Destination Split')
    lines.append('')
    lines.append(f"- Assumption used: {summary['assumption']}")
    lines.append(f"- Binance inflow tx count: {summary['binance_inflow_tx_count']}")
    lines.append(f"- Total paid in (USD at tx time): ${summary['total_paid_in_usd_then']:.2f}")
    lines.append(f"- Total paid in (GBP at tx time): £{summary['total_paid_in_gbp_then']:.2f}")
    lines.append('')
    lines.append('## Group Totals (Where Money Went)')
    lines.append('')
    lines.append('| Grouping | BNB | USD (tx-time) | GBP (tx-time) |')
    lines.append('|---|---:|---:|---:|')
    for g, v in sorted(group_totals.items()):
        lines.append(f"| {g} | {v['bnb']:.8f} | ${v['usd_then']:.2f} | £{v['gbp_then']:.2f} |")

    lines.append('')
    lines.append('## Token-Level Detail')
    lines.append('')
    lines.append('| Grouping | Token | Name | Tx Count | BNB | USD (tx-time) | GBP (tx-time) |')
    lines.append('|---|---|---|---:|---:|---:|---:|')
    for sym in sorted(token_agg.keys()):
        d = token_agg[sym]
        lines.append(
            f"| {d['grouping']} | {sym} | {d['token_name']} | {d['tx_count']} | "
            f"{d['money_into_token_bnb']:.8f} | ${d['money_into_token_usd_then']:.2f} | £{d['money_into_token_gbp_then']:.2f} |"
        )

    OUT_TOKEN_SPLIT_MD.write_text('\n'.join(lines), encoding='utf-8')

    print(json.dumps(summary, indent=2))
    print(f'Wrote: {OUT_SUMMARY_JSON}')
    print(f'Wrote: {OUT_TOKEN_SPLIT_CSV}')
    print(f'Wrote: {OUT_TOKEN_SPLIT_MD}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
