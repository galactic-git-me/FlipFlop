"""New isolated checks. No database, browser, worker or external provider is used."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from decimal import Decimal as D
from app.services.playbook_mvp import trusted_url,publication_limit_reason,source_facts_can_be_verified,mvp_mode,mvp_enabled
from app.schemas.commercial_quote import CellCommercialPolicy
from app.services.playbook_commercial_quote import quote_delivery_modes,PartEvidence
from app.services.commerce_pricing import SupplierOffer,Condition

class MvpChecks(unittest.TestCase):
    def setUp(self):
        self.parent=SimpleNamespace(pricing_model={"mvp_autonomy":{"profile":"matrix_mvp","enabled":True,"budget_ceilings":{"A":1000},"price_anchors":{"A":"900"},"max_price_change_fraction":"0.10"}})
        self.offer={"delivery_products":{"standard":{"recommended_price_gbp":"950"}},"components":[{"source_url":"https://www.amazon.co.uk/dp/B012345678"}]}
    def test_publishing_stays_inside_budget_and_fixed_anchor(self):
        self.assertIsNone(publication_limit_reason(self.parent,{"id":"A"},self.offer))
        self.offer["delivery_products"]["standard"]["recommended_price_gbp"]="999"
        self.assertIn("price moved",publication_limit_reason(self.parent,{"id":"A"},self.offer))
    def test_model_progress_does_not_invalidate_a_commercial_revision(self):
        from app.services.playbook_mvp import commercial_revision_payload
        before={"components":[{"variant_id":1,"photo_ready":True,"media_ready":False,"model_generation_status":"STARTING"}]}
        after={"components":[{"variant_id":1,"photo_ready":True,"media_ready":True,"model_generation_status":"DRAFT_CREATED"}]}
        self.assertEqual(commercial_revision_payload(before),commercial_revision_payload(after))
        self.assertIn("model_generation_status",before["components"][0])

    def test_missing_budget_cannot_auto_publish(self):
        self.assertIn("budget ceiling",publication_limit_reason(self.parent,{"id":"B"},self.offer))
    def test_unknown_or_spoofed_supplier_is_rejected(self):
        for url in ["https://amazon.co.uk.evil.example/p","http://amazon.co.uk/p","https://admin:password@amazon.co.uk/p"]:
            self.assertFalse(trusted_url(url))
    def test_pausing_automation_keeps_the_mvp_presentation(self):
        self.parent.pricing_model["mvp_autonomy"]["enabled"]=False
        self.assertTrue(mvp_mode(self.parent));self.assertFalse(mvp_enabled(self.parent))
    def test_only_current_complete_uncontradicted_exact_facts_can_be_auto_verified(self):
        now=datetime.now(timezone.utc)
        suggestion={"status":"review_ready","source_url":"https://overclockers.co.uk/p","captured_at":now.isoformat(),"suggested_specs":{"socket":"AM5"},"missing_fields":[],"conflicted_fields":[],"reviewed_value_changes":{}}
        self.assertTrue(source_facts_can_be_verified(suggestion,now))
        for patch in [{"missing_fields":["ram_type"]},{"conflicted_fields":["socket"]},{"reviewed_value_changes":{"socket":{}}},{"captured_at":(now+timedelta(days=1)).isoformat()},{"captured_at":(now-timedelta(days=31)).isoformat()}]:
            self.assertFalse(source_facts_can_be_verified({**suggestion,**patch},now))
    def test_standard_can_sell_while_other_modes_are_explicitly_disabled(self):
        now=datetime.now(timezone.utc)
        costs={name:"0" for name in ["build_labour","packaging","outbound_delivery","insurance","payment_fixed","expected_failure_cost","allocated_overhead","other_variable_costs"]}
        mode=dict(costs=costs,minimum_contribution_gbp="60",minimum_margin_fraction="0.10",premium_gbp="0",workshop_working_days=1,courier_working_days=1,maximum_delivery_working_days=5)
        policy=CellCommercialPolicy.model_validate(dict(version=1,definition_sha256="a"*64,required_part_keys=["cpu"],condition="new",vat_rate="0",payment_rate="0.03",warranty_rate="0.05",returns_rate="0.02",modes={name:mode for name in ["standard","fast_track","flexible"]},enabled_modes=["standard"]))
        part=PartEvidence(1,"cpu",SupplierOffer("Amazon","retail",Condition.NEW,D("100"),D("0"),D("0"),D("0"),now.isoformat(),True,True,1))
        result=quote_delivery_modes(policy,[part],{},now=now)
        self.assertTrue(result["modes"]["standard"]["offerable"])
        self.assertFalse(result["modes"]["fast_track"]["offerable"])
        self.assertFalse(result["modes"]["flexible"]["offerable"])
        self.assertIsNone(result["modes"]["fast_track"]["price_gbp"])

class AsyncMvpChecks(unittest.IsolatedAsyncioTestCase):
    async def test_paused_autonomy_does_not_withdraw_offers_or_touch_database(self):
        from app.services.playbook_mvp import withdraw_unsafe_offers
        from unittest.mock import AsyncMock
        db=SimpleNamespace(execute=AsyncMock(side_effect=AssertionError("No writes or queries expected")))
        parent=SimpleNamespace(pricing_model={"mvp_autonomy":{"profile":"matrix_mvp","enabled":False}})
        self.assertEqual(await withdraw_unsafe_offers(db,{"Gaming":parent}),[])
        db.execute.assert_not_called()

    async def test_one_failed_publication_does_not_stop_other_cells_and_no_media_approval_is_called(self):
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock,patch
        from fastapi import HTTPException
        from app.services.curated_build_policy import definitions
        from app.services.playbook_mvp import maintain_offers
        from app.services.playbook_service import SOURCE
        first=definitions()["builds"][0]
        second=next(row for row in definitions()["builds"] if row["segment"]==first["segment"] and row["id"]!=first["id"])
        rows=[first,second]
        parent=SimpleNamespace(id=1,pricing_model={"mvp_autonomy":{"profile":"matrix_mvp","enabled":True,"budget_ceilings":{row["id"]:1000 for row in rows}}})
        offers=[{"cell_id":row["id"],"segment":row["segment"],"blockers":[],"revision_sha256":"a"*64,"delivery_products":{"standard":{"recommended_price_gbp":"900"}},"components":[{"source_url":"https://amazon.co.uk/product"}]} for row in rows]
        proposals=[SimpleNamespace(id=index+1,proposed_data={"cell_id":row["id"]},demand_signals={"source":SOURCE}) for index,row in enumerate(rows)]
        @asynccontextmanager
        async def savepoint():yield
        db=SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda:SimpleNamespace(all=lambda:proposals))),refresh=AsyncMock(),begin_nested=savepoint)
        with patch("app.services.playbook_mvp.withdraw_unsafe_offers",new=AsyncMock(return_value=[])), patch("app.services.playbook_service.approve_proposal",new=AsyncMock(side_effect=[HTTPException(409,"Source changed"),{}])) as approve, patch("app.api.assets_admin.approve_variant_media",new=AsyncMock()) as photos, patch("app.api.assets_admin.publish_review_batch",new=AsyncMock()) as models:
            result=await maintain_offers(db,{first["segment"]:parent},offers)
            self.assertEqual(result["published"],[second["id"]])
            self.assertEqual(result["exceptions"][0]["cell_id"],first["id"])
            self.assertEqual(approve.await_count,2)
            photos.assert_not_called();models.assert_not_called()

class OwnerPhotoChecks(unittest.TestCase):
    def test_exact_build_media_can_include_hidden_custom_only_variants(self):
        from app.api.assets_admin import catalogue_asset_queue_query
        from sqlalchemy.dialects import postgresql
        sql=str(catalogue_asset_queue_query("curated",[31005,32277]).compile(dialect=postgresql.dialect(),compile_kwargs={"literal_binds":True}))
        where=sql.split("WHERE",1)[1].split("ORDER BY",1)[0]
        self.assertNotIn("status",where)
        self.assertIn("custom_for_builds",where)
        self.assertIn("31005",where)

    def test_unscoped_inventory_retains_its_catalogue_and_status_filters(self):
        from app.api.assets_admin import catalogue_asset_queue_query
        from sqlalchemy.dialects import postgresql
        sql=str(catalogue_asset_queue_query("curated",None).compile(dialect=postgresql.dialect(),compile_kwargs={"literal_binds":True}))
        where=sql.split("WHERE",1)[1].split("ORDER BY",1)[0]
        self.assertIn("pending_review",where)
        self.assertIn("curated_for_builds",where)
        self.assertNotIn("custom_for_builds",where)

    def test_photo_led_publication_needs_a_real_owner_selection(self):
        from app.services.shared_variant_assets import approved_model_photos
        variant=SimpleNamespace(asset_media_review={"status":"auto_included","model_image_urls":["https://images.example/a.jpg"]})
        self.assertEqual(approved_model_photos(variant),[])
        variant.asset_media_review["model_references_selected_by"]="owner@example.invalid"
        self.assertEqual(approved_model_photos(variant),["https://images.example/a.jpg"])
        variant.asset_media_review["model_image_urls"]=[{"invalid":"url"}]
        self.assertEqual(approved_model_photos(variant),[])

if __name__=="__main__":unittest.main()

