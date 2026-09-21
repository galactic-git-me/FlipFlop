"""
Star Trek ship naming for curated playbooks.

Maps customer types × tiers to starship names:
- Base tier = ship name (e.g., "Miranda")
- Mid-range = ship name + " Pro" (e.g., "Miranda Pro")
- High-end = ship name + " Ultra" (e.g., "Miranda Ultra")

Configuration in data/ship_names.json allows names to be changed without code changes.
"""
import json
from pathlib import Path
from typing import Optional


def _load_ship_names() -> dict:
    """Load ship names configuration from data/ship_names.json"""
    config_path = Path(__file__).resolve().parents[2] / 'data' / 'ship_names.json'
    if not config_path.exists():
        # Fallback default mapping if file missing
        return {
            "tier_suffixes": {
                "Budget": "",
                "Mid-range": " Pro",
                "High-end": " Ultra"
            },
            "ship_names": {
                "AI Workstation": {"base_name": "Enterprise"},
                "High-performance Gaming": {"base_name": "Defiant"},
                "Great-value Gaming": {"base_name": "Miranda"},
                "Student Hybrid": {"base_name": "Voyager"},
                "Business & Office": {"base_name": "Excelsior"},
                "Content Creation": {"base_name": "Galaxy"},
                "Software Development": {"base_name": "Titan"},
                "Family & Home": {"base_name": "Stargazer"},
            }
        }
    
    return json.loads(config_path.read_text(encoding='utf-8'))


def get_ship_name(segment: str, tier: str) -> str:
    """
    Get the ship name for a curated build.
    
    Args:
        segment: Customer type (e.g., "Great-value Gaming")
        tier: Tier (Budget, Mid-range, High-end)
    
    Returns:
        Ship name with appropriate suffix (e.g., "Miranda", "Miranda Pro", "Miranda Ultra")
    
    Examples:
        >>> get_ship_name("Great-value Gaming", "Budget")
        'Miranda'
        >>> get_ship_name("Great-value Gaming", "Mid-range")
        'Miranda Pro'
        >>> get_ship_name("AI Workstation", "High-end")
        'Enterprise Ultra'
    """
    config = _load_ship_names()
    
    ship_config = config.get("ship_names", {}).get(segment)
    if not ship_config:
        # Fallback: use segment name if no ship name configured
        return segment
    
    base_name = ship_config.get("base_name", segment)
    suffix = config.get("tier_suffixes", {}).get(tier, "")
    
    return f"{base_name}{suffix}"


def get_ship_display_name(build_id: str, segment: str, tier: str) -> str:
    """
    Get the display name for a curated build, handling special cases.
    
    Args:
        build_id: Curated build ID (e.g., "FF-AIW-03")
        segment: Customer type
        tier: Tier
    
    Returns:
        Display name (e.g., "Miranda Pro", or special case handling)
    """
    config = _load_ship_names()
    
    # Check for special case overrides (e.g., FF-AIW-03 bespoke)
    special_cases = config.get("special_cases", {})
    if build_id in special_cases:
        return special_cases[build_id].get("display_name", get_ship_name(segment, tier))
    
    return get_ship_name(segment, tier)


def get_ship_metadata(segment: str) -> Optional[dict]:
    """
    Get metadata about a ship (series, description).
    
    Args:
        segment: Customer type
    
    Returns:
        Dict with base_name, series, description, or None if not found
    """
    config = _load_ship_names()
    return config.get("ship_names", {}).get(segment)


def enrich_curated_build_with_ship_name(build: dict) -> dict:
    """
    Add ship_name and ship_display_name fields to a curated build dict.
    
    Args:
        build: Curated build dict with 'id', 'segment', and 'tier'
    
    Returns:
        Same dict with added 'ship_name' and 'ship_display_name' fields
    """
    build_id = build.get("id", "")
    segment = build.get("segment", "")
    tier = build.get("tier", "")
    
    build["ship_name"] = get_ship_name(segment, tier)
    build["ship_display_name"] = get_ship_display_name(build_id, segment, tier)
    
    # Add ship metadata for rich display
    ship_meta = get_ship_metadata(segment)
    if ship_meta:
        build["ship_series"] = ship_meta.get("series")
        build["ship_description"] = ship_meta.get("description")
    
    return build


def get_tier_display_name(tier: str) -> str:
    """
    Get friendly tier display name for UI.
    
    Args:
        tier: Tier (Budget, Mid-range, High-end)
    
    Returns:
        Display name (Base, Pro, Ultra)
    """
    tier_map = {
        "Budget": "Base",
        "Mid-range": "Pro",
        "High-end": "Ultra"
    }
    return tier_map.get(tier, tier)
