"""Regressions for cross-vendor model-number identity and protected variants."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import unittest
from unittest.mock import AsyncMock

from app.gem_radar.product_identity_registry import identifier_claims, resolve_identifiers
from app.gem_radar.product_identifiers import identity_conflicts, variant_facts
from app.gem_radar.search_identity import last_resort_title_key


class Result:
    def __init__(self, rows=(), scalar=None):
        self._rows = list(rows)
        self._scalar = scalar

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows


def fake_registry_db(rows):
    db = AsyncMock()
    db.info = {"component_identity_registry_available": True}

    async def execute(statement, *args, **kwargs):
        sql = str(statement)
        if "pg_try_advisory_xact_lock" in sql:
            return Result(scalar=True)
        if "JOIN jsonb_to_recordset" in sql:
            return Result(rows=rows)
        if "SELECT kind,namespace,value FROM canonical_component_identifiers WHERE cpk" in sql:
            return Result(rows=[])
        return Result(rows=[])

    db.execute.side_effect = execute
    return db


class CrossVendorModelConsolidation(unittest.IsolatedAsyncioTestCase):
    async def test_same_cpu_model_alias_reconciles_a_valid_existing_listing_cpk(self):
        first_vendor_title = "AMD Ryzen 7 8500X3D Eight Core 5.20GHz Socket AM5"
        second_vendor_title = "AMD Ryzen 7 8500X3D 8-Core AM5 CPU 96MB L3 Processor"
        expected_data = {
            "category": "cpu", "brand": "amd", "model": "amd_ryzen_7_8500x3d",
            "identity_source_title": first_vendor_title,
        }
        # The first vendor already established the manufacturer/model alias.
        # A second vendor has a valid but historically different listing CPK.
        rows = [
            {"cpk": "canonical-model-cpk", "identity": expected_data, "kind": "model_number"},
            {"cpk": "canonical-model-cpk", "identity": expected_data, "kind": "title_product"},
        ]
        db = fake_registry_db(rows)

        result = await resolve_identifiers(
            db, title=second_vendor_title, category="cpu", brand="AMD",
            model_number="8500X3D", source_url="https://retailer-b.example/cpu/8500x3d",
            existing_cpk="legacy-vendor-cpk",
            existing_data={**expected_data, "identity_source_title": second_vendor_title},
        )

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["cpk"], "canonical-model-cpk")
        self.assertEqual(result.get("previous_cpk"), "legacy-vendor-cpk")

    async def test_title_only_manufacturer_model_alias_matches_without_model_metadata(self):
        first_title = "AMD Ryzen 7 8500X3D Eight Core 5.20GHz Socket AM5"
        second_title = "AMD Ryzen 7 8500X3D 8-Core AM5 CPU 96MB L3 Processor"
        data = {
            "category": "cpu", "brand": "amd", "model": "amd_ryzen_7_8500x3d",
            "identity_source_title": first_title,
        }
        db = fake_registry_db([
            {"cpk": "canonical-title-cpk", "identity": data, "kind": "title_product"},
            {"cpk": "vendor-epid-cpk", "identity": data, "kind": "epid"},
        ])

        result = await resolve_identifiers(
            db, title=second_title, category="cpu", brand="AMD", epid="EBAY-123",
            source_url="https://www.ebay.co.uk/itm/123",
        )

        self.assertFalse(any(claim["kind"] == "model_number" for claim in result["claims"]))
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["cpk"], "canonical-title-cpk")

    async def test_category_null_cpu_title_beats_epid_and_keeps_product_gates(self):
        title = "AMD Ryzen 5 2400G 3.6 GHz Processor, Wraith Stealth Cooler and thermal paste"
        expected_data = {
            "category": "cpu", "brand": "amd", "model": "amd_ryzen_5_2400g",
            "identity_source_title": "AMD Ryzen 5 2400G Processor",
        }
        self.assertEqual(
            last_resort_title_key(title, None),
            ("title_product", "cpu", "amd", "amd_ryzen_2400g"),
        )
        rows = [
            {"cpk": "canonical-cpu-cpk", "identity": expected_data, "kind": "title_product"},
            {"cpk": "stale-epid-cpk", "identity": expected_data, "kind": "epid"},
        ]
        result = await resolve_identifiers(
            fake_registry_db(rows), title=title, category=None, brand=None,
            epid="EBAY-2400G", existing_cpk="stale-epid-cpk",
            existing_data=expected_data,
        )
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["cpk"], "canonical-cpu-cpk")
        self.assertTrue(any(claim["kind"] == "title_product" for claim in result["claims"]))

        accessory = "AMD Ryzen 5 2400G CPU cooler only"
        full_build = "Gaming PC complete build with AMD Ryzen 5 2400G, 16GB RAM and 1TB SSD"
        self.assertIsNone(last_resort_title_key(accessory, None))
        self.assertIsNone(last_resort_title_key(full_build, None))
        self.assertIsNone(last_resort_title_key(title, "ram"))
        self.assertFalse(any(c["kind"] == "title_product" for c in identifier_claims(
            title=accessory, category=None)))

    def test_cpu_titles_without_mpn_have_the_same_model_key(self):
        titles = [
            "AMD Ryzen 7 8500X3D Eight Core 5.20GHz Socket AM5",
            "AMD Ryzen 7 8500X3D 8-Core AM5 CPU 96MB L3 Processor",
            "AMD Ryzen 7 8500X3D Processor - Genuine Original AMD CPU - Fully Working",
        ]
        keys = {last_resort_title_key(title, "cpu") for title in titles}
        self.assertEqual(keys, {("title_product", "cpu", "amd", "amd_ryzen_8500x3d")})

    def test_cpu_model_number_matches_when_retailer_omits_ryzen_tier(self):
        detailed = "AMD Ryzen 7 9800X3D Eight Core 5.20GHz Socket AM5 Processor"
        abbreviated = "AMD Ryzen 9800X3D CPU"
        self.assertEqual(
            last_resort_title_key(detailed, "cpu"),
            last_resort_title_key(abbreviated, "cpu"),
        )
        self.assertEqual(
            last_resort_title_key(detailed, "cpu"),
            ("title_product", "cpu", "amd", "amd_ryzen_9800x3d"),
        )
        self.assertEqual(
            identity_conflicts(abbreviated, {
                "category": "cpu", "brand": "amd", "model": "amd_ryzen_7_9800x3d",
            }),
            [],
        )

    def test_ram_variant_signature_includes_capacity_sticks_speed_and_cl(self):
        a = "Corsair Vengeance DDR5 32GB (2x16GB) 6000MHz CL30"
        b = "CORSAIR Vengeance 2 x 16GB DDR5-6000 CL30 Memory Kit"
        c = "Corsair Vengeance DDR5 32GB (2x16GB) 6000MHz CL36"
        d = "Corsair Vengeance DDR5 32GB (4x8GB) 6000MHz CL30"
        e = "Corsair Vengeance DDR5 32GB (2x16GB) 6400MHz CL30"
        f = "Corsair Vengeance DDR5 64GB (2x32GB) 6000MHz CL30"
        self.assertEqual(variant_facts(a, "ram"), variant_facts(b, "ram"))
        expected = {"category": "ram", "variant_facts": variant_facts(a, "ram")}
        self.assertIn("cl", identity_conflicts(c, expected))
        self.assertIn("modules", identity_conflicts(d, expected))
        self.assertIn("speed", identity_conflicts(e, expected))
        self.assertIn("capacity_gb", identity_conflicts(f, expected))
        self.assertNotEqual(last_resort_title_key(a, "ram"), last_resort_title_key(c, "ram"))
        self.assertNotEqual(last_resort_title_key(a, "ram"), last_resort_title_key(d, "ram"))
        self.assertNotEqual(last_resort_title_key(a, "ram"), last_resort_title_key(e, "ram"))
        self.assertNotEqual(last_resort_title_key(a, "ram"), last_resort_title_key(f, "ram"))

    def test_storage_capacity_remains_a_distinct_product_variant(self):
        one_tb = "Samsung 990 PRO 1TB M.2 2280 NVMe SSD"
        two_tb = "Samsung 990 PRO 2TB M.2 2280 NVMe SSD"
        self.assertNotEqual(last_resort_title_key(one_tb, "ssd"),
                            last_resort_title_key(two_tb, "ssd"))

    async def test_manufacturer_model_number_outweighs_marketplace_asin_alias(self):
        title = "AMD Ryzen 7 8500X3D Processor"
        data = {
            "category": "cpu", "brand": "amd", "model": "amd_ryzen_7_8500x3d",
            "identity_source_title": title,
        }
        rows = [
            {"cpk": "model-cpk", "identity": data, "kind": "model_number"},
            {"cpk": "asin-cpk", "identity": data, "kind": "asin"},
        ]
        db = fake_registry_db(rows)

        result = await resolve_identifiers(
            db, title=title, category="cpu", brand="AMD", model_number="8500X3D",
            source_url="https://www.amazon.co.uk/dp/B012345678",
        )

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["cpk"], "model-cpk")


if __name__ == "__main__":
    unittest.main()
