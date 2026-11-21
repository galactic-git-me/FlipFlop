import math

import pytest
from pydantic import ValidationError

from app.schemas.manual_build import ManualBuildCreate, UpdateEbayListingConfigRequest


def test_ebay_listing_config_defines_every_accounting_field_used_by_handler():
    request = UpdateEbayListingConfigRequest(
        marketplace_fees_actual=125.50,
        promotion_cost_actual=12.25,
        refund_amount=40.00,
        warranty_claim_cost=15.75,
    )

    assert request.marketplace_fees_actual == 125.50
    assert request.promotion_cost_actual == 12.25
    assert request.refund_amount == 40.00
    assert request.warranty_claim_cost == 15.75


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_warranty_reserve_rate_rejects_non_finite_input(value):
    with pytest.raises(ValidationError):
        UpdateEbayListingConfigRequest(warranty_reserve_pct=value)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_build_creation_rejects_non_finite_warranty_reserve_rate(value):
    with pytest.raises(ValidationError):
        ManualBuildCreate(warranty_reserve_pct=value)
