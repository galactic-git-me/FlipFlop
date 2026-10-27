from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException
from app.services import playbook_market as market
from app.api.playbook_service import MarketDecision


class MarketFactsTests(TestCase):
    def test_collector_requires_explicit_sold_label_gbp_and_delivery(self):
        from app.gem_radar.adapters.sold_comps import LiveSoldCompsAdapter
        html='''<li class="s-card" data-listingid="1"><span aria-label="Sold item">Sold 14 Oct 2026</span>
        <a href="https://www.ebay.co.uk/itm/123456789012"><h3 class="s-card__title">Desktop PC</h3></a>
        <span class="s-card__subtitle">Brand new</span><span class="s-card__price">£500.00</span><span class="s-card__shipping">Free delivery</span></li>'''
        rows=LiveSoldCompsAdapter()._extract_comps_from_html(html,'new')
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0].delivery_cost_known)
        self.assertEqual(rows[0].sold_date_text,'Sold 14 Oct 2026')
        self.assertEqual(LiveSoldCompsAdapter()._extract_comps_from_html(html.replace('£','$'),'new'),[])
        self.assertEqual(LiveSoldCompsAdapter()._extract_comps_from_html(html.replace('aria-label="Sold item"',''),'new'),[])
    def test_url_identity_and_credentials(self):
        self.assertEqual(market.listing_identity('https://www.ebay.co.uk/itm/build/123456789012?x=1'), '123456789012')
        for url in ('https://evil-ebay.co.uk/itm/123456789012', 'http://www.ebay.co.uk/itm/123456789012',
                    'https://user:secret@www.ebay.co.uk/itm/123456789012'):
            self.assertIsNone(market.listing_identity(url))

    def test_unknown_delivery_and_condition_are_blocked(self):
        row = market.candidate({'price':100,'postage':None,'title':'Desktop PC','condition':'used',
            'url':'https://www.ebay.co.uk/itm/123456789012'}, 'sold','new',0)
        self.assertIsNone(row['total_gbp'])
        self.assertEqual(len(row['blockers']),3)

    def test_sold_and_asking_prices_are_separate(self):
        rows = [{'kind':'sold','total_gbp':str(v)} for v in (100,200,300)]
        rows.append({'kind':'active','total_gbp':'9999'})
        self.assertEqual(market.summarize(rows), {'sold_sample_size':3,'sold_median_gbp':'200.00',
            'sold_p75_gbp':None,'active_sample_size':1,'active_median_gbp':'9999.00'})

    def test_high_end_cap_requires_eight_sold_comps_and_uses_linear_p75(self):
        self.assertIsNone(market.percentile_75(range(1, 8)))
        self.assertEqual(market.percentile_75(range(1, 9)), '6.25')

    def test_core_model_suffix_and_capacity_do_not_cross_match(self):
        parts={role:{'title':title} for role,title in {'cpu':'AMD Ryzen 5 5600','gpu':'NVIDIA RTX 5050 8GB',
            'ram':'32GB DDR4','storage':'1TB NVMe SSD'}.items()}
        self.assertEqual(market.core_spec_blockers('Desktop PC Ryzen 5600 RTX 5050 32GB 1TB',parts),[])
        self.assertTrue(market.core_spec_blockers('Desktop PC Ryzen 5600X RTX 5050 Ti 16GB 2TB',parts))

    def test_component_change_and_age_invalidate_approval(self):
        definition={'id':'C','components':{'cpu':'model'}}
        parts={'cpu':{'variant_id':1,'title':'model'}}
        saved={'bom_sha256':market.bom_hash(definition,parts),'observed_at':datetime.now(timezone.utc).isoformat(),
            'sold_transactions':[{'sold_at':datetime.now(timezone.utc).isoformat()} for _ in range(8)]}
        parent=NS(pricing_model={'cell_market_evidence':{'C':saved}})
        self.assertEqual(market.approved_market(parent,definition,parts),saved)
        self.assertIsNone(market.approved_market(parent,definition,{'cpu':{'variant_id':2,'title':'model'}}))
        saved['observed_at']=(datetime.now(timezone.utc)-timedelta(days=31)).isoformat()
        self.assertIsNone(market.approved_market(parent,definition,parts))


class MarketApprovalTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.parent=NS(pricing_model={'managed_offers':{'unchanged':True}})
        self.definition={'id':'C','components':{'cpu':'model'}}
        self.parts={'cpu':{'variant_id':1,'title':'model'}}
        self.rows=[{'id':f'sold:{123456789000+i}','kind':'sold','title':'PC','condition':'new',
            'url':f'https://www.ebay.co.uk/itm/{123456789000+i}','total_gbp':str(100+i*100),'sold_at':datetime.now(timezone.utc).isoformat(),'blockers':[]} for i in range(3)]
        self.rows.extend({'id':f'sold:{123456789000+i}','kind':'sold','title':'PC','condition':'new',
            'url':f'https://www.ebay.co.uk/itm/{123456789000+i}','total_gbp':str(100+i*100),'sold_at':datetime.now(timezone.utc).isoformat(),'blockers':[]} for i in range(3,8))
        self.batch=NS(id=5,evidence_json={'bom_sha256':market.bom_hash(self.definition,self.parts),
            'observed_at':datetime.now(timezone.utc).isoformat(),'condition':'new','candidates':self.rows})
        self.db=NS(add=Mock(),commit=AsyncMock())
        self.ctx=patch.object(market,'context',AsyncMock(return_value=(self.parent,self.definition,self.parts)))
        self.latest=patch.object(market,'latest',AsyncMock(return_value=self.batch))
        self.view=patch.object(market,'review_view',AsyncMock(return_value={'decision':None}))
        for p in (self.ctx,self.latest,self.view):p.start();self.addCleanup(p.stop)

    def request(self, **overrides):
        return MarketDecision(**{'batch_id':5,'decision':'approve','candidate_ids':[r['id'] for r in self.rows],
            'exact_build_confirmed':True,**overrides})

    async def test_approval_rechecks_transaction_age_even_without_saved_blockers(self):
        self.rows[0]['sold_at']=(datetime.now(timezone.utc)-timedelta(days=60)).isoformat()
        body=MarketDecision(batch_id=5,decision='approve',candidate_ids=[row['id'] for row in self.rows],exact_build_confirmed=True)
        with self.assertRaises(HTTPException):
            await market.decide(self.db,1,'C',body,7)
        self.db.commit.assert_not_awaited()

    async def test_approval_persists_evidence_without_publishing(self):
        await market.decide(self.db,1,'C',self.request(),7)
        saved=self.parent.pricing_model['cell_market_evidence']['C']
        self.assertEqual(saved['sold_median_gbp'],'450.00')
        self.assertEqual(saved['sold_p75_gbp'],'625.00')
        self.assertEqual(saved['minimum_sold_sample_size'],8)
        self.assertEqual(saved['approved_by'],7)
        self.assertEqual(self.parent.pricing_model['managed_offers'],{'unchanged':True})
        audit=self.db.add.call_args.args[0]
        self.assertEqual(audit.status,'market_approved')
        self.assertFalse(audit.decision_json['checkout_changed'])
        self.db.commit.assert_awaited_once()

    async def test_incomplete_review_stale_batch_and_blocked_rows_cannot_approve(self):
        for request in (self.request(exact_build_confirmed=False),self.request(candidate_ids=[self.rows[0]['id']]),
                        self.request(batch_id=6),self.request(candidate_ids=['invented'])):
            with self.assertRaises(HTTPException):await market.decide(self.db,1,'C',request,7)
        self.rows[0]['blockers']=['Unknown delivery']
        with self.assertRaises(HTTPException):await market.decide(self.db,1,'C',self.request(),7)
        self.db.commit.assert_not_awaited()


    async def test_reject_records_actor_without_changing_prices(self):
        before=deepcopy(self.parent.pricing_model)
        await market.decide(self.db,1,'C',self.request(decision='reject'),7)
        self.assertEqual(self.parent.pricing_model,before)
        self.assertEqual(self.db.add.call_args.args[0].status,'market_rejected')

    async def test_expired_or_changed_build_cannot_be_approved(self):
        self.batch.evidence_json['observed_at']=(datetime.now(timezone.utc)-timedelta(days=31)).isoformat()
        with self.assertRaises(HTTPException):await market.decide(self.db,1,'C',self.request(),7)
        self.batch.evidence_json['observed_at']=datetime.now(timezone.utc).isoformat()
        self.parts['cpu']['variant_id']=2
        with self.assertRaises(HTTPException):await market.decide(self.db,1,'C',self.request(),7)
        self.db.commit.assert_not_awaited()


class MarketPersistenceTests(IsolatedAsyncioTestCase):
    async def test_real_session_approval_and_replay_guard(self):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import select
        from app.database import Base
        from app.models.playbook import Playbook, PlaybookProposal
        from app.models.commerce_evidence import PriceQuoteSnapshot
        from app.services.curated_build_policy import definitions
        from app.services.playbook_service import required_parts
        engine=create_async_engine('sqlite+aiosqlite:///:memory:')
        try:
            async with engine.begin() as connection:
                await connection.run_sync(lambda c: Base.metadata.create_all(c,tables=[
                    Playbook.__table__,PlaybookProposal.__table__,PriceQuoteSnapshot.__table__]))
            session=async_sessionmaker(engine,expire_on_commit=False)
            definition=definitions()['builds'][0]
            parts={role:{'role':role,'variant_id':i+1,'title':definition['components'].get(role,role)}
                   for i,role in enumerate(required_parts(definition))}
            async with session() as db:
                db.add(Playbook(id=1,name=definition['segment'],status='active',pricing_model={}))
                db.add(PlaybookProposal(playbook_id=1,action='UPDATE',status='pending',
                    proposed_data={'cell_id':definition['id'],'components':list(parts.values())}))
                rows=[{'id':f'sold:{123456789100+i}','kind':'sold','title':'Desktop PC',
                    'url':f'https://www.ebay.co.uk/itm/{123456789100+i}','total_gbp':str(500+i*100),'sold_at':datetime.now(timezone.utc).isoformat(),'blockers':[]} for i in range(8)]
                batch=PriceQuoteSnapshot(product_key=market.key(1,definition['id']),status='market_candidates',
                    created_by_admin_id=7,evidence_json={'bom_sha256':market.bom_hash(definition,parts),
                        'condition':'new','observed_at':datetime.now(timezone.utc).isoformat(),'candidates':rows},decision_json={})
                db.add(batch);await db.commit()
                body=MarketDecision(batch_id=batch.id,decision='approve',candidate_ids=[r['id'] for r in rows],exact_build_confirmed=True)
                result=await market.decide(db,1,definition['id'],body,7)
                self.assertEqual(result['decision'],'market_approved')
                self.assertEqual(result['approved']['sold_median_gbp'],'850.00')
                self.assertEqual(result['approved']['sold_p75_gbp'],'1025.00')
                with self.assertRaises(HTTPException):await market.decide(db,1,definition['id'],body,7)
            async with session() as db:
                parent=await db.get(Playbook,1)
                self.assertEqual(parent.pricing_model['cell_market_evidence'][definition['id']]['approved_by'],7)
                audits=(await db.execute(select(PriceQuoteSnapshot).where(PriceQuoteSnapshot.status=='market_approved'))).scalars().all()
                self.assertEqual(len(audits),1)
        finally:
            await engine.dispose()

