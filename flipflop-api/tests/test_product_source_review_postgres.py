"""Source writes must preserve concurrent operator reviews in the disposable DB."""
import unittest
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import delete
from app.database import engine,AsyncSessionLocal,Base
from app.models.listing import Listing
from app.services.playbook_product_capture import persist_product_source_capture,PARSER_VERSION


class ProductSourceReviewPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if engine.url.database!='flipflop_readiness_test':
            self.skipTest('Requires the explicitly selected flipflop_readiness_test database')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.url='https://www.amazon.co.uk/dp/B000000001'
        async with AsyncSessionLocal() as db:
            row=Listing(external_id='source-race-'+uuid4().hex,source_id=0,source_name='amazon',
                title='Example CPU',url=self.url,price=100,status='active',
                raw_specs={'gem_radar_category':'cpu'})
            db.add(row)
            await db.commit()
            self.listing_id=row.id

    async def asyncTearDown(self):
        if not hasattr(self,'listing_id'):return
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Listing).where(Listing.id==self.listing_id))
            await db.commit()

    async def test_slow_capture_merges_concurrent_review_then_invalidates_changed_specs_with_history(self):
        async with AsyncSessionLocal() as fetcher:
            stale=await fetcher.get(Listing,self.listing_id)
            async with AsyncSessionLocal() as operator:
                current=await operator.get(Listing,self.listing_id)
                current.raw_specs={**current.raw_specs,'configurator':{'reviewed':True,'socket':'am5',
                    'power_w':65,'source_role':'cpu','source_url':self.url,'reviewed_by':'human-review'}}
                await operator.commit()
            now=datetime.now(timezone.utc).isoformat()
            attempt={'status':'captured','url':self.url,'title':'Example CPU','item_gbp':'110.00',
                'observed_at':now,'attempted_at':now,'parser_version':PARSER_VERSION,
                'product_properties':{'Socket':'AM5','TDP':'65 W'}}
            await persist_product_source_capture(fetcher,stale,'playbook_product_capture',attempt)
            await fetcher.commit()
            self.assertTrue(stale.raw_specs['configurator']['reviewed'])
            self.assertEqual(stale.raw_specs['configurator']['reviewed_by'],'human-review')
            self.assertEqual(stale.price,110)
            changed={**attempt,'product_properties':{'Socket':'AM5','TDP':'95 W'}}
            await persist_product_source_capture(fetcher,stale,'playbook_product_capture',changed)
            await fetcher.commit()
            retained=await persist_product_source_capture(fetcher,stale,'playbook_product_capture',{
                'status':'unresolved','reason':'Retailer temporarily unavailable',
                'attempted_at':datetime.now(timezone.utc).isoformat()})
            await fetcher.commit()
            self.assertEqual(retained,'retained')
            self.assertEqual(stale.last_seen_at,datetime.fromisoformat(now).replace(tzinfo=None))
        async with AsyncSessionLocal() as check:
            row=await check.get(Listing,self.listing_id)
            self.assertFalse(row.raw_specs['configurator']['reviewed'])
            self.assertEqual(row.raw_specs['configurator']['power_w'],65)
            prior=row.raw_specs['configurator_review_history'][0]['review']
            self.assertTrue(prior['reviewed'])
            self.assertEqual(prior['reviewed_by'],'human-review')
            self.assertEqual(row.raw_specs['configurator']['review_invalidation']
                ['reviewed_value_changes']['power_w'],{'reviewed':65,'captured':95})

    async def test_changed_listing_identity_rejects_old_capture_price_and_invalidates_old_review(self):
        async with AsyncSessionLocal() as fetcher:
            stale=await fetcher.get(Listing,self.listing_id)
            async with AsyncSessionLocal() as operator:
                current=await operator.get(Listing,self.listing_id)
                current.raw_specs={**current.raw_specs,'configurator':{'reviewed':True,'socket':'am5',
                    'source_role':'cpu','source_url':self.url,'reviewed_by':'human-review'}}
                current.url='https://www.amazon.co.uk/dp/B000000002'
                await operator.commit()
            now=datetime.now(timezone.utc).isoformat()
            result=await persist_product_source_capture(fetcher,stale,'playbook_product_capture',{
                'status':'captured','url':self.url,'title':'Previous product','item_gbp':'999.00',
                'observed_at':now,'attempted_at':now,'product_properties':{'Socket':'AM5'}})
            await fetcher.commit()
            self.assertEqual(result,'unresolved')
            self.assertEqual(stale.price,100)
            self.assertFalse(stale.raw_specs['configurator']['reviewed'])
            self.assertEqual(stale.raw_specs['configurator_review_history'][0]['review']['source_url'],self.url)
            self.assertIn('URL changed',stale.raw_specs['playbook_product_capture']['reason'])
