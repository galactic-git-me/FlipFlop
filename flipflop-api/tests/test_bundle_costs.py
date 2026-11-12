from decimal import Decimal as D

import pytest

from app.services.bundle_costs import allocate_bundle_cost, compare_bundle_to_standalone_market


def test_bundle_allocation_is_proportional_and_reconciles_exactly():
    result = allocate_bundle_cost(D("180"), {
        "cpu": D("90"), "motherboard": D("85"), "ram": D("50"),
    })
    assert result == {"cpu": D("72.00"), "motherboard": D("68.00"), "ram": D("40.00")}
    assert sum(result.values()) == D("180.00")


def test_rounding_remainder_is_deterministic():
    prices = {"b": D("1"), "a": D("1"), "c": D("1")}
    expected = {"a": D("0.34"), "b": D("0.33"), "c": D("0.33")}
    assert allocate_bundle_cost(D("1"), prices) == expected
    assert allocate_bundle_cost(D("1"), dict(reversed(list(prices.items())))) == expected


def test_bundle_savings_compare_uses_the_full_purchase_total():
    result = compare_bundle_to_standalone_market(D("180"), {
        "cpu": D("90"), "motherboard": D("85"), "ram": D("50"),
    })
    assert result == {
        "bundle_landed_cost": D("180.00"),
        "standalone_market_total": D("225.00"),
        "absolute_savings": D("45.00"),
        "savings_percentage": D("20.00"),
    }


@pytest.mark.parametrize("total, refs", [
    (D("-1"), {"cpu": D("1")}),
    (D("1"), {"cpu": D("0")}),
    (D("1"), {}),
])
def test_invalid_allocation_inputs_fail_closed(total, refs):
    with pytest.raises(ValueError):
        allocate_bundle_cost(total, refs)
