"""Approved defaults and source freshness boundaries; no database/network."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from decimal import Decimal
import unittest
from app.services.commercial_source import commercial_capture
from app.services.commercial_pilot_policy import apply_pilot_rules
from app.services.commercial_readiness import (empty_draft, observation_data, _product_page_source_preview,
    prefer_exact_product_page_preview)
from app.services.commercial_reconciliation import refresh_values


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        self.listing=SimpleNamespace(extracted_at=self.now,stock_status='available',stock_evidence='In stock',
            url='https://www.amazon.co.uk/dp/EXACT',item_price=100.12,postage_price=0)
        self.previous=SimpleNamespace(part_key='cpu',condition='new',fees_gbp=Decimal('0'),
            risk_gbp=Decimal('2'),supplier_confidence=Decimal('0.9'))
        self.source=dict(condition='new',source='amazon',url=self.listing.url,active_listing=True,
            fresh=True,commercial_capture_verified=True,stock_status='available',stock_evidence='In stock',
            item_gbp='100.12',delivery_gbp='0',observed_at=self.now.isoformat(),delivery_working_days=2,
            delivery_estimate_source='scraped',prime_eligible=False,observation_id=1,fingerprint='a'*64)

    def test_pilot_defaults_do_not_invent_operating_costs(self):
        draft=empty_draft({'tier':'High-end'},1,{1:[101,'cpu']},[1,'case'])
        self.assertEqual(draft['modes']['standard']['minimum_contribution_gbp'],'175.00')
        self.assertEqual(draft['modes']['standard']['minimum_margin_fraction'],'0.15')
        self.assertEqual(draft['warranty_rate'],'0.05')
        self.assertEqual(draft['returns_rate'],'0.02')
        self.assertEqual(draft['vat_rate'],'0.00')
        self.assertEqual(draft['modes']['standard']['costs']['build_labour'],'0.00')
        self.assertEqual(draft['modes']['standard']['costs']['packaging'],'10.00')
        self.assertEqual(draft['modes']['standard']['costs']['insurance'],'15.00')
        self.assertEqual(draft['modes']['standard']['costs']['payment_fixed'],'0.20')
        self.assertEqual(draft['payment_rate'],'0.0315')
        self.assertIsNone(draft['modes']['standard']['costs']['outbound_delivery'])
        self.assertIsNone(draft['modes']['fast_track']['premium_gbp'])
        self.assertFalse(draft['checkout_enabled'])

    def test_unknown_tier_has_no_fabricated_floor(self):
        draft=empty_draft({'tier':'Unknown'},1,{},None)
        self.assertIsNone(draft['modes']['standard']['minimum_contribution_gbp'])

    def test_capture_requires_explicit_stock_evidence_and_timezone(self):
        self.assertEqual(commercial_capture(self.listing)['stock_status'],'available')
        self.listing.stock_evidence=None
        self.assertEqual(commercial_capture(self.listing)['stock_status'],'unknown')
        self.listing.stock_evidence='In stock';self.listing.extracted_at=self.now.replace(tzinfo=None)
        self.assertIsNone(commercial_capture(self.listing)['observed_at'])
        self.assertEqual(commercial_capture(self.listing)['stock_status'],'unknown')

    def test_available_refresh_preserves_allowances_and_timestamp(self):
        values=refresh_values(self.previous,self.source)
        self.assertTrue(values['stock_confirmed'])
        self.assertEqual(values['risk_gbp'],Decimal('2'))
        self.assertEqual(values['observed_at'].isoformat(),self.source['observed_at'])

    def test_unknown_inactive_stale_and_changed_condition_never_confirm_stock(self):
        for changes in ({'stock_status':'unknown'},{'active_listing':False},{'fresh':False},
                        {'stock_evidence':None},{'condition':'used'}):
            values=refresh_values(self.previous,{**self.source,**changes})
            self.assertFalse(values['stock_confirmed'])

    def test_legacy_capture_cannot_create_positive_stock(self):
        self.assertIsNone(refresh_values(self.previous,{**self.source,'commercial_capture_verified':False}))

    def test_lightweight_sighting_does_not_refresh_price_capture(self):
        old=self.now-timedelta(days=2)
        self.listing.extracted_at=old
        capture=commercial_capture(self.listing)
        listing=SimpleNamespace(id=1,status='active',url=self.listing.url)
        observation=SimpleNamespace(commercial_source_evidence=capture,listing_id='exact',id=1,
            observed_at=self.now.replace(tzinfo=None),listing_type='buy_it_now',source='amazon',
            condition_normalised='new',item_price=100.12,postage_price=0,delivery_working_days=2,
            delivery_estimate_source='scraped',prime_eligible=False)
        preview=observation_data(listing,observation,None,None)
        self.assertEqual(preview['observed_at'],old.isoformat())
        self.assertFalse(preview['fresh'])

    def test_explicit_retail_stock_text_is_used_only_for_exact_captured_product(self):
        capture={'observed_at':self.now.isoformat(),'url':'https://www.amazon.co.uk/dp/B000000000',
            'item_gbp':'100.12','delivery_gbp':'0','stock_status':'unknown'}
        listing=SimpleNamespace(id=9,status='active',url=capture['url'])
        observation=SimpleNamespace(commercial_source_evidence=capture,listing_id='exact',id=2,
            observed_at=self.now.replace(tzinfo=None),listing_type='buy_it_now',source='amazon',
            condition_normalised='new',item_price=100.12,postage_price=0,delivery_text='FREE delivery. Only 3 left in stock.',
            delivery_working_days=1,delivery_estimate_source='listing_estimate',prime_eligible=False)
        preview=observation_data(listing,observation,None,None)
        self.assertEqual(preview['stock_status'],'available')
        self.assertIn('Only 3 left in stock',preview['stock_evidence'])
        observation.delivery_text='Currently unavailable'
        self.assertEqual(observation_data(listing,observation,None,None)['stock_status'],'unavailable')
        observation.commercial_source_evidence={**capture,'url':'https://www.amazon.co.uk/dp/OTHER'}
        self.assertEqual(observation_data(listing,observation,None,None)['stock_status'],'unknown')
        observation.commercial_source_evidence={**capture,'url':'https://www.overclockers.co.uk/search?sSearch=EXACT'}
        observation.source='overclockers';listing.url=observation.commercial_source_evidence['url']
        self.assertEqual(observation_data(listing,observation,None,None)['stock_status'],'unknown')

    def test_stock_text_does_not_turn_a_search_result_into_inventory(self):
        from app.services.commercial_readiness import _retailer_stock_from_text
        from app.services.playbook_product_capture import supported_product_url
        self.assertEqual(_retailer_stock_from_text('Delivery in 2 days'),('unknown',None))
        self.assertEqual(_retailer_stock_from_text('Only 2 left in stock'),('available','Only 2 left in stock'))
        self.assertTrue(supported_product_url('https://www.amazon.co.uk/dp/B000000000'))
        self.assertTrue(supported_product_url('https://www.overclockers.co.uk/product/amd-ryzen-cpu'))
        self.assertTrue(supported_product_url('https://www.overclockers.co.uk/amd-ryzen-threadripper-pro-7975wx-processor-with-pro-technologies/PRO-AMD-01273.html'))
        self.assertTrue(supported_product_url('https://www.overclockers.co.uk/nvidia-rtx-6000-ada-48gb-gdd6-pci-express-graphics-card-oem/GRA-NVI-05596.html'))
        self.assertFalse(supported_product_url('https://www.overclockers.co.uk/category/example-product.html'))
        self.assertFalse(supported_product_url('https://www.overclockers.co.uk/search?sSearch=amd'))


class AmazonProductPageCaptureTests(unittest.TestCase):
    URL='https://www.amazon.co.uk/dp/B0DC8RVRBZ'

    @staticmethod
    def page(asin='B0DC8RVRBZ', merchant='Sold by Example Retail and Fulfilled by Amazon',
             title='Example graphics card'):
        return f'''<html><input name="ASIN" value="{asin}">
          <span id="productTitle">{title}</span>
          <div id="corePrice_feature_div"><span class="a-offscreen">£249.99</span></div>
          <div id="availability"><span>Only 3 left in stock</span></div>
          <div id="merchant-info">{merchant}</div>
          <table id="productDetails_techSpec_section_1"><tr><th>Socket</th><td>AM4</td></tr>
            <tr><th>Wattage</th><td>65W</td></tr></table>
          <div id="deliveryBlockContainer">
            <div data-csa-c-delivery-type="delivery" data-csa-c-mir-variant="DEFAULT"
                 data-csa-c-delivery-price="FREE"
                 data-csa-c-delivery-time="Wednesday, 16 October">
              FREE delivery Wednesday, 16 October. Deliver to TW12 1JQ
            </div>
          </div></html>'''

    def test_exact_selected_asin_captures_explicit_offer_stock_and_default_delivery(self):
        from app.services.playbook_product_capture import parse_product_capture
        capture=parse_product_capture(self.page(),self.URL)
        self.assertEqual(capture['status'],'captured')
        self.assertEqual(capture['sku'],'B0DC8RVRBZ')
        self.assertEqual(capture['item_gbp'],'249.99')
        self.assertEqual(capture['condition'],'new')
        self.assertEqual(capture['stock_status'],'available')
        self.assertIn('Only 3 left',capture['stock_evidence'])
        self.assertEqual(capture['delivery_gbp'],'0')
        self.assertTrue(capture['postage_verified'])
        self.assertEqual(capture['delivery_destination'],'TW12 1JQ')
        self.assertFalse(capture['engineering_reviewed'])
        self.assertEqual(capture['product_properties'],{'Socket':'AM4','Wattage':'65W'})

    def test_asin_mismatch_cannot_capture_offer_for_another_product(self):
        from app.services.playbook_product_capture import parse_product_capture
        capture=parse_product_capture(self.page(asin='B000000000'),self.URL)
        self.assertEqual(capture['status'],'unresolved')

    def test_amazon_interstitial_is_reported_without_treating_it_as_a_product_page(self):
        from app.services.playbook_product_capture import parse_product_capture
        capture=parse_product_capture('<html><button>Continue shopping</button></html>',self.URL)
        self.assertEqual(capture['status'],'unresolved')
        self.assertIn('verification/interstitial',capture['reason'])

    def test_resale_offer_is_captured_as_used_and_remains_unapprovable(self):
        from app.services.playbook_product_capture import parse_product_capture
        capture=parse_product_capture(self.page(merchant='Amazon Resale',title='Example graphics card Used'),self.URL)
        self.assertEqual(capture['status'],'captured')
        self.assertEqual(capture['condition'],'used')

    def test_transient_retailer_gate_keeps_last_good_exact_url_capture(self):
        from app.services.playbook_product_capture import retain_last_good_capture
        previous={'status':'captured','url':self.URL,'observed_at':'2026-10-14T18:00:00+00:00',
            'item_gbp':'249.99','product_properties':{'Socket':'AM4'}}
        attempt={'status':'unresolved','reason':'verification gate','attempted_at':'2026-10-14T18:30:00+00:00'}
        kept=retain_last_good_capture(previous,attempt,self.URL)
        self.assertEqual(kept['item_gbp'],'249.99')
        self.assertEqual(kept['product_properties'],{'Socket':'AM4'})
        self.assertEqual(kept['last_capture_attempt']['reason'],'verification gate')
        replaced=retain_last_good_capture(previous,{**attempt,'status':'captured','item_gbp':'259.99'},self.URL)
        self.assertEqual(replaced['item_gbp'],'259.99')
        mismatch=retain_last_good_capture(previous,attempt,'https://www.amazon.co.uk/dp/B000000000')
        self.assertEqual(mismatch['status'],'unresolved')


    def test_old_successful_capture_is_refreshed_after_parser_upgrade(self):
        from datetime import datetime, timedelta, timezone
        from app.services.playbook_product_capture import (PARSER_VERSION, capture_refresh_outcome,
            product_capture_refresh_due)
        now=datetime(2026,10,14,19,0,tzinfo=timezone.utc)
        old={'status':'captured','parser_version':PARSER_VERSION-1,
            'attempted_at':(now-timedelta(minutes=5)).isoformat()}
        current={'status':'captured','parser_version':PARSER_VERSION,
            'attempted_at':(now-timedelta(minutes=5)).isoformat()}
        stale={**current,'attempted_at':(now-timedelta(hours=2)).isoformat()}
        self.assertTrue(product_capture_refresh_due(old,now))
        self.assertFalse(product_capture_refresh_due(current,now))
        self.assertTrue(product_capture_refresh_due(stale,now))
        failed={'status':'unresolved'}
        self.assertEqual(capture_refresh_outcome({'status':'captured'},{'status':'captured'}),'captured')
        self.assertEqual(capture_refresh_outcome(failed,{'status':'captured','last_capture_attempt':{'status':'unresolved'}}),'retained')
        self.assertEqual(capture_refresh_outcome(failed,failed),'unresolved')


class ProductPageSourcePreviewTests(unittest.IsolatedAsyncioTestCase):
    def test_exact_offer_beats_newer_weaker_listing_estimate_for_same_price(self):
        url='https://www.amazon.co.uk/AMD-Ryzen-5600X/dp/B08166SLDF/ref=product'
        listing_estimate_url='https://www.amazon.co.uk/AMD-Ryzen-5600X/dp/B08166SLDF/ref=search'
        exact={'identity_source':'exact_retailer_product_page','url':url,'item_gbp':'146.99',
            'condition':'new','stock_status':'available','stock_evidence':'In stock',
            'postage_verified':True,'delivery_working_days':3,
            'delivery_estimate_source':'amazon_displayed_default_destination',
            'observed_at':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}
        weaker={'identity_source':'approved_catalogue_listing_link','url':listing_estimate_url,
            'item_gbp':'146.99','condition':'new','stock_status':'unknown','stock_evidence':None,
            'postage_verified':False,'delivery_working_days':0,'delivery_estimate_source':'listing_estimate',
            'observed_at':datetime.now(timezone.utc).isoformat()}

        self.assertTrue(prefer_exact_product_page_preview(exact,weaker))
        self.assertFalse(prefer_exact_product_page_preview(exact,{**weaker,'item_gbp':'149.99'}))
        self.assertFalse(prefer_exact_product_page_preview(exact,{**weaker,'stock_status':'unavailable'}))

    async def test_exact_fresh_capture_keeps_unknown_stock_and_postage_unknown(self):
        now=datetime.now(timezone.utc).isoformat()
        listing=SimpleNamespace(id=81,external_id=None,
            url='https://www.amazon.co.uk/dp/B08K16S4K1',status='active',price=129.99,
            source_name='Amazon UK',raw_specs={'playbook_product_capture':{'status':'captured',
                'url':'https://www.amazon.co.uk/dp/B08K16S4K1','observed_at':now,
                'item_gbp':'129.99','delivery_gbp':None,'postage_verified':False,
                'delivery_working_days':4,'delivery_estimate_source':'structured_product_offer',
                'stock_status':'unknown','stock_evidence':None,'product_properties':{'Socket':'AM4'}}})
        preview=await _product_page_source_preview(None,listing)
        self.assertTrue(preview['commercial_capture_verified'])
        self.assertFalse(preview['postage_verified'])
        self.assertFalse(preview['active_listing'])
        self.assertEqual(preview['stock_status'],'unknown')
        self.assertEqual(preview['delivery_working_days'],4)
        self.assertEqual(preview['product_properties'],{'Socket':'AM4'})

    async def test_capture_cannot_cross_identity_or_replace_listing_price(self):
        capture={'status':'captured','url':'https://www.amazon.co.uk/dp/B000000000',
            'observed_at':datetime.now(timezone.utc).isoformat(),'item_gbp':'99.99',
            'delivery_gbp':'0','postage_verified':True,'stock_status':'available'}
        listing=SimpleNamespace(id=82,external_id=None,url='https://www.amazon.co.uk/dp/B08K16S4K1',
            status='active',price=100,source_name='Amazon UK',raw_specs={'playbook_product_capture':capture})
        self.assertIsNone(await _product_page_source_preview(None,listing))
        capture['url']=listing.url
        self.assertIsNone(await _product_page_source_preview(None,listing))
