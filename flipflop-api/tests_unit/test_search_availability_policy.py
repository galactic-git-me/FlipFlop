"""Owner-approved availability fallback, without provider calls."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from app.services.commercial_source import search_listing_availability

class AvailabilityChecks(unittest.TestCase):
    def test_current_unknown_listing_is_assumed_available(self):
        status,evidence,assumed=search_listing_availability('unknown')
        self.assertEqual(status,'available');self.assertTrue(assumed);self.assertIn('owner-approved',evidence)
    def test_explicit_negative_and_confirmed_sale_win(self):
        for evidence in ['Sold out','Out of stock','Currently unavailable','Listing has ended']:
            self.assertEqual(search_listing_availability('unknown',evidence)[0],'unavailable')
        self.assertEqual(search_listing_availability('available','In stock',sold_confirmed=True)[0],'unavailable')
        self.assertEqual(search_listing_availability('unavailable')[0],'unavailable')
    def test_historical_sales_counter_is_not_sold_out(self):
        self.assertEqual(search_listing_availability('unknown','25 sold')[0],'available')
        self.assertEqual(search_listing_availability('unknown','Sold as seen')[0],'available')
    def test_explicit_positive_is_not_relabelled_as_assumption(self):
        self.assertEqual(search_listing_availability('available','In stock'),('available','In stock',False))
    def test_stored_supplier_offer_uses_the_same_fallback(self):
        from app.services.playbook_stored_offers import recorded_offer
        from datetime import datetime, timezone
        row={'id':1,'listing_id':'LN151058','title':'Kingston NV3 1TB','cpk':'key',
             'source':'scan','item_price':100,'observed_at':datetime.now(timezone.utc),
             'commercial_source_evidence':{'url':'https://www.scan.co.uk/products/kingston-nv3',
                 'item_gbp':'100','stock_status':'unknown'}}
        offer=recorded_offer(row)
        self.assertEqual(offer['stock_status'],'available');self.assertTrue(offer['availability_assumed'])

    def test_inactive_or_auction_not_promoted(self):
        self.assertEqual(search_listing_availability('unknown',active=False)[0],'unknown')
        self.assertEqual(search_listing_availability('unknown',listing_type='auction')[0],'unknown')
if __name__=='__main__':unittest.main()
