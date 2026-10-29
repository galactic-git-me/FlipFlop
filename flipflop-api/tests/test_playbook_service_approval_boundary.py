from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import catalogue_price_import, playbook_service


@pytest.mark.asyncio
async def test_refresh_releases_catalogue_locks_before_browser_collection_and_retains_completed_stages(monkeypatch):
    import app.database as database
    from app.services import amazon_bestsellers,bestseller_catalogue_sync,playbook_product_capture,royalcdkeys_catalogue_sync
    events=[]
    class Session:
        async def __aenter__(self):return self
        async def __aexit__(self,*_args):return False
        async def commit(self):events.append('commit')
    monkeypatch.setattr(database,'AsyncSessionLocal',Session)
    async def ranks(**_kwargs):return {}
    async def royal(_db):events.append('royal');return {}
    async def sync(_db,*,check_free_software=True):
        events.append('catalogue' if check_free_software else 'catalogue_after_capture');return {}
    async def capture(_db):
        assert events==['royal','commit','catalogue','commit','discovery','commit']
        events.append('capture');return {}
    async def discovery(_db):events.append('discovery');return {}
    monkeypatch.setattr('app.services.playbook_requirement_sources.discover_missing_requirement_sources',discovery)
    async def failed_build(_db,_actor):
        assert events[-4:]==['capture','commit','catalogue_after_capture','commit']
        raise RuntimeError('build failed after source capture')
    monkeypatch.setattr(amazon_bestsellers,'scrape_amazon_component_bestsellers',ranks)
    monkeypatch.setattr(royalcdkeys_catalogue_sync,'refresh_royalcdkeys_os_catalogue',royal)
    monkeypatch.setattr(bestseller_catalogue_sync,'sync_bestseller_catalogues',sync)
    monkeypatch.setattr(playbook_product_capture,'refresh_selected_product_facts',capture)
    monkeypatch.setattr(playbook_service,'refresh_playbooks',failed_build)
    with pytest.raises(RuntimeError,match='build failed'):
        await playbook_service.run_playbook_refresh(0)
    assert events==['royal','commit','catalogue','commit','discovery','commit','capture','commit',
        'catalogue_after_capture','commit']


@pytest.mark.asyncio
async def test_build_offer_assesses_approved_evidence_without_importing_supplier_facts(monkeypatch):
    roles = ("cpu", "gpu")
    parts = {
        role: {
            "role": role,
            "variant_id": index,
            "slot_id": index,
            "listing_id": index,
            "title": f"{role.upper()} product {index}",
            "source_observation": {
                "fresh": True,
                "active_listing": True,
                "stock_status": "available",
            },
            "catalogue_approved": True,
            "engineering": {},
        }
        for index, role in enumerate(roles, start=1)
    }

    monkeypatch.setattr(playbook_service, "required_roles", lambda _definition: roles)
    monkeypatch.setattr(playbook_service, "required_parts", lambda _definition: roles)
    monkeypatch.setattr(playbook_service, "assemble_components", lambda *_args, **_kwargs: (parts, []))
    monkeypatch.setattr(playbook_service, "_performance_context", lambda *_args: {})
    monkeypatch.setattr(playbook_service, "_candidate_performance", lambda *_args: None)
    monkeypatch.setattr(playbook_service, "automatic_policy", lambda *_args: SimpleNamespace(enabled_modes=playbook_service.MODES))
    monkeypatch.setattr(
        playbook_service,
        "component_delivery_eligibility",
        lambda *_args: {"fast_track": True, "standard": True, "flexible": True},
    )
    monkeypatch.setattr(playbook_service, "evaluate_fit", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        playbook_service,
        "estimate_delivery_products",
        lambda *_args: {
            mode: {
                "recommended_price_gbp": "100.00",
                "estimated_profit_gbp": "20.00",
                "reason": "proposed pending evidence review",
            }
            for mode in playbook_service.MODES
        },
    )

    async def assess(_db, _parent, _definition, _policy, _body):
        return {
            "modes": {
                mode: {"offerable": False, "reason": "Supplier evidence awaits operator approval"}
                for mode in playbook_service.MODES
            }
        }, {}

    monkeypatch.setattr("app.services.commercial_quote_evidence.assess_stored_cell", assess)
    monkeypatch.setattr("app.services.commercial_checkout.current_capacity_ids", AsyncMock(return_value={}))
    importer = AsyncMock()
    monkeypatch.setattr(catalogue_price_import, "import_current_catalogue_prices", importer, raising=False)

    definition = {
        "id": "TEST-CELL",
        "segment": "Test segment",
        "tier": "Budget",
        "name": "Test build",
        "components": {"cpu": "CPU product", "gpu": "GPU product"},
    }
    parent = SimpleNamespace(id=7, profit_strategy={}, pricing_model={})
    settings = SimpleNamespace()

    offer = await playbook_service.build_cell_offer(
        object(), definition, parent, settings, [], benchmark_index={}
    )

    importer.assert_not_awaited()
    assert offer["purchasable"] is False
    assert any("Supplier evidence awaits operator approval" in blocker for blocker in offer["blockers"])


@pytest.mark.asyncio
async def test_build_offer_selects_standard_eligible_benchmark_qualified_shared_bom(monkeypatch):
    roles = ("cpu", "gpu")
    monkeypatch.setattr(playbook_service, "required_roles", lambda _definition: roles)
    monkeypatch.setattr(playbook_service, "required_parts", lambda _definition: roles)
    monkeypatch.setattr(playbook_service, "_performance_context", lambda *_args: {
        "cpu": {"metric": "overall_score", "benchmark_source": "passmark",
            "confidence_score": 0.9, "overall_score": 100},
    })
    monkeypatch.setattr(playbook_service, "_candidate_performance", lambda *_args: None)
    monkeypatch.setattr(playbook_service, "evaluate_fit", lambda *_args, **_kwargs: [])

    def policy(*_args):
        return SimpleNamespace(modes={mode: object() for mode in playbook_service.MODES})

    monkeypatch.setattr(playbook_service, "automatic_policy", policy)
    monkeypatch.setattr(playbook_service, "component_delivery_eligibility", lambda part, _policy: {
        mode: part["source_observation"]["delivery_working_days"] <= limit
        for mode, limit in {"fast_track": 3, "standard": 5, "flexible": 14}.items()
    })
    monkeypatch.setattr(playbook_service, "estimate_delivery_products", lambda *_args: {
        mode: {"recommended_price_gbp": None, "reason": "Awaiting reviewed exact supplier costs"}
        for mode in playbook_service.MODES
    })

    def source(days):
        return {"fresh": True, "commercial_capture_verified": True, "active_listing": True,
            "stock_status": "available", "stock_evidence": "In stock", "postage_verified": True,
            "delivery_working_days": days}

    candidates = [
        {"role": "cpu", "title": "AMD Ryzen 5 5600 Processor", "variant_id": 10, "listing_id": 110,
            "slot_id": 1, "listing_price_gbp": "100.00", "supplier_postage_gbp": "0.00",
            "landed_gbp": "100.00", "source_price_verified": True,
            "performance_evidence": {"benchmark_source": "passmark", "confidence_score": 0.9,
                "overall_score": 100}, "engineering": {"reviewed": True},
            "source_observation": source(9), "catalogue_approved": True},
        {"role": "cpu", "title": "AMD Ryzen 5 5600X Processor", "variant_id": 11, "listing_id": 111,
            "slot_id": 1, "listing_price_gbp": "120.00", "supplier_postage_gbp": "0.00",
            "landed_gbp": "120.00", "source_price_verified": True,
            "performance_evidence": {"benchmark_source": "passmark", "confidence_score": 0.9,
                "overall_score": 110}, "engineering": {"reviewed": True},
            "source_observation": source(3), "catalogue_approved": True},
        {"role": "gpu", "title": "NVIDIA GeForce RTX 4060 Graphics Card", "variant_id": 20,
            "listing_id": 120, "slot_id": 2, "listing_price_gbp": "200.00",
            "supplier_postage_gbp": "0.00", "landed_gbp": "200.00", "source_price_verified": True,
            "engineering": {"reviewed": True}, "source_observation": source(3),
            "catalogue_approved": True},
    ]

    definition = {"id": "TEST-DELIVERY", "segment": "Gaming", "tier": "Budget", "name": "Test build",
        "components": {"cpu": "AMD Ryzen 5 5600", "gpu": "NVIDIA GeForce RTX 4060"}}
    offer = await playbook_service.build_cell_offer(object(), definition,
        SimpleNamespace(id=7, profit_strategy={}, pricing_model={}), SimpleNamespace(), candidates, benchmark_index={})

    selected = {part["role"]: part for part in offer["components"]}
    assert selected["cpu"]["variant_id"] == 11
    assert selected["cpu"]["delivery_eligibility"]["standard"] is True
    assert offer["purchasable"] is False
    assert any("Awaiting reviewed exact supplier costs" in blocker for blocker in offer["blockers"])


@pytest.mark.asyncio
async def test_royalcdkeys_approval_activates_os_catalogue_candidates_without_publishing(monkeypatch):
    fingerprint='a'*64
    listing=SimpleNamespace(id=91,source_name='RoyalCDKeys',title='Windows 11 Home OEM Key',url='https://royalcdkeys.com/en-gb/products/windows-11-home-oem-key',raw_specs={
        'royalcdkeys':{'category':'os','handle':'windows-11-home-oem-key'},
        'playbook_product_capture':{'status':'captured','licence_review_required':True,
            'product_properties':{'License type (supplier listing)':'OEM',
                'Key uniqueness (supplier claim)':'No key-reuse statement captured'}}})
    observation={'fresh':True,'licence_review_fingerprint':fingerprint,'product_properties':{
        'License type (supplier listing)':'OEM','Key uniqueness (supplier claim)':'No key-reuse statement captured'}}
    variant=SimpleNamespace(id=103,status='pending_review',reviewed_at=None,reviewed_by=None,updated_at=None)
    listing_result=SimpleNamespace(scalar_one_or_none=lambda:listing)
    variant_result=SimpleNamespace(all=lambda:[(variant,2)])
    db=SimpleNamespace(execute=AsyncMock(side_effect=[listing_result,variant_result]),add=lambda row:setattr(db,'audit',row),flush=AsyncMock())
    monkeypatch.setattr('app.services.commercial_readiness.source_preview',AsyncMock(return_value=observation))

    outcome=await playbook_service.approve_royalcdkeys_licence_source(db,91,fingerprint,7)

    assert outcome['reviewed'] is True
    assert outcome['prices_published'] is False
    assert outcome['checkout_changed'] is False
    assert outcome['activated_catalogue_links']==1
    assert variant.status=='active'
    assert variant.reviewed_by=='7'
    assert listing.raw_specs['playbook_licence_source_review']['reviewed_by_admin_id']==7
    assert db.audit.decision_json['licence_entitlement_independently_verified'] is False
    assert db.audit.decision_json['automatic_resale_authorization_claimed'] is False
    assert db.audit.decision_json['prices_published'] is False


@pytest.mark.asyncio
async def test_royalcdkeys_office_review_does_not_activate_or_publish_a_customer_offer(monkeypatch):
    fingerprint='c'*64
    listing=SimpleNamespace(id=92,source_name='RoyalCDKeys',title='Microsoft Office 2024',
        url='https://royalcdkeys.com/en-gb/products/office-2024',raw_specs={
            'royalcdkeys':{'category':'office','handle':'office-2024'},
            'playbook_product_capture':{'status':'captured','licence_review_required':True,
                'product_properties':{'License type (supplier listing)':'Not stated'}}})
    observation={'fresh':True,'licence_review_fingerprint':fingerprint,'product_properties':{}}
    listing_result=SimpleNamespace(scalar_one_or_none=lambda:listing)
    variant_result=SimpleNamespace(all=lambda:[])
    db=SimpleNamespace(execute=AsyncMock(side_effect=[listing_result,variant_result]),
        add=lambda row:setattr(db,'audit',row),flush=AsyncMock())
    monkeypatch.setattr('app.services.commercial_readiness.source_preview',AsyncMock(return_value=observation))

    outcome=await playbook_service.approve_royalcdkeys_licence_source(db,92,fingerprint,7)

    assert outcome['category']=='office'
    assert outcome['activated_catalogue_links']==0
    assert outcome['customer_offering_enabled'] is False
    assert db.audit.decision_json['software_source_review_only'] is True
    assert db.audit.decision_json['prices_published'] is False
    assert db.audit.decision_json['checkout_changed'] is False


def test_playbook_service_api_exposes_admin_reviewed_licence_workflow(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import playbook_service as api_module
    from app.database import get_db
    from app.database import get_db
    from app.routes.admin_auth import get_current_admin

    app=FastAPI();app.include_router(api_module.router)
    db=SimpleNamespace(commit=AsyncMock())
    async def provide_db():
        yield db
    app.dependency_overrides[get_db]=provide_db
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=17)
    monkeypatch.setattr(api_module,'royalcdkeys_licence_candidates',AsyncMock(return_value=[{'listing_id':1}]))
    review=AsyncMock(return_value={'listing_id':1,'reviewed':True,'reused':False,'published':False})
    monkeypatch.setattr(api_module,'approve_royalcdkeys_licence_source',review)

    with TestClient(app) as client:
        assert client.get('/playbook-service/supplier-licences').json()=={'items':[{'listing_id':1}]}
        response=client.post('/playbook-service/supplier-licences/1/approve',json={'licence_review_fingerprint':'b'*64})
        assert response.status_code==200
        assert review.await_args.args==(db,1,'b'*64,17)
        assert client.post('/playbook-service/supplier-licences/1/approve',json={'licence_review_fingerprint':'bad'}).status_code==422
    db.commit.assert_awaited_once()


def test_playbook_refresh_is_queued_and_status_is_admin_only(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import playbook_service as api_module
    from app.database import get_db
    from app.routes.admin_auth import get_current_admin

    app=FastAPI();app.include_router(api_module.router)
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=17)
    db=SimpleNamespace()
    app.dependency_overrides[get_db]=lambda:db
    job={'job_id':'refresh-test','status':'queued','phase':'Queued source refresh',
        'started_at':'2026-10-15T00:00:00+00:00','completed_at':None,'error':None,'result':None,'started':True}
    monkeypatch.setattr(api_module,'start_playbook_refresh_job',AsyncMock(return_value={**job,'actor_id':17}))
    runner=AsyncMock()
    monkeypatch.setattr(api_module,'run_playbook_refresh_job',runner)
    monkeypatch.setattr(api_module,'playbook_refresh_job_status',AsyncMock(side_effect=lambda _db,job_id:{**job,'job_id':job_id}))

    with TestClient(app) as client:
        response=client.post('/playbook-service/refresh')
        assert response.status_code==200
        assert response.json()['status']=='queued'
        assert 'actor_id' not in response.json()
        assert client.get('/playbook-service/refresh/refresh-test').json()['phase']=='Queued source refresh'
    runner.assert_awaited_once_with('refresh-test',17)


def test_playbook_rebuild_is_queued_as_a_background_job(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import playbook_service as api_module
    from app.database import get_db
    from app.routes.admin_auth import get_current_admin

    app=FastAPI();app.include_router(api_module.router)
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=17)
    db=SimpleNamespace()
    app.dependency_overrides[get_db]=lambda:db
    job={'job_id':'rebuild-test','mode':'rebuild','status':'queued','phase':'Queued proposal rebuild',
        'started_at':'2026-10-15T00:00:00+00:00','completed_at':None,'error':None,'result':None,'started':True}
    start=AsyncMock(return_value={**job,'actor_id':17})
    runner=AsyncMock()
    monkeypatch.setattr(api_module,'start_playbook_refresh_job',start)
    monkeypatch.setattr(api_module,'run_playbook_refresh_job',runner)
    monkeypatch.setattr(api_module,'playbook_refresh_job_status',AsyncMock(side_effect=lambda _db,job_id:{**job,'job_id':job_id}))

    with TestClient(app) as client:
        response=client.post('/playbook-service/rebuild')
        assert response.status_code==200
        assert response.json()['status']=='queued'
        assert response.json()['phase']=='Queued proposal rebuild'
        assert 'actor_id' not in response.json()
        assert client.get('/playbook-service/refresh/rebuild-test').json()['mode']=='rebuild'

    start.assert_awaited_once_with(db,17,mode='rebuild')
    runner.assert_awaited_once_with('rebuild-test',17)


@pytest.mark.asyncio
async def test_captured_catalogue_rebuild_commits_only_pending_proposal_metrics(monkeypatch):
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self,*_args): return None
        commit=AsyncMock()
    session=Session()
    monkeypatch.setattr('app.database.AsyncSessionLocal',lambda:session)
    events=[]
    async def sync(_db,*,check_free_software=True):
        events.append(('sync',check_free_software))
        return {'created_variants':2}
    monkeypatch.setattr(playbook_service,'sync_bestseller_catalogues',sync)
    refresh=AsyncMock(return_value={'cells':24,'complete_hardware':13,'ready_for_approval':0,
        'offers':[{'published':False}]})
    refresh.side_effect=lambda *_args,**_kwargs: events.append(('rebuild',None)) or {
        'cells':24,'complete_hardware':13,'ready_for_approval':0,'offers':[{'published':False}]}
    monkeypatch.setattr(playbook_service,'refresh_playbooks',refresh)

    result=await playbook_service.run_playbook_rebuild(17,progress=lambda _phase:None)

    assert result=={'cells':24,'complete_hardware':13,'ready_for_approval':0,
        'catalogue_sync':{'created_variants':2},'maintenance':None,'published':False}
    assert events==[('sync',False),('rebuild',None)]
    assert refresh.await_args.args==(session,17)
    refresh.assert_awaited_once()
    assert callable(refresh.await_args.kwargs['progress'])
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_playbook_refresh_job_reports_terminal_success_and_failure(monkeypatch):
    class Result:
        def __init__(self,row):self.row=row
        def scalar_one_or_none(self):return self.row
    class Session:
        def __init__(self):self.row=None
        async def __aenter__(self):return self
        async def __aexit__(self,*_args):return False
        async def execute(self,_statement):return Result(self.row if self.row and self.row.status in {'queued','running'} else None)
        def add(self,row):self.row=row
        async def commit(self):return None
        async def refresh(self,_row):return None
        async def get(self,_model,job_id):return self.row if self.row and self.row.job_id==job_id else None
        async def flush(self):return None
        async def rollback(self):return None
    session=Session()
    monkeypatch.setattr('app.database.AsyncSessionLocal',lambda:session)
    db=session
    queued=await playbook_service.start_playbook_refresh_job(db,17)
    assert queued['status']=='queued'
    assert (await playbook_service.start_playbook_refresh_job(db,18))['started'] is False
    monkeypatch.setattr(playbook_service,'run_playbook_refresh',AsyncMock(return_value={'cells':24}))
    await playbook_service.run_playbook_refresh_job(queued['job_id'],17)
    succeeded=await playbook_service.playbook_refresh_job_status(db,queued['job_id'])
    assert succeeded['status']=='succeeded'
    assert succeeded['result']=={'cells':24}

    failed=await playbook_service.start_playbook_refresh_job(db,17)
    monkeypatch.setattr(playbook_service,'run_playbook_refresh',AsyncMock(side_effect=RuntimeError('source failed')))
    await playbook_service.run_playbook_refresh_job(failed['job_id'],17)
    assert (await playbook_service.playbook_refresh_job_status(db,failed['job_id']))['error']=='RuntimeError: source failed'
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as missing:
        await playbook_service.playbook_refresh_job_status(db,'unknown')
    assert missing.value.status_code==404


@pytest.mark.asyncio
async def test_stale_queued_playbook_job_is_interrupted_and_replaced():
    from datetime import timedelta
    from app.models.playbook_refresh_run import PlaybookRefreshRun

    class Result:
        def __init__(self,row):self.row=row
        def scalar_one_or_none(self):return self.row
    class Session:
        def __init__(self,row):self.row=row
        async def execute(self,_statement):return Result(self.row)
        def add(self,row):self.row=row
        async def commit(self):return None
        async def refresh(self,_row):return None
        async def flush(self):return None
        async def rollback(self):return None

    stale_time=playbook_service._utcnow()-timedelta(minutes=6)
    stale=PlaybookRefreshRun(job_id='stale-job',actor_id=0,mode='refresh',status='queued',
        phase='Queued source refresh',started_at=stale_time,heartbeat_at=stale_time)
    session=Session(stale)

    job=await playbook_service.start_playbook_refresh_job(session,17,mode='rebuild')

    assert job['started'] is True
    assert job['job_id']!='stale-job'
    assert stale.status=='interrupted'
    assert stale.completed_at is not None
    assert 'without a heartbeat' in stale.error
    assert session.row.mode=='rebuild'


@pytest.mark.asyncio
async def test_playbook_refresh_status_marks_stale_progress_without_mutating_job():
    from datetime import timedelta
    from app.models.playbook_refresh_run import PlaybookRefreshRun

    class Session:
        async def get(self,_model,job_id):
            assert job_id=='slow-job'
            return row
        async def commit(self):
            raise AssertionError('A status GET must not write job state')
        async def refresh(self,_row):
            raise AssertionError('A status GET must not refresh mutated state')

    stale_time=playbook_service._utcnow()-timedelta(minutes=6)
    row=PlaybookRefreshRun(job_id='slow-job',actor_id=17,mode='refresh',status='running',
        phase='Capturing exact supplier pages',started_at=stale_time,heartbeat_at=stale_time)

    result=await playbook_service.playbook_refresh_job_status(Session(),'slow-job')

    assert result['status']=='running'
    assert result['progress_stale'] is True
    assert row.status=='running'
