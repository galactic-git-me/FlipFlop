"""Risk / trap detection (PRD §17). Each match produces an evidenced,
severity-rated flag rather than a single opaque score, so results stay
auditable (PRD §36) — no black-box risk number.
"""
from __future__ import annotations

import re

from .schemas import RiskFlag

# (code, severity, pattern) — ordered roughly by how often false-positives
# arise from an overly broad match; more specific patterns first.
_RISK_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("PARTS_ONLY", "high", re.compile(r"\bparts\s*only\b|\bfor\s*parts\b", re.IGNORECASE)),
    ("SPARES_OR_REPAIR", "high", re.compile(r"spares?\s*(or|/)?\s*repair", re.IGNORECASE)),
    ("NOT_WORKING", "high", re.compile(r"\bnot\s*working\b|\bfaulty\b|\bdefective\b", re.IGNORECASE)),
    ("NO_POWER", "high", re.compile(r"\bno\s*power\b|\bwon'?t\s*(power|turn)\s*on\b", re.IGNORECASE)),
    ("NO_DISPLAY", "high", re.compile(r"\bno\s*display\b|\bno\s*output\b|\bno\s*signal\b", re.IGNORECASE)),
    ("ARTIFACTING", "high", re.compile(r"\bartifact(ing)?\b", re.IGNORECASE)),
    ("OVERHEATING", "medium", re.compile(r"\boverheat(ing|s)?\b|\bthermal\s*throttl", re.IGNORECASE)),
    ("BIOS_LOCKED", "high", re.compile(r"\bbios\s*lock", re.IGNORECASE)),
    ("PASSWORD_LOCKED", "high", re.compile(r"\bpassword\s*lock|\bicloud\s*lock", re.IGNORECASE)),
    ("SOCKET_DAMAGE", "high", re.compile(r"\bsocket\s*damage|\bbent\s*pins?\b", re.IGNORECASE)),
    ("MISSING_BRACKET", "medium", re.compile(r"\bmissing\s*bracket|\bno\s*bracket\b", re.IGNORECASE)),
    ("MISSING_ACCESSORIES", "low", re.compile(r"\bmissing\s*(accessories|cables|box)\b|\bno\s*(box|manual)\b", re.IGNORECASE)),
    ("UNTESTED", "medium", re.compile(r"\buntested\b|\bnot\s*tested\b", re.IGNORECASE)),
    ("SOLD_AS_SEEN", "medium", re.compile(r"\bsold\s*as\s*seen\b", re.IGNORECASE)),
    ("NO_RETURNS", "low", re.compile(r"\bno\s*returns?\b", re.IGNORECASE)),
    ("JOB_LOT", "medium", re.compile(r"\bjob\s*lot\b|\bbundle\s*of\b", re.IGNORECASE)),
    ("INTERMITTENT", "medium", re.compile(r"\bintermittent\b", re.IGNORECASE)),
    ("PUMP_NOISE", "low", re.compile(r"\bpump\s*noise\b", re.IGNORECASE)),
    ("UNKNOWN_CONDITION", "low", re.compile(r"\bunknown\s*condition\b|\bunknown\s*if\s*working\b", re.IGNORECASE)),
    ("GOLD_RECOVERY", "high", re.compile(r"\bgold\s*recovery\b|\be-?waste\b", re.IGNORECASE)),
    ("NO_CHARGER", "low", re.compile(r"\bno\s*charger\b|\bno\s*psu\s*included\b", re.IGNORECASE)),
    ("NO_CABLES", "low", re.compile(r"\bno\s*cables?\b", re.IGNORECASE)),
    ("LIQUID_DAMAGE", "high", re.compile(r"\bliquid\s*damage\b|\bwater\s*damage\b", re.IGNORECASE)),
]

# Total penalty subtracted from the 0-10 deal score (PRD §15.2 "apply
# explicit risk penalties" after the weighted model). Capped so a single
# listing with many overlapping flags can't drive the score negative before
# clamping — clamping still applies downstream in scoring.py.
_SEVERITY_PENALTY = {"low": 0.2, "medium": 0.5, "high": 1.2}
_MAX_TOTAL_PENALTY = 4.0


def detect_risk_flags(title: str, condition_raw: str | None) -> list[RiskFlag]:
    haystack = f"{title} {condition_raw or ''}"
    flags: list[RiskFlag] = []
    seen_codes: set[str] = set()
    for code, severity, pattern in _RISK_PATTERNS:
        match = pattern.search(haystack)
        if match and code not in seen_codes:
            seen_codes.add(code)
            flags.append(RiskFlag(code=code, severity=severity, evidence=match.group(0)))
    return flags


def risk_penalty(flags: list[RiskFlag]) -> float:
    total = sum(_SEVERITY_PENALTY[f.severity] for f in flags)
    return round(min(total, _MAX_TOTAL_PENALTY), 2)
