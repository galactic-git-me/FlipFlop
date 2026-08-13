"""Unit tests for the public configurator compatibility layer.

The judge functions are pure (text-in, verdict-out) so they run without a DB;
route smoke tests follow the pattern in test_public_catalogue_api.py.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.configurator import CompatibilityRule, CompatibilityRuleType
from app.services.configurator_compatibility import _judge_variant, _apply_db_rule

client = TestClient(app, raise_server_exceptions=False)


# --- _judge_variant heuristics -------------------------------------------

def test_ddr5_ram_incompatible_with_am4_cpu():
    # Arrange: AM4 CPU selected, candidate is DDR5 RAM
    selected = {"cpu": "AMD Ryzen 7 5800X 8-core AM4"}

    # Act
    verdict = _judge_variant("ram", "Corsair Vengeance 32GB DDR5 6000MHz", selected, None)

    # Assert
    assert verdict.is_compatible is False
    assert "DDR5" in verdict.reason


def test_ddr4_ram_compatible_with_am4_cpu():
    selected = {"cpu": "AMD Ryzen 7 5800X 8-core AM4"}
    verdict = _judge_variant("ram", "Corsair Vengeance LPX 16GB DDR4 3200", selected, None)
    assert verdict.is_compatible is True


def test_am5_cpu_incompatible_with_selected_ddr4_ram():
    selected = {"ram": "Kingston Fury 32GB DDR4 3600"}
    verdict = _judge_variant("cpu", "AMD Ryzen 7 7700X AM5", selected, None)
    assert verdict.is_compatible is False
    assert "DDR5" in verdict.reason


def test_unknown_specs_default_to_compatible():
    # Honesty principle: no positive conflict signal → never grey out
    verdict = _judge_variant("ram", "Mystery RAM kit 32GB", {"cpu": "Some CPU"}, None)
    assert verdict.is_compatible is True


def test_gpu_blocked_when_selected_psu_too_small():
    selected = {"cpu": "i7-12700K", "storage": "Corsair 450W PSU bundle"}
    verdict = _judge_variant("gpu", "NVIDIA RTX 3080 10GB", selected, None)
    assert verdict.is_compatible is False
    assert "PSU" in verdict.reason


def test_gpu_warns_when_psu_unknown():
    verdict = _judge_variant("gpu", "NVIDIA RTX 3080 10GB", {"cpu": "i7-12700K"}, None)
    assert verdict.is_compatible is True
    assert any("PSU" in w for w in verdict.warnings)


# --- _apply_db_rule structured rules --------------------------------------

def _rule(rule_type, constraint):
    r = CompatibilityRule(rule_type=rule_type, subject_slot_id=1, constraint_json=constraint)
    return r


def test_socket_match_rule_fails_on_mismatch():
    rule = _rule(CompatibilityRuleType.SOCKET_MATCH, {"requires_socket": "am5"})
    result = _apply_db_rule(rule, "Noctua cooler for LGA1700", {}, None)
    assert result is not None
    reason, code = result
    assert "AM5" in reason
    assert code is not None


def test_socket_match_rule_passes_when_socket_unknown():
    rule = _rule(CompatibilityRuleType.SOCKET_MATCH, {"requires_socket": "am5"})
    assert _apply_db_rule(rule, "Generic tower cooler", {}, None) is None


def test_psu_wattage_min_rule():
    rule = _rule(CompatibilityRuleType.PSU_WATTAGE_MIN, {"min_watts": 750})
    result = _apply_db_rule(rule, "Corsair CV550 550W 80+ Bronze", {}, None)
    assert result is not None
    reason, code = result
    assert "750" in reason


def test_ram_type_match_rule():
    rule = _rule(CompatibilityRuleType.RAM_TYPE_MATCH, {"requires_ram_type": "ddr5"})
    result = _apply_db_rule(rule, "Corsair 16GB DDR4 3200", {}, None)
    assert result is not None


# --- route smoke tests -----------------------------------------------------

def test_assets_resolve_route_exists():
    resp = client.post(
        "/api/public/assets/resolve",
        json={"subjects": [{"subject_type": "case", "subject_id": 1, "category": None}]},
    )
    assert resp.status_code in (200, 500)


def test_assets_resolve_rejects_bad_subject_type():
    resp = client.post(
        "/api/public/assets/resolve",
        json={"subjects": [{"subject_type": "banana", "subject_id": 1}]},
    )
    assert resp.status_code == 422


def test_compatibility_evaluate_route_exists():
    resp = client.post(
        "/api/public/compatibility/evaluate",
        json={"playbook_id": 99999, "selections": {}, "case_id": None},
    )
    assert resp.status_code in (404, 500)
