"""Static API contract regressions; authored but not yet executed."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.payment import PlaybookBuildConfig
from app.routes.payments import _checkout_build_mode


def test_payment_config_accepts_stable_curated_playbook_cell_key():
    config = PlaybookBuildConfig(
        playbook_id=4,
        curated_build_id="FF-GVG-01",
        validation_mode="curated",
    )

    assert config.curated_build_id == "FF-GVG-01"


def test_payment_config_rejects_empty_curated_cell_key():
    with pytest.raises(ValidationError):
        PlaybookBuildConfig(playbook_id=4, curated_build_id="")


def test_made_by_you_payment_config_preserves_the_explicit_budget_tier():
    config = PlaybookBuildConfig(
        playbook_id=4,
        validation_mode="studio",
        budget_tier="High-end",
    )

    assert config.budget_tier == "High-end"


def test_payment_config_rejects_budget_tiers_outside_the_playbook_matrix():
    with pytest.raises(ValidationError):
        PlaybookBuildConfig(playbook_id=4, validation_mode="studio", budget_tier="Premium")


def test_studio_mode_maps_to_custom_catalogue_pricing():
    config = PlaybookBuildConfig(playbook_id=4, validation_mode="studio", budget_tier="Budget")

    assert _checkout_build_mode(config) == "custom"


def test_made_by_you_cannot_bypass_declared_tier_by_omitting_studio_mode():
    config = PlaybookBuildConfig(playbook_id=4, validation_mode="custom")

    with pytest.raises(HTTPException, match="Choose a Playbook budget tier"):
        _checkout_build_mode(config)


def test_curated_mode_requires_a_curated_cell_key():
    config = PlaybookBuildConfig(playbook_id=4, validation_mode="curated")

    with pytest.raises(HTTPException, match="Choose a curated Playbook cell"):
        _checkout_build_mode(config)
