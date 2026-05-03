"""
Extracts structured specs from a raw listing title + description.
Pure regex/heuristics — fast and runs offline.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedSpecs:
    cpu: Optional[str] = None
    ram_gb: Optional[int] = None
    ram_type: Optional[str] = None
    storage_gb: Optional[int] = None
    storage_type: Optional[str] = None
    gpu: Optional[str] = None
    has_psu: bool = True


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

    return specs
