import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from app.services.amazon_product_details import fetch_amazon_item_details
from app.services.amazon_sp_api import AmazonSPAPI, AmazonSPAPIError


class AmazonProductDetailsTests(TestCase):
    def test_returns_exact_asin_catalog_facts_with_api_provenance(self):
        item = {
            "asin": "B000000000",
            "attributes": {
                "brand": [{"value": "Example"}],
                "manufacturer_part_number": [{"value": "EX-123"}],
                "cpu_socket": [{"value": "AM5"}],
            },
            "identifiers": [{"identifierType": "EAN", "identifier": "5012345678900"}],
        }

        async def run():
            lookup = AsyncMock(return_value=item)
            client = SimpleNamespace(configured=True, get_catalog_item_by_asin=lookup)
            result = await fetch_amazon_item_details(client, "B000000000")
            lookup.assert_awaited_once_with("B000000000")
            return result

        result = asyncio.run(run())
        self.assertEqual(result["sourceMethod"], "amazon_sp_api_catalog")
        self.assertEqual(result["identifiers"]["asin"], "B000000000")
        self.assertEqual(result["identifiers"]["brand"], "Example")
        self.assertEqual(result["identifiers"]["mpn"], "EX-123")
        self.assertEqual(result["identifiers"]["gtin"], "5012345678900")
        self.assertEqual(result["specifications"]["Cpu Socket"], ["AM5"])
        self.assertNotIn("selectedOffer", result)

    def test_unconfigured_sp_api_fails_closed(self):
        client = SimpleNamespace(configured=False)

        async def run():
            with self.assertRaisesRegex(AmazonSPAPIError, "not configured"):
                await fetch_amazon_item_details(client, "B000000000")

        asyncio.run(run())

    def test_catalog_item_lookup_requires_exact_asin_match(self):
        client = AmazonSPAPI()

        async def run():
            with patch.object(client, "search_catalog_items_by_asin", new=AsyncMock(return_value={"items": [{"asin": "B000000001"}]})):
                with self.assertRaisesRegex(AmazonSPAPIError, "requested ASIN"):
                    await client.get_catalog_item_by_asin("B000000000")

        asyncio.run(run())
