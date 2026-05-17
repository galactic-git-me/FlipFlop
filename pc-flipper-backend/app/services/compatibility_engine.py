from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CompatibilityResult:
    compatible: bool
    confidence: float
    hard_fail_reasons: list[str]
    warnings: list[str]


_GPU_TDP = {
    "gtx 1060": 120,
    "gtx 1650": 75,
    "gtx 1660": 125,
    "rtx 2060": 160,
    "rtx 2070": 175,
    "rtx 2080": 215,
    "rtx 3060": 170,
    "rtx 3070": 220,
    "rtx 3080": 320,
    "rtx 4060": 115,
    "rx 570": 150,
    "rx 580": 185,
    "rx 6600": 132,
    "rx 6700 xt": 230,
    "rx 7600": 165,
}

_SOCKET_HINTS = {
    "i7-8": "lga1151",
    "i7-9": "lga1151",
    "i7-10": "lga1200",
    "i7-11": "lga1200",
    "i7-12": "lga1700",
    "i7-13": "lga1700",
    "i7-14": "lga1700",
    "ryzen 5 3": "am4",
    "ryzen 5 5": "am4",
    "ryzen 7 5": "am4",
    "ryzen 7 7": "am5",
    "ryzen 7 9": "am5",
    "ryzen 9 7": "am5",
    "ryzen 9 9": "am5",
}


def _norm(s: str) -> str:
    return (s or "").lower().strip()


def _gpu_tdp_from_text(text: str) -> int | None:
    t = _norm(text)
    for key, tdp in _GPU_TDP.items():
        if key in t:
            return tdp
    return None


def _extract_psu_watts(text: str) -> int | None:
    t = _norm(text)
    m = re.search(r"(\d{3,4})\s*w", t)
    if not m:
        return None
    w = int(m.group(1))
    if 150 <= w <= 1600:
        return w
    return None


def _extract_ram_type(text: str) -> str | None:
    t = _norm(text)
    if "ddr5" in t:
        return "ddr5"
    if "ddr4" in t:
        return "ddr4"
    return None


def _infer_cpu_socket(text: str) -> str | None:
    t = _norm(text)
    if "lga1700" in t:
        return "lga1700"
    if "lga1200" in t:
        return "lga1200"
    if "lga1151" in t:
        return "lga1151"
    if "am5" in t:
        return "am5"
    if "am4" in t:
        return "am4"

    for hint, socket in _SOCKET_HINTS.items():
        if hint in t:
            return socket
    return None


def evaluate_build_compatibility(base_spec: str, upgrades: list[dict], constraints: list[str]) -> CompatibilityResult:
    hard_fail_reasons: list[str] = []
    warnings: list[str] = []

    base = _norm(base_spec)
    constraints_text = " | ".join((_norm(c) for c in constraints))
    upgrades_text = " | ".join(_norm(u.get("item", "")) for u in upgrades)

    # 1) PSU headroom for target GPU
    gpu_tdp = _gpu_tdp_from_text(upgrades_text)
    psu_w = _extract_psu_watts(base + " | " + upgrades_text + " | " + constraints_text)
    if gpu_tdp:
        recommended = gpu_tdp + 220
        if psu_w is not None and psu_w < recommended:
            hard_fail_reasons.append(
                f"PSU likely insufficient ({psu_w}W) for target GPU load (~{recommended}W recommended)."
            )
        elif psu_w is None:
            warnings.append("PSU wattage unknown; cannot guarantee GPU stability under load.")

    # 2) RAM generation mismatch (DDR5 requirement on known DDR4-era base)
    ram_type = _extract_ram_type(upgrades_text + " | " + constraints_text)
    if ram_type == "ddr5":
        if any(x in base for x in ["optiplex 70", "optiplex 50", "elitedesk 800 g4", "elitedesk 800 g5", "i7-8", "i7-9", "i5-8", "i5-9"]):
            hard_fail_reasons.append("DDR5 requirement conflicts with likely DDR4-era base platform.")

    # 3) Socket/gen mismatch signals
    socket_needed = _infer_cpu_socket(upgrades_text + " | " + constraints_text)
    base_socket = _infer_cpu_socket(base)
    if socket_needed and base_socket and socket_needed != base_socket:
        hard_fail_reasons.append(
            f"CPU/platform socket mismatch: base suggests {base_socket.upper()} but build requires {socket_needed.upper()}."
        )
    elif socket_needed and not base_socket:
        warnings.append("Base platform socket unclear; compatibility confidence reduced.")

    # 4) Form factor risk
    if "itx" in constraints_text and any(x in base for x in ["tower", "mid tower", "full tower", "optiplex", "elitedesk"]):
        warnings.append("ITX constraint may conflict with common OEM tower chassis dimensions.")

    # Confidence model
    confidence = 0.75
    if warnings:
        confidence -= min(0.25, 0.08 * len(warnings))
    if hard_fail_reasons:
        confidence -= min(0.35, 0.12 * len(hard_fail_reasons))
    confidence = max(0.1, min(0.99, confidence))

    return CompatibilityResult(
        compatible=len(hard_fail_reasons) == 0,
        confidence=round(confidence, 2),
        hard_fail_reasons=hard_fail_reasons,
        warnings=warnings,
    )
