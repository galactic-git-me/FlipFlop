"""
Classification Engine — scores listings and assigns gem classification.
Uses rule-based heuristics. No ML needed at this stage.
"""
import re
from dataclasses import dataclass, field
from app.models.listing import Classification


GEM_SIGNALS = {
    # Title signals (high value)
    "no hdd": 25,
    "no hard drive": 25,
    "no storage": 20,
    "no gpu": 20,
    "no graphics": 15,
    "untested": 20,
    "collection only": 15,
    "for parts": 20,
    "spares or repair": 20,
    "poor condition": 10,
    "no psu": 15,
    "no power supply": 15,
    "faulty": 10,
    "as is": 10,
    "no os": 5,
    "no ram": 15,

    # ── Brand workstations (office clearance gold) ────────────────────────────
    # These are quality platforms that IT departments dump cheaply.
    # Typically Xeon/i7/i9 + no GPU = easy profitable upgrade.
    "elitedesk": 15,
    "optiplex": 15,
    "thinkcentre": 15,
    "thinkstation": 20,
    "hp workstation": 20,
    "dell workstation": 20,
    "hp z240": 20,
    "hp z440": 25,
    "hp z640": 25,
    "hp z420": 20,
    "hp z620": 25,
    "dell precision": 20,
    "prodesk": 12,
    "esprimo": 12,
    "veriton": 10,

    # ── Clearance / distress source signals ──────────────────────────────────
    "ex office": 15,
    "office clearance": 20,
    "it clearance": 20,
    "job lot": 15,
    "quick sale": 10,
    "need gone": 15,
    "clearing out": 10,
    "no longer needed": 10,
    "collect today": 15,
}

NEGATIVE_SIGNALS = {
    "monitor included": -5,
    "keyboard and mouse": -5,
    "gaming setup": -10,
    "gaming pc": -10,       # complete gaming rig — seller has priced in GPU value
    "gaming desktop": -10,
    "rgb gaming": -8,
    "high end": -15,
    "mint condition": -5,
    "complete pc": -10,
    "full build": -10,
    "full setup": -10,
    "boxed": -5,
    "brand new": -10,
    "sealed": -10,
    "rtx 4090": -20,        # top-end GPU — already priced at premium
    "rtx 4080": -15,
    "rx 7900": -15,
    # Already-upgraded / pre-built signals — seller has added value, margin is gone
    "upgraded": -20,
    "custom build": -20,
    "custom built": -20,
    "hand built": -15,
    "self build": -15,
    "self built": -15,
    "ready to game": -15,
    "ready to play": -10,
    "gaming beast": -15,
    "budget gaming": -10,
    "great for gaming": -10,
    "perfect for gaming": -10,
    "includes gpu": -15,
    "with gpu": -10,
    "comes with gpu": -15,
    "installed gpu": -15,
    "added gpu": -15,
    "upgraded gpu": -20,
    "upgraded ram": -15,
    "upgraded storage": -10,
    "with graphics card": -15,
}

POOR_TITLE_PATTERNS = [
    r"^pc$",
    r"^old pc$",
    r"^computer$",
    r"^desktop$",
    r"^tower$",
    r"^pc tower$",
    r"selling pc",
    r"unwanted pc",
]

_AM4_HINTS = ("am4", "b450", "b550", "x470", "x570")
_AM5_HINTS = ("am5", "b650", "x670", "a620")

# Maps component hint substrings to their PartCategory value.
# Order matters — first match wins.
_COMPONENT_CATEGORY_MAP: list[tuple[tuple[str, ...], str]] = [
    (("graphics card", "video card", "gpu only", "geforce rtx", "geforce gtx",
      "radeon rx graphics", "nvidia rtx graphics", "nvidia gtx graphics"), "gpu"),
    ((" cpu", " processor", "bare cpu", "cpu only", "no motherboard"), "cpu"),
    ((" ssd", "solid state drive", "nvme drive", "m.2 drive", " hdd ", "hard drive",
      "hard disk", '2.5" drive', '3.5" drive'), "ssd"),
    (("ram stick", "memory stick", "ddr4 ram", "ddr5 ram", "dimm", "sodimm",
      "16gb ram", "32gb ram", "8gb ram"), "ram"),
    (("motherboard", "mainboard"), "motherboard"),
    (("power supply unit", "psu only", "modular psu"), "psu"),
    (("keyboard", "mouse", "headset", "headphones", "earphones", "earbuds",
      "webcam", "microphone", "speakers", "gaming chair", "monitor",
      "mousepad", "mouse pad", "desk chair"), "accessory"),
]

# Keywords that mark a listing as a bare component rather than a complete PC.
# These listings don't fit the flip model.
_COMPONENT_ONLY_HINTS = (
    # CPUs
    " cpu", " processor", "bare cpu", "cpu only", "no motherboard",
    # GPUs / graphics cards — specific enough that they only appear in component listings
    "graphics card", "video card", "gpu only", "geforce rtx", "geforce gtx",
    "radeon rx graphics", "nvidia rtx graphics", "nvidia gtx graphics",
    # Storage drives (standalone)
    " ssd", "solid state drive", "nvme drive", "m.2 drive", " hdd ", "hard drive",
    "hard disk", "2.5\" drive", "3.5\" drive",
    # RAM / memory sticks — standalone modules, server RAM, ECC/registered
    "ram stick", "memory stick", "ddr4 ram", "ddr5 ram", "dimm", "sodimm",
    "16gb ram", "32gb ram", "8gb ram", "64gb ram",
    "server ram", "server memory", "ecc ram", "ecc registered", "ecc reg",
    "registered ram", "rdimm", "lrdimm", "udimm",
    "pc4-", "pc3-", "pc5-",          # raw JEDEC memory part numbers
    "mt/s",                           # memory speed unit (only in RAM listings)
    "hma", "m393", "m471", "mta36",   # Samsung/Micron/SK Hynix RAM part number prefixes
    # Motherboards and component bundles
    "motherboard", "mainboard",
    "cpu bundle", "mobo bundle", "pc bundle",   # bundles of parts, not complete PCs
    # PSUs (standalone)
    "power supply unit", "psu only", "modular psu",
    # Peripherals / monitors — not flippable PCs
    "monitor", "keyboard", "mouse", "headset", "headphones", "headphone",
    "earphones", "earphone", "earbuds", "earbud", "in-ear", "over-ear",
    "wireless headphones", "gaming headset", "stereo headphones",
    "webcam", "microphone", "mic stand", "speakers", "speaker system",
    "gaming chair", "desk chair", "mousepad", "mouse pad",
    # Laptops and AIOs — not flippable under desktop model
    "laptop", "notebook", "chromebook", "macbook", "thinkpad", "ideapad",
    "elitebook", "probook", "latitude", "zenbook", "vivobook",
    "surface laptop", "surface pro", "surface book",
    "xps 13", "xps 15", "xps 17",
    "precision 5570", "precision 5580", "precision 7570", "precision 7670", "precision 7770",
    "yoga", "legion 5", "legion 7", "legion slim", "flex 5",
    "omen 15", "omen 16", "omen 17",
    "spectre x360", "envy x360", "rog zephyrus", "rog strix g",
    "nitro 5", "predator helios",
    "all-in-one", "all in one", "aio pc", "aio desktop", "imac", "eliteone",
    # Laptop/console parts
    "laptop battery", "laptop screen", "laptop keyboard",
    # Games (video games, board games, not gaming PCs)
    "video game", "board game", "card game", "console game", "nintendo", "playstation", "xbox",
    "ps4", "ps5", "switch", "retro game", "atari", "sega",
    # PC CD-ROM / DVD games — eBay game listings contain "PC CD" or "PC DVD"
    # These must come before _COMPLETE_PC_HINTS overrides them via "pc" substring.
    # Handled via _STRONG_COMPONENT_OVERRIDES below.
)

# These patterns are so specific to non-PC products that they override _COMPLETE_PC_HINTS
# even when the title contains "pc" (e.g. "PC CD", "PC RAM", "PC4-25600").
_STRONG_COMPONENT_SIGNALS = (
    # ── PC CD-ROM / DVD games ─────────────────────────────────────────────────
    # eBay game listings: "Finding Nemo---PC CD", "Age of Empires---PC DVD"
    "pc cd",              # "PC CD" suffix on game titles
    "pc dvd",             # "PC DVD" suffix on game titles
    "mac cd",             # "PC / Mac CD" multi-platform games
    "mac dvd",
    "cd-rom game",
    "dvd game",
    "expansion pack",     # game DLC / expansion — not a PC
    "---game",            # eBay game title pattern "Title---GAME---PC CD"
    "game---",
    " game pc cd",        # "action game pc cd"
    " game pc dvd",
    # ── GPU cards — titles like "GeForce 7900 GS ... Retro PC Gaming Graphics Card"
    # contain "pc" which overrides the _COMPONENT_ONLY_HINTS "graphics card" check.
    "graphics card",
    "video card",
    "gpu card",
    # ── Component bundles containing "pc" ─────────────────────────────────────
    "pc bundle",
    "mobo bundle",
    "cpu bundle",
    # ── External storage — "External Desktop HDD", etc. ──────────────────────
    "external hdd",
    "external hard drive",
    "external desktop hdd",
    "portable hard drive",
    "portable ssd",
    "usb hard drive",
    "external ssd",
    # ── All-in-ones ──────────────────────────────────────────────────────────
    "aio workstation",
    # ── RAM sticks ────────────────────────────────────────────────────────────
    # RAM titles routinely contain "pc" (PC4-25600, "Desktop PC RAM", "Gaming PC RAM")
    "desktop memory",
    "desktop ram",
    "pc ram",
    "pc memory",
    "memory kit",
    "ram kit",
    "ram memory",
    "gaming memory",
    "gaming ram",
    "(2x16gb)", "(2x8gb)", "(4x8gb)", "(4x16gb)", "(2x32gb)",
    "(2 x 16gb)", "(2 x 8gb)", "(4 x 8gb)", "(4 x 16gb)",
    "memory module",
    "288-pin",            # DDR4/5 DIMM pin spec
    "260-pin",            # SO-DIMM pin spec
    " cl16 ", " cl18 ", " cl22 ", " cl36 ", "cl16,", "cl18,", "cl22,",
)
_COMPLETE_PC_HINTS = (
    "pc", "desktop", "tower", "computer", "workstation", "system", "mini pc",
    # Brand workstations — always a complete unit
    "optiplex", "elitedesk", "thinkcentre", "thinkstation", "prodesk",
    "esprimo", "veriton", "dell precision", "hp z2", "hp z4", "hp z6",
)


@dataclass
class ScoringResult:
    score: float = 0.0
    signals: list[str] = field(default_factory=list)
    classification: Classification = Classification.unclassified


def score_listing(
    title: str,
    price: float,
    estimated_profit: float | None,
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    gpu: str | None,
    has_psu: bool,
    location: str | None,
    profit_low: float | None = None,   # conservative (25th-pct resale) profit
    profit_high: float | None = None,  # optimistic  (75th-pct resale) profit
    benchmark_data: dict | None = None,
) -> ScoringResult:
    result = ScoringResult()
    title_lower = title.lower()

    # Reject bare component listings — a CPU/processor without a PC body can't
    # be flipped under our model (missing motherboard, DDR5, etc.).
    # Strong RAM signals override _COMPLETE_PC_HINTS because RAM product titles
    # routinely contain "pc" (e.g. "PC4-25600", "Desktop PC RAM MEMORY").
    is_strong_ram = any(h in title_lower for h in _STRONG_COMPONENT_SIGNALS)
    is_component_only = is_strong_ram or (
        any(h in title_lower for h in _COMPONENT_ONLY_HINTS)
        and not any(h in title_lower for h in _COMPLETE_PC_HINTS)
    )
    if is_component_only:
        result.classification = Classification.overpriced
        result.signals.append("component-only listing")
        return result

    # Require at least some evidence this is a real PC.
    # A listing with no detected specs (no CPU, no GPU, no RAM, no storage)
    # and no known workstation brand in the title is likely a game, peripheral,
    # or bare mystery item — not a flippable PC.
    _KNOWN_BRANDS = (
        "elitedesk", "optiplex", "thinkcentre", "thinkstation", "prodesk",
        "esprimo", "veriton", "hp z2", "hp z4", "hp z6", "dell precision",
        "vostro", "hp elite", "lenovo", "dell", "hp ", "acer ", "asus ",
    )
    has_spec = cpu or gpu or ram_gb or storage_gb
    has_brand = any(b in title_lower for b in _KNOWN_BRANDS)
    if not has_spec and not has_brand:
        result.classification = Classification.unclassified
        return result

    # Gem signals from title
    for signal, pts in GEM_SIGNALS.items():
        if signal in title_lower:
            result.score += pts
            result.signals.append(signal)

    # Negative signals
    for signal, pts in NEGATIVE_SIGNALS.items():
        if signal in title_lower:
            result.score += pts

    # Poor title bonus
    for pattern in POOR_TITLE_PATTERNS:
        if re.search(pattern, title_lower):
            result.score += 15
            result.signals.append("poor title")
            break

    # No storage present
    if storage_gb is None or storage_gb == 0:
        result.score += 20
        result.signals.append("no storage")

    # No GPU
    if not gpu:
        result.score += 10
        result.signals.append("no gpu")

    # No PSU
    if not has_psu:
        result.score += 10
        result.signals.append("no psu")

    # DDR4 and DDR5 both score equally — DDR5 kit prices have normalised.
    if ram_type and ("ddr4" in ram_type.lower() or "ddr5" in ram_type.lower()):
        result.score += 10
        result.signals.append("ddr4/ddr5 value platform")

    if any(h in title_lower for h in _AM4_HINTS) or any(h in title_lower for h in _AM5_HINTS):
        result.score += 8
        result.signals.append("amd platform")


    # Collection-only location hints
    if location and any(x in location.lower() for x in ["only", "local"]):
        result.score += 5
        result.signals.append("collection only")

    # ── Estimated profit — dominant component ─────────────────────────────────
    # Weighted at 1.5× so a £200 flip outscores any title-signal noise.
    # Negative profit contributes nothing (clamped at 0).
    if estimated_profit is not None and estimated_profit > 0:
        profit_pts = estimated_profit * 1.5
        result.score += profit_pts
        result.signals.append(f"£{estimated_profit:.0f} profit")

    # Profit consistency bonus: tight spread = reliable estimate
    if (
        profit_low is not None
        and profit_high is not None
        and profit_low > 0
        and profit_high > 0
    ):
        spread_pct = (profit_high - profit_low) / max(profit_high, 1)
        if spread_pct < 0.20:
            result.score += 20
            result.signals.append("tight profit spread")
        elif spread_pct < 0.35:
            result.score += 10

    # ── Benchmark performance/£ bonus ────────────────────────────────────────
    if benchmark_data:
        cpu_ppp = benchmark_data.get("cpu_performance_per_pound") or 0
        cat_avg = benchmark_data.get("category_avg_ppp") or 0
        if cpu_ppp > 0 and cat_avg > 0:
            ratio = cpu_ppp / cat_avg
            if ratio >= 1.5:
                result.score += 30
                result.signals.append(f"performance/£ {ratio:.1f}x above average")
            elif ratio >= 1.25:
                result.score += 18
                result.signals.append(f"performance/£ {ratio:.1f}x above average")
            elif ratio >= 1.0:
                result.score += 8
                result.signals.append("performance/£ at market average")

    # Normalise raw score to 0–100.
    # Raw score without profit tops out at ~150; with £200+ profit it hits ~450.
    # Dividing by 4 maps £200-profit deals to ~90-100 and signal-only deals to 0-40.
    result.score = round(min(100.0, max(0.0, result.score / 4.0)), 1)

    # Classify from profit estimate (median) + conservative low for safety gate
    result.classification = _classify(result.score, estimated_profit, profit_low, price)
    return result


def _classify(
    score: float,
    estimated_profit: float | None,
    profit_low: float | None,
    price: float,
) -> Classification:
    # No estimate yet — fall back to signal score only (score is now 0–100)
    if estimated_profit is None:
        if score >= 15:
            return Classification.amazing_gem
        if score >= 10:
            return Classification.gem
        return Classification.unclassified

    profit = estimated_profit

    # ── Safety gate (CRITICAL) ────────────────────────────────────────────────
    # If the CONSERVATIVE (low / 25th-pct) resale scenario produces a loss,
    # this deal must be rejected regardless of the median profit.
    # A flip that relies on optimistic pricing to be profitable is not a flip —
    # it is a gamble.
    if profit_low is not None and profit_low < 0:
        # Median is still positive → borderline / risky
        if profit >= 0:
            return Classification.no_profit
        # Both low and median are losses
        return Classification.overpriced

    # ── Normal profit-based classification ───────────────────────────────────
    if profit >= 200:
        return Classification.amazing_gem
    if profit >= 100:
        return Classification.gem
    if profit >= 0:
        return Classification.already_flipped   # seller has priced it in
    if profit >= -30:
        return Classification.no_profit
    return Classification.overpriced


def detect_component_category(title: str) -> str | None:
    """
    Returns the PartCategory value string if the title is a standalone component
    that belongs in the parts catalogue rather than the flip_opportunities catalogue.
    Returns None if the listing looks like a complete PC.
    """
    t = title.lower()
    if any(h in t for h in _COMPLETE_PC_HINTS):
        return None
    for hints, category in _COMPONENT_CATEGORY_MAP:
        if any(h in t for h in hints):
            return category
    return None
