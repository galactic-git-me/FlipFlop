#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests

RPC_URL = "https://bsc-dataseed.binance.org"
IN_DATASET = Path("bscscan_transactions_2021_to_today.enriched.with_external_tags.csv")
IN_LOOKUP = Path("friendly_tag_lookup.extended.csv")

OUT_MATCHES = Path("project_matches_per_tx.csv")
OUT_ENRICHED = Path("bscscan_transactions_2021_to_today.project_attributed.csv")
OUT_SUMMARY = Path("project_match_summary.json")

RECEIPT_CACHE = Path(".cache_tx_receipts.json")
TOKEN_META_CACHE = Path(".cache_token_meta.json")

TARGET_PROJECTS = {
    "safuu": ["safuu", "safuux", "safuu go", "safuugo", "sgo", "sfu", "sfx"],
    "vulcan": ["vulcan", "vul", "pyr", "vulcan forged"],
    "vitruveo": ["vitruveo", "vtrx", "vtru"],
}

TARGET_SYMBOLS = {"SAFUU", "SFX", "SFU", "SGO", "VUL", "PYR", "VTRX", "VTRU"}
TRANSFER_TOPIC = "0xddf252ad"  # keccak(Transfer(address,address,uint256))[:4]
APPROVAL_TOPIC = "0x8c5be1e5"  # keccak(Approval(address,address,uint256))[:4]

KNOWN_PROJECT_ADDRESS_TO_TAG = {
    "0xe5ba47fd94cb645ba4119222e34fb33f59c7cd90": "Safuu: SAFUU Token",
    "0xc38511a85d8fbf2c859e0bce7e831afd4b569939": "Safuu: Deployer",
    "0x9321bc6185adc9b9cb503cc211e17cb311c3fa95": "SafuuGO: SGO Token",
    "0x936e203701c6f8b619fcf8bcba8ec0d4157f02a5": "Vulcan Forged PYR (PYR)",
    "0xd7f7827507c49235a2a6c13ce07bac75ab183ea8": "VulcanSwap: Vulcan Token (VULCAN)",
    "0xb08504d245713ca9692c8fa605e76a0a11ed4955": "Vitruveo Bridged VTRU (VTRU)",
}


def load_json(path: Path, default):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def rpc(method: str, params: list, timeout: int = 30) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(RPC_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error {method}: {data['error']}")
    return data.get("result")


def hex_to_ascii(h: str) -> str:
    h = h[2:] if h.startswith("0x") else h
    try:
        b = bytes.fromhex(h)
    except ValueError:
        return ""
    b = b.rstrip(b"\x00")
    try:
        return b.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def decode_string_result(result_hex: str) -> str:
    if not result_hex or result_hex == "0x":
        return ""
    raw = result_hex[2:]
    if len(raw) == 64:
        return hex_to_ascii(result_hex)
    if len(raw) >= 128:
        # dynamic ABI string: offset(32) + length(32) + data
        try:
            strlen = int(raw[64:128], 16)
            data_hex = raw[128 : 128 + strlen * 2]
            return bytes.fromhex(data_hex).decode("utf-8", errors="ignore").strip()
        except Exception:
            pass
    return hex_to_ascii(result_hex)


def eth_call_string(contract: str, selector: str) -> str:
    try:
        result = rpc(
            "eth_call",
            [{"to": contract, "data": selector}, "latest"],
            timeout=20,
        )
    except Exception:
        return ""
    return decode_string_result(result)


def get_token_meta(addr: str, meta_cache: Dict[str, dict]) -> dict:
    if addr in meta_cache:
        return meta_cache[addr]
    symbol = eth_call_string(addr, "0x95d89b41")  # symbol()
    name = eth_call_string(addr, "0x06fdde03")  # name()
    meta = {"symbol": symbol.strip(), "name": name.strip()}
    meta_cache[addr] = meta
    return meta


def norm(s: str) -> str:
    return (s or "").strip().lower()


def project_from_text(text: str) -> Set[str]:
    t = norm(text)
    hits = set()
    for project, terms in TARGET_PROJECTS.items():
        for term in terms:
            if term in t:
                hits.add(project)
                break
    return hits


def load_lookup_addresses() -> Dict[str, str]:
    out = {}
    if not IN_LOOKUP.exists():
        return out
    with IN_LOOKUP.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tag = (r.get("friendly_tag") or "").strip()
            addr = norm(r.get("address") or "")
            if tag and addr:
                out[addr] = tag
    out.update(KNOWN_PROJECT_ADDRESS_TO_TAG)
    return out


def get_receipt(tx_hash: str, receipt_cache: Dict[str, dict]) -> Optional[dict]:
    tx_hash = tx_hash.lower()
    if tx_hash in receipt_cache:
        return receipt_cache[tx_hash]
    try:
        receipt = rpc("eth_getTransactionReceipt", [tx_hash], timeout=30)
    except Exception:
        return None
    receipt_cache[tx_hash] = receipt
    return receipt


def get_tx(tx_hash: str) -> Optional[dict]:
    try:
        return rpc("eth_getTransactionByHash", [tx_hash], timeout=30)
    except Exception:
        return None


def main() -> int:
    if not IN_DATASET.exists():
        raise SystemExit(f"Missing input dataset: {IN_DATASET}")

    receipt_cache = load_json(RECEIPT_CACHE, {})
    token_meta_cache = load_json(TOKEN_META_CACHE, {})
    lookup_addr_to_tag = load_lookup_addresses()

    with IN_DATASET.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    tx_hashes = [norm(r.get("tx_hash", "")) for r in rows if norm(r.get("tx_hash", ""))]
    matches = []
    project_hit_counts = defaultdict(int)

    for i, txh in enumerate(tx_hashes, start=1):
        row = rows[i - 1]
        evidence = []
        matched_projects = set()

        # 1) direct address matches from from/to
        for col in ("from_address", "to_address"):
            a = norm(row.get(col, ""))
            if a and a in lookup_addr_to_tag:
                tag = lookup_addr_to_tag[a]
                projs = project_from_text(tag)
                if projs:
                    matched_projects.update(projs)
                    evidence.append(f"{col}:{a}:{tag}")

        # 2) direct friendly text in existing fields
        for col in ("from", "to", "from_friendly_tag_final", "to_friendly_tag_final"):
            v = row.get(col, "")
            projs = project_from_text(v)
            if projs:
                matched_projects.update(projs)
                evidence.append(f"{col}:{v}")

        # 3) on-chain tx + receipt
        receipt = get_receipt(txh, receipt_cache)
        txobj = get_tx(txh)

        contract_candidates = set()
        if txobj and txobj.get("to"):
            to_addr = norm(txobj["to"])
            contract_candidates.add(to_addr)
            if to_addr in lookup_addr_to_tag:
                tag = lookup_addr_to_tag[to_addr]
                projs = project_from_text(tag)
                if projs:
                    matched_projects.update(projs)
                    evidence.append(f"tx_to:{to_addr}:{tag}")

        if receipt and receipt.get("logs"):
            for lg in receipt["logs"]:
                addr = norm(lg.get("address", ""))
                if not addr:
                    continue
                contract_candidates.add(addr)
                if addr in lookup_addr_to_tag:
                    tag = lookup_addr_to_tag[addr]
                    projs = project_from_text(tag)
                    if projs:
                        matched_projects.update(projs)
                        evidence.append(f"log_addr:{addr}:{tag}")

                topics = lg.get("topics") or []
                topic0 = (topics[0].lower() if topics else "")
                if topic0.startswith(TRANSFER_TOPIC) or topic0.startswith(APPROVAL_TOPIC):
                    # token-ish contract involved
                    meta = get_token_meta(addr, token_meta_cache)
                    symbol = (meta.get("symbol") or "").upper()
                    name = meta.get("name") or ""

                    if symbol in TARGET_SYMBOLS:
                        # map symbol -> project
                        for p in project_from_text(symbol):
                            matched_projects.add(p)
                        evidence.append(f"token_symbol:{addr}:{symbol}")
                    n_hits = project_from_text(name)
                    if n_hits:
                        matched_projects.update(n_hits)
                        evidence.append(f"token_name:{addr}:{name}")

        # 4) inspect token metadata for any contracts touched
        for caddr in list(contract_candidates):
            meta = get_token_meta(caddr, token_meta_cache)
            symbol = (meta.get("symbol") or "").upper()
            name = meta.get("name") or ""
            if symbol in TARGET_SYMBOLS:
                h = project_from_text(symbol)
                if h:
                    matched_projects.update(h)
                    evidence.append(f"contract_symbol:{caddr}:{symbol}")
            n_hits = project_from_text(name)
            if n_hits:
                matched_projects.update(n_hits)
                evidence.append(f"contract_name:{caddr}:{name}")

        if matched_projects:
            confidence = "low"
            ev_text = " | ".join(evidence)
            if any(x.startswith(("token_symbol:", "token_name:", "log_addr:", "tx_to:")) for x in evidence):
                confidence = "high"
            elif any(x.startswith(("from_address:", "to_address:")) for x in evidence):
                confidence = "medium"

            for p in sorted(matched_projects):
                matches.append(
                    {
                        "tx_hash": txh,
                        "project": p,
                        "confidence": confidence,
                        "evidence": ev_text[:3000],
                    }
                )
                project_hit_counts[p] += 1

        if i % 100 == 0:
            print(f"Processed {i}/{len(tx_hashes)} txs")
            save_json(RECEIPT_CACHE, receipt_cache)
            save_json(TOKEN_META_CACHE, token_meta_cache)
            time.sleep(0.05)

    # Deduplicate tx/project pairs keeping highest confidence
    conf_rank = {"low": 1, "medium": 2, "high": 3}
    best = {}
    for m in matches:
        key = (m["tx_hash"], m["project"])
        if key not in best or conf_rank[m["confidence"]] > conf_rank[best[key]["confidence"]]:
            best[key] = m
    matches = list(best.values())

    with OUT_MATCHES.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["tx_hash", "project", "confidence", "evidence"])
        w.writeheader()
        w.writerows(matches)

    # Attach aggregated project columns back to dataset
    tx_to_projects = defaultdict(list)
    tx_to_conf = {}
    for m in matches:
        tx_to_projects[m["tx_hash"]].append(m["project"])
        tx_to_conf[m["tx_hash"]] = max(tx_to_conf.get(m["tx_hash"], "low"), m["confidence"], key=lambda c: conf_rank[c])

    for r in rows:
        txh = norm(r.get("tx_hash", ""))
        projs = sorted(set(tx_to_projects.get(txh, [])))
        r["project_hit"] = "|".join(projs)
        r["project_hit_count"] = str(len(projs))
        r["project_confidence"] = tx_to_conf.get(txh, "") if projs else ""

    with OUT_ENRICHED.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else []
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    summary = {
        "total_rows": len(rows),
        "matched_rows": sum(1 for r in rows if (r.get("project_hit") or "").strip()),
        "unique_projects": sorted(set(m["project"] for m in matches)),
        "project_match_counts": dict(sorted(project_hit_counts.items())),
        "match_records": len(matches),
        "rpc_url": RPC_URL,
    }
    save_json(OUT_SUMMARY, summary)
    save_json(RECEIPT_CACHE, receipt_cache)
    save_json(TOKEN_META_CACHE, token_meta_cache)

    print(json.dumps(summary, indent=2))
    print(f"Wrote: {OUT_MATCHES}")
    print(f"Wrote: {OUT_ENRICHED}")
    print(f"Wrote: {OUT_SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
