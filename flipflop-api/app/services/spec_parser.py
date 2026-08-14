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
    gpu: Optional[str] = None
    # RAM fields
    ram_gb: Optional[int] = None
    ram_type: Optional[str] = None
    ram_brand: Optional[str] = None
    ram_model: Optional[str] = None
    ram_speed: Optional[int] = None
    ram_cl: Optional[int] = None
    ram_sticks: Optional[int] = None
    # Storage fields
    storage_gb: Optional[int] = None
    storage_type: Optional[str] = None
    storage_brand: Optional[str] = None
    storage_model: Optional[str] = None
    storage_form_factor: Optional[str] = None
    # PSU fields
    psu_included: bool = True
    psu_brand: Optional[str] = None
    psu_wattage: Optional[int] = None
    psu_rating: Optional[str] = None
    # Case fields
    case_brand: Optional[str] = None
    case_model: Optional[str] = None
    case_form_factor: Optional[str] = None
    case_color: Optional[str] = None
    # Validation
    is_likely_valid_pc: bool = True
    validation_reason: Optional[str] = None


CPU_PATTERNS = [
    # Intel Core Ultra (the newest naming scheme, replacing "Core iX" for
    # Meteor Lake/Arrow Lake — "Core Ultra 5 245KF", "Core Ultra 9 285K")
    # must be checked before the legacy "Core iX" pattern below, since a
    # listing can contain both "Core" and "Ultra" and the older pattern's
    # `core\s+` group would otherwise still be present without matching the
    # actual model number.
    r"(intel\s+)?core\s+ultra\s+[3579]\s+\d{3}[a-z]*",
    # Intel Core
    r"(intel\s+)?(core\s+)?(i[3579][-\s]?\d{4,5}[a-z]*)",
    r"(intel\s+)?(pentium|celeron)\s+[a-z]?\d{4}",
    # Xeon — the pattern used to require the model code directly after
    # "xeon", but sampled titles often insert "Core" in between ("Xeon Core
    # W3680"); `(?:core\s+)?` makes that optional without weakening the
    # match for the far more common "Xeon E5-2680" / "Xeon W-2295" phrasing.
    r"(intel\s+)?(xeon\s+(?:core\s+)?[a-z]?\d[-\s]?\w+)",
    # AMD Ryzen. Suffix was `[a-z]*` (letters only), which truncated the X3D
    # (3D V-Cache) variant down to just "X" — "7800X3D" and "7800X" are
    # different, differently-priced products, but the regex silently
    # treated them as the same model. Try the literal "x3d" suffix first,
    # falling back to a plain letter-run for every other suffix (X, G, GE,
    # etc.) — same coverage as before for everything that isn't X3D.
    # `(?:pro\s+)?` accounts for the Ryzen PRO line ("Ryzen 7 Pro 4750G"),
    # which otherwise breaks the tight tier-number -> model-number adjacency
    # this pattern relies on.
    r"(amd\s+)?(ryzen\s+[3579]\s+(?:pro\s+)?\d{4}(?:x3d|[a-z]+)?)",
    # AMD Threadripper (HEDT line — "Threadripper 2970WX", "Threadripper
    # PRO 5995WX") has no single-digit tier number like Ryzen, so it needs
    # its own pattern rather than an extension of the one above.
    r"(amd\s+)?threadripper\s*(?:pro\s*)?\d{4}[a-z]*",
    # FX-series historically used a hyphen ("FX-8350"), which the previous
    # `\s+` (whitespace-only) requirement never matched — same bug class as
    # the AM4/AM3+ CPU-model hyphen gaps found elsewhere in this pipeline.
    r"(amd\s+)?(athlon|fx)[-\s]+\d+",
]

GPU_PATTERNS = [
    r"(rtx\s*\d{4}(?:\s*ti)?(?:\s*super)?(?:\s*\d+gb)?)",
    r"(gtx\s*\d{3,4}(?:\s*ti)?(?:\s*\d+gb)?)",
    r"(geforce\s*(?:rtx|gtx)?\s*\d{3,4}(?:\s*ti)?(?:\s*super)?)",   # GeForce 2060, GeForce RTX 3060
    r"(\d{3,4}\s*(?:nvidia\s*)?geforce(?:\s*(?:rtx|gtx))?)",          # 2060 Nvidia Geforce, 2060 Geforce
    r"(rx\s*\d{3,4}(?:\s*xt)?(?:\s*\d+gb)?)",
    r"(radeon\s+[a-z]+\s*\d+(?:\s*xt)?)",
    r"(quadro\s+[a-z]?\d+)",
    r"(arc\s+[ab]\d{3}(?:\s*\d+gb)?)",                                # Intel Arc A380, B580
    # Older/entry-level NVIDIA GeForce GT-series (no X) — GT 710, GT 1030.
    # Safe from colliding with the GTX pattern above (tried first anyway):
    # "gt" here must be followed directly by whitespace/digits, which can
    # never happen in "GTX 3060" since the literal "x" sits in between.
    r"(\bgt\s*\d{3,4}(?:\s*\d+gb)?)",
]

RAM_PATTERN = r"(\d+)\s*gb\s*(ddr[345]?(?:-?\d+)?|lpddr\d?)?\s*(ram|memory|dimm|ecc)?"
STORAGE_PATTERN = r"(\d+\.?\d*)\s*(tb|gb)\s*(nvme|m\.?2|ssd|hdd|sata|hard drive)?"

# Brand/model databases (for high-confidence extraction)
RAM_BRANDS = {"corsair", "kingston", "g.skill", "crucial", "team", "mushkin", "patriot", "adata", "sk hynix", "samsung", "intel", "hp", "dell"}
RAM_MODELS = {"vengeance", "fury", "dominator", "ripjaws", "trident", "value", "ballistix", "elite"}

STORAGE_BRANDS = {"samsung", "western digital", "wd", "sk hynix", "crucial", "intel", "kingston", "sabrent", "mushkin", "adata", "toshiba", "seagate"}
STORAGE_MODELS = {"970 evo", "860 evo", "red", "blue", "black", "sn850", "firecuda", "barracuda", "pro", "plus"}

PSU_BRANDS = {"corsair", "evga", "seasonic", "thermaltake", "msi", "asus", "cooler master", "lian li", "noctua", "gigabyte", "asrock"}
PSU_RATINGS = {"80+ platinum", "80+ gold", "80+ silver", "80+ bronze"}

CASE_BRANDS = {"lian li", "nzxt", "corsair", "cooler master", "fractal design", "be quiet", "phanteks", "thermaltake", "in win", "antec", "corsair", "aerocool", "silverstone"}
CASE_FORM_FACTORS = {"atx", "matx", "itx", "eatx", "mini-itx", "compact", "sff", "cube"}

NO_STORAGE_SIGNALS = ["no hdd", "no hard drive", "no storage", "no ssd", "no drive"]
NO_GPU_SIGNALS = ["no gpu", "no graphics", "no graphics card", "integrated only"]
NO_PSU_SIGNALS = ["no psu", "no power supply", "no power", "no psu included"]


def _extract_ram_details(text: str) -> tuple[Optional[str], Optional[str], Optional[int], Optional[int], Optional[int]]:
    """Extract RAM brand, model, speed, CL, and stick count from text."""
    brand = None
    model = None
    speed = None
    cl = None
    sticks = None

    # Brand detection
    for b in RAM_BRANDS:
        if b in text:
            brand = b.title()
            break

    # Model detection (look for brand-specific patterns after brand name)
    for m in RAM_MODELS:
        if m in text:
            model = m.title()
            break

    # Speed pattern: "6000", "5600", "3200" followed by optional "MHz"
    speed_match = re.search(r"(\d{3,5})\s*(?:mhz)?(?:\s+mhz)?", text)
    if speed_match:
        potential_speed = int(speed_match.group(1))
        if 1600 <= potential_speed <= 7200:
            speed = potential_speed

    # CAS Latency pattern: "CL16", "CL18", "CAS 16", etc.
    cl_match = re.search(r"cl\s*(\d+)|cas\s*(\d+)|cas\s+latency\s+(\d+)", text, re.IGNORECASE)
    if cl_match:
        cl = int(cl_match.group(1) or cl_match.group(2) or cl_match.group(3))

    # Stick count: "2x8GB", "4x16GB", "2 sticks", "dual channel" etc.
    sticks_match = re.search(r"(\d)x(\d+)gb|(\d)\s+(?:x\s+)?(\d+)\s*gb", text, re.IGNORECASE)
    if sticks_match:
        sticks = int(sticks_match.group(1) or sticks_match.group(3))

    return brand, model, speed, cl, sticks


def _extract_storage_details(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract storage brand, model, and form factor from text."""
    brand = None
    model = None
    form_factor = None

    # Brand detection
    for b in STORAGE_BRANDS:
        if b in text:
            brand = b.title()
            break

    # Model detection
    for m in STORAGE_MODELS:
        if m in text:
            model = m.title()
            break

    # Form factor: M.2, SATA, 2.5", 3.5", NVMe
    if "m.2" in text or "m2" in text:
        form_factor = "M.2"
    elif "2.5" in text or "2.5\"" in text:
        form_factor = "2.5\""
    elif "3.5" in text or "3.5\"" in text:
        form_factor = "3.5\""
    elif "u.2" in text:
        form_factor = "U.2"

    return brand, model, form_factor


def _extract_psu_details(text: str) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """Extract PSU brand, wattage, and rating from text."""
    brand = None
    wattage = None
    rating = None

    # Brand detection
    for b in PSU_BRANDS:
        if b in text:
            brand = b.title()
            break

    # Wattage: "750W", "1000W", "850 watts", etc.
    wattage_match = re.search(r"(\d{3,4})\s*(?:w|watts?)", text, re.IGNORECASE)
    if wattage_match:
        wattage = int(wattage_match.group(1))

    # Rating: "80+ Gold", "80+ Silver", "80+ Bronze", "Platinum"
    if "platinum" in text:
        rating = "80+ Platinum"
    elif "80+ gold" in text or "80+gold" in text:
        rating = "80+ Gold"
    elif "80+ silver" in text or "80+silver" in text:
        rating = "80+ Silver"
    elif "80+ bronze" in text or "80+bronze" in text:
        rating = "80+ Bronze"

    return brand, wattage, rating


def _extract_case_details(text: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Extract case brand, model, form factor, and color from text."""
    brand = None
    model = None
    form_factor = None
    color = None

    # Brand detection
    for b in CASE_BRANDS:
        if b in text:
            brand = b.title()
            break

    # Common case models (after brand is detected or standalone)
    case_models_patterns = {
        "o11": "O11 Vision",
        "o11 vision": "O11 Vision",
        "h510": "H510",
        "crystal": "Crystal Series",
        "nr200": "NR200",
        "meshify": "Meshify",
        "evolv": "Evolv",
        "torrent": "Torrent",
        "noctua": "Noctua",
    }
    for pattern, readable in case_models_patterns.items():
        if pattern in text:
            model = readable
            break

    # Form factor detection
    for ff in CASE_FORM_FACTORS:
        if ff in text:
            form_factor = ff.upper()
            break

    # Color detection
    colors = ["black", "white", "red", "blue", "green", "grey", "gray", "silver", "gold", "transparent", "tempered glass"]
    for c in colors:
        if c in text:
            color = c.title()
            break

    return brand, model, form_factor, color


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

    # RAM details: brand, model, speed, CL, sticks
    specs.ram_brand, specs.ram_model, specs.ram_speed, specs.ram_cl, specs.ram_sticks = _extract_ram_details(text)

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

    # Storage details: brand, model, form_factor
    specs.storage_brand, specs.storage_model, specs.storage_form_factor = _extract_storage_details(text)

    # PSU
    if any(sig in text for sig in NO_PSU_SIGNALS):
        specs.psu_included = False

    # PSU details: brand, wattage, rating
    specs.psu_brand, specs.psu_wattage, specs.psu_rating = _extract_psu_details(text)

    # Case details: brand, model, form_factor, color
    specs.case_brand, specs.case_model, specs.case_form_factor, specs.case_color = _extract_case_details(text)

    # ─ Validation: Check if likely a valid PC (filter false positives)
    specs.is_likely_valid_pc, specs.validation_reason = _validate_is_pc(title, text, specs)

    return specs


def validate_pc_listing(title: str, description: str = "") -> tuple[bool, Optional[str]]:
    """
    Public validation function to check if a listing is a valid PC.
    Can be called from any ingestion pipeline.

    Returns:
        Tuple of (is_valid, rejection_reason)
    """
    text = (title + " " + description).lower()
    is_valid, reason = _validate_is_pc(title, text, ParsedSpecs())
    if not is_valid:
        log.warning("listing.validation_failed", title=title[:80], reason=reason)
    return is_valid, reason


def _validate_is_pc(title: str, text_lower: str, specs: "ParsedSpecs") -> tuple[bool, Optional[str]]:
    """
    Quick validation to filter obvious false positives (games, peripherals).
    Returns (is_valid, rejection_reason).
    """
    # Reject PC CD-ROM / DVD game listings (eBay format: "Title---Game---PC CD")
    if "pc cd" in text_lower or "pc dvd" in text_lower or "mac cd" in text_lower:
        return False, "PC CD/DVD game listing"

    # Reject games and software
    if "cd-rom" in text_lower:
        return False, "CD-ROM listing — not a PC"
    if "expansion pack" in text_lower or "---game" in text_lower or "game---" in text_lower:
        return False, "Game listing"

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
