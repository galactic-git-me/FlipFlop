import pytest
from app.services.catalogue_service import (
    compute_display_price,
    determine_tier,
    infer_slot_type,
)

def test_display_price_rounds_up_to_five():
    assert compute_display_price(164.35) == 190.0

def test_display_price_partial_boundary():
    assert compute_display_price(50.0) == 60.0

def test_display_price_already_on_boundary():
    assert compute_display_price(100.0) == 115.0

def test_display_price_small_amount():
    assert compute_display_price(1.0) == 5.0

class _MockSlot:
    score_band_budget = [40, 65]
    score_band_mid = [65, 80]
    score_band_high = [80, 100]

def test_determine_tier_budget():
    assert determine_tier(45.0, _MockSlot()) == "budget"

def test_determine_tier_budget_boundary():
    assert determine_tier(40.0, _MockSlot()) == "budget"

def test_determine_tier_mid():
    assert determine_tier(65.0, _MockSlot()) == "mid"

def test_determine_tier_mid_upper():
    assert determine_tier(79.9, _MockSlot()) == "mid"

def test_determine_tier_high():
    assert determine_tier(80.0, _MockSlot()) == "high"

def test_determine_tier_perfect_score():
    assert determine_tier(100.0, _MockSlot()) == "high"

def test_infer_slot_type_cpu():
    assert infer_slot_type("Intel Core i7-12700 cpu only") == "cpu"

def test_infer_slot_type_gpu():
    assert infer_slot_type("NVIDIA GeForce RTX 3060 Ti graphics card 8GB") == "gpu"

def test_infer_slot_type_ram():
    assert infer_slot_type("Corsair 32GB DDR4 RAM stick 3200MHz") == "ram"

def test_infer_slot_type_storage():
    assert infer_slot_type("Samsung 870 EVO 1TB SSD solid state drive") == "storage"

def test_infer_slot_type_unknown_returns_none():
    assert infer_slot_type("Complete Gaming PC i7 RTX 3060") is None

def test_infer_slot_type_psu_returns_none():
    assert infer_slot_type("Corsair 650W modular psu") is None
