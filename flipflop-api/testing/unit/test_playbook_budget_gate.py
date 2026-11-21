import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.playbook_service import apply_cell_budget_gate


class PlaybookBudgetGateTests(unittest.TestCase):
    def test_disables_only_modes_over_the_cell_budget(self):
        offer = {
            "tier": "Budget",
            "blockers": [],
            "delivery_products": {
                "fast_track": {"available": True, "recommended_price_gbp": "1325.00"},
                "standard": {"available": True, "recommended_price_gbp": "1299.99"},
                "flexible": {"available": True, "recommended_price_gbp": "1300.00"},
            },
        }

        apply_cell_budget_gate(offer, 1300)

        self.assertFalse(offer["delivery_products"]["fast_track"]["available"])
        self.assertEqual(offer["delivery_products"]["fast_track"]["recommended_price_gbp"], "1325.00")
        self.assertIn("budget ceiling £1300.00", offer["delivery_products"]["fast_track"]["reason"])
        self.assertTrue(offer["delivery_products"]["standard"]["available"])
        self.assertTrue(offer["delivery_products"]["flexible"]["available"])
        self.assertEqual(len(offer["blockers"]), 1)
        self.assertTrue(offer["blockers"][0].startswith("fast_track:"))

    def test_unbounded_high_end_allows_quotes_without_inventing_a_ceiling(self):
        offer = {
            "tier": "High-end",
            "blockers": [],
            "delivery_products": {
                "standard": {"available": True, "recommended_price_gbp": "12545.77"},
                "flexible": {"available": True, "recommended_price_gbp": "12545.77"},
            },
        }

        result = apply_cell_budget_gate(offer, None)

        self.assertIs(result, offer)
        self.assertTrue(offer["delivery_products"]["standard"]["available"])
        self.assertTrue(offer["delivery_products"]["flexible"]["available"])
        self.assertEqual(offer["blockers"], [])

    def test_missing_ceiling_blocks_every_mode_for_bounded_tier(self):
        offer = {
            "tier": "Budget",
            "blockers": [],
            "delivery_products": {
                "standard": {"available": True, "recommended_price_gbp": "899.00"},
                "flexible": {"available": True, "recommended_price_gbp": "899.00"},
            },
        }

        apply_cell_budget_gate(offer, None)

        self.assertFalse(offer["delivery_products"]["standard"]["available"])
        self.assertFalse(offer["delivery_products"]["flexible"]["available"])
        self.assertIn("Configured cell budget ceiling is missing", offer["blockers"])


class ConfiguredPlaybookBudgetGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_cell_range_blocks_review_and_fingerprints_the_blocker(self):
        from app.services.playbook_service import apply_configured_cell_budget_gate

        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            scalar_one_or_none=lambda: None)))
        offer = {"blockers": [], "delivery_products": {}}
        definition = {"id": "TEST-01", "segment": "Test", "tier": "Budget"}
        parent = SimpleNamespace(pricing_model={})

        result = await apply_configured_cell_budget_gate(db, definition, parent, offer)

        self.assertIn("Configured customer budget range is missing", result["blockers"])
        self.assertEqual(len(result["revision_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
