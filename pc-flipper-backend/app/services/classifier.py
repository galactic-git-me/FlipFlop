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
    "high end": -15,
    "mint condition": -5,
    "boxed": -5,
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
    # RAM / memory sticks
    "ram stick", "memory stick", "ddr4 ram", "ddr5 ram", "dimm", "sodimm",
    "16gb ram", "32gb ram", "8gb ram",
    # Motherboards
    "motherboard", "mainboard",
    # PSUs (standalone)
    "power supply unit", "psu only", "modular psu",
    # Peripherals / monitors — not flippable PCs
    "monitor", "keyboard", "mouse", "headset", "webcam", "microphone",
    "speakers", "gaming chair",
    # Laptop/console parts
    "laptop battery", "laptop screen", "laptop keyboard",
    # Games (video games, board games, not gaming PCs)
    "video game", "board game", "card game", "console game", "nintendo", "playstation", "xbox",
    "ps4", "ps5", "switch", "retro game", "atari", "sega",
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
    is_component_only = (
        any(h in title_lower for h in _COMPONENT_ONLY_HINTS)
        and not any(h in title_lower for h in _COMPLETE_PC_HINTS)
    )
    if is_component_only:
        result.classification = Classification.overpriced
        result.signals.append("component-only listing")
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
