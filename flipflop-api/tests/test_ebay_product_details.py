import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import httpx

from app.services.ebay_product_details import fetch_ebay_item_details


class EbayProductDetailsTests(TestCase):
    def test_uses_browse_api_item_details_and_exact_legacy_variation(self):
        requests = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={
                "legacyItemId": "123456789012",
                "legacyVariationId": "99887766",
                "itemWebUrl": "https://www.ebay.co.uk/itm/123456789012",
                "localizedAspects": [
                    {"name": "Brand", "value": "Example"},
                    {"name": "Manufacturer Part Number", "value": "EX-123"},
                    {"name": "Socket Type", "value": "AM5"},
                ],
                "price": {"value": "149.99", "currency": "GBP"},
                "estimatedAvailabilityStatus": "IN_STOCK",
            })

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                with patch("app.services.ebay_product_details._get_ebay_access_token", new=AsyncMock(return_value="token")):
                    return await fetch_ebay_item_details(client, "123456789012", "99887766")

        result = asyncio.run(run())

        self.assertEqual(requests[0].url.path, "/buy/browse/v1/item/get_item_by_legacy_id")
        self.assertEqual(requests[0].url.params["legacy_item_id"], "123456789012")
        self.assertEqual(requests[0].url.params["legacy_variation_id"], "99887766")
        self.assertEqual(requests[0].headers["X-EBAY-C-MARKETPLACE-ID"], "EBAY_GB")
        self.assertEqual(result["sourceMethod"], "ebay_browse_api")
        self.assertEqual(result["identifiers"]["mpn"], "EX-123")
        self.assertEqual(result["specifications"]["Socket Type"], ["AM5"])
        self.assertEqual(result["selectedOffer"]["price"], 149.99)
        self.assertEqual(result["selectedOffer"]["availability"], "available")

    def test_rejects_browse_response_for_a_different_item(self):
        async def run():
            async def respond(request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json={"legacyItemId": "999999999999"})

            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                with patch("app.services.ebay_product_details._get_ebay_access_token", new=AsyncMock(return_value="token")):
                    with self.assertRaisesRegex(RuntimeError, "did not match"):
                        await fetch_ebay_item_details(client, "123456789012")

        asyncio.run(run())
