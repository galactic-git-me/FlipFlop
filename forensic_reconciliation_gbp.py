#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

IN_CSV = Path('bscscan_transactions_with_valuation_and_binance.csv')
TX_CACHE = Path('.cache_txs.json')
RECEIPT_CACHE = Path('.cache_tx_receipts.json')
TOKEN_META_CACHE = Path('.cache_token_meta.json')

OUT_RECON = Path('forensic_cash_reconciliation_gbp.csv')
OUT_WATERFALL = Path('token_conversion_waterfall.csv')
OUT_SUMMARY = Path('forensic_loss_estimate_summary.json')
OUT_MD = Path('forensic_loss_estimate.md')

TARGET = '0x128c33c16ee6d337154d0996220a791d89aa0442'
TRANSFER_TOPIC = '0xddf252ad'

KNOWN_TOKEN_META = {
    '0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90': ('SAFUU', 'Safuu: SAFUU Token'),
    '0x9321bc6185adc9b9cb503cc211e17cb311c3fa95': ('SGO', 'SafuuGO: SGO Token'),
    '0x936e203701c6f8b619fcf8bcba8ec0d4157f02a5': ('PYR', 'Vulcan Forged PYR'),
    '0xd7f7827507c49235a2a6c13ce07bac75ab183ea8': ('VUL', 'VulcanSwap: VULCAN'),
    '0xb08504d245713ca9692c8fa605e76a0a11ed4955': ('VTRU', 'Vitruveo Bridged VTRU'),
}


def norm(s: str) -> str:
    return (s or '').strip().lower()


def parse_addr_topic(topic_hex: str) -> str:
    if not topic_hex or not topic_hex.startswith('0x') or len(topic_hex) < 42:
        return ''
    return '0x' + topic_hex[-40:].lower()


def symbol_for_token(token_addr: str, meta_cache: dict) -> str:
    t = norm(token_addr)
    if t in KNOWN_TOKEN_META:
        return KNOWN_TOKEN_META[t][0]
    m = meta_cache.get(t, {})
    sym = (m.get('symbol') or '').strip().upper()
    return sym if sym else t


def main() -> int:
    rows = list(csv.DictReader(IN_CSV.open(newline='', encoding='utf-8')))
    tx_cache = json.loads(TX_CACHE.read_text(encoding='utf-8')) if TX_CACHE.exists() else {}
    receipt_cache = json.loads(RECEIPT_CACHE.read_text(encoding='utf-8')) if RECEIPT_CACHE.exists() else {}
    token_meta_cache = json.loads(TOKEN_META_CACHE.read_text(encoding='utf-8')) if TOKEN_META_CACHE.exists() else {}

    # 1) External cash legs (Binance assumption)
    binance_in_gbp = 0.0
    binance_out_gbp = 0.0
    binance_in_usd = 0.0
    binance_out_usd = 0.0

    # 2) Internal conversion flow ledger by token direction
    # We model conversions by tx-level token in/out relative to wallet using ERC20 Transfer logs.
    token_in_gbp = defaultdict(float)
    token_out_gbp = defaultdict(float)
    token_in_usd = defaultdict(float)
    token_out_usd = defaultdict(float)

    for r in rows:
        txh = norm(r.get('tx_hash'))
        tx = tx_cache.get(txh) or {}
        receipt = receipt_cache.get(txh) or {}

        from_addr = norm(tx.get('from'))
        to_addr = norm(tx.get('to'))

        usd_then = float((r.get('usd_at_tx_time') or '0') or 0)
        # convert using observed per-row implicit fx from earlier file: binance_inflow_usd_then vs gbp_then not stored globally
        # We approximate GBP using observed global ratio from prior computation.
        # ratio = total_paid_in_gbp / total_paid_in_usd
        # using fixed ratio to keep deterministic without extra API calls in this run.
        fx_usd_to_gbp = 59037.83 / 71372.04 if 71372.04 else 0.826
        gbp_then = usd_then * fx_usd_to_gbp

        is_binance_inflow = (r.get('is_binance_inflow') or '0') == '1'
        is_binance_outflow = (to_addr != TARGET and from_addr == TARGET and 'binance' in (r.get('to','').lower()))

        if is_binance_inflow:
            binance_in_usd += usd_then
            binance_in_gbp += gbp_then

        if is_binance_outflow:
            binance_out_usd += usd_then
            binance_out_gbp += gbp_then

        # token transfers wallet<->token for conversion mapping
        token_delta = defaultdict(float)
        for lg in receipt.get('logs', []) if isinstance(receipt, dict) else []:
            topics = lg.get('topics') or []
            if not topics or not (topics[0] or '').lower().startswith(TRANSFER_TOPIC):
                continue
            if len(topics) < 3:
                continue
            t_from = parse_addr_topic(topics[1])
            t_to = parse_addr_topic(topics[2])
            token_addr = norm(lg.get('address'))
            sym = symbol_for_token(token_addr, token_meta_cache)

            # we don't decode token units; use tx-value GBP/USD as weighted proxy across tokens in tx
            if t_from == TARGET and t_to != TARGET:
                token_delta[sym] -= 1.0
            elif t_to == TARGET and t_from != TARGET:
                token_delta[sym] += 1.0

        if token_delta:
            # split tx fiat value over touched token legs proportionally by absolute leg count
            denom = sum(abs(v) for v in token_delta.values())
            if denom > 0:
                for sym, v in token_delta.items():
                    w = abs(v) / denom
                    if v > 0:
                        token_in_usd[sym] += usd_then * w
                        token_in_gbp[sym] += gbp_then * w
                    elif v < 0:
                        token_out_usd[sym] += usd_then * w
                        token_out_gbp[sym] += gbp_then * w

    # Build waterfall table
    symbols = sorted(set(token_in_gbp.keys()) | set(token_out_gbp.keys()))
    with OUT_WATERFALL.open('w', newline='', encoding='utf-8') as f:
        fields = [
            'token_symbol',
            'internal_in_usd_then','internal_out_usd_then','internal_net_usd_then',
            'internal_in_gbp_then','internal_out_gbp_then','internal_net_gbp_then'
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in symbols:
            in_u = token_in_usd[s]
            out_u = token_out_usd[s]
            in_g = token_in_gbp[s]
            out_g = token_out_gbp[s]
            w.writerow({
                'token_symbol': s,
                'internal_in_usd_then': round(in_u,2),
                'internal_out_usd_then': round(out_u,2),
                'internal_net_usd_then': round(in_u-out_u,2),
                'internal_in_gbp_then': round(in_g,2),
                'internal_out_gbp_then': round(out_g,2),
                'internal_net_gbp_then': round(in_g-out_g,2),
            })

    # Reconciled principal loss: external in - external out (no double count of internal conversions)
    principal_net_usd = binance_in_usd - binance_out_usd
    principal_net_gbp = binance_in_gbp - binance_out_gbp

    with OUT_RECON.open('w', newline='', encoding='utf-8') as f:
        fields = ['metric','usd_then','gbp_then']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerow({'metric':'binance_ramp_in','usd_then':round(binance_in_usd,2),'gbp_then':round(binance_in_gbp,2)})
        w.writerow({'metric':'binance_ramp_out','usd_then':round(binance_out_usd,2),'gbp_then':round(binance_out_gbp,2)})
        w.writerow({'metric':'reconciled_principal_net_loss','usd_then':round(principal_net_usd,2),'gbp_then':round(principal_net_gbp,2)})

    summary = {
        'method': 'No-double-count principal model: loss = external ramp-in minus external ramp-out; internal token conversions treated as reallocations.',
        'binance_ramp_in_usd_then': round(binance_in_usd,2),
        'binance_ramp_in_gbp_then': round(binance_in_gbp,2),
        'binance_ramp_out_usd_then': round(binance_out_usd,2),
        'binance_ramp_out_gbp_then': round(binance_out_gbp,2),
        'reconciled_principal_net_loss_usd_then': round(principal_net_usd,2),
        'reconciled_principal_net_loss_gbp_then': round(principal_net_gbp,2),
        'note': 'If Binance outflows are missing due to label gaps, this is an upper-bound loss estimate.'
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding='utf-8')

    md = []
    md.append('# Forensic Reconciled Loss Estimate')
    md.append('')
    md.append(f"- Method: {summary['method']}")
    md.append('')
    md.append('| Metric | USD (tx-time) | GBP (tx-time) |')
    md.append('|---|---:|---:|')
    md.append(f"| Binance Ramp In | ${summary['binance_ramp_in_usd_then']:.2f} | £{summary['binance_ramp_in_gbp_then']:.2f} |")
    md.append(f"| Binance Ramp Out | ${summary['binance_ramp_out_usd_then']:.2f} | £{summary['binance_ramp_out_gbp_then']:.2f} |")
    md.append(f"| Reconciled Principal Net Loss | ${summary['reconciled_principal_net_loss_usd_then']:.2f} | £{summary['reconciled_principal_net_loss_gbp_then']:.2f} |")
    md.append('')
    md.append(f"- Note: {summary['note']}")
    OUT_MD.write_text('\n'.join(md), encoding='utf-8')

    print(json.dumps(summary, indent=2))
    print(f'Wrote: {OUT_RECON}')
    print(f'Wrote: {OUT_WATERFALL}')
    print(f'Wrote: {OUT_SUMMARY}')
    print(f'Wrote: {OUT_MD}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
