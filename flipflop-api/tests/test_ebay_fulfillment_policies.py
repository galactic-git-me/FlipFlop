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


@pytest.mark.asyncio
async def test_connected_seller_token_bypasses_obsolete_environment_token(monkeypatch):
    async def environment_token_must_not_be_used(_environment: str) -> str:
        raise AssertionError("obsolete environment token was used")

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"fulfillmentPolicies": []}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **kwargs):
            assert kwargs["headers"]["Authorization"] == "Bearer connected-token"
            return Response()

    monkeypatch.setattr(service, "get_valid_ebay_access_token", environment_token_must_not_be_used)
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **_kwargs: Client())

    result = await service.list_fulfillment_policies(
        "production", access_token="connected-token"
    )

    assert result == []
