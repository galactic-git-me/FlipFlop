from app.services.ebay_specifics_generator import (
    _enforce_aspect_cardinality,
    validate_aspects_for_ebay,
)


def test_brand_and_storage_type_accept_only_one_value():
    problems = validate_aspects_for_ebay(
        {
            "Brand": ["AMD", "NVIDIA", "Corsair"],
            "Storage Type": ["SSD", "HDD"],
        }
    )

    assert any(problem.startswith("Brand: has 3 values") for problem in problems)
    assert any(problem.startswith("Storage Type: has 2 values") for problem in problems)


def test_multi_value_aspects_remain_valid():
    assert validate_aspects_for_ebay(
        {"Features": ["RGB Lighting", "Liquid Cooling"]}
    ) == []


def test_generated_single_value_aspects_keep_only_best_choice():
    assert _enforce_aspect_cardinality("Brand", ["Custom Build", "AMD"]) == [
        "Custom Build"
    ]
    assert _enforce_aspect_cardinality("Storage Type", ["SSD", "HDD"]) == ["SSD"]
    assert _enforce_aspect_cardinality("Features", ["RGB Lighting", "Wireless"]) == [
        "RGB Lighting",
        "Wireless",
    ]
