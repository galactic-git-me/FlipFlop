from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException
from app.services import playbook_extension as extension
from app.services.playbook_market import bom_hash
from app.api.gem_radar import PlaybookMarketCapture


class TargetTests(TestCase):
    def test_tags_are_role_scoped_and_queries_follow_selected_parts(self):
        definition={'id':'C','name':'Build','segment':'Gaming','tier':'Budget','components':{}}
        parts={'cpu':{'title':'Ryzen 5 5600','variant_id':1,'asin':'B123456789','cpk':'cpu:5600'},
               'gpu':{'title':'RTX 5050','variant_id':2},'motherboard':{'title':'MSI B550M'},
               'ram':{'title':'32GB DDR4'},'storage':{'title':'1TB SSD'}}
        row=extension.target(definition,NS(id=1),parts)
        self.assertIn('ASIN:cpu:B123456789',row['tags'])
        self.assertIn('CPK:cpu:cpu:5600',row['tags'])
        self.assertIn('MSI B550M',row['preciseQuery'])
        self.assertEqual(row['playbookTarget']['bomSha256'],bom_hash(definition,parts))
        self.assertEqual(row['listingMode'],'both')
        self.assertEqual(len(row['marketplaces']),10)


class CaptureTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.parent=NS(id=1)
        self.definition={'id':'C','components':{}}
        self.parts={'cpu':{'title':'Ryzen 5 5600'},'gpu':{'title':'RTX 5050'},
                    'ram':{'title':'32GB DDR4'},'storage':{'title':'1TB SSD'}}
        self.db=NS(add=Mock(side_effect=lambda row:setattr(row,'id',123)),commit=AsyncMock())
        for name,value in [('context',(self.parent,self.definition,self.parts)),('latest',None)]:
            p=patch.object(extension,name,AsyncMock(return_value=value));p.start();self.addCleanup(p.stop)

    def request(self,**updates):
        return PlaybookMarketCapture(**{'playbook_id':1,'cell_id':'C','bom_sha256':bom_hash(self.definition,self.parts),
            'search_id':'playbook-market-C','vendor':'ebay','kind':'sold',
            'source_url':'https://www.ebay.co.uk/sch/i.html?LH_Sold=1&LH_Complete=1',
            'listings':[{'url':'https://www.ebay.co.uk/itm/123456789012',
              'title':'Desktop PC 5600 RTX 5050 32GB 1TB','itemPrice':500,'postagePrice':10,
              'sold_date_text':'Sold '+datetime.now(timezone.utc).strftime('%d %b %Y'),'currency':'GBP','conditionNormalised':'new','deliveryCostKnown':True,'soldConfirmed':True}],**updates})

    async def test_browser_capture_is_unapproved_and_scoped(self):
        response=await extension.ingest(self.db,self.request())
        snapshot=self.db.add.call_args.args[0]
        self.assertEqual(snapshot.product_key,'playbook:1:cell:C')
        self.assertEqual(snapshot.evidence_json['candidates'][0]['total_gbp'],'510.00')
        self.assertEqual(snapshot.evidence_json['candidates'][0]['blockers'],[])
        self.assertFalse(response['approved'])

    async def test_search_tag_cannot_override_changed_build_or_unsold_source(self):
        for body in (self.request(bom_sha256='b'*64),self.request(source_url='https://www.ebay.co.uk/sch/i.html')):
            with self.assertRaises(HTTPException):await extension.ingest(self.db,body)
        self.db.commit.assert_not_awaited()

    async def test_missing_delivery_and_sold_markers_remain_blocked(self):
        body=self.request();body.listings[0].delivery_cost_known=False;body.listings[0].sold_confirmed=False
        await extension.ingest(self.db,body)
        row=self.db.add.call_args.args[0].evidence_json['candidates'][0]
        self.assertIn('Sold marker not captured',row['blockers'])
        self.assertIsNone(row['total_gbp'])

    async def test_range_and_best_offer_are_not_transaction_prices(self):
        body=self.request()
        body.listings[0].price_is_range=True
        body.listings[0].best_offer_enabled=True
        await extension.ingest(self.db,body)
        row=self.db.add.call_args.args[0].evidence_json['candidates'][0]
        self.assertIn('Configurable price range is not one verified configuration price',row['blockers'])
        self.assertIn('Accepted best-offer sale price is not verified',row['blockers'])

    async def test_other_vendors_are_current_asking_prices_only(self):
        body=self.request(vendor='amazon',kind='active',source_url='https://www.amazon.co.uk/s?k=desktop')
        body.listings[0].url='https://www.amazon.co.uk/dp/B123456789'
        await extension.ingest(self.db,body)
        row=self.db.add.call_args.args[0].evidence_json['candidates'][0]
        self.assertEqual(row['kind'],'active');self.assertEqual(row['blockers'],[])
        with self.assertRaises(HTTPException):await extension.ingest(self.db,self.request(vendor='amazon'))
