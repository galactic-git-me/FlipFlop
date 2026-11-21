"""Per-pace supplier choices must drive full-BOM prices and delivery gates."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from app.services.playbook_pace_sources import component_pace_sources

from app.services.playbook_service import estimate_delivery_products
from app.schemas.commercial_quote import CellCommercialPolicy
from app.services.commerce_pricing import Condition, SupplierOffer
from app.services.playbook_commercial_quote import PartEvidence, quote_delivery_modes
from app.services.commercial_pilot_policy import DELIVERY_CEILINGS
from app.services.commercial_quote_evidence import assess_stored_cell
from datetime import datetime, timedelta, timezone
from decimal import Decimal


class PaceQuoteChecks(unittest.TestCase):
    def test_pilot_delivery_ceilings_match_customer_promises(self):
        self.assertEqual(DELIVERY_CEILINGS, {
            "fast_track": 3, "standard": 5, "flexible": None})

    def test_automatic_policy_allows_unpromised_flexible_delivery(self):
        from app.services.playbook_service import automatic_policy
        parts = {"cpu": {"role": "cpu", "slot_id": 1, "variant_id": 2,
            "landed_gbp": "100.00", "quantity": 1}}
        settings = SimpleNamespace(opportunity_delivery_fallback_gbp=20,
            speedy_delivery_price_gbp=0, speedy_curated_custom_days=5,
            standard_curated_custom_days=9, flexible_curated_custom_days=14)
        policy = automatic_policy(parts,
            {"id": "TEST", "tier": "Budget", "components": {"cpu": "Test CPU"}},
            SimpleNamespace(profit_strategy={}), settings, include_market=False)
        self.assertIsNotNone(policy)
        self.assertEqual(policy.modes["fast_track"].maximum_delivery_working_days, 3)
        self.assertEqual(policy.modes["standard"].maximum_delivery_working_days, 5)
        self.assertIsNone(policy.modes["flexible"].maximum_delivery_working_days)

    def test_flexible_remains_offerable_without_a_standard_price_saving(self):
        now = datetime.now(timezone.utc)
        costs = {name: "0" for name in ["build_labour", "packaging", "outbound_delivery",
            "insurance", "payment_fixed", "expected_failure_cost", "allocated_overhead",
            "other_variable_costs"]}
        mode = {"costs": costs, "minimum_contribution_gbp": "60",
            "minimum_margin_fraction": "0.10", "premium_gbp": "0",
            "workshop_working_days": 1, "courier_working_days": 2,
            "maximum_delivery_working_days": 9}
        policy = CellCommercialPolicy.model_validate({"version": 1,
            "definition_sha256": "a" * 64, "required_part_keys": ["cpu"],
            "condition": "new", "vat_rate": "0", "payment_rate": "0.03",
            "warranty_rate": "0.05", "returns_rate": "0.02",
            "modes": {"standard": mode, "fast_track": {**mode,
                "maximum_delivery_working_days": 5}, "flexible": {**mode,
                "maximum_delivery_working_days": None}},
            "enabled_modes": ["standard", "fast_track", "flexible"]})
        offer = SupplierOffer("Amazon", "retail", Condition.NEW, Decimal("100"),
            Decimal("0"), Decimal("0"), Decimal("0"), now.isoformat(), True,
            True, 1, Decimal("1"))
        result = quote_delivery_modes(policy, [PartEvidence(1, "cpu", offer)], {}, now=now)
        self.assertTrue(result["modes"]["standard"]["offerable"])
        self.assertTrue(result["modes"]["flexible"]["offerable"])
        self.assertEqual(result["modes"]["flexible"]["difference_from_standard_gbp"], "0.00")

    def test_same_url_explicit_supplier_eta_survives_duplicate_without_eta(self):
        now = datetime.now(timezone.utc).isoformat()
        url = "https://www.overclockers.co.uk/exact-cpu/PRO-AMD-02677.html"
        captured = {"url": url, "source": "overclockers", "item_gbp": "100",
            "delivery_gbp": "0", "observed_at": now, "condition": "new",
            "listing_type": "buy_it_now", "stock_status": "available",
            "stock_evidence": "In stock", "fresh": True, "active_listing": True,
            "commercial_capture_verified": True, "postage_verified": True,
            "stock_confirmed": True}
        part = {"role": "cpu", "variant_id": 1, "listing_id": 1,
            "title": "AMD Ryzen 5 9600X", "source_url": url,
            "source_observation": {**captured, "delivery_working_days": 1,
                "delivery_estimate_source": "retailer_page_displayed_estimate"},
            "supplier_offers": [{**captured, "delivery_working_days": None}]}
        class EmptyResult:
            def scalars(self):
                return self
            def all(self):
                return []
        class EmptySession:
            async def execute(self, _query):
                return EmptyResult()
        policy = SimpleNamespace(modes={
            "fast_track": SimpleNamespace(maximum_delivery_working_days=5,
                workshop_working_days=1, courier_working_days=2),
            "standard": SimpleNamespace(maximum_delivery_working_days=9,
                workshop_working_days=1, courier_working_days=2),
            "flexible": SimpleNamespace(maximum_delivery_working_days=None,
                workshop_working_days=1, courier_working_days=2),
        })
        with patch("app.services.playbook_service._current_suggested_supplier_source",
                   side_effect=lambda payload: payload["suggested_supplier_offer"]), \
             patch("app.services.playbook_service._supplier_fact_is_approvable", return_value=True):
            result = asyncio.run(component_pace_sources({"cpu": part}, policy, EmptySession()))
        self.assertTrue(result["fast_track"][0]["available"])
        self.assertEqual(result["fast_track"][0]["sources"][0]["delivery_working_days"], 1)

    def test_flexible_quote_prices_fixed_price_fallback_not_auction(self):
        now = datetime.now(timezone.utc)
        costs = {name: "0" for name in ["build_labour", "packaging", "outbound_delivery",
            "insurance", "payment_fixed", "expected_failure_cost", "allocated_overhead",
            "other_variable_costs"]}
        mode = {"costs": costs, "minimum_contribution_gbp": "1",
            "minimum_margin_fraction": "0.10", "premium_gbp": "0",
            "workshop_working_days": 1, "courier_working_days": 2,
            "maximum_delivery_working_days": 9}
        policy = CellCommercialPolicy.model_validate({"version": 1,
            "definition_sha256": "a" * 64, "required_part_keys": ["cpu"],
            "condition": "new", "vat_rate": "0", "payment_rate": "0",
            "warranty_rate": "0.05", "returns_rate": "0",
            "market_tolerance_fraction": Decimal("0"),
            "modes": {"standard": mode, "fast_track": {**mode,
                "maximum_delivery_working_days": 5}, "flexible": {**mode,
                "maximum_delivery_working_days": None}},
            "enabled_modes": ["standard", "fast_track", "flexible"]})
        auction = SupplierOffer("eBay", "marketplace", Condition.NEW, Decimal("40"),
            Decimal("0"), Decimal("0"), Decimal("0"), now.isoformat(), True,
            True, 2, Decimal("1"))
        retail = SupplierOffer("Retailer", "retail", Condition.NEW, Decimal("100"),
            Decimal("0"), Decimal("0"), Decimal("0"), now.isoformat(), True,
            True, 3, Decimal("1"))
        unknown_marketplace = SupplierOffer("Marketplace seller", "marketplace", Condition.NEW,
            Decimal("50"), Decimal("0"), Decimal("0"), Decimal("0"), now.isoformat(),
            True, True, 2, Decimal("1"))
        parts = [PartEvidence(1, "cpu", auction, "auction"),
                 PartEvidence(2, "cpu", retail, "buy_it_now"),
                 PartEvidence(3, "cpu", unknown_marketplace, None)]
        result = quote_delivery_modes(policy, parts, {}, now=now)
        flexible = result["modes"]["flexible"]
        self.assertTrue(flexible["offerable"])
        self.assertEqual(flexible["supplier_offer_ids"], [2])
        self.assertEqual(flexible["expected_delivery_working_days"], 6)

        row = SimpleNamespace(id=2, part_key="cpu", supplier="Retailer", channel="retail",
            condition="new", item_gbp=Decimal("100"), delivery_gbp=Decimal("0"),
            fees_gbp=Decimal("0"), risk_gbp=Decimal("0"),
            observed_at=now, stock_confirmed=True, delivery_working_days=3,
            prime_eligible=None, supplier_confidence=Decimal("1"),
            evidence_source="reviewed", evidence_ref="https://retailer.example/cpu",
            delivery_estimate_source="captured")
        class Result:
            def __init__(self, values):
                self.values = values
            def scalars(self):
                return self
            def all(self):
                return self.values
        class Session:
            def __init__(self):
                self.calls = 0
            async def execute(self, _query):
                self.calls += 1
                return Result([row] if self.calls == 1 else [])
        body = SimpleNamespace(curated_build_id="TEST", capacity_evidence_ids={},
            nonnew_consent=False, model_dump=lambda **_: {})
        assessed, _evidence = asyncio.run(assess_stored_cell(
            Session(), SimpleNamespace(id=1), {}, policy, body))
        self.assertEqual(assessed["modes"]["flexible"]["expected_delivery_working_days"], 6)

    def test_mode_specific_current_supplier_sources_price_all_three_paces(self):
        costs = SimpleNamespace(model_dump=lambda: {"packaging": "0"})
        modes = {
            "fast_track": SimpleNamespace(maximum_delivery_working_days=5,
                workshop_working_days=1, courier_working_days=2, costs=costs),
            "standard": SimpleNamespace(maximum_delivery_working_days=9,
                workshop_working_days=1, courier_working_days=2, costs=costs),
            "flexible": SimpleNamespace(maximum_delivery_working_days=None,
                workshop_working_days=1, courier_working_days=2, costs=costs),
        }
        policy = SimpleNamespace(modes=modes, market=None)
        parts = {"cpu": {"role": "cpu", "variant_id": 12, "quantity": 1,
            "listing_price_gbp": "90", "supplier_postage_gbp": "0",
            "title": "AMD Ryzen 7 8500X3D CPU",
            "source_observation": {"fresh": False, "active_listing": False,
                "stock_status": "unknown"}},
            "os_secondary": {"role": "os_secondary", "variant_id": 77, "quantity": 1,
                "listing_price_gbp": "0", "supplier_postage_gbp": "0",
                "title": "Ubuntu 24.04 LTS Desktop (official free download)",
                "source_observation": {"fresh": False, "active_listing": False,
                    "stock_status": "unknown"}}}
        def source(price, days, listing_type="buy_it_now"):
            result = {"url": f"https://retailer.example/cpu?price={price}",
                "source": "retailer", "item_gbp": str(price), "delivery_gbp": "5",
                "postage_verified": True, "delivery_working_days": days,
                "listing_type": listing_type,
                "delivery_estimate_source": "captured supplier ETA", "observed_at": "2026-11-17T00:00:00+00:00"}
            if listing_type == "auction":
                result["listing_ends_at"] = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
            return result
        pace_sources = {
            "fast_track": [{"role": "cpu", "variant_id": 12, "available": True,
                "sources": [source(100, 2)]}],
            "standard": [{"role": "cpu", "variant_id": 12, "available": True,
                "sources": [source(90, 6)]}],
            # Flex may use the cheapest retailer fallback even when it is not
            # cheaper than Standard; auction savings are an option, not a gate.
            "flexible": [{"role": "cpu", "variant_id": 12, "available": True,
                "sources": [source(1, 3, "auction"), source(110, 10)]}],
        }
        free_os = {"url": "https://releases.ubuntu.com/24.04/", "source": "Ubuntu",
            "item_gbp": "0", "delivery_gbp": "0", "postage_verified": True,
            "delivery_working_days": 0, "listing_type": "software_download",
            "delivery_estimate_source": "official_software_download",
            "observed_at": "2026-11-17T00:00:00+00:00"}
        for mode in pace_sources:
            pace_sources[mode].append({"role": "os_secondary", "variant_id": 77,
                "available": True, "sources": [free_os]})
        seen_landed = []
        def economics(_policy, _mode, landed):
            seen_landed.append(landed)
            return {"price": landed + 30, "floor": landed + 30, "true_cost": landed,
                "net": landed + 30, "contribution": 30, "charges": {}}

        with patch("app.services.playbook_service.required_parts", return_value={"cpu", "os_secondary"}), \
             patch("app.services.playbook_service.automatic_policy", return_value=policy), \
             patch("app.services.playbook_commercial_quote.mode_economics", side_effect=economics):
            result = estimate_delivery_products(parts, {"id": "TEST", "tier": "Budget"},
                SimpleNamespace(), SimpleNamespace(), pace_sources=pace_sources)

        self.assertEqual(seen_landed, [105, 95, 115])
        self.assertTrue(result["fast_track"]["available"])
        self.assertEqual(result["fast_track"]["supplier_arrival_working_days"], 2)
        self.assertTrue(result["standard"]["available"])
        self.assertEqual(result["standard"]["supplier_arrival_working_days"], 6)
        self.assertTrue(result["flexible"]["available"])
        self.assertEqual(result["flexible"]["supplier_arrival_working_days"], 10)
        self.assertEqual(len(result["flexible"]["auction_options"]), 1)
        self.assertEqual(result["flexible"]["expected_delivery_working_days"], 17)
        self.assertEqual(result["flexible"]["selected_supplier_sources"][0]["listing_type"], "buy_it_now")

        # An auction that expires outside the seven-day window does not make
        # the proposal claim the auction-plus-fallback planning estimate.
        pace_sources["flexible"][0]["sources"][0]["listing_ends_at"] = (
            datetime.now(timezone.utc) + timedelta(days=8)).isoformat()
        with patch("app.services.playbook_service.required_parts", return_value={"cpu", "os_secondary"}), \
             patch("app.services.playbook_service.automatic_policy", return_value=policy), \
             patch("app.services.playbook_commercial_quote.mode_economics", side_effect=economics):
            fallback = estimate_delivery_products(parts, {"id": "TEST", "tier": "Budget"},
                SimpleNamespace(), SimpleNamespace(), pace_sources=pace_sources)
        self.assertEqual(fallback["flexible"]["auction_options"], [])
        self.assertEqual(fallback["flexible"]["expected_delivery_working_days"], 13)
        self.assertEqual(fallback["flexible"]["timing_basis"], "flexible_vendor_fallback")

        # Expired lots are also excluded, even if they ended within the seven-day window.
        pace_sources["flexible"][0]["sources"][0]["listing_ends_at"] = (
            datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with patch("app.services.playbook_service.required_parts", return_value={"cpu", "os_secondary"}), \
             patch("app.services.playbook_service.automatic_policy", return_value=policy), \
             patch("app.services.playbook_commercial_quote.mode_economics", side_effect=economics):
            expired = estimate_delivery_products(parts, {"id": "TEST", "tier": "Budget"},
                SimpleNamespace(), SimpleNamespace(), pace_sources=pace_sources)
        self.assertEqual(expired["flexible"]["auction_options"], [])
        self.assertEqual(expired["flexible"]["expected_delivery_working_days"], 13)


if __name__ == "__main__":
    unittest.main()
