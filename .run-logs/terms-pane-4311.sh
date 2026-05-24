#!/usr/bin/env bash
set +e
while true; do
  python3 - <<'PY'
import json
import urllib.request
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

def prioritize_terms(seq):
    patterns = [
        "motherboard cpu combo",
        "motherboard bundle",
        "cpu motherboard bundle",
        "pc build",
        "pc base unit",
        "desktop pc",
        "pc tower",
        "gaming pc",
    ]
    required = ["AMD Ryzen 7 7800X3D", "Ryzen 9 7900", "Ryzen 9 7900X"]
    out, seen = [], set()
    for t in required:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    for ptn in patterns:
        for t in seq:
            k = t.lower()
            if k in seen:
                continue
            if ptn in k:
                seen.add(k)
                out.append(t)
    for t in seq:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out

def classify_status(item):
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    new = int((item or {}).get("new") or 0)
    if err:
        if "retry" in err or "blocked" in err:
            return "retry"
        return "error"
    if found > 0 or new > 0:
        return "success"
    return "no_data"

base_url = "http://andromeda-ts:4311"
keywords, items = [], []
try:
    with urllib.request.urlopen(f"{base_url}/api/config/search", timeout=4) as r:
        cfg = json.load(r) or {}
    keywords = [str(k).strip() for k in (cfg.get("keywords") or []) if str(k).strip()]
    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/recent", timeout=4) as r:
        payload = json.load(r) or {}
    items = payload.get("items", []) or []
except Exception:
    keywords, items = [], []

keywords = prioritize_terms(keywords)
state_by_term = {}
for it in items:
    term = str((it or {}).get("term") or "").strip()
    if not term:
        continue
    if term not in state_by_term:
        state_by_term[term] = classify_status(it)

styles = {
    "success": "green",
    "error": "red",
    "retry": "yellow",
    "no_data": "white",
}

txt = Text()
for idx, term in enumerate(keywords):
    st = state_by_term.get(term, "no_data")
    txt.append(term, style=styles.get(st, "white"))
    if idx < len(keywords) - 1:
        txt.append(", ", style="white")

console = Console()
console.clear()
console.print(Panel(txt, title="Search Terms", border_style="bright_blue"))
PY
  sleep 4
done
