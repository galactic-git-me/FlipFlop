"""
Star Trek ship naming for curated playbooks.

PUBLIC DISPLAY (customer-facing):
- Budget tier = ship name only (e.g., "Reliant")
- Mid-range tier = ship name + " Pro" (e.g., "Reliant Pro")
- High-end tier = ship name + " Ultra" (e.g., "Reliant Ultra")

DO NOT use "Base" on customer-facing UI, listing packs, perf/spec HTML, or registration cards.
Internal data model can still use Budget/Mid-range/High-end.

Ship names stamped by BuildBot on all 24 playbooks:
- Latest: approval queue ids 122-145 (with display_name field, no "Base")
- Supersedes: ids 98-121 (deprecated - had "Base" naming)

Naming approach:
1. Prefer display_name field from approved playbook payload (BuildBot ids 122-145)
2. Fall back to ship_name from approved payload
3. Fall back to tmp/ship-name-map.json (BuildBot source of truth)
4. Fall back to data/ship_names.json (legacy config)
5. Compute from segment + tier

This ensures we use stamped names when available, but never break if fields missing.
"""
import json
from pathlib import Path
from typing import Optional


def _load_ship_name_map() -> dict:
    """
    Load ship name map - prefer BuildBot stamped version.
    
    Load order:
    1. tmp/ship-name-map.json (BuildBot source of truth, ids 122-145)
    2. data/ship_names.json (legacy config)
    3. Hardcoded fallback
    """
    # Try BuildBot stamped map first (source of truth)
    buildbot_map_path = Path(__file__).resolve().parents[2] / 'tmp' / 'ship-name-map.json'
    if buildbot_map_path.exists():
        return json.loads(buildbot_map_path.read_text(encoding='utf-8'))
    
    # Fall back to legacy config
    config_path = Path(__file__).resolve().parents[2] / 'data' / 'ship_names.json'
    if config_path.exists():
        return json.loads(config_path.read_text(encoding='utf-8'))
    
    # Hardcoded fallback if both missing
    return {
        "tier_suffixes": {
            "Budget": "",
            "Mid-range": " Pro",
            "High-end": " Ultra"
        },
        "segment_ships": {
            "Great-value Gaming": "Reliant",
            "High-performance Gaming": "Defiant",
            "Student Hybrid": "Voyager",
            "Business & Office": "Excelsior",
            "Content Creation": "Galaxy",
            "AI Workstation": "Enterprise",
            "Software Development": "Titan",
            "Family & Home": "Stargazer",
        }
    }


def get_ship_name_from_map(build_id: str) -> Optional[str]:
    """
    Get ship name directly from BuildBot map by build ID.
    
    Preferred method: read stamped ship_name from map.
    
    Args:
        build_id: Curated build ID (e.g., "FF-GVG-02")
    
    Returns:
        Ship name with tier suffix (e.g., "Reliant Pro") or None if not found
    """
    map_data = _load_ship_name_map()
    builds = map_data.get("builds", [])
    
    for build in builds:
        if build.get("id") == build_id:
            return build.get("ship_name")
    
    return None


def get_ship_name(segment: str, tier: str) -> str:
    """
    Get the ship name for a curated build by segment and tier.
    
    Falls back to computing ship name if not in map.
    
    Args:
        segment: Customer type (e.g., "Great-value Gaming")
        tier: Tier (Budget, Mid-range, High-end)
    
    Returns:
        Ship name with appropriate suffix (e.g., "Reliant", "Reliant Pro", "Reliant Ultra")
    
    Examples:
        >>> get_ship_name("Great-value Gaming", "Budget")
        'Reliant'
        >>> get_ship_name("Great-value Gaming", "Mid-range")
        'Reliant Pro'
        >>> get_ship_name("AI Workstation", "High-end")
        'Enterprise Ultra'
    """
    map_data = _load_ship_name_map()
    
    # Try to get base ship name from map
    segment_ships = map_data.get("segment_ships", {})
    ship_names_legacy = map_data.get("ship_names", {})
    
    base_name = segment_ships.get(segment)
    if not base_name and segment in ship_names_legacy:
        # Legacy format compatibility
        base_name = ship_names_legacy[segment].get("base_name")
    
    if not base_name:
        # Ultimate fallback: use segment name
        return segment
    
    # Apply tier suffix
    suffix = map_data.get("tier_suffixes", {}).get(tier, "")
    return f"{base_name}{suffix}"


def get_ship_display_name(build_id: str, segment: str, tier: str) -> str:
    """
    Get the display name for a curated build.
    
    Prefers stamped ship_name from BuildBot map, falls back to computed name.
    
    Args:
        build_id: Curated build ID (e.g., "FF-AIW-03")
        segment: Customer type
        tier: Tier
    
    Returns:
        Display name (e.g., "Reliant Pro", "Enterprise Ultra")
    """
    # First, try to get from BuildBot stamped map (preferred)
    stamped_name = get_ship_name_from_map(build_id)
    if stamped_name:
        return stamped_name
    
    # Fall back to computing from segment + tier
    return get_ship_name(segment, tier)


def get_ship_metadata(segment: str) -> Optional[dict]:
    """
    Get metadata about a ship (series, description).
    
    Args:
        segment: Customer type
    
    Returns:
        Dict with base_name, series, description, or None if not found
    """
    map_data = _load_ship_name_map()
    
    # Try legacy format first (has series/description)
    ship_names_legacy = map_data.get("ship_names", {})
    if segment in ship_names_legacy:
        return ship_names_legacy[segment]
    
    # Fall back to creating minimal metadata from segment_ships
    segment_ships = map_data.get("segment_ships", {})
    base_name = segment_ships.get(segment)
    if base_name:
        return {"base_name": base_name}
    
    return None


def enrich_curated_build_with_ship_name(build: dict) -> dict:
    """
    Add ship_name and ship_display_name fields to a curated build dict.
    
    Priority order for naming (BuildBot re-stamped playbooks with display_name):
    1. display_name field from approved payload (BuildBot ids 122-145, no "Base")
    2. ship_name field from approved payload (older payloads)
    3. Compute from map lookup or segment + tier
    
    Args:
        build: Curated build dict with 'id', 'segment', and 'tier'
    
    Returns:
        Same dict with added/preserved 'ship_name' and 'ship_display_name' fields
    """
    build_id = build.get("id", "")
    segment = build.get("segment", "")
    tier = build.get("tier", "")
    
    # Priority 1: display_name from BuildBot stamped payload (ids 122-145)
    if "display_name" in build and build["display_name"]:
        build["ship_name"] = build["display_name"]
        build["ship_display_name"] = build["display_name"]
    # Priority 2: ship_name already in build (from older payload)
    elif "ship_name" in build and build["ship_name"]:
        build["ship_display_name"] = build["ship_name"]
    # Priority 3: Compute from map or segment + tier
    else:
        computed_name = get_ship_display_name(build_id, segment, tier)
        build["ship_name"] = computed_name
        build["ship_display_name"] = computed_name
    
    # Add ship metadata for rich display (if available)
    ship_meta = get_ship_metadata(segment)
    if ship_meta:
        if "ship_series" not in build:
            build["ship_series"] = ship_meta.get("series")
        if "ship_description" not in build:
            build["ship_description"] = ship_meta.get("description")
    
    # Mark bespoke builds
    map_data = _load_ship_name_map()
    builds_list = map_data.get("builds", [])
    for map_build in builds_list:
        if map_build.get("id") == build_id and map_build.get("bespoke_consult"):
            build["bespoke_consult"] = True
            break
    
    return build


def get_tier_display_name(tier: str) -> str:
    """
    Get friendly tier display name for customer-facing UI.
    
    DO NOT use "Base" - Budget tier should just be the ship name without suffix.
    
    Args:
        tier: Tier (Budget, Mid-range, High-end)
    
    Returns:
        Display suffix for tier ("" for Budget, "Pro" for Mid-range, "Ultra" for High-end)
    
    Note:
        Budget tier returns empty string - display just the ship name.
        Mid-range returns "Pro" - display "{Ship} Pro"
        High-end returns "Ultra" - display "{Ship} Ultra"
    """
    tier_suffix_map = {
        "Budget": "",  # Just ship name, no "Base"
        "Mid-range": "Pro",
        "High-end": "Ultra"
    }
    return tier_suffix_map.get(tier, "")


def get_bot_approval_queue_id(build_id: str) -> Optional[int]:
    """
    Get the bot approval queue ID for a curated build.
    
    Ship names were stamped by BuildBot:
    - Latest: approval queue ids 122-145 (with display_name, no "Base")
    - Supersedes: ids 98-121 (deprecated)
    Pricing approved sells are on ids 66-89.
    
    Args:
        build_id: Curated build ID (e.g., "FF-GVG-02")
    
    Returns:
        Bot approval queue ID or None if not found
    """
    map_data = _load_ship_name_map()
    builds = map_data.get("builds", [])
    
    for build in builds:
        if build.get("id") == build_id:
            return build.get("bot_approval_queue_id")
    
    return None
