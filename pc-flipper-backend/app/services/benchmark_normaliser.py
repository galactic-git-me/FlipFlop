"""
Normalises messy component model strings to canonical slugs.
Used by scraper, benchmark lookup, gem scoring, and listing generator.
"""
import re

_RYZEN_MODEL_PREFIXES = {
    "3": ("3100", "3300", "3600"),
    "5": ("5600", "5700", "7600", "7500"),
    "7": ("5700", "5800", "7700", "7800"),
    "9": ("5900", "5950", "7900", "7950", "9900", "9950"),
}


def _slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def _resolve_bare_cpu_model(model: str) -> str | None:
    """Try to resolve a bare model number like '7800X3D' to a full AMD slug."""
    # Strip spaces so '7800 X3D' becomes '7800x3d' for prefix matching
    m = model.lower().replace(' ', '')
    for series, prefixes in _RYZEN_MODEL_PREFIXES.items():
        for prefix in prefixes:
            if m.startswith(prefix):
                return f"amd_ryzen_{series}_{_slug(model.replace(' ', ''))}"
    return None


_CPU_PATTERNS = [
    # Intel patterns first (more specific)
    (re.compile(r'(?:intel\s+)?(?:core\s+)?i([3579])[- ](\d{4,5}[a-z0-9]*)', re.I),
     lambda m: f"intel_core_i{m.group(1)}_{_slug(m.group(2))}"),
    (re.compile(r'(?:intel\s+)?xeon\s+([a-z0-9-]+)', re.I),
     lambda m: f"intel_xeon_{_slug(m.group(1))}"),
    # AMD Ryzen with explicit series (e.g. "Ryzen 7 7800X3D", "R7 7800X3D")
    (re.compile(r'(?:amd\s+)?(?:ryzen\s+|r)(\d)\s+(\d{4}[a-z0-9 ]*)', re.I),
     lambda m: f"amd_ryzen_{m.group(1)}_{_slug(m.group(2).strip())}"),
    (re.compile(r'(?:amd\s+)?(?:ryzen\s+)?threadripper\s+(?:pro\s+)?(\d{4}[a-z0-9]*)', re.I),
     lambda m: f"amd_threadripper_{_slug(m.group(1))}"),
    # Bare model number (e.g. "7800 X3D", "7800X3D")
    (re.compile(r'\b(\d{4}[a-z0-9 ]{1,8})\b', re.I),
     lambda m: _resolve_bare_cpu_model(m.group(1))),
]


def normalise_cpu(raw: str) -> str:
    """Return a canonical CPU slug or the cleaned input if no pattern matched."""
    s = raw.strip()
    for pattern, builder in _CPU_PATTERNS:
        match = pattern.search(s)
        if match:
            result = builder(match)
            if result:
                return result
    return _slug(s)


def _ti_super_suffix(raw: str) -> str:
    r = raw.lower()
    if " ti" in r or "-ti" in r:
        return "_ti"
    if "super" in r:
        return "_super"
    return ""


_GPU_PATTERNS = [
    (re.compile(r'(?:nvidia\s+)?(?:geforce\s+)?(?:rtx|gtx)\s*(\d{4})(?:\s*ti)?(?:\s*super)?', re.I),
     lambda m, raw: f"nvidia_geforce_{'rtx' if 'rtx' in raw.lower() else 'gtx'}_{m.group(1)}{_ti_super_suffix(raw)}"),
    (re.compile(r'(?:amd\s+)?(?:radeon\s+)?rx\s*(\d{4})(?:\s*xt)?', re.I),
     lambda m, raw: f"amd_radeon_rx_{m.group(1)}{'_xt' if 'xt' in raw.lower() else ''}"),
    # Bare NVIDIA number (e.g. "3070 8GB") — match before AMD bare number
    (re.compile(r'\b(3\d{3}|4\d{3}|10\d{2}|16\d{2}|20\d{2})\b'),
     lambda m, raw: f"nvidia_geforce_{'rtx' if int(m.group(1)) >= 2000 else 'gtx'}_{m.group(1)}{_ti_super_suffix(raw)}"),
    # Bare AMD RX number (5xxx, 6xxx, 7xxx GPU range)
    (re.compile(r'\b([5-7]\d{3})\b'),
     lambda m, raw: f"amd_radeon_rx_{m.group(1)}{'_xt' if 'xt' in raw.lower() else ''}"),
]


def normalise_gpu(raw: str) -> str:
    s = raw.strip()
    for pattern, builder in _GPU_PATTERNS:
        match = pattern.search(s)
        if match:
            return builder(match, s)
    return _slug(s)


_CAPACITY_RE = re.compile(r'(\d+)\s*(tb|gb)', re.I)


def normalise_storage(raw: str) -> str:
    s = raw.strip()
    cap_match = _CAPACITY_RE.search(s)
    cap = ""
    if cap_match:
        val, unit = cap_match.group(1), cap_match.group(2).lower()
        cap = f"_{val}{unit}"
        s = s[:cap_match.start()] + s[cap_match.end():]
    base = _slug(re.sub(r'\b(nvme|m\.?2|sata|ssd|hdd|drive|solid|state)\b', '', s, flags=re.I))
    base = re.sub(r'_+', '_', base).strip('_')
    return f"{base}{cap}" if cap else base


def normalise_ram(raw: str) -> str:
    return _slug(raw)


_CPU_HINTS = re.compile(
    r'\b(ryzen|intel|core\s+i[3579]|xeon|threadripper|athlon|celeron|pentium|i[3579][- ]\d{4})\b', re.I
)
_GPU_HINTS = re.compile(
    r'\b(rtx|gtx|radeon|geforce|rx\s*\d{4}|quadro|tesla\s+[a-z]|a\d{4})\b', re.I
)
_STORAGE_HINTS = re.compile(
    r'\b(ssd|nvme|m\.2|sata\s+ssd|hdd|hard\s+drive|evo|nand|970|870|sn\d{3})\b', re.I
)
_RAM_HINTS = re.compile(
    r'\b(ddr[345]|dimm|sodimm|\d+gb\s+(?:ddr|ram)|ram\s+\d+gb|\d+x\d+gb)\b', re.I
)


def detect_component_type(raw: str) -> str:
    """Return 'cpu' | 'gpu' | 'storage' | 'ram' | 'unknown'."""
    if _CPU_HINTS.search(raw):
        return "cpu"
    if _GPU_HINTS.search(raw):
        return "gpu"
    if _STORAGE_HINTS.search(raw):
        return "storage"
    if _RAM_HINTS.search(raw):
        return "ram"
    return "unknown"
