"""Standalone deterministic contract checks; no database or provider writes."""
import asyncio
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from app.models.order import OrderStatus
from app.services.purchase_activity import public_purchase, recent_purchases


def paid_order(**overrides):
    values = dict(id=42, stripe_payment_intent_id="pi_verified", status=OrderStatus.BUILDING,
        refund_id=None, customer_price=1173.49, created_at=datetime(2026, 10, 14, 10),
        specs={"build_title": "Customer's configured PC", "case_name": "Selected case",
            "payment_evidence": {"provider": "stripe", "status": "succeeded", "livemode": True, "currency": "gbp"},
            "slots": [{"slot_type": "gpu", "title": "Purchased graphics card", "price": 1}],
            "delivery_address": {"name": "Private buyer", "postcode": "PRIVATE"},
            "billing_address": {"secret": "PRIVATE"}, "software_package_ids": ["PRIVATE"]})
    values.update(overrides)
    return SimpleNamespace(**values)


class PurchaseActivityContract(unittest.TestCase):
    def test_verified_payment_carries_provider_live_mode_into_order_evidence(self):
        from app.services.payment_service import PaymentService
        class Intent(dict):
            def __getattr__(self, key):
                return self[key]
        service = PaymentService.__new__(PaymentService)
        for livemode in (False, True):
            intent = Intent(status="succeeded", amount=117349, currency="gbp", created=1700000000,
                            latest_charge="ch_fixture", metadata={}, livemode=livemode)
            with patch("app.services.payment_service.stripe.PaymentIntent.retrieve", return_value=intent):
                result = asyncio.run(service.handle_payment_success("pi_fixture", 1, {}))
            self.assertEqual(result["amount"], 1173.49)
            self.assertEqual(result["payment_evidence"], {"provider": "stripe", "status": "succeeded", "livemode": livemode, "currency": "gbp"})

    def test_exact_paid_total_and_stable_custom_snapshot_link(self):
        result = public_purchase(paid_order())
        self.assertEqual(result["amount_gbp"], 1173.49)
        self.assertEqual(result["product_url"], "/purchases/42")
        self.assertEqual(result["created_at"], "2026-10-14T10:00:00+00:00")
        self.assertEqual(result["parts"], [{"category": "gpu", "name": "Purchased graphics card"}, {"category": "case", "name": "Selected case"}])
        self.assertNotIn("PRIVATE", str(result))
        self.assertNotIn("pi_verified", str(result))


    def test_prebuilt_links_to_the_exact_product_without_catalogue_price_lookup(self):
        order = paid_order()
        order.specs["product_id"] = 79
        self.assertEqual(public_purchase(order)["product_url"], "/builds/79")
        self.assertEqual(public_purchase(order)["amount_gbp"], 1173.49)

    def test_no_refunds_cancellations_unpaid_or_invalid_prices(self):
        for override in ({"status": OrderStatus.CANCELLED}, {"refund_id": "re_1"},
                         {"stripe_payment_intent_id": None}, {"customer_price": 0},
                         {"customer_price": float("nan")}, {"customer_price": float("inf")}):
            self.assertIsNone(public_purchase(paid_order(**override)))

    def test_no_test_mode_unknown_or_unconfirmed_payment_evidence(self):
        for patch in ({"livemode": False}, {"livemode": "true"}, {"status": "pending"}, {"currency": "usd"}, {"provider": "fixture"}):
            order = paid_order()
            order.specs["payment_evidence"].update(patch)
            self.assertIsNone(public_purchase(order))
        self.assertIsNone(public_purchase(paid_order(specs={})))

    def test_feed_filters_even_if_a_storage_adapter_returns_unqualified_rows(self):
        result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [paid_order(), paid_order(refund_id="re_refunded")]))
        session = SimpleNamespace(execute=AsyncMock(return_value=result))
        rows = asyncio.run(recent_purchases(session))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount_gbp"], 1173.49)


if __name__ == "__main__":
    unittest.main()
