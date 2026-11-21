from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.playbook import Playbook
from app.schemas.commercial_quote import CellCommercialPolicy
from app.schemas.payment import PlaybookBuildConfig
from app.services.commercial_checkout import load_checkout_policy
from app.services.commercial_configuration import configuration_definition
from app.services.commercial_quote_evidence import definition_hash
from app.services.playbook_service import automatic_policy
from app.api.configuration_commercial_quotes import ConfigurationPriceApproval
from test_playbook_commercial_quote import policy_data


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    def __init__(self, playbook):
        self.playbook = playbook

    async def execute(self, _statement):
        return _Result(self.playbook)


def _config(variant_id=201):
    return PlaybookBuildConfig(playbook_id=7, curated_build_id=None,
        slot_selections={101: variant_id}, case_id=303, budget_tier="Budget")


@pytest.mark.asyncio
async def test_exact_configuration_checkout_requires_its_own_approved_variant_mapping():
    config = _config()
    definition = await configuration_definition(None, config)
    data = policy_data()
    data.update(definition_sha256=definition_hash(definition), checkout_enabled=True,
        required_part_keys=["variant:201", "case:303"],
        checkout_slot_parts={101: (201, "variant:201")},
        checkout_case=(303, "case:303"))
    policy = CellCommercialPolicy.model_validate(data)
    playbook = SimpleNamespace(id=7, status="active", pricing_model={
        "commercial_configurations": {definition_hash(definition): policy.model_dump(mode="json")}})

    loaded = await load_checkout_policy(_Session(playbook), config)

    assert loaded[0] is playbook
    assert loaded[1] == definition
    assert loaded[2].checkout_enabled is True
    assert loaded[2].checkout_slot_parts == {101: (201, "variant:201")}

    with pytest.raises(HTTPException) as error:
        await load_checkout_policy(_Session(playbook), _config(variant_id=202))
    assert error.value.status_code == 409
    assert "review" in str(error.value.detail).lower()


@pytest.mark.asyncio
async def test_unapproved_exact_configuration_cannot_fall_back_to_legacy_checkout():
    playbook = SimpleNamespace(id=7, status="active", pricing_model={"commercial_cells": {}})

    with pytest.raises(HTTPException) as error:
        await load_checkout_policy(_Session(playbook), _config())

    assert error.value.status_code == 409
    assert "review" in str(error.value.detail).lower()


def test_exact_configuration_approval_accepts_only_the_server_calculated_review_hash():
    ConfigurationPriceApproval.model_validate({"review_sha256": "a" * 64})
    with pytest.raises(ValidationError):
        ConfigurationPriceApproval.model_validate({"review_sha256": "a" * 64, "policy": {"payment_rate": "0.03"}})


def test_exact_configuration_policy_reuses_approved_playbook_rules_without_market_or_manual_values():
    roles = ("cpu", "motherboard", "ram", "gpu", "storage", "cooling", "psu", "os")
    parts = {}
    for index, role in enumerate(roles, start=1):
        parts[role] = {"role": role, "slot_id": index, "variant_id": 100 + index,
            "landed_gbp": "50.00", "source_observation": {"delivery_working_days": 1}}
    parts["case"] = {"role": "case", "slot_id": None, "variant_id": None,
        "case_catalogue_id": 303, "landed_gbp": "80.00",
        "source_observation": {"delivery_working_days": 1}}
    settings = SimpleNamespace(speedy_curated_custom_days=7, standard_curated_custom_days=14,
        flexible_curated_custom_days=28, speedy_delivery_price_gbp=49,
        opportunity_delivery_fallback_gbp=15)
    parent = SimpleNamespace(profit_strategy={})

    policy = automatic_policy(parts, {"id": "FF-GVG-01", "tier": "Budget"}, parent, settings,
        definition_sha256_override="a" * 64, include_market=False, version=4)

    assert policy is not None
    assert policy.version == 4
    assert policy.definition_sha256 == "a" * 64
    assert policy.market is None
    assert policy.checkout_enabled is False
    assert set(policy.modes) == {"fast_track", "standard", "flexible"}
    assert policy.required_part_keys == [f"variant:{100 + index}" for index in range(1, 9)] + ["case:303"]
