from __future__ import annotations

import re
from dataclasses import dataclass


TYPE_TO_SLOT = {
    "cpu": "CPU", "gpu": "GPU", "ram": "RAM", "motherboard": "Motherboard",
    "ssd": "Storage", "storage": "Storage", "psu": "PSU", "case": "PC Case",
    "cooler": "CPU Cooler", "fan": "Case Fans", "os": "Operating System",
}


@dataclass
class CompatibilityResult:
    compatible: bool
    confidence: str
    reasons: list[str]
    warnings: list[str]


def _socket(text: str) -> str | None:
    value = text.lower()
    explicit = re.search(r"\b(am[45]|lga\s?1(?:151|200|700|851))\b", value)
    if explicit:
        return explicit.group(1).replace(" ", "")
    ryzen = re.search(r"\b(?:ryzen\s+[3579]\s+)?(\d{4})[a-z0-9]*\b", value)
    if ryzen and "ryzen" in value:
        generation = int(ryzen.group(1)[0])
        return "am5" if generation >= 7 else "am4"
    intel = re.search(r"\bi[3579][\s-]?(\d{4,5})[a-z]*\b", value)
    if intel:
        number = int(intel.group(1))
        generation = number // 1000 if number < 10000 else number // 1000
        if generation <= 9: return "lga1151"
        if generation <= 11: return "lga1200"
        if generation <= 14: return "lga1700"
    chipset_sockets = {
        "a320": "am4", "b350": "am4", "x370": "am4", "b450": "am4", "x470": "am4", "a520": "am4", "b550": "am4", "x570": "am4",
        "a620": "am5", "b650": "am5", "x670": "am5", "x870": "am5", "b850": "am5",
        "h310": "lga1151", "b360": "lga1151", "z370": "lga1151", "z390": "lga1151",
        "h410": "lga1200", "b460": "lga1200", "z490": "lga1200", "b560": "lga1200", "z590": "lga1200",
        "h610": "lga1700", "b660": "lga1700", "z690": "lga1700", "b760": "lga1700", "z790": "lga1700",
    }
    return next((socket for chipset, socket in chipset_sockets.items() if chipset in value), None)


def _ram_generation(text: str) -> str | None:
    match = re.search(r"\bddr\s?([345])\b", text.lower())
    return f"ddr{match.group(1)}" if match else None


def _watts(text: str) -> int | None:
    matches = [int(value) for value in re.findall(r"\b(\d{3,4})\s*w(?:att)?s?\b", text.lower())]
    return max(matches) if matches else None


def _gpu_min_watts(text: str) -> int | None:
    value = text.lower().replace(" ", "")
    bands = [
        (("4090", "5090"), 850), (("4080", "5080", "7900xtx"), 750),
        (("4070ti", "5070ti", "3090", "3080", "7900xt"), 700),
        (("4070", "5070", "7800xt", "6900xt"), 650),
        (("4060ti", "5060ti", "3070", "6800xt"), 600),
        (("4060", "5060", "3060", "6700xt"), 550),
    ]
    return next((watts for models, watts in bands if any(model in value for model in models)), None)


def check_component(build_components: list[dict], candidate_type: str, candidate_name: str) -> CompatibilityResult:
    names = {str(component.get("slot", "")).lower(): str(component.get("name", "")) for component in build_components}
    reasons: list[str] = []
    warnings: list[str] = []
    compatible = True

    if candidate_type in {"cpu", "motherboard"}:
        counterpart = names.get("motherboard" if candidate_type == "cpu" else "cpu")
        if counterpart:
            candidate_socket, other_socket = _socket(candidate_name), _socket(counterpart)
            if candidate_socket and other_socket:
                compatible = candidate_socket == other_socket
                (reasons if compatible else warnings).append(
                    f"CPU socket {candidate_socket.upper()} {'matches' if compatible else 'does not match'} {other_socket.upper()}"
                )
            else:
                warnings.append("CPU socket could not be confirmed from one or both product names")

    if candidate_type in {"ram", "motherboard"}:
        counterpart = names.get("motherboard" if candidate_type == "ram" else "ram")
        if counterpart:
            candidate_ram, other_ram = _ram_generation(candidate_name), _ram_generation(counterpart)
            if candidate_ram and other_ram:
                matches = candidate_ram == other_ram
                compatible = compatible and matches
                (reasons if matches else warnings).append(
                    f"Memory generation {candidate_ram.upper()} {'matches' if matches else 'does not match'} {other_ram.upper()}"
                )
            else:
                warnings.append("RAM generation could not be confirmed from one or both product names")

    if candidate_type in {"psu", "gpu"}:
        gpu_name = candidate_name if candidate_type == "gpu" else names.get("gpu", "")
        psu_name = candidate_name if candidate_type == "psu" else names.get("psu", "")
        minimum, available = _gpu_min_watts(gpu_name), _watts(psu_name)
        if minimum and available:
            matches = available >= minimum
            compatible = compatible and matches
            (reasons if matches else warnings).append(
                f"{available}W PSU {'meets' if matches else 'is below'} the estimated {minimum}W GPU requirement"
            )
        elif gpu_name and psu_name:
            warnings.append("PSU headroom could not be confirmed from the product names")

    if candidate_type == "motherboard":
        case_name = names.get("pc case") or names.get("case")
        if case_name:
            board = candidate_name.lower()
            case = case_name.lower()
            if "atx" in board and any(size in case for size in ("mini itx", "itx only")):
                compatible = False
                warnings.append("ATX motherboard does not fit the selected ITX case")

    confidence = "high" if reasons and not warnings else "medium" if reasons else "low"
    return CompatibilityResult(compatible=compatible, confidence=confidence, reasons=reasons, warnings=warnings)
