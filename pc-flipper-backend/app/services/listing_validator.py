"""
Listing Validator Service - Filter out false positives before database ingestion.

Rejects:
- PC games and software
- Game expansion packs
- PC peripherals (mice, keyboards, monitors)
- Single components (RAM sticks, PSUs, cases alone)
- Non-PC items that contain "PC" in title

Allows:
- Complete PC systems
- Barebone systems
- Systems with sufficient core components
"""

import re
import structlog
from dataclasses import dataclass
from typing import Optional

log = structlog.get_logger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool
    rejection_reason: Optional[str] = None
    false_positive_type: Optional[str] = None


# Patterns that REJECT a listing (non-PC items)
REJECT_PATTERNS = [
    # Game titles and expansions
    r"\bpc\s+(?:game|cd-?rom|dvd)\b",
    r"\bgame\b.*\bpc\b",
    r"(?:expansion|addon|dlc|pack)\b.*\bpc\b",
    r"\bsoftware\b",
    r"\bos\b.*\bwindows|linux|mac",

    # Peripherals
    r"\b(mouse|keyboard|monitor|headset|speaker|webcam|controller|gamepad|joystick|throttle)\b",
    r"\bgaming\s+(chair|desk|headphone)",
    r"\b(hdmi|displayport|vga|dvi)\s+(?:cable|adapter|converter)",

    # Single components
    r"\bram\s+(?:stick|module|dimm)",
    r"\b(?:256mb|512mb|1gb|2gb|4gb|8gb|16gb|32gb|64gb|128gb)\s+ram\b",
    r"(?:ddr[1-5]|lpddr)[^a-z].*ram",
    r"\bgraphics?\s+card\b",
    r"\bgpu\b",
    r"\bpower\s+(?:supply|pack|unit|psu)",
    r"\bpsu\b",
    r"\bpc\s+case\b",
    r"\bcomputer\s+case\b",
    r"\bchassis\b",
    r"\bhard\s+drive\b",
    r"\bssd\b.*\s(?:512gb|1tb|2tb|4tb)",  # Single drive
    r"\bnvme\b",
    r"\bmotherboard\b",
    r"\bcpu\b.*\s(?:processor|intel|amd)",

    # Vague PC references that aren't systems
    r"^\s*pc\s*$",
    r"^\s*computer\s*$",
    r"^\s*desktop\s*$",
    r"^\s*tower\s*$",
    r"^\s*system\s*$",
    r"^\s*old\s+(?:pc|computer|desktop)",
]

# Patterns that ALLOW a listing (likely valid PCs)
ALLOW_PATTERNS = [
    # Complete systems / brands
    r"\b(?:dell|hp|lenovo|acer|asus|msi|corsair|ibm|gateway)\b.*pc",
    r"\b(?:optiplex|elitedesk|thinkcentre|prodesk|esprimo|veriton)\b",
    r"\b(?:gaming|workstation|server)\s+pc\b",
    r"\bpc\s+(?:build|tower|desktop|system|computer)",
    r"\bbarebones?\b",
    r"(?:intel|amd).{0,30}(?:i[3579]|xeon|ryzen).{0,30}(?:pc|computer|desktop|system)",
]

# Keywords that MUST be present for ambiguous listings
REQUIRED_SYSTEM_COMPONENTS = [
    r"\b(?:intel|amd|processor|cpu)\b",
    r"\b(?:i[3579]|xeon|ryzen|pentium|athlon|fx)\b",
]


def validate_listing(
    title: str,
    description: str = "",
    cpu: Optional[str] = None,
    has_gpu: bool = False,
    has_psu: bool = False,
) -> ValidationResult:
    """
    Validate that a listing is actually a PC system, not a game or peripheral.

    Args:
        title: Listing title
        description: Listing description (optional)
        cpu: Extracted CPU (from spec parser)
        has_gpu: Whether GPU was detected
        has_psu: Whether PSU was detected

    Returns:
        ValidationResult with is_valid bool and optional rejection_reason
    """
    text = (title + " " + description).lower().strip()

    # Check explicit rejection patterns (games, peripherals, single components)
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            reason = _get_rejection_reason(pattern)
            log.info(
                "listing_validator.rejected",
                title=title[:80],
                pattern=pattern[:50],
                reason=reason,
            )
            return ValidationResult(
                is_valid=False,
                rejection_reason=reason,
                false_positive_type=_categorize_false_positive(pattern),
            )

    # Check explicit allow patterns (strong indicators of valid PC)
    for pattern in ALLOW_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            log.info("listing_validator.allowed_by_pattern", title=title[:80])
            return ValidationResult(is_valid=True)

    # For ambiguous listings, require CPU or system component keywords
    has_required_component = any(
        re.search(pattern, text, re.IGNORECASE) for pattern in REQUIRED_SYSTEM_COMPONENTS
    )

    if not has_required_component and not cpu:
        log.warning(
            "listing_validator.rejected_ambiguous",
            title=title[:80],
            reason="No CPU or system component detected in title",
        )
        return ValidationResult(
            is_valid=False,
            rejection_reason="No CPU or system component detected",
            false_positive_type="ambiguous",
        )

    # Require at least some system indicators
    if not title_has_system_indicator(text):
        log.warning(
            "listing_validator.rejected_no_system_indicator",
            title=title[:80],
            cpu=cpu,
        )
        return ValidationResult(
            is_valid=False,
            rejection_reason="No system/PC indicator in title",
            false_positive_type="incomplete_system",
        )

    # Passed all checks
    log.info("listing_validator.passed", title=title[:80], cpu=cpu)
    return ValidationResult(is_valid=True)


def title_has_system_indicator(text: str) -> bool:
    """
    Check if title has indicators of being a complete/partial system.

    Args:
        text: Lowercase title text

    Returns:
        bool indicating presence of system indicator
    """
    system_indicators = [
        r"\bpc\b",
        r"\bcomputer\b",
        r"\bdesktop\b",
        r"\btower\b",
        r"\bworkstation\b",
        r"\bgaming\s+pc\b",
        r"\bbarebones?\b",
        r"dell optiplex|dell poweredge|hp elitedesk|hp prodesk|lenovo thinkcentre",
    ]

    return any(re.search(indicator, text, re.IGNORECASE) for indicator in system_indicators)


def _get_rejection_reason(pattern: str) -> str:
    """Map rejection pattern to human-readable reason."""
    reasons = {
        "game": "Game or software, not a PC system",
        "expansion": "Game expansion pack, not a PC system",
        "peripheral": "PC peripheral, not a system",
        "mouse": "Input device, not a PC",
        "keyboard": "Input device, not a PC",
        "monitor": "Monitor, not a PC",
        "ram": "Memory module, not a complete system",
        "graphics card": "GPU only, not a complete system",
        "power supply": "PSU only, not a complete system",
        "case": "Case only, not a complete system",
        "motherboard": "Motherboard only, not a complete system",
        "hard drive": "Storage only, not a complete system",
    }

    for key, reason in reasons.items():
        if key in pattern.lower():
            return reason

    return "Item does not match PC system criteria"


def _categorize_false_positive(pattern: str) -> str:
    """Categorize the type of false positive detected."""
    if "game" in pattern.lower() or "cd-rom" in pattern.lower():
        return "game"
    elif any(x in pattern.lower() for x in ["mouse", "keyboard", "monitor", "headset"]):
        return "peripheral"
    elif any(x in pattern.lower() for x in ["ram", "gpu", "graphics", "cpu", "motherboard"]):
        return "single_component"
    else:
        return "other"


def validate_batch(listings: list[dict], log_stats: bool = True) -> tuple[list[dict], dict]:
    """
    Validate a batch of listings.

    Args:
        listings: List of listing dicts with title, description, cpu, has_gpu, has_psu
        log_stats: Whether to log summary statistics

    Returns:
        Tuple of (valid_listings, stats_dict)
    """
    valid = []
    stats = {
        "total": len(listings),
        "valid": 0,
        "rejected": 0,
        "rejections_by_type": {},
    }

    for listing in listings:
        result = validate_listing(
            title=listing.get("title", ""),
            description=listing.get("description", ""),
            cpu=listing.get("cpu"),
            has_gpu=bool(listing.get("gpu")),
            has_psu=listing.get("has_psu", True),
        )

        if result.is_valid:
            valid.append(listing)
            stats["valid"] += 1
        else:
            stats["rejected"] += 1
            ftype = result.false_positive_type or "unknown"
            stats["rejections_by_type"][ftype] = stats["rejections_by_type"].get(ftype, 0) + 1

    if log_stats:
        pct_valid = (stats["valid"] / stats["total"] * 100) if stats["total"] > 0 else 0
        log.info(
            "listing_validator.batch_complete",
            total=stats["total"],
            valid=stats["valid"],
            rejected=stats["rejected"],
            valid_pct=f"{pct_valid:.1f}%",
            rejections_by_type=stats["rejections_by_type"],
        )

    return valid, stats
