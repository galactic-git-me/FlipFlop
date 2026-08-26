import pytest

from app.services import ebay_fulfillment_policies as service


@pytest.mark.asyncio
async def test_invalid_refresh_token_becomes_actionable_service_error(monkeypatch):
    async def invalid_token(_environment: str) -> str:
        raise ValueError(
            'Failed to refresh eBay production token: '
            '{"error":"invalid_grant","error_description":"invalid token"}'
        )

    monkeypatch.setattr(service, "get_valid_ebay_access_token", invalid_token)

    with pytest.raises(service.EbayFulfillmentPoliciesError) as caught:
        await service.list_fulfillment_policies("production")

    assert caught.value.status_code == 401
    assert "Reconnect the production eBay account in Settings" in str(caught.value)
