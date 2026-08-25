from app.api.builds_pricing import (
    SoldCompDetail,
    _build_condition,
    _build_sold_queries,
    _extract_ram_gb,
    _extract_storage_gb,
    _title_has_model,
    _weighted_median,
)


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


def test_exact_spec_comps_receive_more_weight():
    comps = [
        SoldCompDetail(price=900, condition="used", sold_at="", match_quality="normalised"),
        SoldCompDetail(price=1000, condition="used", sold_at="", match_quality="exact major specification"),
        SoldCompDetail(price=1300, condition="used", sold_at="", match_quality="normalised"),
    ]
    assert _weighted_median(comps) == 1000
