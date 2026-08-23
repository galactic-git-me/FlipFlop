"""
Feature flags for gating new features and experimental behavior.

Flags are resolved from environment variables (prefixed with FEATURE_).
Safe defaults disable risky operations (email, publish) in all environments.
Production enables them only when explicitly configured.

Usage:
    from app.services.feature_flags import is_enabled

    if is_enabled("price_alerts_email"):
        await send_price_alert_email(...)
"""

import os
from functools import lru_cache
from app.config import get_settings


class FeatureFlags:
    """Feature flag registry."""

    # PRD 02: Price Alerts
    PRICE_ALERTS_EMAIL_ENABLED = "FEATURE_PRICE_ALERTS_EMAIL_ENABLED"
    PRICE_ALERTS_RULES_ENABLED = "FEATURE_PRICE_ALERTS_RULES_ENABLED"
    PRICE_ALERTS_FIVE_STAR_AUTO = "FEATURE_PRICE_ALERTS_FIVE_STAR_AUTO"

    # PRD 02: Listing Proliferator
    LISTING_PUBLISH_ENABLED = "FEATURE_LISTING_PUBLISH_ENABLED"
    LISTING_PUBLISH_DRY_RUN_ONLY = "FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY"
    LISTING_INVENTORY_RESERVATION = "FEATURE_LISTING_INVENTORY_RESERVATION"

    # PRD 02: Optimal Build Designer
    BUILD_DESIGNER_ENABLED = "FEATURE_BUILD_DESIGNER_ENABLED"

    # PRD 01: Demand Intelligence
    DEMAND_INTEL_ENABLED = "FEATURE_DEMAND_INTEL_ENABLED"
    DEMAND_INTEL_EXPORTS = "FEATURE_DEMAND_INTEL_EXPORTS"

    # System flags
    EMAIL_DISPATCH_ENABLED = "FEATURE_EMAIL_DISPATCH_ENABLED"
    RECREATE_CYCLE_END_OLD_LISTING = "FEATURE_RECREATE_CYCLE_END_OLD_LISTING"


@lru_cache
def get_feature_flags() -> dict:
    """
    Build feature flag map from environment.

    Convention: FEATURE_* environment variables are boolean flags.
    Values: "true", "1", "yes" → True; others → False.
    Production default: False (safe, requires explicit opt-in).
    Dev default: varies (email off, publish off for safety).
    """
    settings = get_settings()
    flags = {}

    # Scan environment for FEATURE_* variables
    for key, value in os.environ.items():
        if key.startswith("FEATURE_"):
            flag_name = key
            is_enabled = value.lower() in ("true", "1", "yes", "on")
            flags[flag_name] = is_enabled

    # Safe defaults (explicit in comments for visibility)
    # All production paths default to False unless explicitly enabled
    defaults = {
        # Email safety: disabled by default everywhere
        FeatureFlags.EMAIL_DISPATCH_ENABLED: False,
        # Listing publish: dry-run mode by default
        FeatureFlags.LISTING_PUBLISH_ENABLED: False,
        FeatureFlags.LISTING_PUBLISH_DRY_RUN_ONLY: True,
        # Inventory reservation: disabled until fully tested
        FeatureFlags.LISTING_INVENTORY_RESERVATION: False,
        # Price alerts: rules disabled until full integration
        FeatureFlags.PRICE_ALERTS_RULES_ENABLED: False,
        FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED: False,
        # Build designer: disabled until phase 4
        FeatureFlags.BUILD_DESIGNER_ENABLED: False,
        # Demand intel: disabled until phase 2
        FeatureFlags.DEMAND_INTEL_ENABLED: False,
        FeatureFlags.DEMAND_INTEL_EXPORTS: False,
        # Recreate cycle: don't end old listings until user verifies
        FeatureFlags.RECREATE_CYCLE_END_OLD_LISTING: False,
    }

    # Merge defaults (env overrides defaults)
    merged = defaults.copy()
    merged.update(flags)
    return merged


def is_enabled(flag_name: str) -> bool:
    """
    Check if a feature flag is enabled.

    Args:
        flag_name: Name of the flag (use FeatureFlags.* constants)

    Returns:
        True if flag is enabled, False otherwise
    """
    flags = get_feature_flags()
    return flags.get(flag_name, False)


def set_flag_for_testing(flag_name: str, enabled: bool) -> None:
    """
    Override a flag for testing (clears cache).

    ONLY for tests. Production code should read flags from environment.
    """
    # Clear cache so next call rebuilds
    get_feature_flags.cache_clear()
    # Set/unset environment variable
    if enabled:
        os.environ[flag_name] = "true"
    else:
        os.environ.pop(flag_name, None)
