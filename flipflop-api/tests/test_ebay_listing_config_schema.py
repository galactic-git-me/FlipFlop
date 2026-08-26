from app.schemas.manual_build import UpdateEbayListingConfigRequest


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
