"""
Extracts structured specs from a raw listing title + description.
Pure regex/heuristics — fast and runs offline.
Includes validation to filter out false positives (games, peripherals).
"""
import re
import structlog
from dataclasses import dataclass
from typing import Optional

log = structlog.get_logger(__name__)


@dataclass
class ParsedSpecs:
    cpu: Optional[str] = None
    ram_gb: Optional[int] = None
    ram_type: Optional[str] = None
    storage_gb: Optional[int] = None
    storage_type: Optional[str] = None
    gpu: Optional[str] = None
    has_psu: bool = True
    is_likely_valid_pc: bool = True  # Validation result
    validation_reason: Optional[str] = None  # Why it's invalid, if applicable


CPU_PATTERNS = [
    # Intel Core
    r"(intel\s+)?(core\s+)?(i[3579][-\s]?\d{4,5}[a-z]*)",
    r"(intel\s+)?(pentium|celeron)\s+[a-z]?\d{4}",
    r"(intel\s+)?(xeon\s+[a-z]?\d[-\s]?\w+)",
    # AMD Ryzen
    r"(amd\s+)?(ryzen\s+[3579]\s+\d{4}[a-z]*)",
    r"(amd\s+)?(athlon|fx)\s+\d+",
]

GPU_PATTERNS = [
    r"(gtx\s*\d{3,4}(?:\s*ti)?(?:\s*\d+gb)?)",
    r"(rtx\s*\d{4}(?:\s*ti)?(?:\s*super)?(?:\s*\d+gb)?)",
    r"(rx\s*\d{3,4}(?:\s*xt)?(?:\s*\d+gb)?)",
    r"(radeon\s+[a-z]+\s*\d+(?:\s*xt)?)",
    r"(quadro\s+[a-z]?\d+)",
]

RAM_PATTERN = r"(\d+)\s*gb\s*(ddr[345]?(?:-?\d+)?|lpddr\d?)?\s*(ram|memory|dimm|ecc)?"
STORAGE_PATTERN = r"(\d+\.?\d*)\s*(tb|gb)\s*(nvme|m\.?2|ssd|hdd|sata|hard drive)?"

NO_STORAGE_SIGNALS = ["no hdd", "no hard drive", "no storage", "no ssd", "no drive"]
NO_GPU_SIGNALS = ["no gpu", "no graphics", "no graphics card", "integrated only"]
NO_PSU_SIGNALS = ["no psu", "no power supply", "no power", "no psu included"]


def parse_specs(title: str, description: str = "") -> ParsedSpecs:
    text = (title + " " + description).lower()
    specs = ParsedSpecs()

    # CPU
    for pattern in CPU_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            specs.cpu = m.group(0).strip().title()
            break

    # GPU — check negative signals first
    has_no_gpu = any(sig in text for sig in NO_GPU_SIGNALS)
    if not has_no_gpu:
        for pattern in GPU_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                specs.gpu = m.group(0).strip().upper()
                break

    # RAM
    for m in re.finditer(RAM_PATTERN, text, re.IGNORECASE):
        gb = int(m.group(1))
        if 2 <= gb <= 256:
            specs.ram_gb = gb
            ram_type_raw = (m.group(2) or "").upper()
            if ram_type_raw:
                specs.ram_type = ram_type_raw.split("-")[0]  # DDR4 from DDR4-3200
            break

    # Storage — check negative signals first
    has_no_storage = any(sig in text for sig in NO_STORAGE_SIGNALS)
    if not has_no_storage:
        for m in re.finditer(STORAGE_PATTERN, text, re.IGNORECASE):
            val = float(m.group(1))
            unit = m.group(2).lower()
            stype = (m.group(3) or "").lower()
            gb = int(val * 1024) if unit == "tb" else int(val)
            if gb >= 32:
                specs.storage_gb = gb
                if "nvme" in stype or "m.2" in stype or "m2" in stype:
                    specs.storage_type = "nvme"
                elif "ssd" in stype:
                    specs.storage_type = "ssd"
                else:
                    specs.storage_type = "hdd"
                break

    # PSU
    if any(sig in text for sig in NO_PSU_SIGNALS):
        specs.has_psu = False

    # ─ Validation: Check if likely a valid PC (filter false positives)
    specs.is_likely_valid_pc, specs.validation_reason = _validate_is_pc(title, text, specs)

    return specs


def _validate_is_pc(title: str, text_lower: str, specs: "ParsedSpecs") -> tuple[bool, Optional[str]]:
    """
    Quick validation to filter obvious false positives (games, peripherals).
    Returns (is_valid, rejection_reason).
    """
    # Reject games and software
    game_indicators = [
        "game", "cd-rom", "dvd", "expansion", "addon", "dlc", "software",
        "windows", "linux", "os "
    ]
    if any(indicator in text_lower for indicator in game_indicators):
        if "cd-rom" in text_lower or "game" in text_lower:
            return False, "Likely a game or software, not a PC"

    # Reject obvious peripherals
    peripheral_keywords = [
        "mouse", "keyboard", "monitor", "headset", "speaker", "webcam",
        "controller", "gamepad", "joystick", "cable", "adapter"
    ]
    if any(keyword in text_lower for keyword in peripheral_keywords):
        return False, "Appears to be a peripheral, not a PC"

    # Reject single components when no other system indicators present
    single_component_patterns = [
        ("ram stick", "ram module", "dimm"),
        ("graphics card", "video card", "gpu"),
        ("power supply", "psu"),
        ("motherboard", "mainboard"),
        ("hard drive", "ssd drive", "nvme"),
    ]

    for pattern_group in single_component_patterns:
        if any(p in text_lower for p in pattern_group):
            # Only reject if no CPU and no system keywords
            if not specs.cpu and "pc" not in text_lower and "computer" not in text_lower:
                component_type = pattern_group[0]
                return False, f"Single component ({component_type}) without system indicators"

    # Require system indicator keywords
    system_keywords = ["pc", "computer", "desktop", "tower", "workstation", "gaming"]
    has_system_indicator = any(kw in text_lower for kw in system_keywords)

    # If no system indicator and no CPU, likely not a PC
    if not has_system_indicator and not specs.cpu:
        return False, "No PC or CPU indicators found"

    # Passed validation
    return True, None
