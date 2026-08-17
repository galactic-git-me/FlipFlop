"""
eBay Item Specifics Generator - Generate LLM-powered item specifics for eBay listings.

Generates Item Specifics (eBay's name for attributes) using ONLY eBay's prescribed values
for the "PC Desktops & All-in-Ones" category (179).

This ensures compliance with eBay's validation — each field's value must be from the
category's allowed list, not freeform text.
"""

import structlog
from typing import Optional, Dict, List
from app.models.manual_build import ManualBuild
from app.services.ai_service import chat as _ai_chat

log = structlog.get_logger(__name__)

# eBay's PC Desktops & All-in-Ones (category 179) Item Specifics
# These are the REQUIRED fields and the valid values for each
EBAY_PC_SPECIFICS = {
    "Brand": [
        "ASUS", "MSI", "Gigabyte", "ASRock", "Corsair", "Kingston", "Seagate",
        "Western Digital", "Samsung", "Intel", "AMD", "NVIDIA", "Noctua", "Cooler Master",
        "NZXT", "Thermaltake", "Seasonic", "Lian Li", "Fractal Design", "Be Quiet",
        "Dell", "HP", "Lenovo", "Apple", "Alienware", "Custom Build"
    ],
    "Type": [
        "Desktop PC", "All-in-One PC", "Compact/Mini PC", "Workstation", "Gaming PC"
    ],
    "Processor": [
        # Intel CPUs
        "Intel Core i9-14900K", "Intel Core i9-13900K", "Intel Core i7-14700K", "Intel Core i7-13700K",
        "Intel Core i5-14600K", "Intel Core i5-13600K", "Intel Xeon",
        # AMD CPUs
        "AMD Ryzen 9 7950X", "AMD Ryzen 9 7900X", "AMD Ryzen 7 7800X3D", "AMD Ryzen 7 5800X3D",
        "AMD Ryzen 5 5600X", "AMD Ryzen Threadripper", "AMD Ryzen Embedded",
        # Others
        "Other", "Unknown"
    ],
    "Processor Speed": [
        "2.0 GHz", "2.5 GHz", "3.0 GHz", "3.5 GHz", "4.0 GHz", "4.5 GHz", "5.0 GHz", "5.5 GHz+", "Variable"
    ],
    "RAM Size": [
        "2 GB", "4 GB", "8 GB", "16 GB", "32 GB", "64 GB", "128 GB", "256 GB+"
    ],
    "Maximum RAM Capacity": [
        "8 GB", "16 GB", "32 GB", "64 GB", "128 GB", "256 GB+"
    ],
    "Graphics Processing Type": [
        "Dedicated", "Integrated", "Hybrid"
    ],
    "GPU": [
        # NVIDIA
        "NVIDIA RTX 4090", "NVIDIA RTX 4080", "NVIDIA RTX 4070 Ti", "NVIDIA RTX 4070",
        "NVIDIA RTX 4060 Ti", "NVIDIA RTX 4060", "NVIDIA RTX 3090 Ti", "NVIDIA RTX 3090",
        "NVIDIA RTX 3080 Ti", "NVIDIA RTX 3080", "NVIDIA RTX 3070 Ti", "NVIDIA RTX 3070",
        # AMD
        "AMD Radeon RX 7900 XTX", "AMD Radeon RX 7900 XT", "AMD Radeon RX 6800 XT",
        # Intel
        "Intel Arc A770", "Intel Arc A750",
        # Integrated
        "Intel Iris Xe", "AMD Radeon Vega", "AMD Radeon Ryzen Graphics", "Intel UHD Graphics",
        # Integrated (Apple/other)
        "Integrated Graphics", "Other", "None"
    ],
    "Storage Type": [
        "SSD", "HDD", "Hybrid (SSD + HDD)"
    ],
    "SSD Capacity": [
        "120 GB", "256 GB", "512 GB", "1 TB", "2 TB", "4 TB", "8 TB+"
    ],
    "Hard Drive Capacity": [
        "500 GB", "1 TB", "2 TB", "4 TB", "6 TB", "8 TB", "10 TB", "12 TB+"
    ],
    "Operating System": [
        "Windows 11", "Windows 10", "Windows Server", "Linux", "macOS", "FreeBSD", "Other", "None"
    ],
    "Form Factor": [
        "Full Tower", "Mid Tower", "Mini Tower", "HTPC", "All-in-One", "Compact/Mini", "Small Form Factor", "Other"
    ],
    "Manufacturer Warranty": [
        "Yes", "No", "Seller Warranty", "Unknown"
    ],
    "Model": [
        "Custom Build", "OEM", "Prebuilt", "Unknown"
    ],
    "Most Suitable For": [
        "Gaming", "Video Editing", "3D Rendering", "Content Creation", "Professional Workstation",
        "General Computing", "Office Use", "Development", "Trading/Finance", "Other"
    ],
    "Features": [
        "RGB Lighting", "Overclockable", "Quiet Operation", "Liquid Cooling", "Wireless",
        "USB-C", "Thunderbolt", "Multiple Monitors Ready", "VR Ready"
    ],
    "Connectivity": [
        "Ethernet", "WiFi", "Bluetooth", "USB 3.1", "USB 3.2", "Thunderbolt 3", "Thunderbolt 4"
    ],
    "Colour": [
        "Black", "White", "Silver", "Blue", "Red", "RGB", "Other"
    ],
    "Country of Origin": [
        "China", "Taiwan", "South Korea", "Japan", "United States", "Unknown", "Other"
    ],
    "Release Year": [
        "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "2016", "2015", "2014", "Pre-2014"
    ],
}

# Aspects eBay treats as free text rather than a closed vocabulary — MPN is
# literally the manufacturer's own part number (infinite variability), and
# Series/Motherboard Model are open-ended product-line names. Unlike
# EBAY_PC_SPECIFICS above, these have no allowed-value list to validate
# against; _parse_and_validate_specifics just checks the LLM returned a
# non-empty string. Deliberately excludes Screen Size / Item Length / Item
# Width — those are genuine physical measurements of this specific build,
# not a classification an LLM can reliably infer from component names, and a
# wrong guessed measurement reaching a real listing is worse than omitting
# it for manual entry.
FREE_TEXT_ASPECTS = {"MPN", "Series", "Motherboard Model"}

# Required fields that must always be present
REQUIRED_ASPECTS = {"Brand", "Type"}

# eBay's own Item Specifics value length cap — confirmed via a real listing
# rejection (errorId 25002: "value ... is too long. Enter a value of no
# more than 65 characters"). Applies per-value, including free-text aspects.
EBAY_ASPECT_VALUE_MAX_LENGTH = 65

# Real per-aspect cardinality for category 179, fetched live from eBay's
# Taxonomy API (get_item_aspects_for_category) — confirmed the hard way via
# a second real listing rejection (errorId 25002: "Colour should contain
# only one value. Remove the extra values and try again."). Every aspect
# NOT listed here is itemToAspectCardinality: SINGLE — eBay rejects more
# than one value outright, it doesn't just take the first one. The bug this
# caught: "ChromaFlair (Metallic, colour-shifting blue-green-purple)" got
# blindly comma-split into two array entries (splitting on the comma
# *inside* the parentheses), which is exactly what a SINGLE-cardinality
# aspect can't accept.
EBAY_MULTI_VALUE_ASPECTS = {"Most Suitable For", "Features", "Connectivity", "MPN"}


def validate_aspects_for_ebay(aspects: Dict[str, List[str]]) -> List[str]:
    """Checks aspects against eBay's CONFIRMED real constraint: every value
    must fit eBay's 65-character cap (verified via an actual listing
    rejection — errorId 25002, "value ... is too long. Enter a value of no
    more than 65 characters"). Returns a list of human-readable problems;
    empty means it's safe to submit.

    Deliberately does NOT also require every closed-list aspect (GPU,
    Processor, etc.) to match EBAY_PC_SPECIFICS' hardcoded allowed-value
    list. That list is a manually curated subset (e.g. GPU only lists RTX
    3070 Ti/3080, not plain RTX 3070) for generation-time guidance, not a
    confirmed eBay-side enum — the one real rejection observed so far was
    about LENGTH, not an invalid enum value. Hard-blocking on vocabulary
    match here would reject accurate real values (a genuine "NVIDIA GeForce
    RTX 3070" or "Windows 11 Pro") on an unverified assumption, which is
    worse than the problem this function exists to catch.

    This exists because the admin UI's specifics editor is a plain text
    input per aspect (see EbaySpecificsSection.tsx) with no client-side
    length limit, and the old update_aspects endpoint persisted whatever
    was typed with no validation at all — a long freeform value (e.g.
    someone pasting a full port list into "Connectivity") would sit in the
    DB unnoticed until eBay's API rejected the listing at publish time.
    Call this both on save (update_aspects) and again right before posting
    (post_to_ebay), so a bad value is caught immediately rather than
    Also enforces cardinality (see EBAY_MULTI_VALUE_ASPECTS) — confirmed via
    a second real rejection, so this one IS a hard eBay-side constraint,
    unlike the vocabulary lists above.
    surfacing as a slow eBay round-trip error."""
    problems: List[str] = []
    for aspect, values in aspects.items():
        if aspect not in EBAY_PC_SPECIFICS and aspect not in FREE_TEXT_ASPECTS:
            continue  # unknown aspect keys are dropped elsewhere, not this function's concern
        if aspect not in EBAY_MULTI_VALUE_ASPECTS and len(values) > 1:
            problems.append(
                f"{aspect}: has {len(values)} values but eBay only accepts one for this field "
                f"({', '.join(values)})"
            )
        for value in values:
            if len(value) > EBAY_ASPECT_VALUE_MAX_LENGTH:
                problems.append(
                    f"{aspect}: value is {len(value)} characters, eBay allows at most "
                    f"{EBAY_ASPECT_VALUE_MAX_LENGTH} ({value[:40]}…)"
                )
    return problems


def _enforce_aspect_cardinality(aspect: str, values: List[str]) -> List[str]:
    """Return values in the shape accepted by eBay for this aspect.

    Generation is allowed to be lossy here: the model occasionally returns
    component manufacturers as several Brand values, or both SSD and HDD for
    Storage Type. eBay requires one array entry for those fields, so retain
    the model's best (first) choice. Manual edits remain strict and are
    rejected by ``validate_aspects_for_ebay`` instead of being silently
    changed.
    """
    if aspect not in EBAY_MULTI_VALUE_ASPECTS and len(values) > 1:
        log.warning(
            "ebay_specifics.extra_single_values_dropped",
            aspect=aspect,
            kept=values[0],
            dropped=values[1:],
        )
        return values[:1]
    return values


def repair_legacy_aspect_cardinality(
    aspects: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """Repair specifics saved before single-value validation existed.

    Brand and Storage Type have deterministic eBay-safe combined meanings.
    For any other legacy SINGLE aspect, retain the first (best-ranked) value.
    The returned dictionary is new so SQLAlchemy detects JSON changes.
    """
    repaired: Dict[str, List[str]] = {}
    for aspect, values in aspects.items():
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if aspect in EBAY_MULTI_VALUE_ASPECTS or len(cleaned) <= 1:
            repaired[aspect] = cleaned
        elif aspect == "Brand":
            repaired[aspect] = ["Custom Build"]
        elif aspect == "Storage Type" and {"SSD", "HDD"}.issubset(set(cleaned)):
            repaired[aspect] = ["Hybrid (SSD + HDD)"]
        else:
            repaired[aspect] = cleaned[:1]
    return repaired


async def generate_item_specifics(
    build: ManualBuild,
    selling_principles_text: str = "",
) -> Dict[str, List[str]]:
    """
    Generate eBay Item Specifics using LLM, ensuring all values are from eBay's allowed list.

    Args:
        build: ManualBuild object with components
        selling_principles_text: FlipFlop selling principles to inject context

    Returns:
        Dictionary of aspect_name -> [allowed_values], ready for eBay API submission
    """
    if not build.components:
        log.warning("ebay_specifics.no_components", build_id=build.id)
        return _get_default_specifics()

    # Build component summary for the LLM
    component_summary = _build_component_summary(build.components)

    # Format the allowed values as JSON for the LLM prompt
    allowed_values_json = _format_allowed_values(EBAY_PC_SPECIFICS)

    free_text_json = _format_allowed_values({k: "free text — infer from components, omit if unknown" for k in FREE_TEXT_ASPECTS})

    prompt = f"""You are an eBay listing expert. Generate Item Specifics (eBay's attributes) for a custom PC build.

CRITICAL: For every aspect in the "Allowed Item Specifics" list, you MUST only use values from its allowed list. Never invent values.

Build Components:
{component_summary}

{f"FlipFlop Selling Principles:{chr(10)}{selling_principles_text}" if selling_principles_text else ""}

Allowed Item Specifics and their valid values (closed list — pick from these only):
{allowed_values_json}

Free-text Item Specifics (no fixed list — write the actual value from the components, e.g. the exact CPU/GPU/motherboard part number or product line name; omit the key entirely if you genuinely can't infer it, do not guess):
{free_text_json}

Task:
1. Analyze the build components
2. For EACH closed-list aspect, select the BEST matching value(s) from its allowed list
3. For EACH free-text aspect, write the real value inferred from the components, or omit it
4. Always include Brand and Type (required by eBay)
5. If a component spec doesn't map to any allowed value, use "Other" or "Unknown"
6. Return ONLY valid JSON with no explanation

Cardinality rules:
- Brand is the brand of the complete PC, never a list of component brands. For a
  one-off assembled PC use "Custom Build".
- Storage Type must be exactly one value. If the PC contains both SSD and HDD,
  use the single allowed value "Hybrid (SSD + HDD)".
- Only Most Suitable For, Features, Connectivity, and MPN may contain multiple
  values. Every other aspect must contain exactly one value.

Return JSON format (example):
{{
  "Brand": ["ASUS"],
  "Type": ["Gaming PC"],
  "Processor": ["Intel Core i7-13700K"],
  "Processor Speed": ["5.0 GHz"],
  "RAM Size": ["32 GB"],
  "Graphics Processing Type": ["Dedicated"],
  "GPU": ["NVIDIA RTX 4070"],
  "Storage Type": ["SSD"],
  "SSD Capacity": ["1 TB"],
  "Operating System": ["Windows 11"],
  "Form Factor": ["Mid Tower"],
  "Manufacturer Warranty": ["Unknown"],
  "Most Suitable For": ["Gaming"],
  "Features": ["RGB Lighting", "Overclockable"],
  "Model": ["Custom Build"],
  "MPN": ["BX8071513700K"],
  "Series": ["ROG Strix"],
  "Motherboard Model": ["ASUS ROG Strix Z790-E"]
}}

Generate the JSON response now:"""

    try:
        response, model = await _ai_chat(prompt, [], None)
        specifics = _parse_and_validate_specifics(response)
        log.info("ebay_specifics.generated", build_id=build.id, count=len(specifics), model=model)
        return specifics
    except Exception as e:
        # TEMP DIAGNOSTIC: log.error() alone wasn't visibly reaching us while
        # chasing why the live admin backend (run_dev.py, reload=False) kept
        # returning the 5-field default when a standalone repro of this exact
        # call succeeded. Writes the full traceback to a file so it survives
        # even if this process's stdout/structlog output isn't being
        # captured anywhere we can read. Safe to delete once this is
        # resolved — see debug_ebay_specifics.log next to this file.
        import traceback
        from pathlib import Path
        debug_path = Path(__file__).parent / "debug_ebay_specifics.log"
        with open(debug_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- build_id={build.id} ---\n")
            f.write(traceback.format_exc())
        log.error("ebay_specifics.generation_failed", build_id=build.id, error=str(e))
        return _get_default_specifics()


def _build_component_summary(components: list) -> str:
    """Build a human-readable summary of components for LLM context."""
    summary = []
    for comp in components:
        if isinstance(comp, dict):
            name = comp.get("name", "Unknown")
            specs = comp.get("specs", {})
            if specs:
                spec_str = ", ".join([f"{k}: {v}" for k, v in specs.items()])
                summary.append(f"- {name}: {spec_str}")
            else:
                summary.append(f"- {name}")
    return "\n".join(summary) if summary else "No components specified"


def _format_allowed_values(specifics_dict: Dict) -> str:
    """Format the allowed values dict as readable JSON for LLM."""
    import json
    return json.dumps(specifics_dict, indent=2)


def _parse_and_validate_specifics(json_response: str) -> Dict[str, List[str]]:
    """
    Parse LLM response and validate that all values are from the allowed list.
    Falls back to sensible defaults if parsing fails.
    """
    import json

    try:
        # Extract JSON from response (LLM might include extra text)
        json_start = json_response.find("{")
        json_end = json_response.rfind("}") + 1
        if json_start == -1 or json_end <= json_start:
            log.warning("ebay_specifics.no_json_found_in_response")
            _write_debug_log("no_json_found", json_response)
            return _get_default_specifics()

        json_str = json_response[json_start:json_end]
        parsed = json.loads(json_str)

        # Validate and clean
        validated = {}
        for aspect, values in parsed.items():
            if aspect not in EBAY_PC_SPECIFICS and aspect not in FREE_TEXT_ASPECTS:
                log.warning("ebay_specifics.unknown_aspect", aspect=aspect)
                continue

            # Ensure values is a list
            if isinstance(values, str):
                values = [values]
            elif not isinstance(values, list):
                values = [str(values)]

            if aspect in FREE_TEXT_ASPECTS:
                # No allowed-value list to check against — just drop blanks.
                # If the LLM didn't have enough info it should have omitted
                # the key entirely (see prompt); an empty/whitespace value
                # here means it didn't, so skip the aspect rather than write
                # a blank spec.
                valid_values = [v.strip() for v in values if v and v.strip()]
                if not valid_values:
                    continue
            else:
                # Validate each value against allowed list
                allowed = EBAY_PC_SPECIFICS[aspect]
                valid_values = [v for v in values if v in allowed]

                if not valid_values:
                    log.warning("ebay_specifics.invalid_values", aspect=aspect, values=values, allowed=allowed)
                    # Use first allowed value as fallback
                    valid_values = [allowed[0]]

            validated[aspect] = _enforce_aspect_cardinality(aspect, valid_values)

        # Ensure required fields
        for req_aspect in REQUIRED_ASPECTS:
            if req_aspect not in validated:
                validated[req_aspect] = [EBAY_PC_SPECIFICS[req_aspect][0]]

        # Backfill every closed-list aspect the LLM simply didn't mention —
        # the prompt asks for all of them, but nothing enforces that in the
        # model's own output. Free-text aspects (MPN/Series/Motherboard
        # Model) are deliberately NOT backfilled here: there's no allowed
        # value to fall back to, and inventing one would be worse than
        # leaving it for the frontend to render as an empty, fillable row
        # (see EbaySpecificsSection/EBAY_ASPECT_FIELDS on the admin side).
        for aspect, allowed in EBAY_PC_SPECIFICS.items():
            if aspect not in validated:
                fallback = "Unknown" if "Unknown" in allowed else allowed[-1]
                validated[aspect] = [fallback]

        return validated

    except json.JSONDecodeError as e:
        log.error("ebay_specifics.json_parse_failed", error=str(e))
        _write_debug_log("json_decode_error", json_response, extra=str(e))
        return _get_default_specifics()


def _write_debug_log(reason: str, raw_response: str, extra: str = "") -> None:
    """TEMP DIAGNOSTIC — writes the raw LLM response that failed to parse to
    a file next to this module, so it survives even when this process's
    stdout/structlog output isn't visible to us. Safe to delete this
    function and its call sites once the live 5-field-default issue is
    resolved — see debug_ebay_specifics.log."""
    from pathlib import Path

    debug_path = Path(__file__).parent / "debug_ebay_specifics.log"
    with open(debug_path, "a", encoding="utf-8") as f:
        f.write(f"\n--- reason={reason} {extra} ---\n{raw_response!r}\n")


def _get_default_specifics() -> Dict[str, List[str]]:
    """Return sensible default specifics when generation fails entirely
    (AI unreachable, malformed response). Covers all closed-list aspects
    (not just a handful) so the admin page's full 24-field layout still has
    something in every row rather than only the ones a partial LLM response
    happened to include — free-text aspects (MPN/Series/Motherboard Model)
    are intentionally left out, same reasoning as the backfill in
    _parse_and_validate_specifics."""
    defaults = {
        "Brand": ["Custom Build"],
        "Type": ["Desktop PC"],
        "Model": ["Custom Build"],
        "Form Factor": ["Mid Tower"],
        "Operating System": ["Windows 11"],
    }
    for aspect, allowed in EBAY_PC_SPECIFICS.items():
        if aspect not in defaults:
            fallback = "Unknown" if "Unknown" in allowed else allowed[-1]
            defaults[aspect] = [fallback]
    return defaults
