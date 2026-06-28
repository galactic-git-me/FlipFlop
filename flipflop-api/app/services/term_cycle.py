from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import structlog

_STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "term_cycle_state.json"
log = structlog.get_logger(__name__)


def _load() -> dict[str, Any]:
    try:
        if not _STATE_FILE.exists():
            return {}
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(state: dict[str, Any]) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("term_cycle.state_save_failed", error=str(exc))


def start_cycle(scope: str, batch_size: int, terms_by_vendor: dict[str, list[str]]) -> None:
    state = _load()
    state[scope] = {
        "active": True,
        "batch_size": max(1, int(batch_size)),
        "vendors": {v: {"cursor": 0, "total": len(ts)} for v, ts in terms_by_vendor.items()},
    }
    _save(state)


def next_batch(scope: str, terms_by_vendor: dict[str, list[str]]) -> tuple[bool, dict[str, list[str]], bool]:
    state = _load()
    rec = state.get(scope) or {}
    if not rec.get("active"):
        return False, {}, False
    vendors_state = rec.get("vendors") or {}
    batch_size = max(1, int(rec.get("batch_size") or 5))

    out: dict[str, list[str]] = {}
    all_done = True
    for vendor, terms in terms_by_vendor.items():
        v = vendors_state.get(vendor) or {"cursor": 0}
        cursor = max(0, int(v.get("cursor") or 0))
        if cursor < len(terms):
            out[vendor] = terms[cursor:cursor + batch_size]
            cursor = min(len(terms), cursor + batch_size)
            all_done = all_done and cursor >= len(terms)
            vendors_state[vendor] = {"cursor": cursor, "total": len(terms)}
        else:
            all_done = all_done and True
            vendors_state[vendor] = {"cursor": len(terms), "total": len(terms)}

    rec["vendors"] = vendors_state
    if all_done:
        rec["active"] = False
    state[scope] = rec
    _save(state)
    return True, out, all_done
