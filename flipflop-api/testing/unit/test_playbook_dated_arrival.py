"""A supplier's dated arrival must preserve weekend timing in pace gates."""
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.services.playbook_product_capture import (
    max_working_days_for_calendar_duration, parse_product_capture,
)
from app.services.playbook_service import component_delivery_eligibility

URL = "https://www.overclockers.co.uk/exact-processor/PRO-INT-07479.html"


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 27, 2, 0, tzinfo=timezone.utc)


def offer_html(stock="InStock", premium=True):
    product = {
        "@type": "Product", "name": "Exact processor", "url": URL,
        "offers": {"url": URL, "price": "199.99", "priceCurrency": "GBP",
                   "availability": "https://schema.org/" + stock},
    }
    notice = ("applies to Premium Delivery within United Kingdom"
              if premium else "collection only")
    return ('<script type="application/ld+json">' + json.dumps(product)
            + '</script><p>Order within 12 hours to get it on '
              'Tuesday, 1st of December</p><p>' + notice + '</p>')


class DatedArrivalTests(unittest.TestCase):
    @patch("app.services.playbook_product_capture.datetime", FixedClock)
    def test_amazon_selected_offer_uses_actual_weekdays(self):
        url = "https://www.amazon.co.uk/dp/B0DSR14511"
        html = '''<input name="ASIN" value="B0DSR14511">
            <div id="productTitle">Crucial 64GB DDR5 RAM Kit</div>
            <div id="corePrice_feature_div"><span class="a-offscreen">£739.99</span></div>
            <div id="availability">In Stock</div>
            <div id="sellerProfileTriggerId">Amazon</div>
            <div id="deliveryBlockContainer">
              <div data-csa-c-delivery-type="delivery" data-csa-c-mir-variant="DEFAULT"
                data-csa-c-delivery-price="FREE" data-csa-c-delivery-time="Tuesday, 1 December">
                FREE delivery Tuesday, 1 December
              </div>
            </div>'''
        result = parse_product_capture(html, url)
        self.assertEqual(result["status"], "captured")
        self.assertEqual(result["delivery_calendar_days"], 4)
        self.assertEqual(result["delivery_working_days"], 2)

    def test_undated_calendar_duration_stays_conservative(self):
        self.assertEqual(max_working_days_for_calendar_duration(4), 4)
        self.assertEqual(max_working_days_for_calendar_duration(7), 5)

    @patch("app.services.playbook_product_capture.datetime", FixedClock)
    def test_dated_arrival_counts_actual_weekdays_and_allows_standard(self):
        result = parse_product_capture(offer_html(), URL)
        self.assertEqual(result["delivery_calendar_days"], 4)
        self.assertEqual(result["delivery_working_days"], 2)
        source = {**result, "fresh": True, "active_listing": True}
        policy = SimpleNamespace(modes={
            "standard": SimpleNamespace(maximum_delivery_working_days=5,
                workshop_working_days=1, courier_working_days=2),
            "fast_track": SimpleNamespace(maximum_delivery_working_days=3,
                workshop_working_days=1, courier_working_days=2),
        })
        eligibility = component_delivery_eligibility({"source_observation": source}, policy)
        self.assertTrue(eligibility["standard"])
        self.assertFalse(eligibility["fast_track"])

    @patch("app.services.playbook_product_capture.datetime", FixedClock)
    def test_unavailable_offer_has_no_dated_arrival_promise(self):
        result = parse_product_capture(offer_html("OutOfStock"), URL)
        self.assertNotEqual(result.get("delivery_estimate_source"),
                            "retailer_page_displayed_estimate")

    @patch("app.services.playbook_product_capture.datetime", FixedClock)
    def test_other_service_does_not_gain_premium_arrival(self):
        result = parse_product_capture(offer_html(premium=False), URL)
        self.assertNotEqual(result.get("delivery_estimate_source"),
                            "retailer_page_displayed_estimate")


if __name__ == "__main__":
    unittest.main()
