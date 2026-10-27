"""Pure commercial regressions; runnable via unittest without app/DB fixtures."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

from pydantic import ValidationError

from app.schemas.commercial_quote import CellCommercialPolicy
from app.services.commerce_pricing import Condition, SupplierOffer
from app.services.playbook_commercial_quote import CapacityEvidence, PartEvidence, quote_delivery_modes

NOW = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)


def policy_data():
    costs = dict(build_labour="80", packaging="10", outbound_delivery="20", insurance="5",
                 payment_fixed="0.30", expected_failure_cost="5", allocated_overhead="20",
                 other_variable_costs="0")
    modes = {}
    for name, workshop, target, premium in (("fast_track", 1, 3, "40"),
                                            ("standard", 2, 6, "0"), ("flexible", 2, 12, "0")):
        modes[name] = dict(costs=deepcopy(costs), minimum_contribution_gbp="100",
                           minimum_margin_fraction="0.15", premium_gbp=premium,
                           workshop_working_days=workshop, courier_working_days=1,
                           maximum_delivery_working_days=target)
    return dict(version=1, definition_sha256="a" * 64, required_part_keys=["cpu", "case"],
                condition="new", vat_rate="0.20", payment_rate="0.02", warranty_rate="0.05",
                returns_rate="0.01", market_tolerance_fraction="0.10",
            market=dict(condition="new", sold_median_gbp="2000", sold_p75_gbp="2200", sold_sample_size=10,
                        minimum_sold_sample_size=8, cap_method="sold_p75_linear_interpolation",
                            observed_at=NOW.isoformat(), evidence_source="reviewed_sold_sample",
                            evidence_ref="sample:1"), modes=modes)


def parts():
    rows = []
    for index, key in enumerate(("cpu", "case")):
        for supplier, cost, days, channel in (("Amazon", "300", 1, "retail"),
                                              ("Retailer", "280", 3, "retail"),
                                              ("eBay", "220", 7, "marketplace")):
            rows.append(PartEvidence(len(rows) + 1, key, SupplierOffer(
                supplier, channel, Condition.NEW, D(cost), D("5"), D("0"), D("2"),
                NOW.isoformat(), True, True, days,
            )))
    return rows


def capacities():
    return {name: CapacityEvidence(1, NOW.isoformat(), True, 0)
            for name in ("fast_track", "standard", "flexible")}


class CommercialQuoteTests(unittest.TestCase):
    def test_original_gamers_outlet_licence_is_priced_as_reviewed_digital_software(self):
        data=policy_data();data['required_part_keys']=['cpu','os']
        for name,mode in data['modes'].items():
            mode['costs']['outbound_delivery']='0' if name=='flexible' else '5'
        for vendor in ('gamers_outlet','Gamers Outlet'):
            offers=[PartEvidence(1,'cpu',SupplierOffer('Amazon','retail',Condition.NEW,
                D('300'),D('0'),D('0'),D('0'),NOW.isoformat(),True,True,1)),
                PartEvidence(2,'os',SupplierOffer(vendor,'software',Condition.NEW,
                D('4.68'),D('0'),D('0'),D('0'),NOW.isoformat(),True,True,0))]
            self.assertTrue(all(q['offerable'] for q in self.quote(data,offers)['modes'].values()))
            delayed=replace(offers[1],offer=replace(offers[1].offer,delivery_working_days=1))
            self.assertTrue(all(not q['offerable'] for q in self.quote(data,[offers[0],delayed])['modes'].values()))

    def test_bom_quantities_cost_every_unit_without_changing_supplier_unit_evidence(self):
        data=policy_data();data['market']=None;data['part_quantities']={'cpu':8}
        offers=parts()
        result=self.quote(data=data,offers=offers)
        standard=result['modes']['standard']
        self.assertTrue(standard['offerable'])
        self.assertEqual(D(standard['fixed_costs_gbp']['landed_parts_including_risk']),D('2583'))
        self.assertEqual(standard['part_quantities'],{'cpu':8,'case':1})
        self.assertEqual(offers[1].offer.item_gbp,D('280'))
        for invalid in (0,1.5,True):
            data['part_quantities']={'cpu':invalid}
            with self.assertRaises(ValidationError): CellCommercialPolicy.model_validate(data)
        data['part_quantities']={'not-in-bom':8}
        with self.assertRaises(ValidationError): CellCommercialPolicy.model_validate(data)

    def quote(self, data=None, offers=None, capacity=None, **kwargs):
        return quote_delivery_modes(CellCommercialPolicy.model_validate(data or policy_data()),
                                    parts() if offers is None else offers,
                                    capacities() if capacity is None else capacity, now=NOW, **kwargs)

    def test_three_modes_keep_same_spec_and_deliver_real_saving(self):
        result = self.quote()
        modes = result["modes"]
        self.assertFalse(result["purchasable"])
        self.assertTrue(all(item["offerable"] for item in modes.values()))
        self.assertGreater(D(modes["fast_track"]["price_gbp"]), D(modes["standard"]["price_gbp"]))
        self.assertLess(D(modes["flexible"]["difference_from_standard_gbp"]), 0)
        self.assertEqual(modes["fast_track"]["supplier_offer_ids"], [1, 4])
        self.assertEqual(modes["standard"]["supplier_offer_ids"], [2, 5])
        self.assertEqual(modes["flexible"]["supplier_offer_ids"], [3, 6])
        self.assertEqual([modes[name]["delivery_working_days"] for name in modes], [3, 6, None])
        self.assertEqual([modes[name]['supplier_arrival_working_days'] for name in modes],[1,3,7])
        for name,quote in modes.items():
            if name=='flexible':
                self.assertFalse(quote['delivery_promised'])
                self.assertIsNone(quote['maximum_delivery_working_days'])
                continue
            self.assertEqual(quote['delivery_working_days'],
                max(quote['supplier_arrival_working_days'],quote['workshop_wait_working_days'])
                +quote['workshop_working_days']+quote['courier_working_days'])
            self.assertLessEqual(quote['delivery_working_days'],quote['maximum_delivery_working_days'])

    def test_fees_and_reserves_use_final_gross_price_and_profit_is_net_of_vat(self):
        for name, quote in self.quote()["modes"].items():
            price = D(quote["price_gbp"])
            contribution = D(quote["contribution_gbp"])
            self.assertGreaterEqual(D(quote["sale_based_costs_gbp"]["warranty_rate"]), price * D("0.05"))
            self.assertGreaterEqual(contribution, D("100"))
            self.assertGreaterEqual(contribution, D(quote["net_revenue_gbp"]) * D("0.15"))
            self.assertEqual(contribution, D(quote["net_revenue_gbp"]) - D(quote["true_cost_gbp"]))

    def test_no_vat_registered_policy_is_explicit(self):
        data = policy_data()
        data["vat_rate"] = "0"
        quote = self.quote(data)["modes"]["standard"]
        self.assertEqual(quote["net_revenue_gbp"], quote["price_gbp"])

    def test_complete_costs_required(self):
        data = policy_data()
        del data["modes"]["standard"]["costs"]["insurance"]
        with self.assertRaises(ValidationError):
            self.quote(data)

    def test_duplicate_part_keys_rejected(self):
        data = policy_data()
        data["required_part_keys"] = ["cpu", "cpu"]
        with self.assertRaises(ValidationError):
            self.quote(data)

    def test_nonfinite_and_impossible_rates_rejected(self):
        for field, value in (("payment_rate", "NaN"), ("warranty_rate", "0.90"), ("vat_rate", "Infinity")):
            with self.subTest(field=field):
                data = policy_data()
                data[field] = value
                with self.assertRaises(ValidationError):
                    self.quote(data)

    def test_stale_future_missing_and_out_of_stock_parts_fail_closed(self):
        for changes in (dict(observed_at=(NOW - timedelta(days=2)).isoformat()),
                        dict(observed_at=(NOW + timedelta(seconds=1)).isoformat()),
                        dict(stock_confirmed=False), dict(delivery_working_days=None),
                        dict(delivery_working_days=-1), dict(observed_at="2026-10-13")):
            with self.subTest(changes=changes):
                offers = [replace(part, offer=replace(part.offer, **changes)) for part in parts()]
                self.assertTrue(all(not quote["offerable"] for quote in self.quote(offers=offers)["modes"].values()))
        self.assertTrue(all(not quote["offerable"] for quote in self.quote(offers=parts()[:3])["modes"].values()))

    def test_full_workshop_count_is_only_a_planning_hint_not_a_sales_gate(self):
        cap = capacities()
        cap["fast_track"] = replace(cap["fast_track"], available=False)
        modes = self.quote(capacity=cap)["modes"]
        baseline = self.quote()["modes"]
        self.assertEqual(modes["fast_track"]["offerable"], baseline["fast_track"]["offerable"])
        self.assertEqual(modes["fast_track"]["price_gbp"], baseline["fast_track"]["price_gbp"])
        self.assertIsNone(modes["fast_track"]["capacity_evidence_id"])

    def test_quotes_remain_available_without_workshop_count_evidence(self):
        modes = self.quote(capacity={})["modes"]
        baseline = self.quote()["modes"]
        for name in ("fast_track", "standard", "flexible"):
            with self.subTest(mode=name):
                self.assertEqual(modes[name]["offerable"], baseline[name]["offerable"])
                self.assertEqual(modes[name]["price_gbp"], baseline[name]["price_gbp"])
                self.assertIsNone(modes[name]["capacity_evidence_id"])

    def test_workshop_wait_is_included_in_total_delivery(self):
        cap = {key: replace(value, wait_working_days=20) for key, value in capacities().items()}
        self.assertTrue(all(not quote["offerable"] for quote in self.quote(capacity=cap)["modes"].values()))

    def test_condition_cannot_silently_change_for_flexible(self):
        offers = [replace(part, offer=replace(part.offer, condition=Condition.USED))
                  if part.offer.supplier == "eBay" else part for part in parts()]
        self.assertFalse(self.quote(offers=offers, nonnew_consent=True)["modes"]["flexible"]["offerable"])

    def test_used_build_requires_consent_even_with_exact_condition(self):
        data = policy_data()
        data["condition"] = data["market"]["condition"] = "used"
        offers = [replace(part, offer=replace(part.offer, condition=Condition.USED)) for part in parts()]
        self.assertFalse(self.quote(data, offers=offers)["modes"]["standard"]["offerable"])
        self.assertTrue(self.quote(data, offers=offers, nonnew_consent=True)["modes"]["standard"]["offerable"])

    def test_stale_market_and_unprofitable_market_reject_all_modes(self):
        for change in ({"observed_at": (NOW - timedelta(days=31)).isoformat()},
                       {"sold_median_gbp": "100", "sold_p75_gbp": "100"}):
            data = policy_data()
            data["market"].update(change)
            self.assertTrue(all(not item["offerable"] for item in self.quote(data)["modes"].values()))

    def test_capacity_is_optional_for_standard_quote_comparison(self):
        cap = capacities()
        del cap["standard"]
        flexible = self.quote(capacity=cap)["modes"]["flexible"]
        self.assertTrue(flexible["offerable"])
        self.assertLess(D(flexible["difference_from_standard_gbp"]), 0)

    def test_expiry_never_outlives_supplier_evidence(self):
        offers = [replace(part, offer=replace(part.offer, observed_at=(NOW - timedelta(hours=23, minutes=59)).isoformat()))
                  for part in parts()]
        quote = self.quote(offers=offers)["modes"]["standard"]
        self.assertEqual(datetime.fromisoformat(quote["expires_at"]), NOW + timedelta(minutes=1))

    def test_nan_supplier_cost_is_excluded_without_poisoning_other_modes(self):
        offers = [replace(part, offer=replace(part.offer, item_gbp=D("NaN")))
                  if part.offer.supplier == "Amazon" else part for part in parts()]
        modes = self.quote(offers=offers)["modes"]
        self.assertFalse(modes["fast_track"]["offerable"])
        self.assertTrue(modes["standard"]["offerable"])

    def test_zero_cost_official_linux_component_can_be_quoted_without_becoming_physical_stock(self):
        data=policy_data()
        data['required_part_keys']=['cpu','ubuntu']
        for name,mode in data['modes'].items():
            mode['costs']['outbound_delivery']={'fast_track':'5','standard':'5','flexible':'0'}[name]
        offers=[
            PartEvidence(1,'cpu',SupplierOffer('Amazon','retail',Condition.NEW,D('300'),D('5'),D('0'),D('0'),
                NOW.isoformat(),True,True,1)),
            PartEvidence(2,'ubuntu',SupplierOffer('Ubuntu','software',Condition.NEW,D('0'),D('0'),D('0'),D('0'),
                NOW.isoformat(),True,True,0)),
        ]

        modes=self.quote(data,offers=offers)['modes']

        self.assertTrue(all(row['offerable'] for row in modes.values()))
        self.assertTrue(all(2 in row['supplier_offer_ids'] for row in modes.values()))
        self.assertLess(D(modes['flexible']['price_gbp']),D(modes['standard']['price_gbp']))
        self.assertFalse(self.quote(data,offers=[offers[0],PartEvidence(3,'ubuntu',SupplierOffer(
            'Ubuntu','software',Condition.NEW,D('1'),D('0'),D('0'),D('0'),NOW.isoformat(),True,True,0))])
            ['modes']['standard']['offerable'])

    def test_reviewed_royalcdkeys_digital_licence_fits_all_modes_without_delivery_delay(self):
        data=policy_data()
        data['required_part_keys']=['cpu','os']
        for name,mode in data['modes'].items():
            mode['costs']['outbound_delivery']={'fast_track':'5','standard':'5','flexible':'0'}[name]
        offers=[
            PartEvidence(1,'cpu',SupplierOffer('Amazon','retail',Condition.NEW,D('300'),D('5'),D('0'),D('0'),
                NOW.isoformat(),True,True,1)),
            PartEvidence(2,'os',SupplierOffer('royalcdkeys','software',Condition.NEW,D('5.73'),D('0'),D('0'),D('0'),
                NOW.isoformat(),True,True,0)),
        ]
        modes=self.quote(data,offers=offers)['modes']
        self.assertTrue(all(row['offerable'] for row in modes.values()))
        self.assertTrue(all(2 in row['supplier_offer_ids'] for row in modes.values()))

        with_postage=replace(offers[1],offer=replace(offers[1].offer,delivery_gbp=D('0.01')))
        with_delay=replace(offers[1],offer=replace(offers[1].offer,delivery_working_days=1))
        for invalid in (with_postage,with_delay):
            self.assertTrue(all(not row['offerable'] for row in self.quote(data,offers=[offers[0],invalid])['modes'].values()))


if __name__ == "__main__":
    unittest.main()
