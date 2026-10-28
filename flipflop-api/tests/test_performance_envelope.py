import pytest

from app.services.performance_envelope import CustomerRequirements, build_envelope


def test_1440p_gaming_prioritises_graphics_without_fixed_sku():
    result = build_envelope(CustomerRequirements(primary_use="gaming", budget_gbp=1100, resolution="1440p"))
    assert result["hard_minimums"]["gpu_vram_gb"] == 12
    assert result["condition_policy"] == "NEW_ONLY"
    assert result["status"] == "requirements_only"
    assert "RTX" not in str(result)
    assert any("1440p" in reason for reason in result["budget_strategy"])


def test_development_and_ai_overlays_raise_minimums():
    result = build_envelope(CustomerRequirements(primary_use="software_development", budget_gbp=1500, docker_or_vms=True, local_ai=True))
    assert result["hard_minimums"]["cpu_cores"] >= 8
    assert result["hard_minimums"]["ram_gb"] >= 32
    assert result["hard_minimums"]["gpu_vram_gb"] >= 12


def test_unknown_use_is_rejected():
    with pytest.raises(ValueError, match="Unsupported primary use"):
        build_envelope(CustomerRequirements(primary_use="unknown", budget_gbp=1000))
