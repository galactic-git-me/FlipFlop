"""Mocked adapter regressions; no app startup, engine connection or DB fixtures."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.playbook_commercial_quotes import (
    CoreQuoteRequest, create_playbook_commercial_quote, definition_hash, latest_listing_observations,
    save_cell_commercial_policy,
)
from app.api.commerce_intelligence import router
from app.routes.admin_auth import get_current_admin
from app.schemas.commercial_quote import CellCommercialPolicy
from test_playbook_commercial_quote import policy_data, parts


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.definition = {"id": "cell-1", "segment": "Gaming", "tier": "Budget", "components": {"cpu": "Exact CPU"}}
        policy = policy_data()
        policy["definition_sha256"] = definition_hash(self.definition)
        self.playbook = SimpleNamespace(id=1, name="Gaming", pricing_model={"commercial_cells": {"cell-1": policy}})
        self.db = MagicMock()
        self.db.commit = AsyncMock()
        self.db.refresh = AsyncMock(side_effect=lambda snapshot: setattr(snapshot, "id", 123))
        self.db.get = AsyncMock(return_value=None)
        self.db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=self.playbook)),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        ])
        self.body = CoreQuoteRequest(playbook_id=1, curated_build_id="cell-1")

    async def call(self):
        with patch("app.api.playbook_commercial_quotes.definitions", return_value={"builds": [self.definition]}):
            return await create_playbook_commercial_quote(self.body, self.db, SimpleNamespace(id=7))

    async def test_persists_complete_policy_and_identity_without_authorising_payment(self):
        result = await self.call()
        self.assertEqual(result["quote_snapshot_id"], 123)
        self.assertEqual(result["status"], "assessment_only")
        self.assertFalse(result["purchasable"])
        self.assertEqual(result["curated_build_id"], "cell-1")
        self.assertEqual(len(result["policy_sha256"]), 64)
        snapshot = self.db.add.call_args.args[0]
        self.assertEqual(snapshot.status, "assessment_only")
        self.assertEqual(snapshot.evidence_json["policy"]["version"], 1)
        self.assertEqual(snapshot.evidence_json["definition"], self.definition)
        self.assertEqual(self.db.add.call_count, 1)  # no capacity reservation/order
        self.db.commit.assert_awaited_once()

    async def test_rejects_definition_change_without_writing_snapshot(self):
        self.definition["components"]["cpu"] = "Different CPU"
        with self.assertRaises(HTTPException) as error:
            await self.call()
        self.assertEqual(error.exception.status_code, 409)
        self.db.add.assert_not_called()

    async def test_rejects_missing_policy_without_default_prices(self):
        self.playbook.pricing_model = {}
        with self.assertRaises(HTTPException) as error:
            await self.call()
        self.assertEqual(error.exception.status_code, 409)

    async def test_rejects_cell_from_different_parent(self):
        self.playbook.name = "Office"
        with self.assertRaises(HTTPException) as error:
            await self.call()
        self.assertEqual(error.exception.status_code, 404)

    async def test_manual_policy_update_is_disabled(self):
        data = self.playbook.pricing_model["commercial_cells"]["cell-1"]
        with self.assertRaises(HTTPException) as error:
            await save_cell_commercial_policy(1, "cell-1", CellCommercialPolicy.model_validate(data),
                                              self.db, SimpleNamespace(id=7))
        self.assertEqual(error.exception.status_code, 409)
        self.db.add.assert_not_called()

    async def test_stale_policy_version_cannot_overwrite_newer_policy(self):
        data = self.playbook.pricing_model["commercial_cells"]["cell-1"]
        with patch("app.api.playbook_commercial_quotes.definitions", return_value={"builds": [self.definition]}):
            with self.assertRaises(HTTPException) as error:
                await save_cell_commercial_policy(1, "cell-1", CellCommercialPolicy.model_validate(data),
                                                  self.db, SimpleNamespace(id=7))
        self.assertEqual(error.exception.status_code, 409)
        self.db.commit.assert_not_awaited()

    async def test_quotes_resolve_stored_offers_and_capacity_and_snapshot_all_inputs(self):
        current = datetime.now(timezone.utc)
        self.playbook.pricing_model["commercial_cells"]["cell-1"]["market"]["observed_at"] = current.isoformat()
        rows = []
        for part in parts():
            rows.append(SimpleNamespace(id=part.evidence_id, part_key=part.part_key,
                **{**part.offer.__dict__, "condition": part.offer.condition.value,
                   "observed_at": current, "evidence_source": "approved_observation",
                   "evidence_ref": f"listing:{part.evidence_id}", "delivery_estimate_source": "listing_estimate"}))
        self.db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=self.playbook)),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))),
        ]
        iso = current.date().isocalendar()
        cap = SimpleNamespace(id=5, build_week=f"{iso.year}-W{iso.week:02}", observed_at=current,
                              available_builds=5, evidence_source="workshop_review", evidence_ref="week:1")
        self.db.get.return_value = cap
        self.body.capacity_evidence_ids = {name: 5 for name in ("fast_track", "standard", "flexible")}
        with patch("app.services.commercial_quote_evidence.latest_capacity_evidence", AsyncMock(return_value=cap)), \
             patch("app.services.commercial_quote_evidence.active_hold_count", AsyncMock(return_value=0)):
            result = await self.call()
        self.assertTrue(all(quote["offerable"] for quote in result["modes"].values()))
        evidence = self.db.add.call_args.args[0].evidence_json
        self.assertEqual(len(evidence["supplier_offers"]), 6)
        self.assertEqual(evidence["capacities"]["standard"]["id"], 5)
        self.assertFalse(result["purchasable"])

    def test_request_cannot_override_price_or_policy(self):
        with self.assertRaises(ValidationError):
            CoreQuoteRequest(playbook_id=1, curated_build_id="cell-1", price_gbp="1")

    def test_newer_out_of_stock_evidence_supersedes_old_stock(self):
        old = SimpleNamespace(id=1, part_key="cpu", supplier="Amazon", channel="retail",
                              evidence_ref="listing:1", observed_at=datetime(2026, 10, 12, tzinfo=timezone.utc),
                              stock_confirmed=True)
        new = SimpleNamespace(**{**old.__dict__, "id": 2,
                              "observed_at": datetime(2026, 10, 13, tzinfo=timezone.utc), "stock_confirmed": False})
        self.assertEqual(latest_listing_observations([new, old]), [new])

    def test_route_keeps_admin_authentication(self):
        app = FastAPI()
        app.include_router(router)

        async def unauthorized():
            raise HTTPException(401, "Admin authentication required")

        app.dependency_overrides[get_current_admin] = unauthorized
        with TestClient(app) as client:
            response = client.post("/commerce-intelligence/playbook-quotes",
                                   json={"playbook_id": 1, "curated_build_id": "cell-1"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
