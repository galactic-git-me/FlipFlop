from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.amazon_sp_api import AmazonSPAPI, AmazonSPAPIError
from app.services.playbook_product_capture import (
    amazon_catalog_capture_refresh_due,
    refresh_amazon_catalogue_attributes,
    retain_last_good_amazon_catalog_capture,
)
from app.services.playbook_service import (
    _amazon_catalog_engineering_properties,
    _source_engineering_values,
)


def test_amazon_catalog_attributes_are_bound_to_the_exact_asin_and_labeled_fields():
    url = "https://www.amazon.co.uk/dp/B000000000"
    capture = {
        "status": "captured",
        "asin": "B000000000",
        "url": url,
        "attributes": {
            "cpu_socket": [{"value": "AM5", "marketplace_id": "A1F83G8C2ARO7P"}],
            "processor_base_power": [{"value": 65, "unit": "watts"}],
            "item_dimensions": [{"length": {"value": 42, "unit": "centimeters"}}],
        },
    }

    properties = _amazon_catalog_engineering_properties(capture, "cpu", url)

    assert properties == {"CPU Socket": "AM5", "Processor Base Power": "65 W"}
    assert _source_engineering_values("cpu", [properties], "") == {
        "socket": "am5",
        "power_w": 65,
    }
    assert _amazon_catalog_engineering_properties(
        {**capture, "asin": "B000000001"}, "cpu", url
    ) == {}


def test_conflicting_retailer_and_amazon_values_do_not_become_a_suggestion():
    assert _source_engineering_values(
        "cpu", [{"Socket": "AM4"}, {"CPU Socket": "AM5"}], "Ryzen AM5"
    ) == {}


def test_catalog_capture_retry_is_bounded_and_last_good_data_survives_access_errors():
    now = datetime.now(timezone.utc)
    assert not amazon_catalog_capture_refresh_due(
        {"status": "captured", "attempted_at": (now - timedelta(days=20)).isoformat()}, now
    )
    assert amazon_catalog_capture_refresh_due(
        {"status": "captured", "attempted_at": (now - timedelta(days=31)).isoformat()}, now
    )
    assert not amazon_catalog_capture_refresh_due(
        {"status": "unavailable", "attempted_at": (now - timedelta(days=2)).isoformat()}, now
    )
    prior = {"status": "captured", "asin": "B000000000", "url": "https://www.amazon.co.uk/dp/B000000000", "attributes": {"cpu_socket": "AM5"}}
    kept = retain_last_good_amazon_catalog_capture(prior, {
        "status": "unavailable", "asin": "B000000000", "url": prior["url"],
        "error_code": "access_denied", "attempted_at": now.isoformat(),
    }, prior["url"])
    assert kept["attributes"] == prior["attributes"]
    assert kept["last_capture_attempt"]["error_code"] == "access_denied"


@pytest.mark.asyncio
async def test_sp_api_catalog_search_batches_exact_asins_and_requests_technical_fields():
    client = AmazonSPAPI()
    response = SimpleNamespace(json=lambda: {"items": [{"asin": "B000000000"}]})
    with patch.object(client, "_request", AsyncMock(return_value=response)) as request:
        payload = await client.search_catalog_items_by_asin(["b000000000", "B000000001"])

    assert payload["items"][0]["asin"] == "B000000000"
    request.assert_awaited_once_with(
        "GET",
        "/catalog/2022-04-01/items",
        params={
            "marketplaceIds": client.marketplace_id,
            "identifiers": "B000000000,B000000001",
            "identifiersType": "ASIN",
            "includedData": "attributes,dimensions,identifiers,summaries",
        },
    )


@pytest.mark.asyncio
async def test_sp_api_catalog_search_rejects_invalid_batches_without_a_request():
    client = AmazonSPAPI()
    with patch.object(client, "_request", AsyncMock()) as request:
        with pytest.raises(AmazonSPAPIError, match="one to twenty valid ASINs"):
            await client.search_catalog_items_by_asin(["not-an-asin"])
        request.assert_not_awaited()


@pytest.mark.asyncio
async def test_catalog_refresh_records_role_denial_without_destroying_last_good_facts():
    url = "https://www.amazon.co.uk/dp/B000000000"
    listing = SimpleNamespace(source_name="amazon", url=url, raw_specs={
        "playbook_amazon_catalog_capture": {
            "status": "captured", "asin": "B000000000", "url": url,
            "attempted_at": "2026-09-01T00:00:00+00:00", "attributes": {"cpu_socket": "AM5"},
        },
    })
    client = SimpleNamespace(configured=True,
        search_catalog_items_by_asin=AsyncMock(side_effect=AmazonSPAPIError("Denied", status_code=403)))
    with patch("app.services.amazon_sp_api.AmazonSPAPI", return_value=client):
        result = await refresh_amazon_catalogue_attributes([listing], datetime.now(timezone.utc))

    assert result["unavailable"] == 1
    stored = listing.raw_specs["playbook_amazon_catalog_capture"]
    assert stored["attributes"] == {"cpu_socket": "AM5"}
    assert stored["last_capture_attempt"]["error_code"] == "access_denied"
