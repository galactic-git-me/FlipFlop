"""Real persistence/locking regressions, restricted to an explicit disposable DB."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.engine import make_url

import app.models  # register schema before creating disposable tables
from app.database import Base, engine, AsyncSessionLocal
from app.models.customer import Customer
from app.models.order import Order
from app.models.playbook import Playbook
from app.models.catalogue import CatalogueVariant, CaseCatalogue, PlaybookSlot
from app.models.listing import Listing
from app.models.commerce_evidence import SupplierOfferEvidence, WorkshopCapacityEvidence, PriceQuoteSnapshot, WorkshopCapacityReservation
from app.models.order_checkout_snapshot import OrderCheckoutSnapshot
from app.schemas.payment import PlaybookBuildConfig, CreatePaymentIntentRequest
from app.schemas.commercial_quote import CellCommercialPolicy
from app.services.commercial_quote_evidence import definition_hash
from app.services.commercial_checkout import (
    create_checkout_quote, load_checkout_policy, accept_checkout_quote,
    commercial_order_snapshot, accepted_summary,
)
from app.api.playbook_commercial_quotes import save_cell_commercial_policy
from test_playbook_commercial_quote import policy_data, parts


class CommercialPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not (make_url(str(engine.url)).database or "").endswith("_test"):
            self.skipTest("Requires an explicitly selected disposable PostgreSQL _test database")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.db = AsyncSessionLocal()
        suffix = uuid4().hex[:12]
        self.definition = {"id": f"CELL-{suffix}", "segment": f"Gaming {suffix}", "tier": "Budget", "components": {
            "cpu": "Exact CPU", "motherboard": "Exact motherboard", "ram": "Exact RAM",
            "cooling": "Exact cooler", "psu": "Exact PSU", "storage": "Exact SSD",
            "case": "Exact Case"}}
        self.playbook = Playbook(name=self.definition["segment"], status="active")
        self.customer = Customer(name="Test customer", email=f"commercial-{suffix}@example.test")
        self.db.add_all([self.playbook, self.customer])
        await self.db.flush()

        role_specs = {
            "cpu": {"socket": "AM4", "cpu_id": "Exact CPU", "integrated_graphics": True, "power_w": 65},
            "motherboard": {"socket": "AM4", "ram_type": "DDR4", "ram_slots": 4,
                "form_factor": "atx", "m2_slots": 1, "m2_lengths": ["2280"],
                "storage_interfaces": ["nvme"], "bios_cpu_ids": ["Exact CPU"]},
            "ram": {"ram_type": "DDR4", "ram_modules": 2, "ram_height_mm": 35},
            "cooling": {"supported_sockets": ["AM4"], "height_mm": 120, "ram_clearance_mm": 40},
            "psu": {"form_factor": "ATX", "wattage": 650, "length_mm": 140},
            "storage": {"storage_interface": "nvme", "m2_length": "2280"},
        }
        slots = {}
        variants = {}
        self.listings = {}
        for role, specs in role_specs.items():
            slot = PlaybookSlot(playbook_id=self.playbook.id, slot_type=role)
            self.db.add(slot)
            await self.db.flush()
            listing = Listing(external_id=f"checkout-fixture:{suffix}:{role}", source_id=0,
                source_name="test", source_confidence="fixture", title=f"Exact {role}",
                url=f"https://example.test/{suffix}/{role}", price=100,
                image_urls=[], condition="new", listing_type="buy_it_now", status="active",
                raw_specs={"configurator": {**specs, "reviewed": True,
                    "source_url": f"https://example.test/{suffix}/{role}"}})
            self.db.add(listing)
            await self.db.flush()
            variant = CatalogueVariant(listing_id=listing.id, slot_id=slot.id, status="active",
                display_price=100, tier="mid", curated_for_builds=True)
            self.db.add(variant)
            await self.db.flush()
            slots[role] = slot
            variants[role] = variant
            self.listings[role] = listing
        self.case = CaseCatalogue(name="Exact Case", brand="Fixture", form_factor="atx",
            rrp_gbp=100, status="active", max_cooler_height_mm=150,
            notes=json.dumps({"configurator": {"reviewed": True, "psu_form_factors": ["ATX"],
                "max_psu_length_mm": 160}}))
        self.db.add(self.case)
        await self.db.flush()
        data = policy_data()
        self.slot_selections = {slots[role].id: variants[role].id for role in role_specs}
        self.configured_parts = {slots[role].id: (variants[role].id, role) for role in role_specs}
        data.update(definition_sha256=definition_hash(self.definition), checkout_enabled=True,
                    required_part_keys=[*role_specs, "case"],
                    checkout_slot_parts=self.configured_parts,
                    checkout_case=(self.case.id, "case"))
        self.now = datetime.now(timezone.utc)
        data["market"]["observed_at"] = self.now.isoformat()
        data["market"]["sold_median_gbp"] = "10000"
        self.policy = CellCommercialPolicy.model_validate(data)
        self.playbook.pricing_model={"commercial_cells": {self.definition["id"]: self.policy.model_dump(mode="json")}}
        self.config = PlaybookBuildConfig(playbook_id=self.playbook.id, slot_selections=self.slot_selections,
                                          case_id=self.case.id, curated_build_id=self.definition["id"], validation_mode="curated")
        self.rows = []
        templates = {part.part_key: part for part in parts()}
        fixture_parts = list(parts())
        for role in role_specs:
            if role == "cpu":
                continue
            template = templates["cpu"]
            for supplier, cost, days, channel in (("Amazon", "300", 1, "retail"),
                                                  ("Retailer", "280", 3, "retail"),
                                                  ("eBay", "220", 7, "marketplace")):
                fixture_parts.append(type(template)(0, role, type(template.offer)(
                    supplier, channel, template.offer.condition, Decimal(cost), Decimal("5"), Decimal("0"),
                    Decimal("2"), self.now.isoformat(), True, True, days)))
        await self.db.flush()
        for part in fixture_parts:
            offer = part.offer
            row = SupplierOfferEvidence(part_key=part.part_key, supplier=offer.supplier,
                channel=offer.channel, condition=offer.condition.value, item_gbp=offer.item_gbp,
                delivery_gbp=offer.delivery_gbp, fees_gbp=offer.fees_gbp, risk_gbp=offer.risk_gbp,
                observed_at=self.now, stock_confirmed=True, delivery_working_days=offer.delivery_working_days,
                supplier_confidence=Decimal(1), evidence_source="disposable_fixture",
                evidence_ref=f"listing:{part.part_key}:{offer.supplier}", captured_by_admin_id=0)
            self.rows.append(row)
        iso = self.now.date().isocalendar()
        self.capacity = WorkshopCapacityEvidence(build_week=f"{iso.year}-W{iso.week:02}", available_builds=20,
            observed_at=self.now, evidence_source="disposable_fixture", evidence_ref="workshop:fixture", captured_by_admin_id=0)
        self.db.add_all([*self.rows, self.capacity])
        await self.db.flush()
        self.patches = [patch("app.services.commercial_checkout.definitions", return_value={"builds":[self.definition]}),
                        patch("app.api.playbook_commercial_quotes.definitions", return_value={"builds":[self.definition]}),
                        patch("app.services.curated_build_policy.definitions", return_value={"builds":[self.definition]})]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        if hasattr(self, "db"):
            await self.db.rollback()
            await self.db.close()
            for item in self.patches:
                item.stop()

    async def accept(self, quote, mode="flexible"):
        loaded = await load_checkout_policy(self.db, self.config)
        return await accept_checkout_quote(self.db, self.config, quote["quote_snapshot_id"], mode,
            self.customer.id, loaded, {"playbook_id": self.playbook.id, "curated_build_id": self.config.curated_build_id,
                "slots": [{"slot_id":slot_id,"variant_id":variant_id,
                    "title":"Exact CPU" if role=="cpu" else f"Exact {role}"}
                    for slot_id,(variant_id,role) in self.configured_parts.items()],
                "case_id":self.case.id, "parts_total":999,
                "software_profile":{"recommended_package_ids":[]}})

    async def test_manual_policy_entry_is_disabled(self):
        with self.assertRaises(HTTPException) as error:
            await save_cell_commercial_policy(self.playbook.id, self.config.curated_build_id,
                self.policy, self.db, SimpleNamespace(id=42))
        self.assertEqual(error.exception.status_code, 409)

    async def test_public_response_hides_costs_and_profit(self):
        quote = await create_checkout_quote(self.db,self.config)
        self.assertEqual(quote["pricing_mode"],"commercial")
        self.assertTrue(all(mode["offerable"] for mode in quote["modes"].values()))
        self.assertNotIn("contribution_gbp",str(quote))
        self.assertNotIn("supplier_offer_ids",str(quote))
        self.assertLess(Decimal(quote["modes"]["flexible"]["price_gbp"]), Decimal(quote["modes"]["standard"]["price_gbp"]))

    async def test_quote_creation_requires_reviewed_fit_and_integrated_graphics(self):
        cpu = self.listings["cpu"]
        original = deepcopy(cpu.raw_specs)
        cpu.raw_specs = {**original, "configurator": {**original["configurator"], "reviewed": False}}
        await self.db.flush()
        with self.assertRaises(HTTPException) as unreviewed:
            await create_checkout_quote(self.db, self.config)
        self.assertEqual(unreviewed.exception.status_code, 409)

        cpu.raw_specs = {**original, "configurator": {**original["configurator"], "integrated_graphics": False}}
        await self.db.flush()
        with self.assertRaises(HTTPException) as no_graphics:
            await create_checkout_quote(self.db, self.config)
        self.assertEqual(no_graphics.exception.status_code, 409)

    async def test_acceptance_is_frozen_and_retries_reuse_one_hold(self):
        quote = await create_checkout_quote(self.db,self.config)
        self.assertTrue(quote["modes"]["flexible"]["offerable"], quote["modes"]["flexible"])
        accepted = await self.accept(quote)
        again = await self.accept(quote)
        self.assertEqual(accepted.id,again.id)
        holds=(await self.db.execute(select(WorkshopCapacityReservation).where(WorkshopCapacityReservation.quote_snapshot_id==accepted.id))).scalars().all()
        self.assertEqual(len(holds),1)
        snapshot=await commercial_order_snapshot(self.db,{"commercial_quote_snapshot_id":str(accepted.id)},
                                                self.customer.id,accepted.decision_json["quote"]["price_gbp"])
        self.assertEqual(snapshot["commercial_quote"],accepted_summary(accepted))
        self.assertEqual(snapshot["delivery_option"],"flexible")
        self.assertEqual(snapshot["slots"][0]["title"],"Exact CPU")

    async def test_checkout_does_not_need_a_weekly_build_count_or_create_a_slot_hold(self):
        await self.db.delete(self.capacity)
        await self.db.flush()
        # Keep other tests' persisted schedule evidence from leaking into this
        # no-capacity scenario; schedule hints are optional and should create
        # no hold when the current quote carries no capacity evidence.
        with patch("app.services.commercial_checkout.current_capacity_ids", AsyncMock(return_value={})):
            quote = await create_checkout_quote(self.db, self.config)
            self.assertTrue(all(mode["offerable"] for mode in quote["modes"].values()))
            accepted = await self.accept(quote)
        reservations = (await self.db.execute(select(WorkshopCapacityReservation).where(
            WorkshopCapacityReservation.quote_snapshot_id == accepted.id
        ))).scalars().all()
        self.assertEqual(reservations, [])

    async def test_changed_component_or_case_cannot_use_core_quote(self):
        quote = await create_checkout_quote(self.db,self.config)
        changed_selections=dict(self.config.slot_selections)
        first_slot=next(iter(changed_selections))
        changed_selections[first_slot]=max(changed_selections.values())+1000
        for updates in ({"slot_selections":changed_selections},{"case_id":self.case.id+1000}):
            altered=self.config.model_copy(update=updates)
            with self.assertRaises(HTTPException) as error:
                await load_checkout_policy(self.db,altered)
            self.assertEqual(error.exception.status_code,409)

    async def test_new_out_of_stock_observation_requires_new_customer_quote(self):
        quote=await create_checkout_quote(self.db,self.config)
        row=self.rows[2]
        self.db.add(SupplierOfferEvidence(part_key=row.part_key,supplier=row.supplier,channel=row.channel,
            condition=row.condition,item_gbp=row.item_gbp,delivery_gbp=row.delivery_gbp,fees_gbp=row.fees_gbp,
            risk_gbp=row.risk_gbp,observed_at=datetime.now(timezone.utc),stock_confirmed=False,
            delivery_working_days=row.delivery_working_days,supplier_confidence=row.supplier_confidence,
            evidence_source=row.evidence_source,evidence_ref=row.evidence_ref,captured_by_admin_id=0))
        await self.db.flush()
        with self.assertRaises(HTTPException) as error:
            await self.accept(quote)
        self.assertEqual(error.exception.status_code,409)

    async def test_expired_quote_cannot_start_payment(self):
        quote=await create_checkout_quote(self.db,self.config)
        stored=await self.db.get(PriceQuoteSnapshot,quote["quote_snapshot_id"])
        data=deepcopy(stored.decision_json)
        data["modes"]["flexible"]["expires_at"]=(self.now-timedelta(seconds=1)).isoformat()
        stored.decision_json=data
        await self.db.flush()
        with self.assertRaises(HTTPException):
            await self.accept(quote)

    async def test_disabled_policy_cannot_fall_back_to_legacy_price(self):
        data=self.policy.model_dump(mode="json")
        data["checkout_enabled"]=False
        self.playbook.pricing_model={"commercial_cells":{self.config.curated_build_id:data}}
        await self.db.flush()
        with self.assertRaises(HTTPException) as error:
            await create_checkout_quote(self.db,self.config)
        self.assertEqual(error.exception.status_code,409)

    async def test_recovery_rejects_wrong_customer_or_paid_amount(self):
        accepted=await self.accept(await create_checkout_quote(self.db,self.config))
        metadata={"commercial_quote_snapshot_id":str(accepted.id)}
        for customer,amount in ((self.customer.id+1,accepted.decision_json["quote"]["price_gbp"]), (self.customer.id,"1.00")):
            with self.assertRaises(ValueError):
                await commercial_order_snapshot(self.db,metadata,customer,amount)

    async def test_intent_uses_accepted_total_metadata_and_persisted_contract(self):
        from app.routes.payments import create_payment_intent
        from app.services.playbook_pricing import PricedBuild, PricedSlot
        quote=await create_checkout_quote(self.db,self.config)
        address=dict(full_name="Test Customer",line1="1 Test Road",city="Test Town",postcode="TE1 1ST",country="GB")
        request=CreatePaymentIntentRequest(customer_id=self.customer.id,build_config=self.config,
            commercial_quote_id=quote["quote_snapshot_id"],delivery_option="flexible",software_package_ids=[],
            checkout_addresses={"delivery":address,"billing":address})
        priced=PricedBuild(playbook_id=self.playbook.id,playbook_name=self.playbook.name,
            slots=[PricedSlot(slot_id,role,variant_id,"Exact CPU" if role=="cpu" else f"Exact {role}",300)
                for slot_id,(variant_id,role) in self.configured_parts.items()],
            case_id=self.case.id,case_name="Exact Case",total=999)
        intent_id="pi_commercial_"+uuid4().hex
        async def provider(**kwargs):
            # The accepted contract must already be visible to a second session
            # before any irreversible provider action could succeed.
            async with AsyncSessionLocal() as observer:
                stored=await observer.get(PriceQuoteSnapshot,int(kwargs["metadata"]["commercial_quote_snapshot_id"]))
                self.assertEqual(stored.status,"checkout_accepted")
                pending=(await observer.execute(select(OrderCheckoutSnapshot).where(
                    OrderCheckoutSnapshot.payment_intent_id==f"commercial:{stored.id}"))).scalar_one()
                self.assertEqual(pending.delivery_address["postcode"],"TE1 1ST")
            return dict(client_secret="test_secret",publishable_key="test_key",intent_id=intent_id,
                        amount=float(kwargs["budget"]),currency="gbp")
        payment=SimpleNamespace(create_payment_intent=AsyncMock(side_effect=provider))
        with patch("app.routes.payments.price_playbook_build",AsyncMock(return_value=priced)), \
             patch("app.routes.auth.get_current_user",AsyncMock(return_value=self.customer)), \
             patch("app.routes.payments.software_profile_for_curated_cell_from_db",AsyncMock(return_value={"recommended_package_ids":[]})), \
             patch("app.routes.payments.PaymentService",return_value=payment):
            result=await create_payment_intent(request,self.db,"Bearer fixture")
        self.assertEqual(Decimal(str(result.amount)),Decimal(quote["modes"]["flexible"]["price_gbp"]))
        self.assertNotEqual(result.amount,999)
        kwargs=payment.create_payment_intent.call_args.kwargs
        self.assertEqual(kwargs["metadata"]["delivery_option"],"flexible")
        self.assertIn("commercial:",kwargs["idempotency_key"])
        checkout=(await self.db.execute(select(OrderCheckoutSnapshot).where(OrderCheckoutSnapshot.payment_intent_id==intent_id))).scalar_one()
        self.assertEqual(checkout.build_snapshot["commercial_quote"]["price_gbp"],quote["modes"]["flexible"]["price_gbp"])
        from app.routes.payments import confirm_payment
        from app.schemas.payment import ConfirmPaymentRequest
        payment.handle_payment_success=AsyncMock(return_value={"intent_id":intent_id,"amount":result.amount,"currency":"gbp",
                                                              "metadata":kwargs["metadata"]})
        with patch("app.routes.payments.PaymentService",return_value=payment), \
             patch("app.services.getting_started_jobs.ensure_order_job",AsyncMock()), \
             patch("app.routes.payments.send_order_confirmation_email",AsyncMock()), \
             patch("app.routes.payments.record_order_event",AsyncMock()):
            confirmation=await confirm_payment(ConfirmPaymentRequest(intent_id=intent_id,
                customer_id=self.customer.id,build_config=self.config),self.db)
        order=await self.db.get(Order,confirmation.order_id)
        self.assertEqual(order.specs["commercial_quote"]["price_gbp"],quote["modes"]["flexible"]["price_gbp"])
        self.assertEqual(order.specs["delivery_option"],"flexible")
        self.assertEqual(order.specs["slots"][0]["title"],"Exact CPU")
        self.assertIsNone(order.promised_delivery_date)

    async def test_webhook_recovers_accepted_build_and_mode_without_checkout_snapshot(self):
        from app.routes.webhooks import _handle_payment_intent_succeeded
        accepted=await self.accept(await create_checkout_quote(self.db,self.config),mode="fast_track")
        intent_id="pi_webhook_"+uuid4().hex
        metadata={"commercial_quote_snapshot_id":str(accepted.id),"customer_id":str(self.customer.id),
                  "playbook_id":str(self.playbook.id),"curated_build_id":self.config.curated_build_id,
                  "fulfilment_type":"curated"}
        event={"data":{"object":{"id":intent_id,"metadata":metadata,
                                    "amount":int(Decimal(accepted.decision_json["quote"]["price_gbp"])*100)}}}
        with patch("app.services.getting_started_jobs.ensure_order_job",AsyncMock()), \
             patch("app.routes.webhooks.send_order_confirmation_email",AsyncMock()), \
             patch("app.routes.webhooks.record_order_event",AsyncMock()):
            await _handle_payment_intent_succeeded(event,self.db)
        order=(await self.db.execute(select(Order).where(Order.stripe_payment_intent_id==intent_id))).scalar_one()
        self.assertTrue(order.fast_track_selected)
        self.assertGreater(order.fast_track_fee,0)
        self.assertEqual(order.playbook_id,self.playbook.id)
        self.assertEqual(order.specs["slots"][0]["title"],"Exact CPU")
        self.assertEqual(order.specs["commercial_quote"]["quote_snapshot_id"],accepted.id)
        self.assertIsNotNone(order.promised_delivery_date)

    async def test_webhook_preserves_provisional_addresses_after_ambiguous_provider_result(self):
        from app.routes.webhooks import _handle_payment_intent_succeeded
        from app.services.storefront_delivery import checkout_metadata
        from app.services.commercial_checkout import accepted_delivery
        accepted=await self.accept(await create_checkout_quote(self.db,self.config))
        address={"full_name":"Test Customer","line1":"1 Test Road","city":"Test Town","postcode":"TE1 1ST","country":"GB"}
        self.db.add(OrderCheckoutSnapshot(payment_intent_id=f"commercial:{accepted.id}",customer_id=self.customer.id,
            delivery_address=address,billing_address=address,build_snapshot=accepted.evidence_json["build_snapshot"],
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(days=30)))
        await self.db.commit()
        intent_id="pi_provisional_"+uuid4().hex
        metadata={**checkout_metadata(accepted_delivery(accepted)),"commercial_quote_snapshot_id":str(accepted.id),
                  "customer_id":str(self.customer.id),"playbook_id":str(self.playbook.id),
                  "curated_build_id":self.config.curated_build_id,"fulfilment_type":"curated"}
        event={"data":{"object":{"id":intent_id,"metadata":metadata,
              "amount":int(Decimal(accepted.decision_json["quote"]["price_gbp"])*100)}}}
        with patch("app.services.getting_started_jobs.ensure_order_job",AsyncMock()), \
             patch("app.routes.webhooks.send_order_confirmation_email",AsyncMock()), \
             patch("app.routes.webhooks.record_order_event",AsyncMock()):
            await _handle_payment_intent_succeeded(event,self.db)
        order=(await self.db.execute(select(Order).where(Order.stripe_payment_intent_id==intent_id))).scalar_one()
        self.assertEqual(order.specs["delivery_address"]["postcode"],"TE1 1ST")
        self.assertEqual(order.specs["commercial_quote"]["delivery_option"],"flexible")

    async def test_webhook_failure_is_not_silently_acknowledged_for_commercial_payment(self):
        from app.routes.webhooks import _handle_payment_intent_succeeded
        accepted=await self.accept(await create_checkout_quote(self.db,self.config))
        event={"data":{"object":{"id":"pi_invalid_"+uuid4().hex,"amount":100,
              "metadata":{"customer_id":str(self.customer.id),"commercial_quote_snapshot_id":str(accepted.id)}}}}
        with self.assertRaises(HTTPException) as error:
            await _handle_payment_intent_succeeded(event,self.db)
        self.assertEqual(error.exception.status_code,500)


if __name__=="__main__":
    unittest.main()
