import pytest

from app.api.builds_pricing import (
    SoldCompDetail,
    _build_condition,
    _canonical_ebay_item_id,
    _build_search_query,
    _build_sold_queries,
    _extract_ram_gb,
    _extract_storage_gb,
    _observed_warranty_rate,
    _sale_based_reserve_floor,
    _sale_based_warranty_reserve,
    _title_has_model,
    _verified_build_sold_item_id,
    _weighted_median,
)
from types import SimpleNamespace


def test_pricing_reserve_uses_expected_sale_price():
    assert _sale_based_warranty_reserve(1000, 5) == 50


def test_warranty_calibration_uses_historical_sale_value_denominator():
    assert _observed_warranty_rate(100, 1000) == 10
    assert _observed_warranty_rate(100, 0) is None


def test_pricing_floor_accounts_for_sale_based_reserve_and_fees():
    floor = _sale_based_reserve_floor(1000, 0.10, 5)
    assert floor == pytest.approx(1100 / 0.845)


def test_full_pc_capacity_parsing_ignores_gpu_vram():
    title = "Gaming PC Ryzen 7800X3D RTX 4070 12GB 32GB DDR5 2TB NVMe"
    assert _extract_ram_gb(title) == 32
    assert _extract_storage_gb(title) == 2048


def test_exact_identity_accepts_short_marketplace_wording():
    title = "Gaming PC 7800X3D RTX 4070 SUPER 32GB DDR5"
    assert _title_has_model(title, "AMD Ryzen 7 7800X3D")
    assert _title_has_model(title, "NVIDIA GeForce RTX 4070 Super")
    assert not _title_has_model(title, "NVIDIA GeForce RTX 4080")


def test_component_profile_can_derive_used_build_condition():
    components = [{"condition": "new"}, {"condition": "used"}, {"condition": "new"}]
    assert _build_condition(None, components) == "used"


def test_combined_exact_query_is_first():
    components = [
        {"slot": "CPU", "name": "AMD Ryzen 7 7800X3D"},
        {"slot": "GPU", "name": "NVIDIA RTX 4070 Super"},
    ]
    assert _build_sold_queries(components)[0] == 'gaming PC "7800X3D" "RTX 4070 Super"'


def test_build_sold_comps_require_explicit_sold_badge_and_date():
    comp = SimpleNamespace(
        url="https://www.ebay.co.uk/itm/Gaming-PC/123456789012?itmmeta=abc",
        sold_confirmed=True,
        sold_date_text="Sold 16 Nov 2026",
    )
    assert _verified_build_sold_item_id(comp) == "123456789012"
    assert _verified_build_sold_item_id(SimpleNamespace(**{
        **vars(comp), "sold_confirmed": False,
    })) is None
    assert _verified_build_sold_item_id(SimpleNamespace(**{
        **vars(comp), "sold_date_text": None,
    })) is None


def test_build_sold_comps_reject_active_bin_results_and_dedupe_url_tracking():
    active = SimpleNamespace(
        url="https://www.ebay.co.uk/itm/123456789012?_skw=PC&LH_BIN=1",
        sold_confirmed=True,
        sold_date_text="Sold 16 Nov 2026",
    )
    assert _verified_build_sold_item_id(active) is None
    assert _canonical_ebay_item_id(
        "https://www.ebay.co.uk/itm/123456789012?_skw=first"
    ) == _canonical_ebay_item_id(
        "https://www.ebay.co.uk/itm/123456789012?_skw=second"
    )


def test_live_sold_query_uses_distinctive_models_not_full_component_names():
    assert _build_search_query(
        "AMD Ryzen 7 7800X3D",
        "Palit GameRock NVIDIA GeForce RTX 3070 8GB",
    ) == "gaming pc 7800X3D RTX 3070"


def test_exact_spec_comps_receive_more_weight():
    comps = [
        SoldCompDetail(price=900, condition="used", sold_at="", match_quality="normalised"),
        SoldCompDetail(price=1000, condition="used", sold_at="", match_quality="exact major specification"),
        SoldCompDetail(price=1300, condition="used", sold_at="", match_quality="normalised"),
    ]
    assert _weighted_median(comps) == 1000
