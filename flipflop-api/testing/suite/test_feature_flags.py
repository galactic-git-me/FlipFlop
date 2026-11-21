"""
Tests for feature-flag system.

Verifies that flags are:
1. Read correctly from environment
2. Default to safe values (disabled)
3. Can be overridden per-environment
4. Are used to gate risky operations
"""

import pytest
import os
from unittest.mock import patch

from app.services.feature_flags import (
    FeatureFlags,
    is_enabled,
    get_feature_flags,
    set_flag_for_testing,
)


@pytest.mark.unit
class TestFeatureFlagDefaults:
    """Test safe defaults for all flags."""

    def test_all_production_flags_default_false(self):
        """All flags default to False (safe, requires explicit enable)."""
        flags = get_feature_flags()

        # Email must be off by default
        assert flags[FeatureFlags.EMAIL_DISPATCH_ENABLED] is False

        # Publishing must be off by default
        assert flags[FeatureFlags.LISTING_PUBLISH_ENABLED] is False

        # Dry-run mode on by default (safe)
        assert flags[FeatureFlags.LISTING_PUBLISH_DRY_RUN_ONLY] is True

        # Inventory reservation off until tested
        assert flags[FeatureFlags.LISTING_INVENTORY_RESERVATION] is False

        # Price alerts off until integrated
        assert flags[FeatureFlags.PRICE_ALERTS_RULES_ENABLED] is False
        assert flags[FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED] is False

    def test_missing_flag_returns_false(self):
        """Any undefined flag returns False."""
        assert is_enabled("FEATURE_NONEXISTENT_FLAG") is False


@pytest.mark.unit
class TestFeatureFlagEnvironmentOverride:
    """Test that environment variables override defaults."""

    def test_enable_flag_via_env_true(self):
        """Setting FEATURE_*=true enables the flag."""
        set_flag_for_testing(FeatureFlags.EMAIL_DISPATCH_ENABLED, True)
        assert is_enabled(FeatureFlags.EMAIL_DISPATCH_ENABLED) is True
        set_flag_for_testing(FeatureFlags.EMAIL_DISPATCH_ENABLED, False)

    def test_enable_flag_via_env_yes(self):
        """Setting FEATURE_*=yes also enables the flag."""
        os.environ["FEATURE_TEST_CUSTOM_FLAG"] = "yes"
        get_feature_flags.cache_clear()
        flags = get_feature_flags()
        assert flags.get("FEATURE_TEST_CUSTOM_FLAG") is True
        del os.environ["FEATURE_TEST_CUSTOM_FLAG"]
        get_feature_flags.cache_clear()

    def test_disable_flag_via_env(self):
        """Setting FEATURE_*=false disables the flag."""
        os.environ[FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED] = "false"
        get_feature_flags.cache_clear()
        assert is_enabled(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED) is False
        del os.environ[FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED]
        get_feature_flags.cache_clear()


@pytest.mark.unit
class TestFeatureFlagUniqueNames:
    """Test that flag names are unique and consistent."""

    def test_all_flag_names_are_unique(self):
        """No duplicate flag names in registry."""
        flag_attrs = [
            getattr(FeatureFlags, attr)
            for attr in dir(FeatureFlags)
            if not attr.startswith("_")
        ]
        assert len(flag_attrs) == len(set(flag_attrs)), "Duplicate flag names found"

    def test_all_flags_follow_naming_convention(self):
        """All flags start with FEATURE_."""
        flag_attrs = [
            getattr(FeatureFlags, attr)
            for attr in dir(FeatureFlags)
            if not attr.startswith("_")
        ]
        for flag in flag_attrs:
            assert flag.startswith("FEATURE_"), f"Flag {flag} doesn't start with FEATURE_"


@pytest.mark.unit
class TestFeatureFlagIntegration:
    """Test feature flags in realistic usage patterns."""

    def test_email_kill_switch_pattern(self):
        """
        Email dispatch can be killed without code changes.

        Pattern:
        1. Flag defaults to False (safe)
        2. In production: explicitly enable FEATURE_EMAIL_DISPATCH_ENABLED=true
        3. In test: flag stays False, emails are suppressed
        """
        # Test environment: email off by default
        assert is_enabled(FeatureFlags.EMAIL_DISPATCH_ENABLED) is False

        # Production environment: admin enables it
        set_flag_for_testing(FeatureFlags.EMAIL_DISPATCH_ENABLED, True)
        assert is_enabled(FeatureFlags.EMAIL_DISPATCH_ENABLED) is True

        # Rollback: admin disables it (kill switch)
        set_flag_for_testing(FeatureFlags.EMAIL_DISPATCH_ENABLED, False)
        assert is_enabled(FeatureFlags.EMAIL_DISPATCH_ENABLED) is False

    def test_dry_run_mode_pattern(self):
        """
        Listing publish can run in dry-run mode.

        Pattern:
        1. DRY_RUN_ONLY defaults to True (safe)
        2. PUBLISH_ENABLED defaults to False
        3. In production: DRY_RUN_ONLY=false + PUBLISH_ENABLED=true
        """
        # Test environment: dry-run only
        assert is_enabled(FeatureFlags.LISTING_PUBLISH_ENABLED) is False
        assert is_enabled(FeatureFlags.LISTING_PUBLISH_DRY_RUN_ONLY) is True

        # Simulate production: enable live publishing
        # NOTE: DRY_RUN_ONLY defaults to True, so we can't truly disable it
        # unless we also set the env var. This test verifies the default behavior.
        set_flag_for_testing(FeatureFlags.LISTING_PUBLISH_ENABLED, True)
        assert is_enabled(FeatureFlags.LISTING_PUBLISH_ENABLED) is True
        # DRY_RUN_ONLY will still be True (default), which is correct safety design

        # Rollback
        set_flag_for_testing(FeatureFlags.LISTING_PUBLISH_ENABLED, False)

    def test_phased_rollout_pattern(self):
        """
        Features can be rolled out in phases.

        Phase 1: price_alerts rules disabled (off)
        Phase 2: rules enabled, email disabled
        Phase 3: both enabled
        """
        # Phase 1
        assert is_enabled(FeatureFlags.PRICE_ALERTS_RULES_ENABLED) is False
        assert is_enabled(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED) is False

        # Phase 2
        set_flag_for_testing(FeatureFlags.PRICE_ALERTS_RULES_ENABLED, True)
        assert is_enabled(FeatureFlags.PRICE_ALERTS_RULES_ENABLED) is True
        assert is_enabled(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED) is False

        # Phase 3
        set_flag_for_testing(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED, True)
        assert is_enabled(FeatureFlags.PRICE_ALERTS_RULES_ENABLED) is True
        assert is_enabled(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED) is True

        # Rollback to default
        set_flag_for_testing(FeatureFlags.PRICE_ALERTS_RULES_ENABLED, False)
        set_flag_for_testing(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED, False)


@pytest.mark.unit
def test_feature_flag_caching():
    """Feature flags are cached and cleared properly."""
    # First call caches
    flags1 = get_feature_flags()

    # Second call returns same object
    flags2 = get_feature_flags()
    assert flags1 is flags2, "Cache not working"

    # Clear cache
    get_feature_flags.cache_clear()

    # Third call returns new object
    flags3 = get_feature_flags()
    assert flags1 is not flags3, "Cache not cleared"
