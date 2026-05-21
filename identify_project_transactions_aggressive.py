#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

import requests

RPC_URL = "https://bsc-dataseed.binance.org"
BASE_ATTR = Path("bscscan_transactions_2021_to_today.project_attributed.csv")
BASE_MATCHES = Path("project_matches_per_tx.csv")
OUT_MATCHES = Path("project_matches_per_tx.aggressive.csv")
OUT_DATASET = Path("bscscan_transactions_2021_to_today.project_attributed.aggressive.csv")
OUT_SUMMARY = Path("project_match_summary.aggressive.json")

TX_CACHE = Path(".cache_txs.json")

# Canonical targets / aliases
PROJECT_ADDRS = {
    "safuu": {
        "0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90",  # SAFUU token
        "0x9321bc6185adc9b9cb503cc211e17cb311c3fa95",  # SGO token
        "0xc38511a85d8fbf2c859e0bce7e831afd4b569939",  # deployer
    },
    "vulcan": {
        "0x936e203701c6f8b619fcf8bcba8ec0d4157f02a5",  # PYR
        "0xd7f7827507c49235a2a6c13ce07bac75ab183ea8",  # VULCAN
    },
    "vitruveo": {
        "0xb08504d245713ca9692c8fa605e76a0a11ed4955",  # VTRU bridged
    },
}

PROJECT_TERMS = {
    "safuu": ["safuu", "safuux", "safuu go", "safuugo", "sgo", "sfu", "sfx"],
    "vulcan": ["vulcan", "vul", "pyr", "vulcan forged"],
    "vitruveo": ["vitruveo", "vtrx", "vtru"],
}

ADDR20_RE = re.compile(r"[0-9a-fA-F]{24}([0-9a-fA-F]{40})")


def norm(s: str) -> str:
    return (s or "").strip().lower()


def load_json(path: Path, default):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def rpc(method: str, params: list, timeout: int = 30):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = requests.post(RPC_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        return None
    return j.get("result")


def detect_projects_from_text(text: str) -> Set[str]:
    t = norm(text)
    out = set()
    for p, terms in PROJECT_TERMS.items():
        if any(term in t for term in terms):
            out.add(p)
    return out


def extract_embedded_addresses(input_data: str) -> Set[str]:
    if not input_data or input_data == "0x":
        return set()
    hexdata = input_data[2:] if input_data.startswith("0x") else input_data
    out = set()
    # ABI words often left-pad addresses: 000...<40hex>
    for m in ADDR20_RE.finditer(hexdata):
        out.add("0x" + m.group(1).lower())
    return out


def main() -> int:
    if not BASE_ATTR.exists() or not BASE_MATCHES.exists():
        raise SystemExit("Missing prerequisite files. Run the first attribution pass first.")

    tx_cache: Dict[str, dict] = load_json(TX_CACHE, {})

    with BASE_ATTR.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    base_matches = []
    with BASE_MATCHES.open(newline="", encoding="utf-8") as f:
        base_matches = list(csv.DictReader(f))

    by_tx_project = {(norm(m["tx_hash"]), m["project"]): m for m in base_matches}
    new_matches = []

    for idx, row in enumerate(rows, start=1):
        txh = norm(row.get("tx_hash", ""))
        if not txh:
            continue

        tx = tx_cache.get(txh)
        if tx is None:
            tx = rpc("eth_getTransactionByHash", [txh])
            tx_cache[txh] = tx

        projects = set()
        evidence = []

        # Existing text evidence still useful
        for col in ("from", "to", "from_friendly_tag_final", "to_friendly_tag_final"):
            v = row.get(col, "")
            hits = detect_projects_from_text(v)
            if hits:
                projects.update(hits)
                evidence.append(f"text:{col}")

        if tx:
            to_addr = norm(tx.get("to") or "")
            if to_addr:
                for p, addrs in PROJECT_ADDRS.items():
                    if to_addr in addrs:
                        projects.add(p)
                        evidence.append(f"tx_to:{to_addr}")

            input_data = tx.get("input") or "0x"
            embedded = extract_embedded_addresses(input_data)
            for ea in embedded:
                for p, addrs in PROJECT_ADDRS.items():
                    if ea in addrs:
                        projects.add(p)
                        evidence.append(f"calldata_embedded_addr:{ea}")

        # low-confidence heuristic: if project term appears in to/from and calldata exists
        if tx and (tx.get("input") not in (None, "0x")):
            joined = f"{row.get('from','')} | {row.get('to','')} | {row.get('from_friendly_tag_final','')} | {row.get('to_friendly_tag_final','')}"
            hits = detect_projects_from_text(joined)
            if hits:
                projects.update(hits)
                evidence.append("heuristic:text+calldata")

        for p in sorted(projects):
            key = (txh, p)
            if key not in by_tx_project:
                new_matches.append(
                    {
                        "tx_hash": txh,
                        "project": p,
                        "confidence": "medium" if any(e.startswith("calldata_embedded_addr") for e in evidence) else "low",
                        "evidence": " | ".join(sorted(set(evidence)))[:3000],
                    }
                )

        if idx % 200 == 0:
            print(f"Processed {idx}/{len(rows)}")

    all_matches = base_matches + new_matches

    # Dedup with best confidence
    rank = {"low": 1, "medium": 2, "high": 3}
    best = {}
    for m in all_matches:
        key = (norm(m["tx_hash"]), m["project"])
        if key not in best or rank.get(m["confidence"], 0) > rank.get(best[key]["confidence"], 0):
            best[key] = m
    final_matches = list(best.values())

    with OUT_MATCHES.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["tx_hash", "project", "confidence", "evidence"])
        w.writeheader()
        w.writerows(final_matches)

    tx_to_projects = defaultdict(set)
    tx_to_conf = {}
    for m in final_matches:
        tx = norm(m["tx_hash"])
        tx_to_projects[tx].add(m["project"])
        prev = tx_to_conf.get(tx, "low")
        if rank[m["confidence"]] > rank[prev]:
            tx_to_conf[tx] = m["confidence"]
        elif tx not in tx_to_conf:
            tx_to_conf[tx] = m["confidence"]

    for r in rows:
        txh = norm(r.get("tx_hash", ""))
        projs = sorted(tx_to_projects.get(txh, set()))
        r["project_hit"] = "|".join(projs)
        r["project_hit_count"] = str(len(projs))
        r["project_confidence"] = tx_to_conf.get(txh, "") if projs else ""

    with OUT_DATASET.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)

    summary = {
        "total_rows": len(rows),
        "base_matches": len(base_matches),
        "new_matches_added": len(new_matches),
        "final_match_records": len(final_matches),
        "matched_rows": sum(1 for r in rows if (r.get("project_hit") or "").strip()),
        "project_counts": dict(sorted((p, sum(1 for m in final_matches if m["project"] == p)) for p in {m['project'] for m in final_matches})),
    }
    save_json(OUT_SUMMARY, summary)
    save_json(TX_CACHE, tx_cache)

    print(json.dumps(summary, indent=2))
    print(f"Wrote: {OUT_MATCHES}")
    print(f"Wrote: {OUT_DATASET}")
    print(f"Wrote: {OUT_SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
