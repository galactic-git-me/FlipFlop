from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import figural_insurance
from app.services.figural_insurance import FiguralError


class FakeResponse:
    def __init__(self, *, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


@pytest.mark.asyncio
async def test_policy_creation_error_does_not_log_or_return_raw_provider_body(monkeypatch):
    private_email = "buyer-private@example.test"
    private_address = "44 Private Road, London"
    raw_body = f"Provider echoed {private_email} at {private_address}"
    fake_client = FakeAsyncClient(FakeResponse(
        status_code=422,
        payload={"response": {"success": False, "detail": raw_body}},
        text=raw_body,
    ))
    logger = SimpleNamespace(error=Mock())
    monkeypatch.setattr(figural_insurance, "log", logger)
    monkeypatch.setattr(figural_insurance, "get_settings", lambda: SimpleNamespace(
        secursus_live_parcel_creation_enabled=True,
        secursus_api_identifier="test-key",
        secursus_api_secret_key="test-secret",
    ))
    monkeypatch.setattr(figural_insurance.httpx, "AsyncClient", lambda **_kwargs: fake_client)

    with pytest.raises(FiguralError) as raised:
        await figural_insurance.create_insurance_policy({
            "parcel_value": 12000,
            "first_name": "Example",
            "last_name": "Buyer",
            "email": private_email,
            "full_address": private_address,
            "country_origin": "gb",
            "country_destination": "gb",
            "cart_data": {"build_id": 123},
        })

    assert "HTTP 422" in str(raised.value)
    assert private_email not in str(raised.value)
    assert private_address not in str(raised.value)
    assert private_email not in repr(logger.error.call_args)
    assert private_address not in repr(logger.error.call_args)
    assert raw_body not in repr(logger.error.call_args)


@pytest.mark.asyncio
async def test_missing_policy_id_logs_only_response_field_names(monkeypatch):
    private_email = "buyer-private@example.test"
    private_address = "44 Private Road, London"
    fake_client = FakeAsyncClient(FakeResponse(
        status_code=200,
        payload={"response": {"success": True}, "data": {"attributes": {
            "email": private_email,
            "full_address": private_address,
        }}},
    ))
    logger = SimpleNamespace(error=Mock())
    monkeypatch.setattr(figural_insurance, "log", logger)
    monkeypatch.setattr(figural_insurance, "get_settings", lambda: SimpleNamespace(
        secursus_live_parcel_creation_enabled=True,
        secursus_api_identifier="test-key",
        secursus_api_secret_key="test-secret",
    ))
    monkeypatch.setattr(figural_insurance.httpx, "AsyncClient", lambda **_kwargs: fake_client)

    with pytest.raises(FiguralError, match="did not include a policy ID"):
        await figural_insurance.create_insurance_policy({
            "parcel_value": 12000,
            "first_name": "Example",
            "last_name": "Buyer",
            "email": private_email,
            "full_address": private_address,
            "country_origin": "gb",
            "country_destination": "gb",
            "cart_data": {"build_id": 123},
        })

    logged = repr(logger.error.call_args)
    assert private_email not in logged
    assert private_address not in logged
    assert "response_fields" in logged
