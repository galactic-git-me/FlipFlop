"""Catalogue-owned Playbook offers: assemble, cost, check and propose centrally.

The service never treats a bestseller rank as stock or an unknown measurement
as compatible. Proposals retain source links; approval accepts their revision,
not operator-entered numbers.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import json
import re
from urllib.parse import urlsplit
from uuid import uuid4
from sqlalchemy import select, text
from fastapi import HTTPException
from app.models.catalogue import CatalogueVariant, PlaybookSlot, CaseCatalogue
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.curated_build_segment import CuratedBuildSegment
from app.models.listing import Listing
from app.models.motherboard_spec import MotherboardSpec
from app.models.playbook import Playbook, PlaybookProposal
from app.models.order import Order, OrderStatus
from app.models.growth import AnalyticsEvent
from app.models.playbook_refresh_run import PlaybookRefreshRun
from app.models.app_settings import AppSettings
from app.services.curated_build_policy import definitions
from app.services.commercial_readiness import fingerprint, source_preview, source_preview_many
from app.services.commercial_pilot_policy import APPROVED_TIER_FLOORS
from app.services.studio_fit import engineering_specs, evaluate_playbook_fit as evaluate_fit
from app.services.playbook_mvp import mvp_enabled, mvp_mode, prepare_candidates, publication_limit_reason, commercial_revision_payload
from app.services.compatibility_engine import _infer_cpu_socket, _extract_ram_type
from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu
from app.services.bestseller_catalogue_sync import HARDWARE_ROLES, sync_bestseller_catalogues, amazon_asin
from app.services.amazon_bestsellers import bestseller_item_matches_category

MODES=('fast_track','standard','flexible')
SOURCE='catalogue_playbook_service_v1'
MAX_CHOICES_PER_ROLE=100

PLAYBOOK_REFRESH_HEARTBEAT_SECONDS=15
PLAYBOOK_REFRESH_STALE_AFTER=timedelta(minutes=5)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _playbook_refresh_run_payload(row):
    return {'job_id':row.job_id,'mode':row.mode,'status':row.status,'phase':row.phase,
        'started_at':row.started_at.replace(tzinfo=timezone.utc).isoformat(),
        'completed_at':row.completed_at.replace(tzinfo=timezone.utc).isoformat() if row.completed_at else None,
        'error':row.error,'result':row.result}


async def start_playbook_refresh_job(db,actor_id,mode='refresh'):
    """Persist the job before returning so API reloads cannot erase its status."""
    await db.execute(text('SELECT pg_advisory_xact_lock(61311, 2)'))
    if mode=='refresh':
        rebuild=(await db.execute(select(PlaybookRefreshRun).where(
            PlaybookRefreshRun.actor_id==0,PlaybookRefreshRun.mode=='rebuild',
            PlaybookRefreshRun.status=='queued'
        ).order_by(PlaybookRefreshRun.started_at.asc()).limit(1))).scalar_one_or_none()
        if rebuild:
            payload=_playbook_refresh_run_payload(rebuild)
            await db.rollback()
            return {**payload,'started':False,'reason':'prioritized_rebuild_pending'}
    active=(await db.execute(select(PlaybookRefreshRun).where(
        PlaybookRefreshRun.status.in_(('queued','running'))
    ).order_by(PlaybookRefreshRun.started_at.desc()).limit(1).with_for_update())).scalar_one_or_none()
    now=_utcnow()
    if active:
        last_progress=active.heartbeat_at or active.started_at
        if now-last_progress<=PLAYBOOK_REFRESH_STALE_AFTER:
            payload=_playbook_refresh_run_payload(active)
            await db.rollback()
            return {**payload,'started':False}
        active.status='interrupted'
        active.phase='Interrupted after the queued job stopped progressing'
        active.completed_at=now
        active.error='The Playbook job remained queued or running without a heartbeat.'
        await db.flush()
    row=PlaybookRefreshRun(job_id=str(uuid4()),actor_id=actor_id,mode=mode,status='queued',
        phase='Queued proposal rebuild' if mode=='rebuild' else 'Queued source refresh',
        started_at=now,heartbeat_at=now)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {**_playbook_refresh_run_payload(row),'started':True,'actor_id':actor_id}


async def playbook_refresh_job_status(db,job_id):
    row=await db.get(PlaybookRefreshRun,job_id)
    if row is None:
        raise HTTPException(404,'Playbook refresh job not found')
    payload=_playbook_refresh_run_payload(row)
    last_progress=row.heartbeat_at or row.started_at
    payload['progress_stale']=bool(row.status in {'queued','running'}
        and _utcnow()-last_progress>PLAYBOOK_REFRESH_STALE_AFTER)
    return payload


async def _update_playbook_refresh_run(job_id,**changes):
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        row=await db.get(PlaybookRefreshRun,job_id)
        if row is None:
            return
        for key,value in changes.items():
            setattr(row,key,value)
        await db.commit()


async def run_playbook_refresh_job(job_id,actor_id):
    import asyncio
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(text('SELECT pg_advisory_xact_lock(61311, 4)'))
        row=await db.get(PlaybookRefreshRun,job_id)
        if row is None or row.status!='queued' or row.actor_id!=actor_id:
            return
        mode=row.mode
        phase_state={'phase':'Rebuilding proposals from captured catalogue facts' if mode=='rebuild'
            else 'Collecting Amazon hardware demand and selected Gamers Outlet software offers'}
        row.status='running';row.phase=phase_state['phase'];row.heartbeat_at=_utcnow()
        await db.commit()

    async def heartbeat():
        while True:
            await asyncio.sleep(PLAYBOOK_REFRESH_HEARTBEAT_SECONDS)
            if mode=='refresh':
                async with AsyncSessionLocal() as db:
                    queued_rebuild=(await db.execute(select(PlaybookRefreshRun.job_id).where(
                        PlaybookRefreshRun.actor_id==0,PlaybookRefreshRun.mode=='rebuild',
                        PlaybookRefreshRun.status=='queued'
                    ).limit(1))).scalar_one_or_none()
                if queued_rebuild:
                    if job_task and not job_task.done():
                        job_task.cancel()
                    return
            await _update_playbook_refresh_run(job_id,phase=phase_state['phase'],heartbeat_at=_utcnow())

    job_task=asyncio.current_task()
    heartbeat_task=asyncio.create_task(heartbeat())
    try:
        progress=lambda phase: phase_state.update(phase=phase)
        result=(await run_playbook_rebuild(actor_id,progress=progress) if mode=='rebuild'
                else await run_playbook_refresh(actor_id,progress=progress))
        await _update_playbook_refresh_run(job_id,status='succeeded',phase='Playbook proposals refreshed',
            heartbeat_at=_utcnow(),completed_at=_utcnow(),result=result,error=None)
    except Exception as error:
        await _update_playbook_refresh_run(job_id,status='failed',phase='Playbook refresh failed',
            heartbeat_at=_utcnow(),completed_at=_utcnow(),error=f'{type(error).__name__}: {error}')
    except asyncio.CancelledError:
        if mode!='refresh':
            raise
        await _update_playbook_refresh_run(job_id,status='interrupted',
            phase='Source refresh preempted for a prioritized Playbook rebuild',
            heartbeat_at=_utcnow(),completed_at=_utcnow(),
            error='A queued proposal rebuild took priority over source collection.')
        await run_pending_scheduled_playbook_rebuild()
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


async def run_scheduled_playbook_refresh():
    """Run the hourly catalogue refresh with the same durable status as admin runs."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        job=await start_playbook_refresh_job(db,actor_id=0,mode='refresh')
    if not job.get('started'):
        return {'ok':True,'skipped':True,'reason':'another Playbook refresh is active',
            'job_id':job.get('job_id')}
    await run_playbook_refresh_job(job['job_id'],actor_id=0)
    async with AsyncSessionLocal() as db:
        result=await playbook_refresh_job_status(db,job['job_id'])
    return {'ok':result['status']=='succeeded','job_id':job['job_id'],
        'status':result['status'],'phase':result['phase'],'error':result['error'],
        'cells':(result.get('result') or {}).get('cells',0)}


async def enqueue_scheduled_playbook_rebuild(reason):
    """Coalesce changed commercial facts into a durable, automatic rebuild."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(text('SELECT pg_advisory_xact_lock(61311, 2)'))
        queued=(await db.execute(select(PlaybookRefreshRun).where(
            PlaybookRefreshRun.actor_id==0,PlaybookRefreshRun.mode=='rebuild',
            PlaybookRefreshRun.status=='queued'
        ).order_by(PlaybookRefreshRun.started_at.desc()).limit(1).with_for_update())).scalar_one_or_none()
        if queued:
            result=_playbook_refresh_run_payload(queued)
            await db.rollback()
            return {**result,'started':False,'coalesced':True}
        now=_utcnow()
        row=PlaybookRefreshRun(job_id=str(uuid4()),actor_id=0,mode='rebuild',status='queued',
            phase=f'Queued automatic rebuild: {reason}',started_at=now,heartbeat_at=now)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return {**_playbook_refresh_run_payload(row),'started':True,'actor_id':0}


async def run_pending_scheduled_playbook_rebuild():
    """Run a queued rebuild only after other durable Playbook work has cleared."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        queued=(await db.execute(select(PlaybookRefreshRun).where(
            PlaybookRefreshRun.actor_id==0,PlaybookRefreshRun.mode=='rebuild',
            PlaybookRefreshRun.status=='queued'
        ).order_by(PlaybookRefreshRun.started_at.asc()).limit(1))).scalar_one_or_none()
        if queued is None:
            return {'ok':True,'skipped':True,'reason':'no_pending_rebuild'}
        active=(await db.execute(select(PlaybookRefreshRun).where(
            PlaybookRefreshRun.status.in_(('queued','running')),
            PlaybookRefreshRun.job_id!=queued.job_id
        ).with_for_update())).scalars().all()
        now=_utcnow()
        live=[]
        stale=[]
        for row in active:
            last_progress=row.heartbeat_at or row.started_at
            if now-last_progress>PLAYBOOK_REFRESH_STALE_AFTER:
                stale.append(row)
            else:
                live.append(row)
        for row in stale:
            row.status='interrupted'
            row.phase='Interrupted to release the queue for a prioritized Playbook rebuild'
            row.completed_at=now
            row.error='No heartbeat within the stale-job window; a queued rebuild took priority.'
        if stale:
            await db.commit()
        if live:
            return {'ok':True,'skipped':True,'reason':'another_playbook_job_is_active',
                'job_id':queued.job_id}
        job_id=queued.job_id
    await run_playbook_refresh_job(job_id,actor_id=0)
    async with AsyncSessionLocal() as db:
        result=await playbook_refresh_job_status(db,job_id)
    return {'ok':result['status']=='succeeded','job_id':job_id,'status':result['status'],
        'phase':result['phase'],'error':result['error'],
        'cells':(result.get('result') or {}).get('cells',0)}


async def run_playbook_rebuild(actor_id=0,progress=None):
    """Recalculate proposals from persisted catalogue facts without remote collection."""
    import asyncio
    from app.database import AsyncSessionLocal
    # Exact-page captures may have supplied a current price after the previous
    # catalogue sync. Link those persisted offers before rebuilding so an
    # operator-triggered rebuild does not require another retailer scrape.
    async with AsyncSessionLocal() as db:
        catalogue_sync=await sync_bestseller_catalogues(db,check_free_software=False)
        result=await asyncio.wait_for(refresh_playbooks(db,actor_id,progress=progress,catalogue_sync=catalogue_sync,maintain_live_offers=False),timeout=600)
        await db.commit()
    return {'cells':result['cells'],'complete_hardware':result['complete_hardware'],
        'ready_for_approval':result['ready_for_approval'],'catalogue_sync':catalogue_sync,
        'maintenance':result.get('maintenance'),
        'published':bool((result.get('maintenance') or {}).get('published'))}


def _decimal(value):
    try:
        amount=Decimal(str(value))
        return amount if amount.is_finite() and amount>=0 else None
    except Exception:
        return None


def _money(value):
    return str(Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_CEILING))


def _candidate_source_prices(_catalogue_price, source):
    """Use captured prices for planning; freshness remains visible for procurement."""
    current = _decimal(source.get('item_gbp')) if source else None
    verified = bool(source and source.get('fresh') and source.get('commercial_capture_verified')
        and current is not None and (current > 0 or source.get('evidence_kind')=='official_free_software'
            and current==0))
    item = current if current is not None and current > 0 else _decimal(_catalogue_price)
    if source and source.get('evidence_kind')=='official_free_software':
        item = current
    elif item == 0:
        item = None
    postage = _decimal(source.get('delivery_gbp')) if source and source.get('postage_verified') else None
    if postage is None:
        # Missing inbound delivery is a costing assumption, never proof that the
        # retailer ships free. Keep the source observation's proof flag intact.
        postage = Decimal('0.00')
    return item, postage, verified


def _apply_exact_source_core_engineering(role,listing,source,engineering):
    """Use only explicitly stated core fit facts from the exact product source."""
    if not isinstance(source,dict) or source.get('url')!=listing.url:
        return engineering
    values=_source_engineering_values(role,source.get('product_properties'),listing.title)
    core_fields={
        'cpu':{'socket','integrated_graphics'},
        'motherboard':{'socket','ram_type','form_factor','gpu_interfaces'},
        'ram':{'ram_type'},
        'gpu':{'gpu_interface'},
        'case':{'supported_form_factors'},
    }.get(role,set())
    selected={key:values[key] for key in core_fields if key in values}
    if not selected:
        return engineering
    current=dict(engineering or {})
    if current.get('reference_conflicts'):
        return current
    actor=str(current.get('reviewed_by') or '')
    conflicts={key:{'existing':current[key],'captured':value}
        for key,value in selected.items() if key in current and current[key]!=value}
    if conflicts and current.get('reviewed') is True and actor and not actor.startswith('automation:'):
        return {**current,'reviewed':False,'reference_conflicts':conflicts}
    return {**current,**selected,'reviewed':True,
        'source_url':listing.url,'reviewed_by':'automation:exact-source-core-facts',
        'reviewed_at':source.get('observed_at') or _utcnow().isoformat(),
        'source_fingerprint':fingerprint({'listing_id':listing.id,'url':listing.url,'facts':selected})}


def _current_suggested_supplier_source(part):
    """Promote a fresh exact stored offer into the draft's source snapshot.

    The matched offer is still only proposal evidence. Supplier approval and
    the normal publication checks remain required. Unknown inbound postage
    uses the owner's £0 costing fallback and stays labelled as an assumption.
    """
    if str(part.get('role') or '').startswith('os'):
        return None  # Windows stays with its original licence supplier and terms review.
    offer=part.get('suggested_supplier_offer') or {}
    url=str(offer.get('url') or '')
    from app.services.playbook_product_capture import supported_product_url
    if (not supported_product_url(url) or offer.get('commercial_capture_verified') is not True
            or offer.get('condition')!='new' or offer.get('listing_type')!='buy_it_now'
            or offer.get('stock_status') not in {'available','in_stock'}
            or not offer.get('stock_evidence')):
        return None
    try:
        observed=datetime.fromisoformat(str(offer['observed_at']).replace('Z','+00:00'))
        if observed.tzinfo is None:
            return None
        age=(datetime.now(timezone.utc)-observed.astimezone(timezone.utc)).total_seconds()
        item=Decimal(str(offer['item_gbp']))
        delivery=Decimal(str(offer['delivery_gbp'])) if offer.get('postage_verified') is True else None
    except (KeyError,ValueError,TypeError,ArithmeticError):
        return None
    if not 0<=age<=86400 or not item.is_finite() or item<=0 or delivery is not None and (
            not delivery.is_finite() or delivery<0):
        return None
    delivery_days=offer.get('delivery_working_days')
    delivery_source=offer.get('delivery_estimate_source')
    if delivery_days is None:
        from app.services.commerce_pricing import estimate_delivery_working_days
        delivery_days,default_source=estimate_delivery_working_days(
            str(offer.get('source') or 'retail'),None,offer.get('prime_eligible'))
        delivery_source=delivery_source or default_source
    source={
        'listing_db_id':offer.get('listing_db_id'),
        'listing_id':str(offer.get('listing_id') or part.get('listing_id') or ''),
        'observation_id':offer.get('observation_id'),
        'observed_at':observed.astimezone(timezone.utc).isoformat(),
        'url':url,'source':offer.get('source'),'condition':'new','listing_type':'buy_it_now',
        'item_gbp':str(item.quantize(Decimal('.01'))),
        'delivery_gbp':str(delivery.quantize(Decimal('.01'))) if delivery is not None else '0.00',
        'postage_verified':delivery is not None,
        'postage_assumption':None if delivery is not None else 'owner-approved-zero-fallback',
        'stock_status':'available','stock_evidence':offer.get('stock_evidence'),
        'active_listing':True,'commercial_capture_verified':True,
        'delivery_working_days':delivery_days,
        'delivery_estimate_source':delivery_source or (
            'owner_fallback' if delivery is None else 'captured_supplier_observation'),
        'prime_eligible':offer.get('prime_eligible'),'identity_source':'exact_supplier_observation',
        'fresh':True,'lifecycle_status':None,'lifecycle_updated_at':None,
    }
    source['fingerprint']=fingerprint(source)
    return source


def _supplier_fact_is_approvable(part,source):
    from app.services.commercial_quote_evidence import supplier_identity
    from app.services.commercial_readiness import same_listing_product
    from app.services.playbook_product_capture import supported_product_url
    url=source.get('url') or ''
    item=_decimal(source.get('item_gbp'));postage=_decimal(source.get('delivery_gbp'))
    if source.get('evidence_kind')=='official_free_software':
        from urllib.parse import urlsplit
        try:
            parsed=urlsplit(url)
        except ValueError:
            return False
        return bool(part.get('role')=='os_secondary' and parsed.scheme=='https'
            and parsed.hostname=='releases.ubuntu.com' and source.get('identity_source')=='official_free_software'
            and source.get('condition')=='new' and source.get('listing_type')=='software_download'
            and source.get('fresh') and source.get('commercial_capture_verified')
            and source.get('active_listing') and source.get('stock_status')=='available'
            and item==0 and postage==0 and source.get('delivery_working_days')==0)
    identity=supplier_identity(source.get('source'),url)
    accepted_identity=identity in {'amazon','overclockers'}
    if identity in {'royalcdkeys','gamers_outlet'}:
        # A digital-key offer needs an explicit operator review of the
        # supplier's licence type and UK resale/install terms before its cost
        # can enter a customer quote.
        accepted_identity=bool(part.get('role','').startswith('os') and source.get('licence_source_reviewed'))
    postage_is_usable=(source.get('postage_verified') is True and postage is not None
        or source.get('postage_assumption')=='owner-approved-zero-fallback' and postage==0)
    return bool(source.get('fresh') and source.get('commercial_capture_verified')
        and source.get('active_listing') and source.get('condition')=='new'
        and source.get('listing_type')=='buy_it_now' and source.get('stock_status')=='available'
        and source.get('stock_evidence') and postage_is_usable
        and item is not None and item>0 and supported_product_url(url)
        and accepted_identity and (url==part.get('source_url') or same_listing_product(url,part.get('source_url'))))


def _supplier_snapshot_matches_current(proposed, current):
    """Compare commercial facts, not incidental metadata from two capture paths.

    Proposal assembly may use the exact supplier observation while the review
    endpoint resolves the same listing through its retailer-page capture. The
    IDs and descriptive properties differ, but supplier evidence is still the
    same when its identity, price, condition, stock and chronology agree.
    """
    from urllib.parse import urlsplit
    from datetime import datetime
    def timestamp(value):
        try:
            parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
            return parsed if parsed.tzinfo is not None else None
        except (TypeError,ValueError):
            return None
    old_url=str(proposed.get('url') or '')
    new_url=str(current.get('url') or '')
    try:
        old=urlsplit(old_url);new=urlsplit(new_url)
    except ValueError:
        return False
    from app.services.commercial_readiness import same_listing_product
    same_url=(old_url==new_url or same_listing_product(old_url,new_url) or
        old.scheme=='https' and new.scheme=='https' and old.hostname==new.hostname
        and old.hostname in {'amazon.co.uk','www.amazon.co.uk'}
        and old.path.rstrip('/')==new.path.rstrip('/'))
    default_estimates={'vendor_default','prime_default','saved_vendor_default',
        'configured_vendor_default','owner_fallback'}
    old_default=proposed.get('delivery_estimate_source') in default_estimates
    new_default=current.get('delivery_estimate_source') in default_estimates
    arrival_matches=(old_default and new_default) or (
        not old_default and not new_default
        and proposed.get('delivery_working_days')==current.get('delivery_working_days'))
    old_price=_decimal(proposed.get('item_gbp'))
    new_price=_decimal(current.get('item_gbp'))
    old_time=timestamp(proposed.get('observed_at'))
    new_time=timestamp(current.get('observed_at'))
    if not (same_url and old_price is not None and old_price==new_price
            and proposed.get('condition')=='new' and current.get('condition')=='new'
            and proposed.get('active_listing') is True and current.get('active_listing') is True
            and proposed.get('stock_status')=='available' and current.get('stock_status')=='available'
            and arrival_matches
            and proposed.get('prime_eligible')==current.get('prime_eligible')
            and proposed.get('commercial_capture_verified') is True
            and current.get('commercial_capture_verified') is True
            and old_time is not None and new_time is not None and new_time>=old_time):
        return False
    # A previously verified non-zero postage amount cannot silently become a
    # zero fallback. Unknown postage may be refreshed to a recorded amount.
    if proposed.get('postage_verified') is True:
        old_delivery=_decimal(proposed.get('delivery_gbp'))
        new_delivery=_decimal(current.get('delivery_gbp'))
        zero_fallback=(old_delivery==0 and new_delivery==0
            and current.get('postage_assumption')=='owner-approved-zero-fallback')
        if old_delivery is None or (old_delivery!=new_delivery and not zero_fallback):
            return False
    return True


async def _persisted_supplier_snapshot_is_current(db, part, proposed, current):
    """Revalidate a newer exact matched offer when the catalogue preview lags it."""
    from app.models.gem_radar_observation import GemRadarListingObservation
    from app.services.commercial_quote_evidence import supplier_identity
    from app.services.playbook_product_capture import supported_product_url
    try:
        observation=await db.get(GemRadarListingObservation,int(proposed.get('observation_id')))
        observed=datetime.fromisoformat(str(proposed['observed_at']).replace('Z','+00:00'))
        item=Decimal(str(proposed['item_gbp']))
    except (TypeError,ValueError,KeyError,ArithmeticError):
        return False
    capture=(observation.commercial_source_evidence or {}) if observation else {}
    from app.services.commercial_source import search_listing_availability
    stock_status, stock_evidence, _ = search_listing_availability(
        capture.get('stock_status'), capture.get('stock_evidence'),
        listing_type=observation.listing_type if observation else 'unknown')
    url=str(proposed.get('url') or '')
    same_url=(capture.get('url')==url and url==part.get('source_url'))
    if not same_url:
        return False
    if not (observed.tzinfo is not None and 0<=(datetime.now(timezone.utc)-observed.astimezone(timezone.utc)).total_seconds()<=86400
            and observation.condition_normalised=='new' and observation.listing_type=='buy_it_now'
            and _decimal(capture.get('item_gbp'))==item
            and stock_status=='available' and stock_evidence
            and supported_product_url(url)
            and supplier_identity(observation.source,url)==supplier_identity(proposed.get('source'),url)):
        return False
    # Only a newer capture of this same supplier product can supersede the
    # selected observation. A newer catalogue observation from a different
    # retailer is not evidence that this independently captured offer changed.
    current_time=None
    try:
        current_time=datetime.fromisoformat(str(current.get('observed_at')).replace('Z','+00:00')) if current else None
    except ValueError:
        pass
    current_url=str((current or {}).get('url') or '')
    same_exact_product=current_url==url
    if not same_exact_product and current_url:
        from app.services.commercial_readiness import same_listing_product
        same_exact_product=same_listing_product(current_url,url)
    if (same_exact_product and current_time is not None and current_time.tzinfo is not None
            and current_time>observed):
        return _supplier_snapshot_matches_current(proposed,current)
    return True


def _model_tokens(value):
    return set(re.findall(r'[a-z]+\d+[a-z0-9]*|\d{3,5}[a-z0-9]*',value.casefold()))


def _verified_windows_licence_listing(listing):
    """Only recommend an exact per-device Windows licence listing for operator review."""
    raw=listing.raw_specs if isinstance(listing.raw_specs,dict) else {}
    royal=(raw.get('gamers_outlet') or raw.get('royalcdkeys') or {})
    capture=raw.get('playbook_product_capture') if isinstance(raw.get('playbook_product_capture'),dict) else {}
    properties=capture.get('product_properties') if isinstance(capture.get('product_properties'),dict) else {}
    title=capture.get('title') or listing.title
    expected_edition=re.search(r'\bwindows\s+11\s+(home|pro)\b',listing.title,re.I)
    captured_edition=re.search(r'\bwindows\s+11\s+(home|pro)\b',title,re.I)
    license_type=str(properties.get('License type (supplier listing)') or '').casefold()
    handle=royal.get('handle')
    captured_handle=capture.get('supplier_product_handle')
    from app.services.playbook_product_capture import supported_product_url
    return bool(royal.get('category')=='os' and royal.get('handle')
        and capture.get('status')=='captured' and capture.get('digital_product') is True
        and capture.get('licence_review_required') is True and capture.get('licence_resale_rights_verified') is False
        and capture.get('url')==listing.url and supported_product_url(listing.url)
        and handle==captured_handle and expected_edition and captured_edition
        and expected_edition.group(1).casefold()==captured_edition.group(1).casefold()
        and license_type in {'oem','retail'}
        and 'not guaranteed' not in str(properties.get('Key uniqueness (supplier claim)','')).casefold())


def _candidate_key(candidate, preferred):
    wanted=_model_tokens(preferred)
    present=_model_tokens(candidate['title'])
    suggested=candidate.get('suggested_supplier_offer') or {}
    price=_decimal(suggested.get('item_gbp',candidate.get('listing_price_gbp')))
    quantity=candidate.get('quantity') or 1
    if suggested and price is not None:
        price*=quantity
    postage=(_decimal(suggested.get('delivery_gbp',candidate.get('supplier_postage_gbp'))) or Decimal(0))
    if suggested:
        postage*=quantity
    # Range membership already carries the bestseller signal. For a draft,
    # favour the required identity and affordable parts within that range;
    # missing delivery/approval metadata must not force a costly alternative.
    stock=(suggested.get('stock_status') or (candidate.get('source_observation') or {}).get('stock_status'))
    stock_priority=1
    try:
        observed=datetime.fromisoformat(str(suggested.get('observed_at') or candidate.get('price_observed_at')).replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-observed.replace(tzinfo=observed.tzinfo or timezone.utc)).total_seconds()
        if 0<=age<=86400:
            stock_priority=0 if stock in {'available','in_stock'} else 2 if stock=='unavailable' else 1
    except (ValueError,TypeError):
        pass
    # Fresh exact stock takes precedence over model preference and old prices.
    # This lets the assembler move to a capable in-stock catalogue alternative
    # instead of repeatedly selecting a product the supplier has sold out of.
    # Availability here is only a selection hint; publication still rechecks
    # exact source, compatibility, media, economics and the configured limits.
    condition=suggested.get('condition') or (candidate.get('source_observation') or {}).get('condition')
    return (stock_priority, condition!='new', price is None, -len(wanted&present),
            price + postage
                if price is not None else Decimal('Infinity'),
            candidate.get('rank') or 10000, candidate['variant_id'])


async def _stock_replacements(db, offer, parent, candidates):
    """Explain active catalogue replacements for unavailable or inactive BOM parts."""
    managed=((parent.pricing_model or {}).get('managed_offers') or {}).get(offer['cell_id']) or {}
    previous={part.get('role'):part for part in managed.get('components',[]) if part.get('role')}
    if not previous:
        segment=(await db.execute(select(CuratedBuildSegment).where(
            CuratedBuildSegment.customer_type==offer['segment'],
            CuratedBuildSegment.budget_level==offer['tier']))).scalar_one_or_none()
        if segment:
            previous={role:{'role':role,'variant_id':variant_id}
                for role,variant_id in (segment.components or {}).items()}
    current={part['variant_id']:part for part in candidates}
    selected={part.get('role'):part for part in offer.get('components',[]) if part.get('role')}
    replacements=[]
    for role,old in previous.items():
        new=selected.get(role)
        if not new or old.get('variant_id')==new.get('variant_id'):
            continue
        old_variant=await db.get(CatalogueVariant,old.get('variant_id'))
        old_listing=await db.get(Listing,old_variant.listing_id) if old_variant else None
        unavailable=(current.get(old.get('variant_id')) or {}).get('source_observation') or {}
        if not unavailable and old_listing:
            unavailable=await source_preview(db,old_listing) or {}
        source_out=bool(unavailable.get('stock_status')=='unavailable' and unavailable.get('fresh'))
        listing_active=(getattr(old_listing.status,'value',old_listing.status)=='active') if old_listing else False
        variant_active=bool(old_variant and old_variant.status=='active')
        catalogue_out=not variant_active or not listing_active
        if not source_out and not catalogue_out:
            continue
        replacements.append({
            'role':role,
            'from_variant_id':old.get('variant_id'),
            'from_title':old.get('title') or (old_listing.title if old_listing else None),
            'from_source_url':old.get('source_url') or (old_listing.url if old_listing else None),
            'trigger':'supplier_out_of_stock' if source_out else 'catalogue_part_inactive',
            'from_stock_status':unavailable.get('stock_status'),
            'stock_evidence':unavailable.get('stock_evidence'),
            'from_catalogue_status':old_variant.status if old_variant else 'missing',
            'from_listing_status':getattr(old_listing.status,'value',old_listing.status) if old_listing else 'missing',
            'to_variant_id':new.get('variant_id'),
            'to_title':new.get('title'),
            'to_source_url':new.get('source_url'),
            'status':'proposed',
            'reason':('Fresh exact supplier evidence reports the live component out of stock.' if source_out else
                'The saved build component is no longer active in the shared catalogue.')+
                ' This active catalogue alternative was selected for full Playbook revalidation.'})
    if replacements:
        offer['availability_replacements']=replacements
        offer['revision_sha256']=fingerprint(commercial_revision_payload(offer) if mvp_mode(parent) else offer)
    return offer


def _plausible_role_candidate(role,title):
    """Reject exact-title category mismatches before a catalogue offer is assembled."""
    text=re.sub(r'[™®©]','',str(title or ''))
    if re.search(r'\bb[ -]grade\b|\bb[ -]stock\b|\brefurbished\b',text,re.I):
        return False
    if role in {'cpu', 'gpu', 'motherboard', 'ram', 'storage', 'storage_secondary', 'psu'}:
        # A complete system can mention the exact chip without being that part.
        from app.gem_radar.identity import is_full_system_listing
        if is_full_system_listing(text):
            return False
    if role == 'wireless_adapter':
        return bool(re.search(r'\b(?:wi[ -]?fi|wireless)\b', text, re.I)
            and bool(re.search(r'\b(?:adapter|card)\b', text, re.I)))
    if role=='cpu':
        if (re.search(r'\b\d+\s*GB\s+(?:RAM|DDR)',text,re.I)
                and re.search(r'\b\d+\s*(?:GB|TB)\s+(?:SSD|NVMe|HDD)',text,re.I)):
            return False
        # Exclude packaging and accessories even when a marketplace category
        # labels them as processors. Keep the recognized family and model in
        # the title so compatibility and benchmark lookups have a real identity.
        family=(r'\b(?:ryzen(?:sets)?\s+(?:ai\s+)?[3579]\s+\d{3,5}[a-z0-9]*'
            r'|ryzen\s+threadripper(?:\s+pro)?\s+\d{4,5}[a-z0-9]*'
            r'|threadripper(?:\s+pro)?\s+\d{4,5}[a-z0-9]*'
            r'|core\s+ultra\s+[3579]\s+(?:processor\s+)?\d{3,5}[a-z0-9]*(?:\s+plus)?'
            r'|core\s+i[3579]\s*-?\s*\d{4,5}[a-z0-9]*'
            r'|xeon\s+[a-z0-9-]+|pentium\s+[a-z0-9-]+|celeron\s+[a-z0-9-]+)\b')
        return bool(re.search(family,text,re.I)) and not re.search(
            r'\b(?:packaging|clamshell|holder|protector|tray\s+only|sticker|decal|mounting\s+bracket|bundle|motherboard|laptop|notebook|mini[- ]?pc)\b|\b[2-9]\d*\s+units\b',text,re.I)
    if role=='motherboard':
        if re.search(r'\bfit for\b',text,re.I): return False
        board=bool(re.search(r'\b(?:motherboard|mother\s+board|mainboard)\b',text,re.I)
            or (re.search(r'\b(?:b|x|a|z|h)\d{3,4}[a-z]?\b',text,re.I)
                and re.search(r'\b(?:am[45]|lga\s*\d{4,5}|atx|micro[- ]?atx|mini[- ]?itx)\b',text,re.I)))
        return board and not re.search(r'\b(?:socket\s+protector|tray\s+only|replacement\s+socket|cover\s+only|repair\s+kit)\b',text,re.I)
    if role=='ram':
        if re.search(r'\b(?:processor|motherboard|mainboard)\b',text,re.I):
            return False
        return bool(re.search(r'\bddr[345]\b',text,re.I)
            and re.search(r'\b\d+\s*gb\b|\b\d+\s*x\s*\d+\s*gb\b',text,re.I)
            and re.search(r'\b(?:ram|memory|dimm|rdimm|sodimm)\b|\b(?:single|dual|quad|octa)[ -]channel\s+kit\b',text,re.I))
    if role in {'storage','storage_secondary'}:
        return bool(re.search(r'\b(?:ssd|nvme|hdd|hard\s+drive|solid\s+state\s+drive)\b',text,re.I)
            and not re.search(r'\b(?:heatsink|heat\s+sink|cover\s+only|enclosure|adapter|docking\s+station|hub|case\s+only)\b',text,re.I))
    if role=='gpu':
        identity=(r'\b(?:geforce\s+)?(?:rtx|gtx)\s*(?:\d{3,4}|a\s*\d{3,4})\b'
            r'|\b(?:radeon\s+)?rx\s*\d{4}\b|\b(?:radeon\s+)?(?:ai\s+pro|pro)\s+r?\d{3,5}\b'
            r'|\b(?:intel\s+)?arc\s+[ab]\d{3,4}\b|\bquadro\s+(?:rtx\s*)?[a-z0-9-]+\b')
        return bool(re.search(identity,text,re.I)) and not re.search(
            r'\b(?:backplate|riser|bracket|adapter|water\s*block|replacement\s+fan|fan\s+only|no\s+gpu|decoration|collectible|replica|dummy|laptop|notebook|erazer|chassis|pc\s+case)\b',text,re.I)
    if role=='psu':
        # Marketplace categories sometimes place low-voltage adapters in PC
        # power supplies. Require a computer PSU form factor and rated wattage.
        pc_supply=bool(re.search(r'\b(?:atx|sfx|tfx|flex\s+atx|pc\s+power\s+supply|computer\s+power\s+supply|psu)\b',text,re.I))
        wattage=bool(re.search(r'\b\d{3,4}\s*w\b|\b(?:rm|cx|hx|ax|sf|tx|vs)\d{3,4}[a-z]?\b',text,re.I))
        accessory=bool(re.search(r'\b(?:led\s+strip|probe\s+signal\s+lamp|signal\s+lamp|universal\s+regulated\s+switching\s+adapter|transformers?|dc\s+adapter|keyboard|recliner)\b',text,re.I))
        return pc_supply and wattage and not accessory
    if role=='cooling':
        return bool(re.search(r'\b(?:cpu\s+cooler|air\s+cooler|liquid\s+cooler|aio\s+(?:liquid\s+)?cooler|cpu\s+heatsink|cpu\s+water\s+cooling)\b',text,re.I))
    if role=='case':
        if re.search(r'\b(?:dust\s+filters?|fan\s+(?:dust\s+)?filters?|filter\s+(?:cover|mesh)|replacement\s+(?:panel|glass)|case\s+fans?|screw\s+kit|pc\s+case\s+(?:feet|stand|cover))\b',text,re.I):
            return False
        if re.search(r'\b(?:raspberry\s*pi|pi\s*5|hailo|mini\s*pc\s+case|vertical\s+gpu\s+kit|riser\s+kit|test\s+bench|open\s+(?:case|chassis))\b',text,re.I):
            return False
        from app.services.playbook_component_facts import manufacturer_facts
        known_case=(manufacturer_facts('case',text).get('supported_form_factors')
            and not re.search(r'\b(?:panels?|brackets?|cables?|covers?|mounts?|stands?|fans?)\b',text,re.I))
        return bool(re.search(r'\b(?:pc\s+case|computer\s+case|mid[- ]tower|mini[- ]tower|full[- ]tower|pc\s+chassis|computer\s+chassis|gaming\s+chassis)\b',text,re.I)
            or known_case)
    return True


def _upgrade_quality_verified(role,base,target,metric='overall_score'):
    if role in {'cpu','gpu'}:
        before=base.get('performance_evidence') or {};after=target.get('performance_evidence') or {}
        return bool(before.get(metric) is not None and after.get(metric) is not None
            and before.get('benchmark_source') and before.get('benchmark_source')==after.get('benchmark_source')
            and (before.get('confidence_score') or 0)>=0.8 and (after.get('confidence_score') or 0)>=0.8
            and after[metric]>before[metric])
    before=base.get('engineering') or {};after=target.get('engineering') or {}
    if before.get('reviewed') is not True or after.get('reviewed') is not True:return False
    if role in {'ram','storage','storage_secondary'}:
        from app.services.curated_build_policy import _capacity_gb
        old=_capacity_gb(base.get('title'));new=_capacity_gb(target.get('title'))
        interface='ram_type' if role=='ram' else 'storage_interface'
        if not (old and new and new>old and before.get(interface)
                and before.get(interface)==after.get(interface)):return False
        if role=='ram':
            for requirement in ('ecc','rdimm'):
                required=bool(re.search(r'\b'+requirement+r'\b',base.get('title',''),re.I))
                if requirement=='ecc' and re.search(r'\bnon[ -]?ecc\b',base.get('title',''),re.I):required=False
                if required and (
                        not re.search(r'\b'+requirement+r'\b',target.get('title',''),re.I)
                        or requirement=='ecc' and re.search(r'\bnon[ -]?ecc\b',target.get('title',''),re.I)):
                    return False
        return True
    fields={'psu':('wattage',),'cooling':('cooling_capacity_w',),
        'motherboard':('ram_slots','m2_slots')}.get(role)
    if fields is None:return False
    values=[(_decimal(before.get(key)),_decimal(after.get(key))) for key in fields]
    return all(a is not None and b is not None and b>=a for a,b in values) and any(b>a for a,b in values)


def _distinct_storage_devices(parts):
    # Each storage slot represents a separately costed unit. Two units may use
    # the same SKU/listing; they must occupy their own catalogue slot variants.
    drives=[part.get('variant_id') for role,part in parts.items() if role in {'storage','storage_secondary'}]
    return len(drives)<2 or all(drives) and len(set(drives))==len(drives)


def _publication_upgrade_rows(offer):
    """Translate only evidence-backed, compatible generated upsells to the customer contract."""
    selected={part['role']:part for part in offer.get('components',[])}
    result=[]
    for item in offer.get('upsells',[]):
        role=item.get('role');part=item.get('component') or {};base=selected.get(role)
        source=part.get('source_observation') or {}
        if (role=='case' or role.startswith('os') or base is None or not item.get('compatibility_verified')
                or not item.get('quality_verified')
                or not _upgrade_quality_verified(role,base,part,item.get('performance_metric') or 'overall_score')
                or not part.get('catalogue_approved') or not _supplier_fact_is_approvable(part,source)
                or not part.get('slot_id') or not part.get('variant_id')):
            continue
        if not _distinct_storage_devices({**selected,role:part}):continue
        if role in {'cpu','gpu'}:
            metric=item.get('performance_metric') or 'overall_score'
            base_evidence=base.get('performance_evidence') or {}
            upgrade_evidence=part.get('performance_evidence') or {}
            if (not base_evidence.get(metric) or not upgrade_evidence.get(metric)
                    or base_evidence.get('benchmark_source')!=upgrade_evidence.get('benchmark_source')
                    or (base_evidence.get('confidence_score') or 0)<0.8
                    or (upgrade_evidence.get('confidence_score') or 0)<0.8
                    or upgrade_evidence[metric]<=base_evidence[metric]):
                continue
        base_price=_decimal(base.get('listing_price_gbp'))
        target_price=_decimal(part.get('listing_price_gbp'))
        if base_price is None or target_price is None or target_price<=base_price:
            continue
        result.append({
            'candidate_index':len(result),'category':role,'from_sku':base['title'],'to_sku':part['title'],
            'slot_id':int(part['slot_id']),'target_variant_id':int(part['variant_id']),
            'target_title':part['title'],'target_display_price':float(part.get('display_price') or target_price),
            'playbook_service':True,
        })
    return result


def required_roles(definition):
    integrated='integrated' in definition.get('components',{}).get('gpu','').casefold()
    return tuple(role for role in HARDWARE_ROLES if role!='gpu' or not integrated)


def required_parts(definition):
    components=definition.get('components',{})
    storage_items=[item.strip() for item in str(components.get('storage') or '').split('+') if item.strip()]
    os_spec=str(components.get('os') or '')
    roles=list(required_roles(definition))
    if len(storage_items)>1:
        roles.append('storage_secondary')
    if os_spec:
        roles.append('os')
        if ('ubuntu' in os_spec.casefold() and 'windows' in os_spec.casefold()
                and not re.search(r'\b(?:vm|option)\b',os_spec,re.I)):
            roles.append('os_secondary')
    return tuple(roles)


def required_hardware_parts(definition):
    return tuple(role for role in required_parts(definition) if not role.startswith('os'))


def unmodelled_required_components(definition):
    """Return authored BOM shapes beyond the service's explicit multi-slot model."""
    components=definition.get('components',{})
    blockers=[]
    storage_items=[item.strip() for item in str(components.get('storage') or '').split('+') if item.strip()]
    if len(storage_items)>2:
        blockers.append('Automatic BOM assembly currently supports at most two authored storage devices')
    return blockers


def withhold_incomplete_bom_prices(delivery,missing_components):
    """Never quote one-slot costs as a price for an authored multi-part BOM."""
    if not missing_components:
        return delivery
    reason='The complete authored build is not represented: '+'; '.join(missing_components)
    for offer in delivery.values():
        offer.update(available=False,recommended_price_gbp=None,estimated_profit_gbp=None,
            difference_from_standard_gbp=None,reason=reason,recommended_component_variant_ids=[],
            profit_floor_gbp=None,estimated_total_cost_gbp=None,net_revenue_gbp=None,vat_gbp=None)
    return delivery


def _planning_integrated_graphics(candidate):
    if 'integrated_graphics' in (candidate.get('manufacturer_facts') or {}):
        return candidate['manufacturer_facts']['integrated_graphics'] is True
    if (candidate.get('engineering') or {}).get('integrated_graphics') is True:
        return True
    title = candidate.get('title') or ''
    # Explicit source wording is enough to retain a planning candidate; it does
    # not turn unreviewed engineering into verified compatibility.
    return bool(re.search(r'\bintegrated\s+(?:radeon\s+)?graphics\b|\bradeon graphics (?:included|built[- ]in)\b', title, re.I))


def _planning_socket(candidate):
    if re.search(r'\b79\d{2}wx\b',candidate.get('title') or '',re.I):
        return 'str5'
    socket = (candidate.get('manufacturer_facts') or {}).get('socket') or _infer_cpu_socket(candidate.get('title') or '')
    if socket:
        return socket
    socket = (candidate.get('planning_engineering') or candidate.get('engineering') or {}).get('socket')
    if socket:
        return _infer_cpu_socket(str(socket)) or re.sub(r'[^a-z0-9]', '', str(socket).casefold())
    properties = (candidate.get('source_observation') or {}).get('product_properties') or {}
    labelled = ' '.join(str(value) for key,value in properties.items()
        if re.sub(r'[^a-z]', '', key.casefold()) in {'cpusocket','cpusockettype','sockettype','processorsocket'})
    return _infer_cpu_socket(labelled) or _infer_cpu_socket(candidate.get('title') or '')


def _candidate_capacity(candidate):
    from app.services.curated_build_policy import _capacity_gb
    return (_capacity_gb(candidate.get('title') or '') or 0)*(candidate.get('quantity') or 1)


def _ram_quantity(candidate, minimum):
    """Represent separately purchased identical server DIMMs explicitly."""
    capacity=_candidate_capacity(candidate)
    if (not capacity or capacity>=minimum or not re.search(r'\bRDIMM\b',candidate['title'],re.I)
            or not re.search(r'\b1\s*x\s*\d+\s*GB\b',candidate['title'],re.I)
            or minimum%capacity or minimum/capacity>8):
        return candidate
    quantity=int(minimum/capacity)
    result=deepcopy(candidate)
    result.update(quantity=quantity,unit_price_gbp=candidate.get('listing_price_gbp'))
    for key in ('listing_price_gbp','supplier_postage_gbp','landed_gbp'):
        value=_decimal(candidate.get(key))
        result[key]=_money(value*quantity) if value is not None else None
    if result.get('suggested_supplier_offer'):
        supplier=result['suggested_supplier_offer']
        supplier.update(quantity=quantity,unit_item_gbp=supplier.get('item_gbp'))
    result['engineering']={**(result.get('engineering') or {}),'ram_modules':quantity}
    result['planning_engineering']={**(result.get('planning_engineering') or {}),'ram_modules':quantity}
    return result


def _planning_vram(candidate):
    if (candidate.get('manufacturer_facts') or {}).get('vram_gb'):
        return candidate['manufacturer_facts']['vram_gb']
    from app.services.curated_build_policy import _capacity_gb
    properties = (candidate.get('source_observation') or {}).get('product_properties') or {}
    for key,value in properties.items():
        if re.sub(r'[^a-z]', '', key.casefold()) in {'graphicsramsize','graphicscardram','graphicsram','videomemorysize'}:
            capacity = _capacity_gb(str(value))
            if capacity is not None:
                return capacity
    title = candidate.get('title') or ''
    short = re.search(r'\b(\d{1,2})G\b', title, re.I)
    return _capacity_gb(title) or (float(short.group(1)) if short else None)


def _selected_fit_passes(checks, selected_roles, complete):
    # Once both sides of a relationship have been selected, unrelated later
    # parts cannot supply its absent evidence. Prune that branch immediately.
    return not any(check['severity']=='error' or check['severity']=='unknown' and
        (complete or bool(check.get('affected')) and set(check['affected']).issubset(selected_roles))
        for check in checks)


def assemble_components(definition, candidates, *, delivery_mode=None, performance_baselines=None,
        fit_check=None, search_limit=100000):
    """Assemble a draft, searching reviewed alternatives when a fit predicate is supplied."""
    pools={role:[] for role in (*HARDWARE_ROLES,'storage_secondary','os','os_secondary')}
    storage_items=[item.strip() for item in str(definition.get('components',{}).get('storage') or '').split('+') if item.strip()]
    for candidate in candidates:
        if candidate.get('catalogue_approved') is False and not candidate.get('draft_software_candidate'):
            continue
        role=candidate['role']
        if not _plausible_role_candidate(role,candidate.get('title')):
            continue
        if delivery_mode is not None and not (candidate.get('delivery_eligibility') or {}).get(delivery_mode,False):
            continue
        constraints=definition.get('constraints') or {}
        # Reconstructed capability profiles can constrain architecture more
        # tightly than legacy benchmark tiers. Unknown facts cannot satisfy it.
        if role in {'cpu','motherboard'} and (socket:=(constraints.get('cpu') or {}).get('socket')):
            required_socket=_infer_cpu_socket(socket) or re.sub(r'[^a-z0-9]','',socket.casefold())
            if _planning_socket(candidate)!=required_socket:
                continue
        if role=='ram' and (memory:=constraints.get('memory')):
            if memory.get('module_type')=='ECC RDIMM' and not re.search(r'\b(?:RDIMM|registered)\b',candidate['title'],re.I):
                continue
            if memory.get('module_type')=='UDIMM' and re.search(r'\b(?:RDIMM|registered|SO[- ]?DIMM)\b',candidate['title'],re.I):
                continue
        if role in pools:
            pools[role].append(candidate)
    def choices(role,chosen):
        preferred=(storage_items[1] if role=='storage_secondary' and len(storage_items)>1 else
            str(definition.get('components',{}).get('os') or '').split('+',1)[0].strip()
            if role=='os' else
            'Ubuntu 24.04 LTS' if role=='os_secondary' else
            definition.get('components',{}).get(role,''))
        values=sorted(pools[role],key=lambda row:_candidate_key(row,preferred))
        if role in HARDWARE_ROLES:
            def supplier_condition(row):
                offer=row.get('suggested_supplier_offer') or {}
                source=row.get('source_observation') or {}
                return offer.get('condition') or source.get('condition')
            # Do not select a used offer when the exact catalogue role has a
            # current new-condition supplier alternative.
            new_offers=[row for row in values if supplier_condition(row)=='new']
            if new_offers:
                values=new_offers
        if role=='os':
            os_requirement=str(definition.get('components',{}).get('os') or '')
            edition='pro' if re.search(r'\bpro\b',os_requirement,re.I) else 'home'
            values=[row for row in values if 'windows 11' in row['title'].casefold()
                and re.search(r'\b'+edition+r'\b',row['title'],re.I)]
        if role=='os_secondary':
            values=[row for row in values if 'ubuntu' in row['title'].casefold()
                and '24.04' in row['title']]
        if role in {'cpu','gpu'} and preferred:
            normalise=normalise_cpu if role=='cpu' else normalise_gpu
            target_model=normalise(preferred)
            exact=[row for row in values if normalise(row['title'])==target_model]
            baseline=(performance_baselines or {}).get(role)
            metric=baseline.get('metric') if baseline else None
            target=baseline.get(metric) if baseline and metric else None
            substitutes=[]
            if target is not None and baseline.get('benchmark_source'):
                substitutes=[row for row in values if (evidence:=row.get('performance_evidence'))
                    and normalise(row['title'])!=target_model
                    and evidence.get('benchmark_source')==baseline['benchmark_source']
                    and (evidence.get('confidence_score') or 0)>=0.8
                    and evidence.get(metric) is not None and evidence[metric]>=target]
                substitutes.sort(key=lambda row:(row['performance_evidence'][metric]-target,
                    *_candidate_key(row,preferred)))
            if exact:
                # An unavailable exact model must not hide a demonstrably
                # capable, fresh in-stock alternative. Unknown or stale stock
                # is never promoted by this replacement path.
                available_substitutes=[row for row in substitutes if _candidate_key(row,preferred)[0]==0]
                values=(sorted([*exact,*available_substitutes],key=lambda row:_candidate_key(row,preferred))
                    if available_substitutes and not any(_candidate_key(row,preferred)[0]==0 for row in exact)
                    else exact)
            else:
                values=substitutes
                if 'gpu' not in required_roles(definition):
                    values=[row for row in values if _planning_integrated_graphics(row)]
            if role=='gpu':
                from app.services.curated_build_policy import _capacity_gb
                minimum_vram=_capacity_gb(preferred)
                if minimum_vram:
                    values=[row for row in values if (_planning_vram(row) or 0)>=minimum_vram]
        if role=='cpu' and 'gpu' not in required_roles(definition):
            values=[row for row in values if _planning_integrated_graphics(row)]
        if role in {'ram','storage'}:
            from app.services.curated_build_policy import _capacity_gb
            minimum=_capacity_gb(preferred)
            if minimum:
                if role=='ram':
                    values=[_ram_quantity(row,minimum) for row in values]
                values=[row for row in values if _candidate_capacity(row)>=minimum]
        if role=='ram':
            server_memory=bool(re.search(r'\b(?:threadripper|rdimm)\b',
                str(definition.get('components',{}).get('cpu',''))+' '+str(preferred),re.I))
            values=[row for row in values if bool(re.search(r'\bRDIMM\b|registered',row['title'],re.I))==server_memory]
            if minimum:
                # Capacity is a hard authored requirement: choose the smallest
                # kit that satisfies it first, then use fresh stock and cost
                # to break ties. Letting stock priority outrank capacity made
                # an in-stock 128 GB kit displace a stale 32 GB fit in every
                # ordinary desktop build, inflating its BOM by thousands.
                values.sort(key=lambda row:(_candidate_capacity(row)-minimum,*_candidate_key(row,preferred)))
            # Capacity alone cannot replace the authored platform architecture.
            board_generation=_extract_ram_type((chosen.get('motherboard') or {}).get('title',''))
            family=re.search(r'\b(?:LPDDR[345]X?|DDR[345])\b',board_generation or str(preferred),re.I)
            if family:
                values=[row for row in values if re.search(r'\b'+re.escape(family.group())+r'\b',row['title'],re.I)]
            if re.search(r'\b(?:SO[- ]?DIMM|SODIMM)\b',str(preferred),re.I):
                values=[row for row in values if re.search(r'\bSO[- ]?DIMM\b',row['title'],re.I)]
            elif family and not family.group().upper().startswith('LPDDR'):
                values=[row for row in values if not re.search(r'\bSO[- ]?DIMM\b',row['title'],re.I)]
        if role in {'storage','storage_secondary'}:
            # Base build storage is internal; USB/portable offers are not a
            # substitute even when their headline capacity is larger.
            values=[row for row in values if not re.search(r'\b(?:external|portable|USB)\b',row['title'],re.I)]
            values=[row for row in values if re.search(r'\bnvme\b|\bsata\b|\bm\.2\b|\bpcie\b',row['title'],re.I)]
            interface=re.search(r'\b(?:NVMe|SATA)\b',str(preferred),re.I)
            if interface:
                values=[row for row in values if re.search(r'\b'+interface.group()+r'\b',row['title'],re.I)]
            if role=='storage' and minimum:
                values.sort(key=lambda row:((_capacity_gb(row['title']) or minimum)-minimum,
                                            *_candidate_key(row,preferred)))
        if role=='storage_secondary':
            from app.services.curated_build_policy import _capacity_gb
            minimum=_capacity_gb(preferred)
            if minimum:
                values=[row for row in values if (_capacity_gb(row['title']) or 0)>=minimum]
            primary=chosen.get('storage')
            if primary:
                values=[row for row in values if row['variant_id']!=primary['variant_id']
                    and (not row.get('listing_id') or row['listing_id']!=primary.get('listing_id'))]
        if role=='psu':
            requirement = re.search(r'\b(\d{3,4})\s*w\b', preferred, re.I)
            if requirement:
                minimum_watts = int(requirement.group(1))
                def watts(row):
                    labelled = (row.get('engineering') or {}).get('wattage')
                    match = re.search(r'\b(\d{3,4})\s*w\b', row['title'], re.I)
                    try: return int(labelled) if labelled is not None else int(match.group(1)) if match else 0
                    except (ValueError, TypeError): return 0
                values = [row for row in values if watts(row) >= minimum_watts]
        if role=='cooling' and chosen.get('cpu') and _planning_socket(chosen['cpu'])=='str5':
            values=[row for row in values if re.search(r'\b(?:s?tr5|sp6)\b',row['title'],re.I)]
        elif role=='cooling' and chosen.get('cpu'):
            socket=_planning_socket(chosen['cpu'])
            values=[row for row in values if not (row.get('planning_engineering') or {}).get('supported_sockets')
                or socket in row['planning_engineering']['supported_sockets']]
        if role=='case' and chosen.get('cpu') and _planning_socket(chosen['cpu'])=='str5':
            # This authored EEB workstation cannot use a cheap desktop chassis.
            from app.services.playbook_requirement_catalogue import matches_requirement
            def verified_eeb_case(row):
                facts={**(row.get('engineering') or {}),**(row.get('manufacturer_facts') or {})}
                return facts.get('reviewed') is True and any(
                    re.sub(r'[^a-z]','',str(factor).casefold()) in {'ssieeb','eeb'}
                    for factor in facts.get('supported_form_factors',[]))
            values=[row for row in values if matches_requirement('case',row['title'],preferred) or verified_eeb_case(row)]
        if role=='motherboard' and chosen.get('cpu'):
            socket=_infer_cpu_socket(chosen['cpu']['title'])
            if socket:
                values=[row for row in values if _planning_socket(row)==socket.casefold()
                    or (_planning_socket(row) is None and _model_tokens(preferred)
                        and _model_tokens(preferred).issubset(_model_tokens(row['title'])))]
        # Amazon bestsellers define the product pool. Keep platform,
        # performance and capacity requirements above, then let the
        # compatibility checks validate a different selected board.
        if role=='ram' and chosen.get('motherboard'):
            generation=_extract_ram_type(chosen['motherboard']['title'])
            if generation:
                values=[row for row in values if _extract_ram_type(row['title'])==generation]
        if role=='case':
            from app.services.playbook_planning_checks import case_conflicts
            values=[row for row in values if not case_conflicts(chosen,row)]
            values.sort(key=lambda row:(not bool(row.get('manufacturer_facts')),*_candidate_key(row,preferred)))
        if role=='case' and chosen.get('motherboard'):
            board=chosen['motherboard']
            board_text=board['title'].casefold()
            board_factor=str((board.get('engineering') or {}).get('form_factor') or '')
            full_atx=(board_factor.upper()=='ATX' or bool(re.search(r'\batx\b',board_text)
                and not re.search(r'micro[ -]?atx|\bmatx\b|mini[ -]?itx',board_text)))
            if full_atx:
                values=[row for row in values if not re.search(r'\ba3\b|\bmini[ -]?itx\b',row['title'],re.I)
                    and not ((row.get('engineering') or {}).get('form_factor') in {'micro_atx','mini_itx'})]
        return values
    chosen={};blockers=[]
    roles=required_parts(definition)
    for role in roles:
        values=choices(role,chosen)
        if values:chosen[role]=deepcopy(values[0])
        else:
            blockers.append(f'No {role} catalogue candidate meets this cell requirement or verified performance/compatibility constraints'
                if pools[role] else f'Automatic sourcing needs a matching {role} catalogue product')
    if fit_check is None:
        return chosen,blockers
    # Only core compatibility roles need reviewed engineering input for the
    # publication gate. Storage, cooling and PSU measurement gaps stay visible
    # as workshop work and must not exhaust the compatible-candidate search.
    core_roles={'cpu','motherboard','ram','gpu'}
    if any(not any((row.get('engineering') or {}).get('reviewed') is True for row in pools[role])
            for role in roles if role in core_roles):
        return chosen,blockers
    # Check motherboard-to-case fit before walking combinations of storage,
    # PSU, cooling and software, which do not change the Playbook gate.
    search_roles=tuple(role for role in ('cpu','motherboard','ram','gpu','case') if role in roles)+tuple(
        role for role in roles if role not in core_roles and role!='case')
    remaining=search_limit
    def search(index,selected):
        nonlocal remaining
        if index==len(search_roles):return deepcopy(selected) if fit_check(selected,True) else None
        role=search_roles[index]
        for value in choices(role,selected):
            if role in core_roles and (value.get('engineering') or {}).get('reviewed') is not True:
                continue
            if remaining<=0:return None
            remaining-=1
            selected[role]=value
            if fit_check(selected,False):
                result=search(index+1,selected)
                if result is not None:return result
            selected.pop(role,None)
        return None
    compatible=search(0,{})
    if compatible is not None:return compatible,[]
    blockers.append('Compatible catalogue search reached its bounded search limit' if remaining<=0
        else 'No fully verified compatible catalogue combination meets this cell requirements')
    return chosen,blockers


def automatic_policy(parts, definition, parent, settings, *, definition_sha256_override=None,
        include_market=True, version=1):
    from app.schemas.commercial_quote import CellCommercialPolicy
    from app.services.commercial_quote_evidence import definition_hash
    landed=sum((_decimal(part.get('landed_gbp')) or Decimal(0) for part in parts.values()),Decimal(0))
    floor,margin=APPROVED_TIER_FLOORS[definition['tier']]
    floor=Decimal(floor)
    target=max(floor,_decimal((parent.profit_strategy or {}).get('target_profit_gbp')) or floor)
    courier=_decimal(getattr(settings,'opportunity_delivery_fallback_gbp',None))
    if courier is None:
        courier = Decimal('20.00')
    if not parts:
        return None
    source_days=max((days for part in parts.values()
        if isinstance(days:=(part.get('source_observation') or {}).get('delivery_working_days'),int)
        and not isinstance(days,bool) and days>=0),default=0)
    modes={}
    for mode in MODES:
        target_days=getattr(settings,{'fast_track':'speedy_curated_custom_days','standard':'standard_curated_custom_days','flexible':'standard_curated_custom_days'}[mode],None)
        if not isinstance(target_days,int) or isinstance(target_days,bool) or target_days<1:
            return None
        modes[mode]={'costs':{'build_labour':'0.00','packaging':'6.00','outbound_delivery':_money(courier),
            'insurance':'15.00','payment_fixed':'0.20','expected_failure_cost':'0.00',
            'allocated_overhead':_money(landed*Decimal('.10')),'other_variable_costs':'0.00'},
            'minimum_contribution_gbp':str(floor if mode=='flexible' else target),
            'minimum_margin_fraction':margin,'premium_gbp':str(getattr(settings,'speedy_delivery_price_gbp',0) if mode=='fast_track' else 0),
            'workshop_working_days':max(1,target_days-source_days-1),'courier_working_days':1,
            'maximum_delivery_working_days':None if mode=='flexible' else target_days}
    mappings={part['slot_id']:(part['variant_id'],f"variant:{part['variant_id']}") for role,part in parts.items() if role!='case'}
    case=parts.get('case') or {}
    case_id=case.get('case_catalogue_id')
    case_key=f'case:{case_id}' if case_id else f"variant:{case.get('variant_id')}"
    from app.services.playbook_market import approved_market
    market = approved_market(parent, definition, parts) if include_market else None
    market_policy = {key: market.get(key) for key in ('condition','sold_median_gbp','sold_p75_gbp',
        'sold_sample_size','minimum_sold_sample_size','cap_method','observed_at',
        'evidence_source','evidence_ref')} if market else None
    return CellCommercialPolicy.model_validate({'version':version,
        'definition_sha256':definition_sha256_override or definition_hash(definition),
        'required_part_keys':[value[1] for value in mappings.values()]+([case_key] if case else []),
        'part_quantities':{f"variant:{part['variant_id']}":part['quantity']
            for role,part in parts.items() if role!='case' and (part.get('quantity') or 1)>1},
        'condition':'new','vat_rate':'0','payment_rate':'.0315','warranty_rate':'.05','returns_rate':'.02',
        'market':market_policy,'market_tolerance_fraction':'0','modes':modes,'checkout_enabled':False,
        'checkout_slot_parts':mappings,'checkout_case':(case_id,case_key) if case_id else None,
        'enabled_modes':list(MODES)})


def component_delivery_eligibility(part, policy):
    from app.services.playbook_commercial_quote import supplier_meets_delivery_commitment
    # Use the same fresh, exact new supplier capture that will be promoted into
    # the draft. The catalogue page can still describe an older/used offer for
    # this product; letting that stale snapshot decide delivery eligibility can
    # incorrectly discard the authored CPU (or another exact part) during the
    # Standard-mode reassembly.
    source=_current_suggested_supplier_source(part) or part.get('source_observation') or {}
    current=source.get('fresh') and source.get('active_listing') and source.get('stock_status')=='available'
    days,_=_supplier_arrival_estimate(part,source)
    return {mode:bool(current and supplier_meets_delivery_commitment(days,rule))
        for mode,rule in policy.modes.items()}


def _supplier_arrival_estimate(part, source=None):
    """Use captured arrival days or the saved vendor default, never a postage value."""
    source=source if isinstance(source,dict) else part.get('source_observation') or {}
    days=source.get('delivery_working_days')
    if isinstance(days,int) and not isinstance(days,bool) and days>=0:
        return days,source.get('delivery_estimate_source') or 'captured listing estimate'
    suggested=part.get('suggested_supplier_offer') or {}
    url=source.get('url') or suggested.get('url') or part.get('source_url') or ''
    vendor=source.get('source') or suggested.get('source') or ''
    # Prefer the marketplace host to a merchant/seller label from the page.
    # For example, an Amazon offer may name the third-party seller as source.
    try:
        host=(urlsplit(str(url)).hostname or '').casefold()
    except ValueError:
        host=''
    if host=='amazon.co.uk' or host.endswith('.amazon.co.uk'):
        vendor='Amazon UK'
    elif host=='ebay.co.uk' or host.endswith('.ebay.co.uk') or host=='ebay.com' or host.endswith('.ebay.com'):
        vendor='eBay'
    elif host=='vinted.co.uk' or host.endswith('.vinted.co.uk'):
        vendor='Vinted'
    if not vendor and url:
        vendor=host
    if not vendor:
        # The normal retail fallback is three working days. A missing vendor
        # identity cannot prove delivery eligibility, but it should not leave
        # an empty ETA or be confused with a postage charge.
        return 3,'general_supplier_default'
    prime=source.get('prime_eligible')
    if prime is None:
        prime=suggested.get('prime_eligible')
    from app.services.commerce_pricing import estimate_delivery_working_days
    return estimate_delivery_working_days(str(vendor),None,prime)


def _store_supplier_arrival_default(part):
    """Add the applicable vendor ETA to the proposal, keeping it labelled as an estimate."""
    source=part.get('source_observation')
    if not isinstance(source,dict):
        return
    days=source.get('delivery_working_days')
    if isinstance(days,int) and not isinstance(days,bool) and days>=0:
        return
    days,estimate_source=_supplier_arrival_estimate(part,source)
    if days is not None:
        part['source_observation']={**source,'delivery_working_days':days,
            'delivery_estimate_source':estimate_source or 'vendor_default'}


def estimate_delivery_products(parts, definition, parent, settings):
    from app.services.playbook_commercial_quote import mode_economics
    required=set(required_parts(definition))
    missing=[f'{role}: catalogue product' for role in sorted(required-set(parts))]
    for role,part in parts.items():
        if _decimal(part.get('listing_price_gbp')) is None:
            missing.append(f'{role}: current item price')
    # Unknown component postage is an owner-approved £0 costing fallback.
    # Preserve supplier evidence as unknown; only the proposal's landed-cost
    # calculation uses zero. Supplier stock and ETA checks remain separate.
    values=[(_decimal(part.get('listing_price_gbp')) or Decimal(0))
        + (_decimal(part.get('supplier_postage_gbp')) or Decimal(0)) for part in parts.values()]
    allowed_roles=required | ({'wireless_adapter'} if 'wireless_adapter' in parts else set())
    if missing or set(parts)!=allowed_roles or any(value is None for value in values):
        reason='Current exact supplier data is missing: '+', '.join(missing or ['complete landed costs'])
        return {mode:{'available':False,'recommended_price_gbp':None,
                     'reason':reason} for mode in MODES}
    policy=automatic_policy(parts,definition,parent,settings)
    if policy is None:
        return {mode:{'available':False,'recommended_price_gbp':None,'reason':'Automatic business rule refresh is required'} for mode in MODES}
    landed=sum(values,Decimal(0));outputs={}
    for mode in MODES:
        ineligible=[role for role,part in parts.items() if not component_delivery_eligibility(part,policy)[mode]]
        ineligible_details=[]
        for role in ineligible:
            source=(parts[role].get('source_observation') or {})
            days,arrival_source=_supplier_arrival_estimate(parts[role],source)
            if (source.get('fresh') and source.get('active_listing')
                    and source.get('stock_status')=='available'
                    and isinstance(days,int) and not isinstance(days,bool) and days>=0):
                estimate=arrival_source or 'supplier estimate'
                commitment=policy.modes[mode].maximum_delivery_working_days
                ineligible_details.append(
                    f"{role} ({days} working-day arrival from {estimate}; the selected delivery option cannot meet its {commitment}-working-day total after build and courier)"
                )
            else:
                ineligible_details.append(f'{role} (fresh in-stock offer and arrival estimate required)')
        delivery_evidence_complete=all(
            _decimal(part.get('supplier_postage_gbp')) is not None
            and bool((part.get('source_observation') or {}).get('postage_verified'))
            for part in parts.values())
        postage_assumptions=[f"{part['role']}: £0.00 fallback" for part in parts.values()
            if (part.get('supplier_postage_assumption')=='owner-approved-zero-fallback'
                or (part.get('source_observation') or {}).get('postage_verified') is not True)]
        if ineligible:
            economics=mode_economics(policy,policy.modes[mode],landed)
            outputs[mode]={'available':False,'recommended_price_gbp':_money(economics['price']),
                'estimated_profit_gbp':_money(economics['contribution']),
                'profit_floor_gbp':_money(economics['floor']),
                'estimated_total_cost_gbp':_money(economics['true_cost']),
                'maximum_delivery_working_days':policy.modes[mode].maximum_delivery_working_days,
                'ineligible_component_roles':ineligible,
                'reason':'Price uses current part costs and the £0.00 fallback for unknown buying postage; this delivery option is unavailable because: '+', '.join(ineligible_details),
                'postage_assumptions':postage_assumptions,
                'cost_basis':'owner_approved_pilot_and_current_application_delivery_allowance'}
            continue
        economics=mode_economics(policy,policy.modes[mode],landed)
        price=economics['price'];profit=economics['contribution']
        market_cap=(policy.market.sold_p75_gbp if policy.market and policy.market.sold_p75_gbp is not None
                    else policy.market.sold_median_gbp if policy.market else None)
        if definition.get('tier') == 'High-end' and mode == 'standard' and (
                policy.market is not None and policy.market.sold_p75_gbp is not None
                and price > policy.market.sold_p75_gbp):
            outputs[mode]={'available':False,'recommended_price_gbp':None,'estimated_profit_gbp':None,
                'profit_floor_gbp':_money(economics['floor']),
                'market_cap_gbp':_money(policy.market.sold_p75_gbp),
                'estimated_total_cost_gbp':_money(economics['true_cost']),
                'reason':'Full cost and approved margin floor exceed the reviewed sold-price P75; revise the build or leave unpublished'}
            continue
        outputs[mode]={'available':True,'recommended_price_gbp':_money(price),
            'estimated_profit_gbp':_money(profit),'estimated_margin_fraction':str(profit/economics['net']),
            'profit_floor_gbp':_money(economics['floor']),
            'estimated_total_cost_gbp':_money(economics['true_cost']),
            'net_revenue_gbp':_money(economics['net']),
            'vat_gbp':_money(price-economics['net']),
            'costs':{**{key:str(value) for key,value in policy.modes[mode].costs.model_dump().items()},
                'parts_and_supplier_postage_gbp':_money(landed),
                **{key:str(value) for key,value in economics['charges'].items()}},
            'reason':'Proposed from current item costs; unknown supplier postage defaults to £0.00. Source availability, delivery ETA and compatibility must pass before approval.',
            'pricing_basis':('full_cost_plus_approved_margin_fallback' if definition.get('tier')=='High-end'
                and mode=='standard' and (policy.market is None or policy.market.sold_p75_gbp is None)
                else 'full_cost_plus_approved_margin'),
            'market_evidence_note':('No reviewed eight-sale complete-PC P75 is available; this draft uses the approved full-cost margin floor.'
                if definition.get('tier')=='High-end' and mode=='standard'
                and (policy.market is None or policy.market.sold_p75_gbp is None) else None),
            'postage_assumptions':postage_assumptions,
            'cost_basis':'owner_approved_pilot_and_current_application_delivery_allowance'}
    supplier_times=[_supplier_arrival_estimate(part)[0] for part in parts.values()]
    supplier_days=max(supplier_times) if supplier_times and all(
        isinstance(days,int) and not isinstance(days,bool) and days>=0 for days in supplier_times) else None
    for mode,product in outputs.items():
        rule=policy.modes[mode]
        product.update(supplier_arrival_working_days=supplier_days,workshop_wait_working_days=None,
            workshop_working_days=rule.workshop_working_days,courier_working_days=rule.courier_working_days,
            maximum_delivery_working_days=rule.maximum_delivery_working_days,
            delivery_promised=mode!='flexible',
            estimated_delivery_working_days=(supplier_days+rule.workshop_working_days+rule.courier_working_days)
                if mode!='flexible' and supplier_days is not None else None,
            timing_basis='proposed_from_delivery_target')
    standard_price=outputs['standard']['recommended_price_gbp']
    standard=Decimal(standard_price) if standard_price is not None else None
    for mode,offer in outputs.items():
        offer['difference_from_standard_gbp']=_money(Decimal(offer['recommended_price_gbp'])-standard) if standard is not None and offer['recommended_price_gbp'] is not None else None
    flexible_price=outputs['flexible']['recommended_price_gbp']
    if flexible_price is not None and (standard is None or Decimal(flexible_price)>=standard):
        outputs['flexible'].update(recommended_price_gbp=None,estimated_profit_gbp=None,
            difference_from_standard_gbp=None,
            reason='Current full-cost margin floors do not support a genuine Flex saving')
    return outputs


async def _catalogue_candidates(db,parent_id,catalogue,source_cache=None,*,variant_ids=None):
    source_cache={} if source_cache is None else source_cache
    from sqlalchemy import or_
    rows=(await db.execute(select(CatalogueVariant,Listing,PlaybookSlot).join(Listing,Listing.id==CatalogueVariant.listing_id)
        .join(PlaybookSlot,PlaybookSlot.id==CatalogueVariant.slot_id).where(
            PlaybookSlot.playbook_id==parent_id,CatalogueVariant.curated_for_builds.is_(True),
            CatalogueVariant.status.in_(('active','pending_review','hidden')),
            or_(Listing.price.is_(None),Listing.price>0,(PlaybookSlot.slot_type=='os_secondary')&(Listing.price==0)),
            Listing.status=='active',
            CatalogueVariant.id.in_(variant_ids) if variant_ids is not None else True))).all()
    # Reuse only exact, human-reviewed reference-board evidence. Fuzzy board
    # matches are useful for exploratory configurator warnings, but cannot
    # certify a Playbook component for sale.
    board_specs=(await db.execute(select(MotherboardSpec).where(MotherboardSpec.reviewed.is_(True)))).scalars().all()
    grouped={role:[] for role in (*HARDWARE_ROLES,'storage_secondary','os','os_secondary','wireless_adapter')}
    for variant,listing,slot in rows:
        if slot.slot_type not in grouped:
            continue
        bestseller=(listing.raw_specs or {}).get('bestseller') or {}
        grouped[slot.slot_type].append((variant,listing,slot,bestseller))
    selected=[]
    for role,items in grouped.items():
        items.sort(key=lambda row:(row[0].status!='active',row[3].get('rank') or 10000,
            row[1].price is None, row[1].price if row[1].price is not None else 0, row[0].id))
        # Bound source lookups and search effort; never fetch the public catalogue
        # here because unpublished cells also need automatically built proposals.
        for variant,listing,slot,bestseller in items[:MAX_CHOICES_PER_ROLE]:
            if not _plausible_role_candidate(slot.slot_type,listing.title):
                continue
            if slot.slot_type=='os' and not _verified_windows_licence_listing(listing):
                continue
            raw=listing.raw_specs if isinstance(listing.raw_specs,dict) else {}
            free_software=raw.get('playbook_free_software')
            if slot.slot_type=='os_secondary' and listing.price==0 and not (
                    isinstance(free_software,dict) and free_software.get('kind')=='official_free_os_download'):
                continue
            selected.append((role,variant,listing,slot,bestseller,raw,free_software))
    pending=[row[2] for row in selected if row[2].id not in source_cache]
    if pending:
        source_cache.update(await source_preview_many(db,pending))
    from app.services.shared_variant_assets import final_assets_by_variant, approved_model_photos
    from app.services.curated_media import media_urls
    ready_assets=await final_assets_by_variant(db,[variant for _,variant,*_ in selected])
    ready_ids=set(ready_assets)
    external_ids={listing.external_id for _,_,listing,_,_,_,_ in selected}
    catalogue_identities={}
    cpk_identities={}
    bestseller_cpks={str(row[4].get('cpk')) for row in selected
        if isinstance(row[4],dict) and row[4].get('cpk') and not str(row[4].get('cpk')).startswith('asin:')}
    if external_ids:
        from app.models.gem_radar_listing_cpk import GemRadarListingCpk
        identity_rows=(await db.execute(select(GemRadarListingCpk.listing_id,
            GemRadarListingCpk.cpk,GemRadarListingCpk.cpk_data,GemRadarListingCpk.cpk_confidence).where(
                GemRadarListingCpk.listing_id.in_(external_ids) | GemRadarListingCpk.cpk.in_(bestseller_cpks)))).mappings().all()
        catalogue_identities={row['listing_id']:dict(row) for row in identity_rows}
        for identity_row in identity_rows:
            if identity_row['cpk']:
                cpk_identities.setdefault(identity_row['cpk'],[]).append(dict(identity_row))
    from app.services.catalogue_cpk import identity_is_usable
    candidates=[]
    for role,variant,listing,slot,bestseller,raw,free_software in selected:
        if isinstance(free_software,dict) and free_software.get('kind')=='official_free_os_download':
            from app.services.commercial_readiness import official_free_software_preview
            source=official_free_software_preview(listing,free_software)
        else:
            source=source_cache.get(listing.id)
            if source is None and raw.get('playbook_requirement_source'):
                source={**raw['playbook_requirement_source'],'source':listing.source_name,
                    'fresh':False,'commercial_capture_verified':False}
        # Price and postage must come from the same current exact-product
        # observation. Bestseller catalogue prices are a ranking snapshot,
        # not a substitute for the latest supplier quote.
        item,postage,source_price_verified=_candidate_source_prices(listing.price,source)
        invalidate_conflicting_product_engineering(listing,role)
        engineering=engineering_specs(listing.raw_specs)
        if role=='motherboard':
            from app.services.motherboard_matching import match_exact_reviewed_motherboard_spec
            board=match_exact_reviewed_motherboard_spec(listing.title,board_specs)
            if board:
                reference={'socket':board.socket,'ram_type':board.ram_type,'ram_slots':board.ram_slots,
                    'form_factor':board.form_factor,'m2_slots':board.m2_slots,'reviewed':True}
                capture=((board.raw_ai_response or {}).get('manufacturer_source_capture') or {})
                capture_evidence=capture.get('field_evidence') or {}
                wireless_evidence=str(capture_evidence.get('wifi') or '')
                wireless_url=str(capture.get('source_url') or '')
                wireless_host=(urlsplit(wireless_url).hostname or '').casefold()
                if (board.wifi is True and re.search(r'\bbluetooth\b',wireless_evidence,re.I)
                        and wireless_host in {'asus.com','www.asus.com','rog.asus.com'}):
                    reference.update(wifi=True,bluetooth=True,wireless_reference_url=wireless_url)
                # A conflict between two approved records is still unknown
                # to this service; never silently choose one source.
                suggestion=_playbook_engineering_suggestion(listing,role)
                source_values=(suggestion or {}).get('suggested_specs') or {}
                source_conflicts=set((suggestion or {}).get('conflicted_fields') or []).intersection(reference)
                invalidation=((listing.raw_specs or {}).get('configurator') or {}).get('review_invalidation') or {}
                mismatches={key for key,value in reference.items() if key!='reviewed' and value is not None
                    and (key in engineering and engineering[key]!=value
                        or key in source_values and source_values[key]!=value)}
                invalidated_facts=set(invalidation.get('conflicted_fields') or []) | (
                    set(invalidation.get('reviewed_value_changes') or {})-{'source_url'})
                if not source_conflicts and not mismatches and not invalidated_facts:
                    # Changing supplier invalidates that retailer's review,
                    # not the independently reviewed exact-model reference.
                    # Certify only the reference fields when the old retailer
                    # review is invalid; never promote its unrelated facts.
                    engineering={**(engineering if engineering.get('reviewed') is True else {}),
                        **{key:value for key,value in reference.items() if value is not None},
                        'source_url':capture.get('source_url'),
                        'reviewed_by':board.reviewed_by or 'reviewed:motherboard-reference',
                        'engineering_reference':f'motherboard_specs:{board.canonical_model}'}
                else:
                    engineering={**engineering,'reviewed':False,
                        'reference_conflicts':sorted(source_conflicts|mismatches
                            |set(invalidation.get('conflicted_fields') or []))}
        from app.services.playbook_component_facts import resolve_primary_engineering
        if not engineering.get('reference_conflicts'):
            engineering=resolve_primary_engineering({'role':role,'title':listing.title,
                'engineering':engineering})
        engineering=_apply_exact_source_core_engineering(role,listing,source,engineering)
        identity=catalogue_identities.get(listing.external_id) or {}
        identity_data=identity.get('cpk_data') or {}
        product_cpk=(identity.get('cpk') if identity.get('cpk')
                     and identity_is_usable(listing.title,identity_data,{role}) else None)
        # Amazon's bestseller CPK links this durable product anchor to
        # supplier observations. Reuse only a unique, valid identity.
        if not product_cpk:
            amazon_cpk=bestseller.get('cpk') if isinstance(bestseller,dict) else None
            matching=[row for row in cpk_identities.get(amazon_cpk,[])
                if identity_is_usable(listing.title,row.get('cpk_data') or {},{role})] if amazon_cpk else []
            unique_cpks={row.get('cpk') for row in matching if row.get('cpk')}
            unique_data={json.dumps(row.get('cpk_data') or {},sort_keys=True,default=str) for row in matching}
            if len(unique_cpks)==1 and len(unique_data)==1:
                product_cpk=next(iter(unique_cpks))
                identity_data=matching[0].get('cpk_data') or {}
            elif amazon_cpk and not cpk_identities.get(amazon_cpk):
                # Retain the ASIN observation's source CPK when no identity
                # row exists yet. Supplier metadata is validated below before
                # it can populate or update this canonical identity.
                product_cpk=amazon_cpk
        requirement_source=raw.get('playbook_requirement_source') or {}
        candidates.append({'role':role,'variant_id':variant.id,'slot_id':slot.id,'listing_id':listing.id,
            'title':listing.title,'external_listing_id':listing.external_id,
            'source_url':(source or {}).get('url') or listing.url,
            'amazon_listing_url':listing.url if amazon_asin(listing.url) else None,
            'images':media_urls(listing.image_urls or []),
            'listing_price_gbp':_money(item) if item is not None else None,
            'source_price_verified':source_price_verified,
            'display_price':_money(variant.display_price) if variant.display_price is not None else None,
            'supplier_postage_gbp':_money(postage if postage is not None else Decimal('0.00')),
            'supplier_postage_assumption':('captured' if source and source.get('postage_verified')
                else 'owner-approved-zero-fallback'),
            'landed_gbp':_money(item+(postage if postage is not None else Decimal('0.00'))) if item is not None else None,
            'catalogue':'curated',
            'catalogue_approved':variant.status=='active',
            'catalogue_status':variant.status,
            # Cost an exact captured licence in the proposal while its source
            # review is pending. This never makes it eligible for publication.
            'draft_software_candidate':bool(role=='os' and _verified_windows_licence_listing(listing)
                and not (source or {}).get('licence_source_reviewed')
                and (variant.status in {'active','pending_review'} or variant.status=='hidden'
                    and (variant.consecutive_misses or 0)>=2
                    and (not variant.reject_reason or variant.reject_reason.startswith('freshness:')))),
            'media_ready':role.startswith('os') or variant.id in ready_ids,
            'photo_ready':role.startswith('os') or bool(approved_model_photos(variant)),
            'model_generation_status':((variant.asset_media_review or {}).get('generation') or {}).get('status'),
            'not_live_reason':None if role.startswith('os') or variant.id in ready_ids else (
                'Choose one to four product photos for the 3D model' if not (
                    1 <= len((variant.asset_media_review or {}).get('model_image_urls') or
                        ((variant.asset_media_review or {}).get('image_urls') or [])) <= 4
                ) else
                'An active final model matching the chosen 3D reference photos is required'),
            'rank':bestseller.get('rank'),'asin':bestseller.get('asin'),
            # The durable listing identity is the canonical source for all
            # active catalogue products. Bestseller and authored requirement
            # CPK values remain fallbacks for rows awaiting reconciliation.
            'cpk':product_cpk,
            'cpk_data':identity_data if product_cpk else None,
                'price_observed_at':(source or {}).get('observed_at'),
            'source_observation':source,'engineering':engineering,
            'playbook_verified_specs':raw.get('playbook_verified_specs') if isinstance(raw.get('playbook_verified_specs'),dict) else {},
            'case_catalogue_id':listing.case_catalogue_id})
    if not candidates:
        return []
    from app.services.playbook_stored_offers import stored_offers, suggested_offer, offers_for_part
    from app.services.playbook_component_facts import manufacturer_facts
    offers=await stored_offers(db,{part.get('cpk') for part in candidates})
    for part in candidates:
        matched_offers=[] if part['role'].startswith('os') else offers_for_part(part,offers)
        part['suggested_supplier_offer']=suggested_offer(part,matched_offers)
        from app.services.playbook_stored_offers import same_product
        valid_supplier_offers=[offer for offer in matched_offers if same_product(part,offer)]
        valid_supplier_offers.sort(key=lambda offer:(Decimal(str(offer['item_gbp']))
            +Decimal(str(offer.get('delivery_gbp') or '0')),
            str(offer.get('source') or ''),str(offer.get('url') or '')))
        part['supplier_offers']=[{key:offer.get(key) for key in (
            'source','title','url','item_gbp','delivery_gbp','postage_verified',
            'postage_assumption','observed_at','stock_status','condition','match_basis',
            'observation_id','listing_id','listing_type','stock_evidence','commercial_capture_verified',
            'delivery_working_days','delivery_estimate_source','prime_eligible')}
            for offer in valid_supplier_offers]
        from app.gem_radar.product_identity_registry import registry_available
        if part.get('cpk') and not part.get('cpk_data') and not await registry_available(db):
            # Supplier observations carry the shared CPK identity. Enrich the
            # Amazon ASIN row only if exactly one specific identity validates
            # against both exact product titles; this makes the join durable.
            from app.services.catalogue_cpk import identity_is_usable
            identities={}
            for offer in matched_offers:
                data=offer.get('cpk_data') or {}
                if (offer.get('cpk')==part['cpk']
                        and identity_is_usable(part['title'],data,{part['role']})
                        and identity_is_usable(offer['title'],data,{part['role']})):
                    identities[json.dumps(data,sort_keys=True,default=str)]=data
            if len(identities)==1 and part.get('external_listing_id'):
                data=dict(next(iter(identities.values())))
                data.update(cpk=part['cpk'],catalogue_identity_match='exact_bestseller_and_supplier_cpk')
                part['cpk_data']=data
                await db.execute(text("""
                    INSERT INTO gem_radar_listing_cpk
                        (listing_id,cpk,cpk_data,cpk_confidence,updated_at)
                    VALUES (:listing_id,:cpk,CAST(:cpk_data AS jsonb),:confidence,CURRENT_TIMESTAMP)
                    ON CONFLICT (listing_id) DO UPDATE SET
                        cpk=EXCLUDED.cpk,cpk_data=EXCLUDED.cpk_data,
                        cpk_confidence=EXCLUDED.cpk_confidence,updated_at=CURRENT_TIMESTAMP
                """),{'listing_id':part['external_listing_id'],'cpk':part['cpk'],
                    'cpk_data':json.dumps(data),'confidence':0.95})
        part.pop('external_listing_id',None)
        part['manufacturer_facts']=manufacturer_facts(part['role'],part['title'])
        cache=db.info.setdefault('playbook_planning_specs',{})
        if part['listing_id'] not in cache:
            listing=next(row[2] for row in selected if row[2].id==part['listing_id'])
            suggestion=_playbook_engineering_suggestion(listing,part['role'])
            cache[part['listing_id']]=(suggestion or {}).get('suggested_specs') or {}
        part['planning_engineering']={**part['engineering'],**cache[part['listing_id']],**part['manufacturer_facts'],
            **(part.get('playbook_verified_specs') or {})}
    return candidates


def _performance_context(definition,benchmark_index):
    from app.services.hardware_performance import _normalise_for_category
    context=(definition.get('segment','')+' '+definition.get('use','')).casefold()
    baselines={}
    for role,normalise in (('cpu',normalise_cpu),('gpu',normalise_gpu)):
        preferred=definition.get('components',{}).get(role,'')
        if not preferred or role=='gpu' and 'integrated' in preferred.casefold(): continue
        norm=normalise(preferred)
        baseline=(benchmark_index or {}).get((role,norm))
        if (role=='gpu' and baseline and 'ada' in preferred.casefold()
                and 'ada' not in baseline.model.casefold()):
            continue  # A GRID/vGPU record is not this physical Ada workstation card.
        requested_metric=('workstation_score' if any(word in context for word in ('creation','workstation','software development','ai'))
            else 'gaming_score' if role=='gpu' and 'gaming' in context else 'overall_score')
        # PassMark imports currently provide CPU Mark / 3D GPU score only. Keep
        # same-source, same-metric comparisons usable when a workload-specific
        # field is absent, while exposing that limitation in the evidence.
        metric=requested_metric
        if baseline and getattr(baseline,metric,None) is None and getattr(baseline,'overall_score',None) is not None:
            metric='overall_score'
        if baseline and getattr(baseline,metric,None) is not None and (baseline.confidence_score or 0)>=0.8:
            baselines[role]={'model':baseline.model,'normalized_model':norm,'metric':metric,
                'benchmark_source':baseline.benchmark_source,'confidence_score':baseline.confidence_score,
                'source_url':baseline.source_url,metric:getattr(baseline,metric),
                'requested_metric':requested_metric,
                'workload_specific_metric_available':metric==requested_metric}
    return baselines


def _candidate_performance(role,title,benchmark_index):
    from app.services.hardware_performance import _normalise_for_category
    if role not in {'cpu','gpu'} or not benchmark_index:return None
    normalised=_normalise_for_category(role,title)
    row=benchmark_index.get((role,normalised)) if normalised else None
    if not row:return None
    if role=='gpu' and 'ada' in title.casefold() and 'ada' not in row.model.casefold():
        return None
    return {'model':row.model,'normalized_model':normalised,'benchmark_source':row.benchmark_source,
        'confidence_score':row.confidence_score,'source_url':row.source_url,
        'overall_score':row.overall_score,'gaming_score':row.gaming_score,
        'workstation_score':row.workstation_score}


def media_candidate_pool(candidates):
    """Prefer live products; retain blocked roles for internal research only."""
    ready_roles={part['role'] for part in candidates if part.get('media_ready') is True}
    return [part for part in candidates
            if part['role'] not in ready_roles or part.get('media_ready') is True]


async def paid_component_sales(db, window_days=90):
    """Count exact variants in paid, non-cancelled curated orders for proposal ranking."""
    from collections import Counter
    cutoff=_utcnow()-timedelta(days=window_days)
    rows=(await db.execute(select(Order.specs,Order.stripe_payment_intent_id).where(
        Order.created_at>=cutoff,Order.created_at<=_utcnow(),
        Order.status!=OrderStatus.CANCELLED,Order.refund_id.is_(None)))).all()
    by_cell={}
    all_cells=Counter()
    for specs,payment_intent_id in rows:
        if not isinstance(specs,dict):
            continue
        payment=specs.get('payment_evidence') if isinstance(specs.get('payment_evidence'),dict) else {}
        if payment.get('status')!='succeeded' and not payment_intent_id:
            continue
        cell_id=str(specs.get('curated_build_id') or '').strip()
        if not cell_id:
            continue
        variants={row.get('variant_id') for row in (specs.get('slots') or [])
            if isinstance(row,dict) and isinstance(row.get('variant_id'),int)
            and not isinstance(row.get('variant_id'),bool)}
        variants.update(row.get('variant_id',row.get('target_variant_id'))
            for row in (specs.get('playbook_upgrades') or [])
            if isinstance(row,dict) and isinstance(row.get('variant_id',row.get('target_variant_id')),int)
            and not isinstance(row.get('variant_id',row.get('target_variant_id')),bool))
        counts=by_cell.setdefault(cell_id,Counter())
        for variant_id in variants:
            counts[variant_id]+=1
            all_cells[variant_id]+=1
    return {'by_cell':dict(by_cell),'all_cells':all_cells}


async def build_cell_offer(db,definition,parent,settings,candidates,benchmark_index=None,
        paid_component_sales=None):
    paid_component_sales=paid_component_sales or {'by_cell':{},'all_cells':{}}
    cell_sales=paid_component_sales['by_cell'].get(definition['id'],{})
    all_sales=paid_component_sales['all_cells']
    # Media readiness is a publication gate, never a product-identity filter.
    candidates=list(candidates)
    baselines=_performance_context(definition,benchmark_index or {})
    candidates=[{**candidate,'performance_evidence':candidate.get('performance_evidence') or
        _candidate_performance(candidate['role'],candidate['title'],benchmark_index or {}),
        'cell_paid_orders_90d':cell_sales.get(candidate['variant_id'],0),
        'all_cell_paid_orders_90d':all_sales.get(candidate['variant_id'],0)} for candidate in candidates]
    def fit_engineering(part):
        """Use exact-model manufacturer references alongside reviewed catalogue facts."""
        return {**(part.get('engineering') or {}),**(part.get('manufacturer_facts') or {})}
    case_ids={part['case_catalogue_id'] for part in candidates if part.get('case_catalogue_id')}
    case_rows=(await db.execute(select(CaseCatalogue).where(CaseCatalogue.id.in_(case_ids)))).scalars().all() if case_ids else []
    cases={case.id:case for case in case_rows}
    def chassis_for(selected):
        part=selected.get('case') or {}
        case=cases.get(part.get('case_catalogue_id'))
        chassis={'form_factor':case.form_factor,'max_gpu_length_mm':case.max_gpu_length_mm,
            'max_cooler_height_mm':case.max_cooler_height_mm,'radiator_support':case.radiator_support} if case else {}
        specs=fit_engineering(part)
        return {**chassis,**specs,'engineering':specs}
    def fit_check(selected,complete):
        checks=evaluate_fit({role:fit_engineering(part) for role,part in selected.items()
            if role!='case' and not role.startswith('os')},chassis_for(selected),
            gpu_required='gpu' in required_roles(definition))
        return _selected_fit_passes(checks,set(selected),complete)
    parts,blockers=assemble_components(definition,candidates,performance_baselines=baselines,fit_check=fit_check)
    for part in parts.values():
        _store_supplier_arrival_default(part)
    for role,part in parts.items():
        normalise=normalise_cpu if role=='cpu' else normalise_gpu
        if role in baselines and normalise(definition['components'].get(role,''))!=normalise(part['title']):
            part['performance_comparison']={'baseline':baselines[role],
                'selected':part.get('performance_evidence'),'meets_or_exceeds':bool(part.get('performance_evidence'))}
    policy=automatic_policy(parts,definition,parent,settings) if parts else None
    if policy:
        candidates=[{**part,'delivery_eligibility':component_delivery_eligibility(part,policy)} for part in candidates]
        parts={role:{**part,'delivery_eligibility':component_delivery_eligibility(part,policy)} for role,part in parts.items()}
        # One published configuration is shared across delivery choices. Keep
        # that BOM feasible for the default Standard promise; faster modes can
        # then remain unavailable when any selected supplier misses their tighter
        # deadline. Requiring fully reviewed engineering here would hide useful
        # source and price proposals before the operator can review the facts.
        standard_parts,standard_blockers=assemble_components(definition,candidates,
            delivery_mode='standard',performance_baselines=baselines,fit_check=fit_check)
        if set(standard_parts)==set(required_parts(definition)) and not standard_blockers:
            standard_policy=automatic_policy(standard_parts,definition,parent,settings)
            if standard_policy:
                policy=standard_policy
                candidates=[{**part,'delivery_eligibility':component_delivery_eligibility(part,policy)}
                    for part in candidates]
            parts={role:{**part,'delivery_eligibility':component_delivery_eligibility(part,policy)}
                for role,part in standard_parts.items()}
            selected_roles=set(parts)
            blockers=[message for message in blockers if not any(
                message==f'Automatic sourcing needs a matching {role} catalogue product'
                for role in selected_roles)]
    for part in parts.values():
        _store_supplier_arrival_default(part)
    # Apply exact newer supplier captures after the optional Standard-delivery
    # reassembly above. That second assembly can otherwise restore the original
    # catalogue snapshot (often with unknown condition) and discard the fresh,
    # exact new/stock evidence selected for the proposal.
    for part in parts.values():
        stored_source=_current_suggested_supplier_source(part)
        current_source=part.get('source_observation') or {}
        if stored_source and current_source.get('observation_id')!=stored_source.get('observation_id'):
            item=Decimal(stored_source['item_gbp'])
            delivery=(Decimal(stored_source['delivery_gbp'])
                if stored_source.get('postage_verified') else Decimal('0.00'))
            quantity=part.get('quantity') or 1
            part.update(source_observation=stored_source,source_url=stored_source['url'],
                price_observed_at=stored_source['observed_at'],listing_price_gbp=_money(item*quantity),
                supplier_postage_gbp=_money(delivery*quantity),
                supplier_postage_assumption=('captured' if stored_source.get('postage_verified')
                    else 'owner-approved-zero-fallback'),
                landed_gbp=_money((item+delivery)*quantity),source_price_verified=True)
    from app.services.playbook_planning_checks import wireless_extra_required
    missing_radios=wireless_extra_required(parts.get('motherboard'))
    wireless_extra=None
    wireless_missing_bom=[]
    if missing_radios:
        adapter=next((part for part in candidates if part.get('role')=='wireless_adapter'
            and part.get('catalogue_status') in {'active','pending_review'}
            and part.get('planning_engineering',{}).get('wifi') is True
            and part.get('planning_engineering',{}).get('bluetooth') is True
            and _decimal(part.get('listing_price_gbp')) is not None),None)
        if adapter:
            parts['wireless_adapter']=dict(adapter)
            if policy:
                parts['wireless_adapter']['delivery_eligibility']=component_delivery_eligibility(adapter,policy)
            source=adapter.get('source_observation') or {}
            if not adapter.get('catalogue_approved'):
                blockers.append('wireless_adapter: approve the exact adapter in the shared catalogue before publication')
            if not (source.get('fresh') and source.get('active_listing')
                    and source.get('stock_status')=='available' and source.get('condition')=='new'):
                blockers.append('wireless_adapter: refresh and verify a new, in-stock supplier offer before publication')
            wireless_extra={**adapter,'provides':['Wi-Fi','Bluetooth'],
                'missing_on_motherboard':missing_radios,'source_status':'catalogue_candidate'}
        else:
            wireless_missing_bom=['wireless_adapter: no approved, priced new adapter is available']
            blockers.append('Add and source a new Wi-Fi/Bluetooth adapter; motherboard connectivity is missing or unverified for '
                +' and '.join(missing_radios))
    for role,part in parts.items():
        if part.get('draft_software_candidate'):
            blockers.append(f'{role}: review the exact software licence source before publication')
        if not role.startswith('os') and role!='wireless_adapter' and not part.get('photo_ready'):
            blockers.append(f"{role}: approve the product photos in the Playbook")
    engineering={role:fit_engineering(part) for role,part in parts.items() if role!='case' and not role.startswith('os')}
    chassis=chassis_for(parts)
    checks=evaluate_fit(engineering,chassis,gpu_required='gpu' in required_roles(definition))
    compatible=not any(check['severity'] in {'error','unknown'} for check in checks)
    if not compatible:
        blockers.append('Compatibility facts still need confirmation before publication')
    required=set(required_parts(definition))
    allowed=required|({'wireless_adapter'} if 'wireless_adapter' in parts else set())
    availability=required.issubset(parts) and set(parts).issubset(allowed)
    if missing_radios and wireless_extra is None:
        availability=False
    condition_gaps=[]
    for part in parts.values():
        source=part.get('source_observation') or {}
        if not (source.get('fresh') and source.get('active_listing')
                and source.get('stock_status')=='available'):
            availability=False
        if source and source.get('condition') != 'new':
            condition_gaps.append(part['role'])
    if not availability:
        source_gaps=[]
        for role,part in parts.items():
            source=part.get('source_observation') or {}
            gaps=[]
            if not source.get('fresh'):gaps.append('source capture missing or stale')
            if not source.get('active_listing'):gaps.append('listing not confirmed active')
            if source.get('stock_status')!='available':gaps.append(f"stock {source.get('stock_status') or 'unconfirmed'}")
            if gaps:source_gaps.append(f"{role} ({'; '.join(gaps)})")
        blockers.append('Refresh exact supplier stock evidence for: '+', '.join(source_gaps or ['missing catalogue roles']))
    if condition_gaps:
        blockers.append('Replace non-new supplier offers for: '+', '.join(sorted(condition_gaps)))
    if definition.get('components',{}).get('os') and 'os' not in parts:
        blockers.append('Automatic sourcing must link the operating-system licence and its cost from the catalogue')
    unmodelled_components=unmodelled_required_components(definition)
    blockers.extend(unmodelled_components)
    delivery=estimate_delivery_products(parts,definition,parent,settings)
    delivery=withhold_incomplete_bom_prices(delivery,[*unmodelled_components,*wireless_missing_bom])
    if definition.get('components',{}).get('os') and 'os' not in parts:
        for row in delivery.values():
            row.update(recommended_price_gbp=None,estimated_profit_gbp=None,
                profit_floor_gbp=None,estimated_total_cost_gbp=None,net_revenue_gbp=None,vat_gbp=None,
                reason='The complete build price requires a sourced operating-system licence')
    for mode,row in delivery.items():
        if row['recommended_price_gbp'] is None and mode=='standard':
            if not (unmodelled_components and str(row['reason']).startswith(
                    'The complete authored build is not represented:')):
                blockers.append(f"{mode}: {row['reason']}")
    if not blockers:
        from app.services.commercial_quote_evidence import assess_stored_cell
        from app.services.commercial_checkout import current_capacity_ids
        from types import SimpleNamespace
        # Proposal generation must never persist supplier facts as "reviewed".
        # The operator's explicit supplier-review action is the only importer;
        # this read-only assessment uses previously approved evidence, if any.
        policy=automatic_policy(parts,definition,parent,settings)
        capacities=await current_capacity_ids(db)
        body=SimpleNamespace(curated_build_id=definition['id'],capacity_evidence_ids=capacities,nonnew_consent=False,
            model_dump=lambda **_: {'curated_build_id':definition['id'],'capacity_evidence_ids':capacities})
        assessed,_=await assess_stored_cell(db,parent,definition,policy,body)
        for mode,quote in assessed['modes'].items():
            if mode not in policy.enabled_modes:
                delivery[mode].update(available=False, recommended_price_gbp=None, reason='Not offered in the MVP')
                continue
            if not quote['offerable']:
                delivery[mode].update(available=False,reason=quote['reason'],recommended_price_gbp=None)
                if mode=='standard':blockers.append(f"{mode}: {quote['reason']}")
            else:
                delivery[mode].update(available=True,recommended_price_gbp=quote['price_gbp'],
                    estimated_profit_gbp=quote['contribution_gbp'],
                    profit_floor_gbp=quote.get('profit_floor_gbp'),
                    estimated_total_cost_gbp=quote.get('true_cost_gbp'),
                    net_revenue_gbp=quote.get('net_revenue_gbp'),
                    vat_gbp=_money(Decimal(quote['price_gbp'])-Decimal(quote['net_revenue_gbp'])) if quote.get('net_revenue_gbp') is not None else None,
                    delivery_working_days=quote['delivery_working_days'],
                    difference_from_standard_gbp=quote.get('difference_from_standard_gbp'),
                    reason='Exact source, full cost, compatibility and workshop checks passed; awaiting approval')
                delivery[mode].update({key:quote[key] for key in (
                    'supplier_arrival_working_days','workshop_wait_working_days','workshop_working_days',
                    'courier_working_days','maximum_delivery_working_days') if key in quote})
                delivery[mode].update(estimated_delivery_working_days=quote['delivery_working_days'],
                    delivery_promised=mode!='flexible',
                    timing_basis='reviewed_workshop_policy')
    upsells=[]
    for role,selected in ([] if unmodelled_components or mvp_mode(parent) else parts.items()):
        if role=='case' or role.startswith('os'):
            continue
        alternatives=[part for part in candidates if part['role']==role and part['variant_id']!=selected['variant_id']]
        metric=baselines.get(role,{}).get('metric','overall_score')
        for alternative in sorted(alternatives,key=lambda row:(not _upgrade_quality_verified(role,selected,row,metric),
                *_candidate_key(row,definition.get('components',{}).get(role,''))))[:3]:
            upgraded={**parts,role:alternative}
            upgraded_checks=evaluate_fit({key:value['engineering'] for key,value in upgraded.items() if key not in {'case','os'}},
                {**alternative['engineering'],'engineering':alternative['engineering']} if role=='case' else chassis,
                gpu_required='gpu' in required_roles(definition))
            if not _distinct_storage_devices(upgraded):
                upgraded_checks.append({'code':'DISTINCT_STORAGE_DEVICES','severity':'error',
                    'message':'Each authored drive requires a separately represented catalogue device.',
                    'affected':['storage','storage_secondary']})
            quality_verified=_upgrade_quality_verified(role,selected,alternative,metric)
            upgraded_quotes=estimate_delivery_products(upgraded,definition,parent,settings)
            upgraded_policy=automatic_policy(upgraded,definition,parent,settings)
            alternative={**alternative,'delivery_eligibility':component_delivery_eligibility(alternative,upgraded_policy) if upgraded_policy else {mode:False for mode in MODES}}
            upsells.append({'role':role,'component':alternative,'delivery_products':upgraded_quotes,
                'compatibility_verified':not any(check['severity'] in {'error','unknown'} for check in upgraded_checks),
                'quality_verified':quality_verified,'performance_metric':baselines.get(role,{}).get('metric','overall_score'),
                'checks':upgraded_checks})
    for mode,product in delivery.items():
        # A shared BOM must never masquerade as a Fast Track recommendation
        # when even one of its parts misses the customer commitment.
        product['recommended_component_variant_ids']=[part['variant_id'] for part in parts.values()] if product['recommended_price_gbp'] is not None else []
    from app.services.playbook_pace_sources import component_pace_sources
    pace_sources=component_pace_sources(parts,automatic_policy(parts,definition,parent,settings))
    offer={'cell_id':definition['id'],'playbook_id':parent.id,'segment':definition['segment'],'tier':definition['tier'],
        'name':definition['name'],'description':definition.get('description'),'intended_use':definition.get('use'),
        'components':list(parts.values()),'case_choices':[] if mvp_mode(parent) else [part for part in candidates if part['role']=='case'],
        'paid_order_signal_window_days':90,
        'delivery_eligible_variant_ids':{mode:[part['variant_id'] for part in candidates
            if (part.get('delivery_eligibility') or {}).get(mode,False)] for mode in MODES},
        'delivery_products':delivery,'component_pace_options':pace_sources,
        'upsells':upsells,'compatibility':{'verified':compatible,'checks':checks},
        'recommended_selling_price_gbp':delivery['standard']['recommended_price_gbp'],
        'source_available':availability,'purchasable':False,'blockers':blockers,
        'catalogue_review_required':any(not part['catalogue_approved'] for part in parts.values()),
        'complete_hardware':set(required_hardware_parts(definition)).issubset(parts)
            and not unmodelled_components,
        'required_hardware_count':len(required_roles(definition)),'source':SOURCE}
    from app.services.playbook_planning_checks import assess
    offer['planning_compatibility']=assess(definition,offer)
    if missing_radios:
        offer['required_extras']=[wireless_extra] if wireless_extra else [{
            'role':'wireless_adapter','title':'Combined Wi-Fi and Bluetooth adapter',
            'provides':['Wi-Fi','Bluetooth'],'missing_on_motherboard':missing_radios,
            'listing_price_gbp':None,'source_status':'needs_current_supplier_offer'}]
    publishable_ids={row['target_variant_id'] for row in _publication_upgrade_rows(offer)}
    from app.services.playbook_market import approved_market
    offer['market_evidence_batch_id'] = (approved_market(parent, definition, parts) or {}).get('batch_id')
    for item in offer['upsells']:
        item['publication_eligible']=item['component']['variant_id'] in publishable_ids
    offer['revision_sha256']=fingerprint(commercial_revision_payload(offer) if mvp_mode(parent) else offer)
    return offer


async def approve_proposal(db,proposal_id,revision,actor_id,*,exact_reviewed_bom=False):
    """Rebuild the exact reviewed offer before enabling any sale."""
    await db.execute(text('SELECT pg_advisory_xact_lock(61311, 1)'))
    proposal=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.id==proposal_id)
        .with_for_update())).scalar_one_or_none()
    if proposal is None or (proposal.demand_signals or {}).get('source')!=SOURCE:
        raise HTTPException(404,'Generated Playbook proposal not found')
    if proposal.status!='pending' or proposal.proposed_data.get('revision_sha256')!=revision:
        raise HTTPException(409,'The proposal changed; reload before reviewing')
    parent=(await db.execute(select(Playbook).where(Playbook.id==proposal.playbook_id)
        .with_for_update())).scalar_one()
    definition=next((row for row in definitions()['builds'] if row['id']==proposal.proposed_data['cell_id']),None)
    if definition is None or parent.name!=definition['segment'] or getattr(parent.status,'value',parent.status)!='active':
        raise HTTPException(409,'The active segment definition changed; refresh the proposal')
    from app.services.hardware_performance import load_benchmark_context
    benchmark_index,_=await load_benchmark_context(db)
    selected_ids=({part['variant_id'] for part in proposal.proposed_data['components']}
        if exact_reviewed_bom else None)
    candidates=await _catalogue_candidates(db,parent.id,'curated',variant_ids=selected_ids)
    # Proposal refresh normalizes exact source/manufacturer engineering facts
    # before it selects the BOM. Repeat that same non-price-mutating step here
    # before comparing revisions; using raw candidates selected a different
    # motherboard/adapter set from the proposal and made every review appear
    # stale. Supplier prices and stock are still rebuilt and checked below.
    candidates=await prepare_candidates(db,parent,candidates,reconcile_prices=False)
    current=await build_cell_offer(db,definition,parent,await db.get(AppSettings,1),
        candidates,benchmark_index,
        await paid_component_sales(db))
    current=await _stock_replacements(db,current,parent,candidates)
    if current['revision_sha256']!=revision:
        raise HTTPException(409,'Catalogue products, prices or availability changed; refresh and review the new proposal')
    limit_reason=publication_limit_reason(parent,definition,current) if mvp_enabled(parent) else None
    if limit_reason:
        raise HTTPException(409,limit_reason)
    if current['blockers']:
        raise HTTPException(409,{'message':'The service must complete source checks before approval',
            'service_work_remaining':current['blockers']})
    # The checkout adapter revalidates capacity and exact supplier observations.
    # Source facts cannot be approved through operator-entered replacements.
    from app.services.catalogue_price_import import import_current_catalogue_prices
    from app.services.commercial_quote_evidence import assess_stored_cell
    from app.services.commercial_checkout import current_capacity_ids
    from types import SimpleNamespace
    parts={part['role']:part for part in current['components']}
    policy=automatic_policy(parts,definition,parent,await db.get(AppSettings,1))
    if policy is None:
        raise HTTPException(409,'The automatic commercial policy is not complete')
    publication_upgrades=_publication_upgrade_rows(current)
    source_parts={}
    for role,part in parts.items():
        key=f"case:{part['case_catalogue_id']}" if role=='case' and part.get('case_catalogue_id') else f"variant:{part['variant_id']}"
        source_parts[key]={'role':role,'part_key':key,'source':part['source_observation']}
    for upgrade in publication_upgrades:
        part=next(row['component'] for row in current['upsells']
            if row['component']['variant_id']==upgrade['target_variant_id'])
        key=f"variant:{part['variant_id']}"
        source_parts[key]={'role':upgrade['category'],'part_key':key,'source':part['source_observation']}
    imported=await import_current_catalogue_prices(db,list(source_parts.values()),actor_id)
    if imported['blocked']:
        raise HTTPException(409,{'message':'Source collection is incomplete','service_work_remaining':imported['blocked']})
    capacities=await current_capacity_ids(db)
    body=SimpleNamespace(curated_build_id=definition['id'],capacity_evidence_ids=capacities,nonnew_consent=False,
        model_dump=lambda **_: {'curated_build_id':definition['id'],'capacity_evidence_ids':capacities})
    assessment,_=await assess_stored_cell(db,parent,definition,policy,body)
    for mode,quote in assessment['modes'].items():
        if mode not in policy.enabled_modes:
            continue
        reviewed=current['delivery_products'][mode]
        if mode!='standard' and not reviewed.get('available'):
            if quote['offerable']:
                raise HTTPException(409,'Delivery eligibility changed; review the new pace quote')
            continue
        if not quote['offerable'] or Decimal(quote['price_gbp'])!=Decimal(reviewed['recommended_price_gbp']):
            raise HTTPException(409,'Current source and workshop evidence must support the exact three reviewed prices')

    # The exact proposal approval is also the Playbook publication approval.
    # Publish the same server-selected BOM and Standard price through the
    # existing customer catalogue only after source, fit, economics, capacity,
    # and revision checks above have passed.
    cell=(await db.execute(select(CuratedBuildSegment).where(
        CuratedBuildSegment.customer_type==definition['segment'],
        CuratedBuildSegment.budget_level==definition['tier'],
    ).with_for_update())).scalar_one_or_none()
    if cell is None:
        cell=CuratedBuildSegment(customer_type=definition['segment'],budget_level=definition['tier'])
        db.add(cell)
    chosen={part['role']:part for part in current['components']}
    cell.components={role:int(part['variant_id']) for role,part in chosen.items()
        if part.get('variant_id') is not None}
    cell.selling_price=float(current['delivery_products']['standard']['recommended_price_gbp'])
    cell.proposed_selling_price=cell.selling_price
    cell.component_cost_snapshot=float(sum((_decimal(part.get('landed_gbp')) or Decimal(0)
        for part in chosen.values()),Decimal(0)))
    cell.availability_status='in_stock'
    cell.approved_upgrades=publication_upgrades

    # A proposal-scoped approval may activate only the exact selected catalogue
    # rows whose supplier evidence was imported above. Visibility stays scoped
    # to this Playbook slot; it does not expose the items in other segments.
    published_parts=[*chosen.values(),*(next(row['component'] for row in current['upsells']
        if row['component']['variant_id']==upgrade['target_variant_id']) for upgrade in publication_upgrades)]
    for part in published_parts:
        variant=(await db.execute(select(CatalogueVariant).where(
            CatalogueVariant.id==part['variant_id'],CatalogueVariant.slot_id==part['slot_id'],
        ).with_for_update())).scalar_one_or_none()
        listing=await db.get(Listing,part['listing_id']) if part.get('listing_id') else None
        if (variant is None or not variant.curated_for_builds
                or listing is None or getattr(listing.status,'value',listing.status)!='active'):
            raise HTTPException(409,'A selected catalogue product changed before publication')
        variant.status='active'
        visibility=(await db.execute(select(ConfiguratorCatalogueVisibility).where(
            ConfiguratorCatalogueVisibility.playbook_slot_id==part['slot_id'],
            ConfiguratorCatalogueVisibility.catalogue_variant_id==part['variant_id'],
        ).with_for_update())).scalar_one_or_none()
        if visibility is None:
            visibility=ConfiguratorCatalogueVisibility(playbook_slot_id=part['slot_id'],
                catalogue_variant_id=part['variant_id'],is_publicly_visible=True)
            db.add(visibility)
        else:
            visibility.is_publicly_visible=True

    from app.api.public_catalogue import public_playbook_slots, public_list_cases
    from app.services.curated_publication import publication_snapshot, PublicationError
    try:
        publication_snapshot(definition,cell,await public_playbook_slots(parent.id,db),
            await public_list_cases(db),require_live=False)
    except PublicationError as exc:
        cell.is_live=False
        raise HTTPException(409,{'message':'The generated build passed commercial review but the storefront publication checks failed',
            'publication_blocker':str(exc)}) from exc
    cell.is_live=True
    from app.services.playbook_book import record_cell_event
    record_cell_event(db,definition['id'],'offer_published','Automatic publication within owner-enabled MVP rules' if actor_id==0 else 'Operator approved the exact checked proposal',
        {'approved_revision':((parent.pricing_model or {}).get('managed_offers') or {}).get(definition['id'],{}).get('revision_sha256')},
        {'approved_revision':revision,'selling_price':cell.selling_price,'components':cell.components,'is_live':True},actor_id)

    pricing=dict(parent.pricing_model or {})
    cells=dict(pricing.get('commercial_cells') or {})
    policy=policy.model_copy(update={'version':int((cells.get(definition['id']) or {}).get('version',0))+1,'checkout_enabled':True})
    cells[definition['id']]=policy.model_dump(mode='json')
    managed=dict(pricing.get('managed_offers') or {})
    managed[definition['id']]={**current,'approved_revision_sha256':revision,'approved_policy_version':policy.version,'approved_at':datetime.now(timezone.utc).isoformat(),
        'published_upgrade_candidate_indexes':[row['candidate_index'] for row in publication_upgrades]}
    parent.pricing_model={**pricing,'commercial_cells':cells,'managed_offers':managed}
    proposal.status='approved';proposal.resolved_at=datetime.utcnow();proposal.resolved_by=str(actor_id)
    await db.flush()
    return {'proposal_id':proposal.id,'status':'approved','published':True,'policy_version':policy.version,
        'cell_id':definition['id'],'curated_segment_id':cell.id}


async def _reviewed_supplier_source_is_current(db,part,proposed,current,reviewed_fingerprint):
    if (not proposed.get('fingerprint')
            or proposed.get('fingerprint')!=reviewed_fingerprint):
        return False
    return (current is not None and _supplier_snapshot_matches_current(proposed,current)
        or await _persisted_supplier_snapshot_is_current(db,part,proposed,current))


async def approve_current_supplier_sources(db,proposal_id,revision,actor_id,source_evidence=None):
    """Persist only exact, fresh supplier facts the operator explicitly reviewed."""
    from app.models.commerce_evidence import PriceQuoteSnapshot
    from app.services.commercial_readiness import product_key
    from app.services.catalogue_price_import import import_current_catalogue_prices
    await db.execute(text('SELECT pg_advisory_xact_lock(61311, 1)'))
    proposal=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.id==proposal_id)
        .with_for_update())).scalar_one_or_none()
    if proposal is None or (proposal.demand_signals or {}).get('source')!=SOURCE:
        raise HTTPException(404,'Generated Playbook proposal not found')
    # A background Playbook rebuild can replace component choices while the
    # operator is reviewing supplier evidence. Keep the review bound to the
    # exact (role, listing, fingerprint) tuple they saw: unchanged captures can
    # still be recorded, while changed/new listings are returned as pending.
    # A proposal revision change alone must not discard the whole review.
    if proposal.status!='pending':
        raise HTTPException(409,'This proposal is no longer pending supplier review')
    parent=(await db.execute(select(Playbook).where(Playbook.id==proposal.playbook_id)
        .with_for_update())).scalar_one()
    cell_id=proposal.proposed_data.get('cell_id')
    definition=next((row for row in definitions()['builds'] if row['id']==cell_id),None)
    if definition is None or parent.name!=definition['segment'] or getattr(parent.status,'value',parent.status)!='active':
        raise HTTPException(409,'The active segment definition changed; refresh the proposal')

    approved=[];pending_roles=[]
    reviewed_fingerprints={(item.get('role'),int(item.get('listing_id') or 0)):item.get('fingerprint')
        for item in (source_evidence or [])}
    for part in proposal.proposed_data.get('components',[]):
        role=part.get('role'); proposed=part.get('source_observation') or {}
        if not proposed:
            pending_roles.append(role);continue
        listing_id=part.get('listing_id')
        listing=await db.get(Listing,listing_id) if listing_id else None
        current=await source_preview(db,listing) if listing else None
        if source_evidence is not None:
            reviewed_fingerprint=reviewed_fingerprints.get((role,int(listing_id or 0)))
            # A saved vendor-ETA default or a harmless representation change
            # (for example "0.00" -> "0") can change a legacy fingerprint.
            # If the operator reviewed this proposal's fingerprint and its
            # exact supplier facts still match the current source preview,
            # retain the review. A changed price, stock state, condition,
            # listing identity or captured postage still fails the snapshot
            # comparison below.
            reviewed_same_snapshot=await _reviewed_supplier_source_is_current(
                db,part,proposed,current,reviewed_fingerprint)
            if (not proposed.get('fingerprint') or not reviewed_fingerprint
                    or ((current or {}).get('fingerprint')!=reviewed_fingerprint and not reviewed_same_snapshot)):
                pending_roles.append(role)
                continue
        review_source=current
        if current is None:
            if await _persisted_supplier_snapshot_is_current(db,part,proposed,current):
                current={};review_source=proposed
            elif source_evidence is not None:
                pending_roles.append(role)
                continue
            else:
                raise HTTPException(409,'A supplier capture changed or disappeared; refresh before approving source evidence')
        if (current.get('fingerprint')!=proposed.get('fingerprint')
                and not _supplier_snapshot_matches_current(proposed,current)
                and not await _persisted_supplier_snapshot_is_current(db,part,proposed,current)):
            # A changed component must not invalidate evidence already reviewed
            # for the other parts in this build. Keep it pending so the UI can
            # report partial progress and load a fresh capture for this role.
            if source_evidence is not None:
                pending_roles.append(role)
                continue
            raise HTTPException(409,'A supplier capture changed; refresh before approving source evidence')
        if current.get('fingerprint')!=proposed.get('fingerprint') and not _supplier_snapshot_matches_current(proposed,current):
            review_source=proposed
        if not _supplier_fact_is_approvable(part,review_source):
            pending_roles.append(role);continue
        source_url=str(review_source.get('url') or '')
        canonical_url=str(part.get('source_url') or '')
        from app.services.commercial_readiness import same_listing_product
        if len(source_url)>500 and same_listing_product(source_url,canonical_url):
            review_source={**review_source,'url':canonical_url}
            review_source['fingerprint']=fingerprint({key:value for key,value in review_source.items()
                if key not in {'fingerprint','fresh'}})
        part_key=(f"case:{part['case_catalogue_id']}" if role=='case' and part.get('case_catalogue_id')
                  else f"variant:{part['variant_id']}")
        approved.append({'role':role,'part_key':part_key,'source':review_source})

    result=await import_current_catalogue_prices(db,[
        {'role':row['role'],'part_key':row['part_key'],'source':row['source']} for row in approved],actor_id)
    if result['blocked']:
        raise HTTPException(409,{'message':'Supplier evidence changed or failed validation','service_work_remaining':result['blocked']})
    audit=PriceQuoteSnapshot(product_key=product_key(parent.id,cell_id),status='evidence_import',
        created_by_admin_id=actor_id,evidence_json={'proposal_id':proposal.id,'revision_sha256':revision,
            'approved_roles':[row['role'] for row in approved],
            'sources':[row['source'] for row in approved]},
        decision_json={'imported_ids':result['imported'],'reused_ids':result['reused'],
            'pending_roles':pending_roles,'checkout_changed':False,'prices_published':False})
    db.add(audit)
    await db.flush()
    return {'proposal_id':proposal.id,'imported':result['imported'],'reused':result['reused'],
        'pending_roles':pending_roles,'audit_id':audit.id,'checkout_changed':False,'prices_published':False}


def _licence_supplier_terms_url(listing):
    host=(urlsplit(str(listing.url or '')).hostname or '').casefold()
    if host in {'gamers-outlet.net','www.gamers-outlet.net'}:
        return 'https://www.gamers-outlet.net/en/terms-and-conditions'
    return 'https://royalcdkeys.com/pages/terms-conditions'


async def approve_royalcdkeys_licence_source(db,listing_id,licence_review_fingerprint,actor_id):
    """Approve an exact software listing for internal Playbook OS catalogue use."""
    from app.models.commerce_evidence import PriceQuoteSnapshot
    from app.models.catalogue import CatalogueVariant, PlaybookSlot
    from app.services.commercial_readiness import source_preview
    listing=(await db.execute(select(Listing).where(Listing.id==listing_id).with_for_update())).scalar_one_or_none()
    if listing is None or listing.source_name not in {'RoyalCDKeys','Gamers Outlet'}:
        raise HTTPException(404,'Software supplier Playbook product not found')
    raw=listing.raw_specs if isinstance(listing.raw_specs,dict) else {}
    capture=raw.get('playbook_product_capture') if isinstance(raw.get('playbook_product_capture'),dict) else {}
    royal=(raw.get('gamers_outlet') or raw.get('royalcdkeys') or {})
    current=await source_preview(db,listing)
    category=royal.get('category')
    if (category not in {'os','office','ai_subscription'} or capture.get('status')!='captured'
            or capture.get('licence_review_required') is not True
            or current is None or not current.get('fresh')
            or current.get('licence_review_fingerprint')!=licence_review_fingerprint):
        raise HTTPException(409,'The exact software licence facts changed or are stale; refresh them before review')
    properties=current.get('product_properties') or {}
    license_type=str(properties.get('License type (supplier listing)') or '').casefold()
    unique_claim=str(properties.get('Key uniqueness (supplier claim)') or '').casefold()
    if category=='os' and (license_type not in {'oem','retail'} or 'not guaranteed' in unique_claim):
        raise HTTPException(409,'This listing does not identify a single-device OEM/Retail offer suitable for Playbook review')
    previous=raw.get('playbook_licence_source_review') or {}
    terms_url=_licence_supplier_terms_url(listing)
    reused=bool(previous.get('reviewed') is True
        and previous.get('licence_review_fingerprint')==licence_review_fingerprint)
    reviewed_at=(previous.get('reviewed_at') if reused else datetime.now(timezone.utc).isoformat())
    if not reused:
        listing.raw_specs={**raw,'playbook_licence_source_review':{
            'reviewed':True,'reviewed_by_admin_id':actor_id,'reviewed_at':reviewed_at,
            'licence_review_fingerprint':licence_review_fingerprint,
            'review_scope':('Operator approved this exact listing as an internal Playbook OS catalogue candidate after reviewing licence type, device scope, activation claims and supplier terms.' if category=='os' else
                'Operator reviewed this exact Office/software subscription supplier listing for possible Playbook merchandising. This review does not approve a customer price, segment inclusion, entitlement, resale authorization or storefront publication.'),
            'product_category':category,
            'terms_url':terms_url}}
    variants=(await db.execute(select(CatalogueVariant,PlaybookSlot.playbook_id)
        .join(PlaybookSlot,PlaybookSlot.id==CatalogueVariant.slot_id)
        .where(CatalogueVariant.listing_id==listing.id,PlaybookSlot.slot_type=='os')
        .with_for_update())).all()
    activated=[]
    for variant,playbook_id in variants:
        if variant.status!='pending_review':
            continue
        variant.status='active'
        variant.reviewed_at=reviewed_at
        variant.reviewed_by=str(actor_id)
        variant.updated_at=reviewed_at
        activated.append({'variant_id':variant.id,'playbook_id':playbook_id})
    supplier_key='gamers_outlet' if listing.source_name=='Gamers Outlet' else 'royalcdkeys'
    audit=PriceQuoteSnapshot(product_key=f'{supplier_key}_licence_source:{listing.id}',
        status='supplier_licence_source_review',created_by_admin_id=actor_id,
        evidence_json={'listing_id':listing.id,'title':listing.title,'source':listing.source_name,
            'source_url':listing.url,'licence_review_fingerprint':licence_review_fingerprint,
            'product_properties':properties,'terms_url':terms_url,
            'activated_catalogue_links':activated,'product_category':category},
        decision_json={'reviewed':True,'licence_entitlement_independently_verified':False,
            'automatic_resale_authorization_claimed':False,'internal_os_catalogue_approved':category=='os',
            'software_source_review_only':category!='os','customer_offering_enabled':False,
            'prices_published':False,'checkout_changed':False})
    db.add(audit)
    await db.flush()
    return {'listing_id':listing.id,'reviewed':True,'reused':reused,'category':category,
        'activated_catalogue_links':len(activated),'audit_id':audit.id,
        'prices_published':False,'checkout_changed':False,'customer_offering_enabled':False}


async def royalcdkeys_licence_candidates(db):
    """Return exact captured RoyalCDKeys OS listings for explicit admin review."""
    from app.models.catalogue import CatalogueVariant, PlaybookSlot
    rows=(await db.execute(select(Listing).where(Listing.source_name.in_(('RoyalCDKeys','Gamers Outlet')))
        .order_by(Listing.title,Listing.id))).scalars().all()
    result=[]
    for listing in rows:
        raw=listing.raw_specs if isinstance(listing.raw_specs,dict) else {}
        capture=raw.get('playbook_product_capture') if isinstance(raw.get('playbook_product_capture'),dict) else {}
        royal=(raw.get('gamers_outlet') or raw.get('royalcdkeys') or {})
        if royal.get('category') not in {'os','office','ai_subscription'} or capture.get('status')!='captured':
            continue
        observation=await source_preview(db,listing)
        if observation is None:
            continue
        variants=(await db.execute(select(CatalogueVariant.status,PlaybookSlot.playbook_id)
            .join(PlaybookSlot,PlaybookSlot.id==CatalogueVariant.slot_id)
            .where(CatalogueVariant.listing_id==listing.id,PlaybookSlot.slot_type=='os')
            .order_by(PlaybookSlot.playbook_id))).all()
        review=raw.get('playbook_licence_source_review') or {}
        result.append({'listing_id':listing.id,'title':listing.title,'url':listing.url,
            'supplier_name':listing.source_name,
            'price_gbp':observation.get('item_gbp'),'image_url':(listing.image_urls or [None])[0],
            'seller_product_claims':capture.get('seller_product_claims'),
            'supplier_handle':capture.get('supplier_product_handle'),
            'digital_product':capture.get('digital_product') is True,
            'licence_review_fingerprint':observation.get('licence_review_fingerprint'),
            'licence_source_reviewed':observation.get('licence_source_reviewed') is True,
            'fresh':observation.get('fresh') is True,'stock_status':observation.get('stock_status'),
            'stock_evidence':observation.get('stock_evidence'),
            'product_properties':observation.get('product_properties') or {},
            'catalogue_statuses':[{'playbook_id':row.playbook_id,'status':row.status} for row in variants],
            'terms_url':_licence_supplier_terms_url(listing),
            'category':royal.get('category'),'customer_offering_enabled':False})
    return result


async def approve_all_current_supplier_sources(db,expected_proposals,actor_id):
    """Batch-review only current proposal IDs and the exact source facts shown."""
    await db.execute(text('SELECT pg_advisory_xact_lock(61311, 1)'))
    rows=await current_proposals(db)
    expected={item['proposal_id']:item for item in expected_proposals}
    actual={row['proposal_id']:row for row in rows}
    if not expected:
        raise HTTPException(422,'Select at least one proposal for supplier review')
    # The scheduled Playbook thread can add, resolve or replace proposals while
    # the review page is open. Review the still-pending IDs only; exact role,
    # listing and capture fingerprints below prevent stale/new facts from being
    # approved. Missing IDs are reported instead of cancelling the whole batch.
    current=[row for row in rows if row['proposal_id'] in expected]
    totals={'proposals':len(current),'skipped_proposals':len(expected)-len(current),
        'imported':0,'reused':0,'pending_roles':[],'prices_published':False}
    for row in current:
        result=await approve_current_supplier_sources(db,row['proposal_id'],row['revision_sha256'],actor_id,
            expected[row['proposal_id']].get('source_evidence'))
        totals['imported']+=result['imported']
        totals['reused']+=result['reused']
        totals['pending_roles'].extend({'cell_id':row['cell_id'],'role':role} for role in result['pending_roles'])
    return totals


async def refresh_playbooks(db,actor_id=0,progress=None,*,catalogue_sync=None, maintain_live_offers=True,
        resolve_missing=True, cell_ids=None, defer_compatibility=True):
    import asyncio
    if cell_ids is not None and (not cell_ids or set(cell_ids)-{row['id'] for row in definitions()['builds']}):
        raise HTTPException(422,'Choose existing Playbook cell IDs to rebuild')
    await db.execute(text('SELECT pg_advisory_xact_lock(61311, 1)'))
    if progress: progress('Linking captured catalogue products')
    sync=catalogue_sync if catalogue_sync is not None else await sync_bestseller_catalogues(db)
    from app.services.catalogue_cpk import reconcile_active_catalogue_cpks
    cpk_reconciliation=await reconcile_active_catalogue_cpks(db,allow_model_extraction=resolve_missing)
    sync={**sync,'catalogue_cpk':cpk_reconciliation}
    parents={row.name:row for row in (await db.execute(select(Playbook).where(Playbook.status=='active'))).scalars().all()}
    settings=await db.get(AppSettings,1)
    from app.services.hardware_performance import load_benchmark_context
    benchmark_index,_=await load_benchmark_context(db)
    paid_sales=await paid_component_sales(db)
    pools={};offers=[];source_cache={};prepared=set();compatibility_tasks=[];compatibility_proposals={}
    compatibility_slots=asyncio.Semaphore(3)
    async def review_offer(offer):
        async with compatibility_slots:
            try:
                from app.services.compatibility_llm_review import review_compatibility_evidence
                return await review_compatibility_evidence(offer)
            except Exception as error:
                return {'status':'review_unavailable',
                    'summary':f'Local compatibility review unavailable ({type(error).__name__}); deterministic checks remain in force.',
                    'checks':[],'authority':'advisory_only'}
    for definition in definitions()['builds']:
        if cell_ids is not None and definition['id'] not in cell_ids:
            continue
        parent=parents.get(definition['segment'])
        if parent is None:
            raise HTTPException(409,f"Automatic Playbook bootstrap needs the {definition['segment']} segment")
        if parent.id not in pools:
            if progress: progress(f"Loading {parent.name} catalogue candidates")
            pools[parent.id]=await _catalogue_candidates(db,parent.id,'curated',source_cache)
        if parent.id not in prepared:
            # Exact-source validation is preparation, not publication authority.
            # Keep commercial evidence imports behind the existing live policy.
            pools[parent.id]=await prepare_candidates(db,parent,pools[parent.id],
                reconcile_prices=maintain_live_offers and mvp_enabled(parent))
            prepared.add(parent.id)
        if progress: progress(f"Rechecking {definition['id']} compatibility and delivery prices")
        offer=await build_cell_offer(db,definition,parent,settings,pools[parent.id],benchmark_index,paid_sales)
        offer=await _stock_replacements(db,offer,parent,pools[parent.id])
        history=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.playbook_id==parent.id,
            PlaybookProposal.action=='UPDATE').order_by(PlaybookProposal.id.desc()))).scalars().all()
        previous=next((row for row in history if (row.demand_signals or {}).get('source')==SOURCE
            and (row.proposed_data or {}).get('cell_id')==definition['id']),None)
        unchanged=bool(previous and (previous.proposed_data or {}).get('revision_sha256')==offer['revision_sha256'])
        if unchanged and previous.status!='pending':
            offers.append(offer)
            continue
        from app.services.compatibility_llm_review import compatibility_evidence_fingerprint
        cached_review=(previous.proposed_data or {}).get('compatibility_review') if previous else None
        reuse_review=bool(cached_review and cached_review.get('validation_version') in {8,9} and (defer_compatibility
            or cached_review.get('status') not in {'review_unavailable','review_pending'})
            and compatibility_evidence_fingerprint(previous.proposed_data)==compatibility_evidence_fingerprint(offer))
        if reuse_review:
            from app.services.compatibility_llm_review import validate_compatibility_review
            offer['compatibility_review']=validate_compatibility_review(offer,cached_review)
            if unchanged and previous.status=='pending':
                previous.proposed_data=deepcopy(offer)
                offers.append(offer)
                continue
        # Every pending proposal receives a local LLM cross-check during the
        # scheduled Playbook thread. The annotation is deliberately added after
        # the commercial revision is calculated, so model wording cannot change
        # approval fingerprints or commercial eligibility.
        if not reuse_review:
            if progress: progress(f"Queueing local LLM compatibility review for {definition['id']} (including motherboard-to-case fit)")
            offer['compatibility_review']={'status':'review_pending','summary':'Local compatibility assessment is running.',
                'checks':[],'authority':'advisory_only'}
            if not defer_compatibility:
                compatibility_tasks.append((offer,asyncio.create_task(review_offer(offer))))
        from app.services.playbook_book import record_cell_event
        old_offer=(previous.proposed_data or {}) if previous else {}
        def audit_state(value):
            return {key:value.get(key) for key in ('revision_sha256','components','delivery_products','blockers','availability_replacements')}
        record_cell_event(db,definition['id'],'proposal_recalculated',
            ('Unavailable or inactive build components triggered active-catalogue replacements and full Playbook revalidation'
                if offer.get('availability_replacements') else
                'Catalogue refresh recalculated selected products, prices and blockers; no live offer was changed'),
            audit_state(old_offer),audit_state(offer),actor_id)
        existing=previous if previous and previous.status=='pending' else None
        if existing is None:
            existing=PlaybookProposal(playbook_id=parent.id,action='UPDATE',status='pending',
                reason=('Availability replacement candidate; compatibility, exact source, pricing and publication rules rechecked'
                    if offer.get('availability_replacements') else
                    'Automatically assembled from the curated catalogue and exact source listings'),
                proposed_data=deepcopy(offer),demand_signals={'source':SOURCE})
            db.add(existing)
        else:
            # Keep a separate immutable-before-review snapshot. Sharing the
            # same dict lets the later LLM mutation also mutate SQLAlchemy's
            # remembered old JSON value, so its final assignment is not
            # detected and the saved review remains review_pending.
            existing.proposed_data=deepcopy(offer)
            if offer.get('availability_replacements'):
                existing.reason='Availability replacement candidate; compatibility, exact source, pricing and publication rules rechecked'
        compatibility_proposals[id(offer)]=existing
        offers.append(offer)
    if compatibility_tasks:
        async def keep_database_connection_alive():
            # Local compatibility reviews can queue for several minutes. Keep
            # the proposal transaction's pooled connection active while the
            # model runs so PostgreSQL/proxy idle-connection expiry cannot
            # discard all proposal updates after successful reviews.
            while True:
                await asyncio.sleep(20)
                await db.execute(text('SELECT 1'))
        keepalive=asyncio.create_task(keep_database_connection_alive())
        try:
            results=await asyncio.gather(*(task for _,task in compatibility_tasks))
        finally:
            keepalive.cancel()
            try:
                await keepalive
            except asyncio.CancelledError:
                pass
        for (offer,_),review in zip(compatibility_tasks,results):
            offer['compatibility_review']=review
            # SQLAlchemy JSON columns do not track nested in-place changes.
            # Reassign the completed snapshot so the advisory result does not
            # remain permanently stuck at review_pending in the saved proposal.
            proposal=compatibility_proposals.get(id(offer))
            if proposal is not None:
                proposal.proposed_data=deepcopy(offer)
    await db.flush()
    if resolve_missing and not maintain_live_offers:
        from app.services.playbook_requirement_catalogue import link_missing_requirements
        repairs=await link_missing_requirements(db,offers)
        if repairs['linked']:
            if progress: progress(f"Linked {repairs['linked']} required supplier products; rebuilding complete drafts")
            result=await refresh_playbooks(db,actor_id,progress=progress,catalogue_sync=sync,
                maintain_live_offers=False,resolve_missing=False,cell_ids=cell_ids)
            result['requirement_repairs']=repairs
            return result
    from app.services.playbook_mvp import maintain_offers
    maintenance=(await maintain_offers(db,parents,offers) if maintain_live_offers else
        {'published':[], 'paused':[], 'exceptions':[], 'skipped':'proposal_only_rebuild'})
    return {'maintenance':maintenance,'catalogue_sync':sync,'cells':len(offers),'complete_hardware':sum(row['complete_hardware'] for row in offers),
        'ready_for_approval':sum(not row['blockers'] for row in offers),'offers':offers}


async def current_proposals(db):
    rows=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.action=='UPDATE',
        PlaybookProposal.status=='pending').order_by(PlaybookProposal.id.desc()))).scalars().all()
    now=_utcnow()
    recent=(await db.execute(select(Order.specs,Order.created_at,Order.stripe_payment_intent_id)
        .where(Order.created_at>=now-timedelta(days=60),Order.created_at<=now,
            Order.status!=OrderStatus.CANCELLED,Order.refund_id.is_(None))
        .order_by(Order.created_at.desc()))).all()
    sales_by_cell={}
    for specs,created_at,payment_intent_id in recent:
        if not isinstance(specs,dict):
            continue
        payment=specs.get('payment_evidence') if isinstance(specs.get('payment_evidence'),dict) else {}
        if payment.get('status')!='succeeded' and not payment_intent_id:
            continue
        cell_id=str(specs.get('curated_build_id') or '').strip()
        if not cell_id:
            continue
        item=sales_by_cell.setdefault(cell_id,{'last_30_days':0,'previous_30_days':0,
            'delivery_options':{'fast_track':0,'standard':0,'flexible':0},'last_paid_order_at':None})
        age=now-created_at
        if age<=timedelta(days=30):
            item['last_30_days']+=1
        else:
            item['previous_30_days']+=1
        quote=specs.get('commercial_quote') if isinstance(specs.get('commercial_quote'),dict) else {}
        mode=str(specs.get('delivery_option') or quote.get('delivery_option') or '').casefold()
        if mode in item['delivery_options']:
            item['delivery_options'][mode]+=1
        if item['last_paid_order_at'] is None:
            item['last_paid_order_at']=created_at.replace(tzinfo=timezone.utc).isoformat()
    journey_rows=(await db.execute(select(AnalyticsEvent.event_name,AnalyticsEvent.session_id,
        AnalyticsEvent.properties).where(AnalyticsEvent.source=='curated_journey',
        AnalyticsEvent.occurred_at>=now-timedelta(days=30)))).all()
    journey_by_cell={}
    event_metric={'curated_build_view':'view_sessions','component_selected':'configured_sessions',
        'case_selected':'configured_sessions','build_added_to_cart':'cart_sessions',
        'checkout_started':'checkout_sessions'}
    for event_name,session,properties in journey_rows:
        cell_id=(properties or {}).get('curated_build_id') if isinstance(properties,dict) else None
        metric=event_metric.get(event_name)
        if not cell_id or not metric or not session:
            continue
        item=journey_by_cell.setdefault(cell_id,{'view_sessions':set(),'configured_sessions':set(),
            'cart_sessions':set(),'checkout_sessions':set()})
        item[metric].add(session)
    journey_counts={cell_id:{key:len(sessions) for key,sessions in metrics.items()}
        for cell_id,metrics in journey_by_cell.items()}
    positions={row['id']:index for index,row in enumerate(definitions()['builds'])}
    items=[{'proposal_id':row.id,**row.proposed_data} for row in rows
        if (row.demand_signals or {}).get('source')==SOURCE]
    for item in items:
        item['storefront_sales']=sales_by_cell.get(item['cell_id'],{
            'last_30_days':0,'previous_30_days':0,
            'delivery_options':{'fast_track':0,'standard':0,'flexible':0},'last_paid_order_at':None})
        item['consented_journey']=journey_counts.get(item['cell_id'],{
            'view_sessions':0,'configured_sessions':0,'cart_sessions':0,'checkout_sessions':0})
    return sorted(items,key=lambda row:positions.get(row['cell_id'],10000))


async def list_motherboard_engineering_suggestions(db):
    """Expose only Playbook-linked, unreviewed research for operator review."""
    rows=(await db.execute(select(MotherboardSpec).where(MotherboardSpec.source.in_(('ai_generated','manufacturer_capture','listing_title')),
        MotherboardSpec.reviewed.is_(False)).order_by(MotherboardSpec.id))).scalars().all()
    suggestions=[]
    for row in rows:
        evidence=row.raw_ai_response if isinstance(row.raw_ai_response,dict) else {}
        if not evidence.get('playbook_source_url') or not evidence.get('playbook_source_title'):
            continue
        manufacturer=evidence.get('manufacturer_source_capture') or {}
        suggestions.append({'id':row.id,'canonical_model':row.canonical_model,'brand':row.brand,
            'socket':row.socket,'ram_type':row.ram_type,'ram_slots':row.ram_slots,
            'max_ram_gb':row.max_ram_gb,'form_factor':row.form_factor,
            'chipset':row.chipset,'m2_slots':row.m2_slots,'sata_ports':row.sata_ports,
            'source_title':evidence['playbook_source_title'],'source_url':evidence['playbook_source_url'],
            'manufacturer_source_url':manufacturer.get('source_url'),
            'manufacturer_source_title':manufacturer.get('source_title'),
            'manufacturer_source_captured_at':manufacturer.get('captured_at'),
            'manufacturer_facts_captured':bool(manufacturer.get('facts')),
            'listing_title_facts_captured':bool((evidence.get('listing_title_fact_capture') or {}).get('facts')),
            'source_basis':evidence.get('research_basis')})
    return suggestions


_PLAYBOOK_ENGINEERING_FIELDS={
    'cpu': {'socket':('socket','cpu socket'),'power_w':('tdp','processor base power','thermal design power')},
    'motherboard': {'socket':('cpu socket','processor socket'),'ram_type':('memory type','supported memory','system memory type','ram memory technology'),
        'ram_slots':('memory slots','number of memory slots','available memory slots'),'form_factor':('form factor','motherboard form factor'),
        'm2_slots':('m.2 slots','m.2 socket count'),'sata_ports':('sata ports','sata connectors','total sata ports')},
    'gpu': {'length_mm':('graphics card length','gpu length','card length'),
        'gpu_interface':('graphics card interface','gpu interface','pci express interface'),
        'power_w':('graphics card power','gpu power','total graphics power')},
    'ram': {'ram_type':('memory technology','memory type'),'ram_modules':('number of modules','memory modules'),
        'ram_height_mm':('memory module height','ram height')},
    'cooling': {'supported_sockets':('socket compatibility','supported cpu sockets'),
        'height_mm':('cooler height','heatsink height'),'radiator_mm':('radiator size','radiator length'),
        'ram_clearance_mm':('ram clearance','memory clearance'),
        'front_radiator_depth_mm':('front radiator thickness','front radiator depth')},
    'psu': {'wattage':('wattage','maximum power','power output','rated power'),'form_factor':('power supply form factor','psu form factor'),
        'length_mm':('power supply length','psu length'),'psu_connectors':('power connectors','connector configuration')},
    'storage': {'storage_interface':('interface','storage interface'),'m2_length':('m.2 form factor','m.2 length')},
    'storage_secondary': {'storage_interface':('interface','storage interface'),'m2_length':('m.2 form factor','m.2 length')},
    'case': {'max_gpu_length_mm':('maximum gpu length','maximum graphics card length'),
        'max_cooler_height_mm':('maximum cpu cooler height','maximum cooler height'),
        'max_psu_length_mm':('maximum power supply length','maximum psu length')},
}

# These are the same typed fields consumed by studio_fit's reviewed records.
# Only explicitly labelled source values may enter a suggestion.
_PLAYBOOK_ENGINEERING_FIELDS['cpu']['cpu_id']=('cpu id','processor model number')
_PLAYBOOK_ENGINEERING_FIELDS['cpu']['integrated_graphics']=('integrated graphics','processor graphics included')
_PLAYBOOK_ENGINEERING_FIELDS['cooling']['cooling_capacity_w']=('cooling capacity','rated cooling capacity')
_PLAYBOOK_ENGINEERING_FIELDS['motherboard'].update({
    'gpu_interfaces':('graphics card interface','gpu interface','pci express interface'),
    'storage_interfaces':('supported storage interfaces',),
    'm2_lengths':('supported m.2 lengths',),
    'bios_cpu_ids':('bios supported cpu ids',),
})
_PLAYBOOK_ENGINEERING_FIELDS['gpu']['gpu_power_connectors']=('required power connectors','gpu power connectors')
_PLAYBOOK_ENGINEERING_FIELDS['case'].update({
    'psu_form_factors':('supported psu form factors',),
    'supported_form_factors':('supported motherboard form factors',),
    'sata_bays':('sata drive bays',),
})


def _structured_engineering_value(target,value):
    """Parse explicit source lists/counts without guessing omitted capabilities."""
    if target in {'psu_connectors','gpu_power_connectors'}:
        connectors={}
        aliases={'8-pin':'8pin','6-pin':'6pin','12vhpwr':'12vhpwr','12v-2x6':'12v2x6'}
        for item in re.split(r'\s*[;,]\s*',value):
            match=re.fullmatch(r'(\d+)\s*[x×]\s*(8-pin|6-pin|12vhpwr|12v-2x6)',item.strip(),re.I)
            if not match:return None
            key=aliases[match.group(2).casefold()]
            if key in connectors:return None
            connectors[key]=int(match.group(1))
        return connectors or None
    items=[item.strip() for item in re.split(r'\s*[;,]\s*',value)]
    if not items or any(not item for item in items):return None
    if target=='m2_lengths':
        return [int(item) for item in items] if all(re.fullmatch(r'\d{4,5}',item) for item in items) else None
    if target in {'gpu_interface','gpu_interfaces'}:
        if all(re.search(r'(?i)\bPCI\s*[- ]?(?:Express|e)\b',item) for item in items):
            return 'pcie' if target=='gpu_interface' else ['pcie']
        return None
    if target=='storage_interfaces':
        return [item.casefold() for item in items] if all(item.casefold() in {'nvme','sata'} for item in items) else None
    if target in {'psu_form_factors','supported_form_factors'}:
        return [item.casefold() for item in items] if all(item.casefold() in {'atx','matx','itx','sfx','sfx-l','e-atx'} for item in items) else None
    if target in {'cpu_id','bios_cpu_ids'}:
        if not all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}',item) for item in items):return None
        return items[0] if target=='cpu_id' and len(items)==1 else items if target=='bios_cpu_ids' else None
    return None


def _source_engineering_values(role,properties,title=None,*,conflicts=None):
    """Extract only explicitly labelled catalogue-page values; never infer fit facts."""
    import re
    fields=_PLAYBOOK_ENGINEERING_FIELDS.get(role,{})
    source_maps=properties if isinstance(properties,list) else [properties]
    by_label={}
    for source_map in source_maps:
        for label,value in (source_map or {}).items():
            if value is None:continue
            normalized=re.sub(r'[^a-z0-9.]+',' ',str(label).casefold()).strip()
            by_label.setdefault(normalized,[]).extend(str(item).strip()
                for item in (value if isinstance(value,list) else [value]))
    result={}
    ambiguous=set()
    numeric={'power_w','length_mm','height_mm','radiator_mm','ram_clearance_mm','ram_slots','ram_modules','m2_slots','sata_bays','sata_ports','wattage','cooling_capacity_w','m2_length','ram_height_mm','front_radiator_depth_mm','max_gpu_length_mm','max_cooler_height_mm','max_psu_length_mm'}
    for target,labels in fields.items():
        values=[value for label in labels for value in by_label.get(label,[]) if value]
        if target=='socket':
            values=[re.sub(r'\s+','',re.sub(r'(?i)^socket\s+','',value)).casefold() for value in values]
        elif target=='ram_type':
            values=[re.sub(r'(?i)\s+SDRAM$','',value).replace(' ','').casefold() for value in values]
        elif target in {'storage_interface','form_factor'}:
            aliases={'micro-atx':'matx','micro atx':'matx','m-atx':'matx','mini-itx':'itx'} if target=='form_factor' else {}
            values=[aliases.get(value.casefold(),value.casefold()) for value in values]
        elif target in numeric:
            normalized=[]
            for value in values:
                number=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(?:w|watts?|mm|slots?|modules?|ports?)?\s*',value,re.I)
                normalized.append(format(Decimal(number.group(1)).normalize(),'f') if number else value)
            values=normalized
        if len(set(values))!=1:
            if values:ambiguous.add(target)
            continue
        value=values[0]
        if target=='integrated_graphics':
            if value.casefold() in {'yes','true','included'}:result[target]=True
            elif value.casefold() in {'no','false','none','not included'}:result[target]=False
        elif target in numeric:
            match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(?:w|watts?|mm|slots?|modules?|ports?)?\s*',value,re.I)
            if not match: continue
            number=float(match.group(1))
            if not number.is_integer(): continue
            result[target]=int(number)
        elif target in {'socket','ram_type','storage_interface','form_factor'}:
            if target=='socket':value=re.sub(r'(?i)^socket\s+','',value)
            if target=='ram_type':value=re.sub(r'(?i)\s+SDRAM$','',value)
            match={'socket':r'(?i)(?:AM[2345]|sTRX4|sTR5|LGA\s*\d{4,5})',
                'ram_type':r'(?i)DDR[345]', 'storage_interface':r'(?i)(?:NVMe|SATA)',
                'form_factor':r'(?i)(?:ATX|micro-ATX|mATX|mini-ITX|E-ATX|SFX-L?|ATX12VO)'}[target]
            found=re.fullmatch(match,value)
            if found:
                canonical=found.group(0).replace(' ','').casefold()
                if target=='form_factor': canonical={'micro-atx':'matx','mini-itx':'itx','sfx':'sfx','sfx-l':'sfx-l'}.get(canonical,canonical)
                result[target]=canonical
        elif target=='supported_sockets':
            matches=re.findall(r'(?i)(?:AM[2345]|sTRX4|sTR5|LGA\s*\d{4,5})',value)
            if matches and len(matches)<=12: result[target]=list(dict.fromkeys(item.replace(' ','').casefold() for item in matches))
        elif target in {'gpu_interface','gpu_interfaces','psu_connectors','gpu_power_connectors','storage_interfaces','m2_lengths',
                'bios_cpu_ids','cpu_id','psu_form_factors','supported_form_factors'}:
            parsed=_structured_engineering_value(target,value)
            if parsed is not None:result[target]=parsed
    title=str(title or '')
    title_values={}
    if role=='cpu':
        sockets=set(re.findall(r'(?i)\b(AM[2345]|LGA\s*\d{4,5})\s*(?:socket)?\b',title))
        powers=set(re.findall(r'(?i)\b(\d{2,3})\s*W\s*TDP\b',title))
        if len(sockets)==1:title_values['socket']=next(iter(sockets)).replace(' ','').casefold()
        if len(powers)==1:title_values['power_w']=int(next(iter(powers)))
        if re.search(r'(?i)\b(?:no|without)\s+(?:integrated\s+)?(?:radeon\s+)?graphics\b|\b(?:integrated\s+)?(?:radeon\s+)?graphics\s+not\s+included\b',title):
            title_values['integrated_graphics']=False
        elif re.search(r'(?i)\bintegrated\s+(?:radeon\s+)?graphics\b|\b(?:radeon\s+)?graphics\s+included\b',title):
            title_values['integrated_graphics']=True
    elif role=='motherboard':
        from app.services.motherboard_spec_ai import title_verified_motherboard_facts
        verified=title_verified_motherboard_facts(title)
        title_values={key:value for key,value in verified.items()
            if key in {'socket','ram_type','ram_slots','form_factor','m2_slots','sata_ports'}}
    elif role=='ram':
        types=set(re.findall(r'(?i)\bDDR[345]\b',title))
        modules=set(re.findall(r'(?i)\b(\d+)\s*[x×]\s*\d+\s*GB\b',title))
        if len(types)==1:title_values['ram_type']=next(iter(types)).casefold()
        if len(modules)==1:title_values['ram_modules']=int(next(iter(modules)))
    elif role in {'storage','storage_secondary'}:
        lengths=set(re.findall(r'(?i)\bM\.2\s*(\d{4})\b',title))
        interfaces=set(re.findall(r'(?i)\b(NVMe|SATA)\b',title))
        if len(lengths)==1:title_values['m2_length']=int(next(iter(lengths)))
        if len(interfaces)==1:title_values['storage_interface']=next(iter(interfaces)).casefold()
    elif role=='psu':
        watts=set(re.findall(r'(?i)\b(\d{3,4})\s*W\b',title))
        if len(watts)==1:title_values['wattage']=int(next(iter(watts)))
    elif role=='cooling' and re.search(r'(?i)\b(?:socket|compatible|compatibility|supports?)\b',title):
        sockets=list(dict.fromkeys(item.replace(' ','').casefold() for item in
            re.findall(r'(?i)\b(?:AM[2345]|LGA\s*\d{4,5})\b',title)))
        if sockets:title_values['supported_sockets']=sockets
    elif role=='gpu':
        lengths=set(re.findall(r'(?i)\b(?:graphics card|gpu|card)\s+length\s*[:=]?\s*(\d{2,3})\s*mm\b',title))
        if len(lengths)==1:title_values['length_mm']=int(next(iter(lengths)))
    elif role=='case':
        gpu=set(re.findall(r'(?i)\b(?:max(?:imum)?\s+)?(?:graphics card|gpu)\s+length\s*[:=]?\s*(\d{2,3})\s*mm\b',title))
        cooler=set(re.findall(r'(?i)\b(?:max(?:imum)?\s+)?(?:cpu\s+)?cooler\s+height\s*[:=]?\s*(\d{2,3})\s*mm\b',title))
        if len(gpu)==1:title_values['max_gpu_length_mm']=int(next(iter(gpu)))
        if len(cooler)==1:title_values['max_cooler_height_mm']=int(next(iter(cooler)))
    if role=='gpu' and re.search(r'(?i)\bPCI(?:[- ]?Express|e)\b',title):
        title_values['gpu_interface']='pcie'
    if role=='motherboard' and re.search(r'(?i)\bPCI(?:[- ]?Express|e)\s*[0-9.]*\s*x\s*16\b',title):
        title_values['gpu_interfaces']=['pcie']
    for key,value in title_values.items():
        if key in ambiguous:continue
        if key in result and result[key]!=value:
            result.pop(key)
            ambiguous.add(key)
        else:result.setdefault(key,value)
    if conflicts is not None:conflicts.update(ambiguous)
    return result


def _playbook_engineering_suggestion(listing,role):
    import hashlib,json
    raw=listing.raw_specs if isinstance(listing.raw_specs,dict) else {}
    capture=raw.get('playbook_product_capture') if isinstance(raw.get('playbook_product_capture'),dict) else {}
    engineering_capture=(raw.get('playbook_product_engineering_capture')
        if isinstance(raw.get('playbook_product_engineering_capture'),dict) else {})
    engineering_capture_matches=(engineering_capture.get('url')==listing.url
        and isinstance(engineering_capture.get('product_properties'),dict))
    commercial_capture_matches=(capture.get('status')=='captured' and capture.get('url')==listing.url)
    capture_matches=engineering_capture_matches or commercial_capture_matches
    retailer_properties=(engineering_capture.get('product_properties') if engineering_capture_matches
        and engineering_capture.get('product_properties') else
        capture.get('product_properties') if commercial_capture_matches
        and isinstance(capture.get('product_properties'),dict) else {})
    catalog_capture=raw.get('playbook_amazon_catalog_capture') if isinstance(raw.get('playbook_amazon_catalog_capture'),dict) else {}
    catalog_properties=_amazon_catalog_engineering_properties(catalog_capture,role,listing.url)
    source_title=(engineering_capture.get('title') if engineering_capture_matches else None) or (
        capture.get('title') if capture.get('url')==listing.url else None) or listing.title
    conflicts=set()
    values=_source_engineering_values(role,[retailer_properties,catalog_properties],source_title,conflicts=conflicts)
    current=raw.get('configurator') or {}
    changes={key:{'reviewed':current[key],'captured':value} for key,value in values.items()
        if key in current and current[key]!=value} if current.get('reviewed') is True or current.get('review_invalidation') else {}
    required_fields=set(_PLAYBOOK_ENGINEERING_FIELDS.get(role,{}))
    evidence={'listing_id':listing.id,'role':role,'source_url':listing.url,
        'source_title':source_title,'captured_at':(
            engineering_capture.get('observed_at') if engineering_capture_matches else capture.get('observed_at')),
        'retailer_properties':retailer_properties,'amazon_catalog_properties':catalog_properties,
        'amazon_catalog_capture':catalog_capture,'suggested_specs':values,
        'missing_fields':sorted(required_fields-set(values)),
        'capture_status':('captured' if commercial_capture_matches else
            capture.get('status') if capture.get('url')==listing.url else 'not_captured_for_current_url'),
        'conflicted_fields':sorted(conflicts),'reviewed_value_changes':changes}
    fingerprint=hashlib.sha256(json.dumps(evidence,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    status=('source_conflict' if conflicts else 'review_ready' if values else
            'needs_source_facts' if capture_matches else 'needs_product_capture')
    return {**evidence,'status':status,
        'properties':{'retailer':retailer_properties,'amazon_catalog':catalog_properties},'fingerprint':fingerprint}


def invalidate_conflicting_product_engineering(listing,role):
    """Retain the operator's old review in history, but stop certifying changed facts."""
    raw=dict(listing.raw_specs or {});current=raw.get('configurator') or {}
    if current.get('reviewed') is not True:return False
    independent_product_review=(current.get('source_reference_kind')=='owner_reviewed_exact_product'
        and current.get('reviewed_by')=='owner:approved-release-supplier'
        and current.get('reviewed_product_title')==listing.title)
    if current.get('source_url') and current['source_url']!=listing.url and not independent_product_review:
        changes={'source_url':{'reviewed':current['source_url'],'captured':listing.url}}
        conflicting=set()
        source_fingerprint=fingerprint({'listing_id':listing.id,'changed_source_url':changes})
    else:
        suggestion=_playbook_engineering_suggestion(listing,role)
        if not suggestion:return False
        conflicting=set(suggestion['conflicted_fields']).intersection(current)
        changes=suggestion['reviewed_value_changes']
        if not conflicting and not changes:return False
        source_fingerprint=suggestion['fingerprint']
    history=list(raw.get('configurator_review_history') or [])
    history.append({'review':deepcopy(current),'superseded_by_source_fingerprint':source_fingerprint,
        'invalidated_at':datetime.now(timezone.utc).isoformat()})
    raw['configurator_review_history']=history
    raw['configurator']={**current,'reviewed':False,'review_invalidation':{
        'source_fingerprint':source_fingerprint,'conflicted_fields':sorted(conflicting),
        'reviewed_value_changes':changes}}
    listing.raw_specs=raw
    return True


def _amazon_catalog_engineering_properties(capture,role,listing_url):
    """Keep whitelisted labelled SP-API attributes; never treat item/package dimensions as fit data."""
    import re
    from urllib.parse import urlsplit
    match=re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)',urlsplit(listing_url).path,re.I)
    if (capture.get('status')!='captured' or not match
            or capture.get('url')!=listing_url or str(capture.get('asin','')).upper()!=match.group(1).upper()):
        return {}
    aliases={
        'cpu':{'cpu_socket':'CPU Socket','processor_socket':'Processor Socket','socket_type':'Socket',
            'thermal_design_power':'TDP','tdp':'TDP','processor_base_power':'Processor Base Power'},
        'motherboard':{'cpu_socket':'CPU Socket','processor_socket':'Processor Socket','socket_type':'Socket',
            'memory_type':'Memory Type','ram_type':'Memory Type','form_factor':'Form Factor',
            'number_of_memory_slots':'Memory Slots','memory_slots':'Memory Slots','m2_slots':'M.2 Slots'},
        'gpu':{'graphics_card_length':'Graphics Card Length','gpu_length':'GPU Length'},
        'ram':{'memory_technology':'Memory Technology','memory_type':'Memory Type','number_of_memory_modules':'Number of Modules',
            'module_count':'Number of Modules','memory_module_height':'Memory Module Height'},
        'cooling':{'socket_compatibility':'Socket Compatibility','compatible_sockets':'Supported CPU Sockets',
            'cpu_cooler_height':'Cooler Height','cooler_height':'Cooler Height','radiator_size':'Radiator Size',
            'ram_clearance':'RAM Clearance'},
        'psu':{'wattage':'Wattage','rated_power':'Rated Power','psu_form_factor':'Power Supply Form Factor',
            'power_supply_length':'Power Supply Length'},
        'storage':{'storage_interface':'Storage Interface','interface':'Interface','m2_length':'M.2 Length','m2_size':'M.2 Form Factor'},
        'storage_secondary':{'storage_interface':'Storage Interface','interface':'Interface','m2_length':'M.2 Length','m2_size':'M.2 Form Factor'},
        'case':{'maximum_gpu_length':'Maximum GPU Length','max_gpu_length':'GPU Length','maximum_graphics_card_length':'Maximum Graphics Card Length',
            'maximum_cpu_cooler_height':'Maximum CPU Cooler Height','max_cooler_height':'Maximum Cooler Height',
            'maximum_power_supply_length':'Maximum Power Supply Length'},
    }.get(role,{})
    attributes=capture.get('attributes') if isinstance(capture.get('attributes'),dict) else {}
    result={}
    def values(node):
        if isinstance(node,list):return [value for item in node for value in values(item)]
        if not isinstance(node,dict):return [str(node)] if isinstance(node,(str,int,float)) else []
        if 'value' in node:
            value=node.get('value')
            if not isinstance(value,(str,int,float)):return []
            unit=node.get('unit') or node.get('unit_of_measure')
            if isinstance(unit,dict):unit=unit.get('value')
            unit={'millimeters':'mm','millimeter':'mm','watts':'W','watt':'W'}.get(str(unit).casefold(),unit)
            return [f'{value} {unit}' if unit else str(value)]
        return []
    for key,label in aliases.items():
        raw=attributes.get(key)
        found=list(dict.fromkeys(values(raw)))
        if found:result[label]=', '.join(found)
    return result


async def list_playbook_product_engineering_suggestions(db):
    """Return exact selected product facts requiring an operator compatibility review."""
    from app.models.listing import Listing
    proposals=await current_proposals(db)
    roles={}
    for proposal in proposals:
        for part in proposal.get('components',[]):
            if part.get('listing_id') and part.get('role') in _PLAYBOOK_ENGINEERING_FIELDS:
                roles.setdefault(part['listing_id'],part['role'])
        for upgrade in proposal.get('upsells',[]):
            part=upgrade.get('component') or {}
            if part.get('listing_id') and part.get('role') in _PLAYBOOK_ENGINEERING_FIELDS:
                roles.setdefault(part['listing_id'],part['role'])
    if not roles:return []
    listings=(await db.execute(select(Listing).where(Listing.id.in_(roles)).order_by(Listing.id))).scalars().all()
    suggestions=[]
    for listing in listings:
        suggestion=_playbook_engineering_suggestion(listing,roles[listing.id])
        current=(listing.raw_specs or {}).get('configurator') or {}
        if (suggestion['status']=='review_ready' and not suggestion['conflicted_fields']
                and current.get('reviewed') is True and current.get('source_url')==suggestion['source_url']
                and all(current.get(key)==value for key,value in suggestion['suggested_specs'].items())):
            continue
        suggestions.append(suggestion)
    return suggestions


async def approve_playbook_product_engineering(db,listing_id,fingerprint,actor,*,replace_reviewed_values=False):
    from fastapi import HTTPException
    from app.models.listing import Listing
    listing=(await db.execute(select(Listing).where(Listing.id==listing_id).with_for_update()
        .execution_options(populate_existing=True))).scalar_one_or_none()
    if listing is None:raise HTTPException(404,'Playbook catalogue product not found')
    roles={}
    for proposal in await current_proposals(db):
        for part in proposal.get('components',[]):
            if part.get('listing_id'):roles.setdefault(part['listing_id'],part.get('role'))
        for upgrade in proposal.get('upsells',[]):
            part=upgrade.get('component') or {}
            if part.get('listing_id'):roles.setdefault(part['listing_id'],part.get('role'))
    suggestion=_playbook_engineering_suggestion(listing,roles.get(listing_id,''))
    if not suggestion or suggestion['status']!='review_ready' or not suggestion['suggested_specs']:
        raise HTTPException(409,'No exact source-backed engineering facts are available to approve; collect the product or manufacturer specifications first')
    if suggestion['fingerprint']!=fingerprint:
        raise HTTPException(409,'The exact source capture or suggested facts changed; refresh before reviewing')
    if suggestion['conflicted_fields']:
        raise HTTPException(409,'The current source contains contradictory specification values; resolve the source conflict before approval')
    raw=dict(listing.raw_specs or {});current=raw.get('configurator') if isinstance(raw.get('configurator'),dict) else {}
    conflicts={key:(current[key],value) for key,value in suggestion['suggested_specs'].items()
        if key in current and current[key]!=value}
    previously_reviewed=current.get('reviewed') is True or bool(current.get('review_invalidation'))
    if conflicts and previously_reviewed and not replace_reviewed_values:
        raise HTTPException(409,'Review the previous and captured values and explicitly approve their replacement')
    if conflicts and previously_reviewed and not current.get('review_invalidation'):
        raw['configurator_review_history']=[*(raw.get('configurator_review_history') or []),
            {'review':deepcopy(current),'replaced_by':getattr(actor,'email',str(actor)),
             'replaced_at':datetime.now(timezone.utc).isoformat()}]
    current={key:value for key,value in current.items() if key!='review_invalidation'}
    raw['configurator']={**current,**suggestion['suggested_specs'],'reviewed':True,
        'source_url':suggestion['source_url'],'source_capture_at':suggestion['captured_at'],
        'source_properties':suggestion['properties'],'source_role':suggestion['role'],
        'reviewed_by':getattr(actor,'email',str(actor)),
        'reviewed_at':datetime.utcnow().isoformat()}
    listing.raw_specs=raw
    await db.flush()
    return {'listing_id':listing.id,'role':suggestion['role'],'approved_specs':suggestion['suggested_specs'],
        'reviewed':True,'published':False}


async def research_playbook_motherboard_specs(db, progress=None):
    """Capture exact official board specifications for review; never auto-approve."""
    from app.services.motherboard_spec_ai import extract_motherboard_spec, title_verified_motherboard_facts
    from app.services.playbook_motherboard_sources import (capture_official_motherboard_facts,
        _known_official_candidates,_model_name_prefix)
    from app.services.motherboard_matching import _normalize
    proposals=await current_proposals(db)
    parts=[]
    for proposal in proposals:
        parts.extend(part for part in proposal.get('components',[]) if part.get('role')=='motherboard')
        parts.extend(item.get('component') or {} for item in proposal.get('upsells',[])
            if item.get('role')=='motherboard')
    unique={part.get('listing_id'):part for part in parts if part.get('listing_id') and part.get('title')}
    known=(await db.execute(select(MotherboardSpec))).scalars().all()
    known_keys={_normalize(row.canonical_model) for row in known}
    pending_titles={_normalize((row.raw_ai_response or {}).get('playbook_source_title',''))
        for row in known if isinstance(row.raw_ai_response,dict) and not row.reviewed}
    known_by_title={_normalize((row.raw_ai_response or {}).get('playbook_source_title','')):row
        for row in known if isinstance(row.raw_ai_response,dict)
        and (row.raw_ai_response or {}).get('playbook_source_title')}
    created=[];updated=[];unresolved=[];manufacturer_unresolved=[];listing_titled=[]
    skipped=0;manufacturer_attempted=0
    manufacturer_captured=0
    # Search a small number each hour: official pages are fetched only for
    # exact active proposal models, under the brand's own domain, then saved
    # as review-required evidence. Subsequent cycles cover the remaining board
    # references without queuing a burst of web searches.
    manufacturer_limit=5
    # Spend the limited manufacturer fetch budget first on models with a
    # deterministic official product URL; this prevents the initial catalogue
    # ordering from starving later ROG/PRIME/TUF boards on every hourly pass.
    ordered_parts=sorted(unique.values(),key=lambda part:not _known_official_candidates(part['title']))
    research_parts=ordered_parts[:32]
    for index,part in enumerate(research_parts,1):
        if progress:
            progress(f'Researching motherboard source facts {index}/{len(research_parts)}')
        title=part['title'];normalized=_normalize(title)
        existing=known_by_title.get(normalized)
        if existing is None:
            exact=[row for row in known if _normalize(row.canonical_model)
                and _normalize(row.canonical_model) in normalized]
            existing=exact[0] if len(exact)==1 else None
        if existing and existing.source not in {'ai_generated','manufacturer_capture','listing_title'}:
            skipped+=1;continue
        existing_evidence=(existing.raw_ai_response if existing and isinstance(existing.raw_ai_response,dict) else {})
        prior_capture=existing_evidence.get('manufacturer_source_capture')
        title_retry=existing_evidence.get('manufacturer_source_attempted_at')
        retry_recent=False
        if title_retry:
            try:
                retry_time=datetime.fromisoformat(title_retry)
                if retry_time.tzinfo is None: retry_time=retry_time.replace(tzinfo=timezone.utc)
                retry_recent=datetime.now(timezone.utc)-retry_time<timedelta(hours=24)
            except (TypeError,ValueError):
                retry_recent=False
        if existing and existing.source=='listing_title' and retry_recent:
            skipped+=1;continue
        enrich_approved_title=bool(existing and existing.reviewed
            and existing.source=='listing_title' and not isinstance(prior_capture,dict))
        if existing and ((existing.reviewed and not enrich_approved_title) or
                (isinstance(prior_capture,dict) and prior_capture.get('facts') and prior_capture.get('source_url'))):
            skipped+=1;continue
        manufacturer=None
        attempted_manufacturer=False
        if manufacturer_attempted<manufacturer_limit:
            manufacturer_attempted+=1
            attempted_manufacturer=True
            try:
                manufacturer=await capture_official_motherboard_facts(title)
            except Exception:
                manufacturer=None
        if manufacturer:
            facts=manufacturer['facts']
            evidence={**(existing.raw_ai_response or {} if existing and isinstance(existing.raw_ai_response,dict) else {}),
                'playbook_source_title':title,'playbook_source_url':part.get('source_url'),
                'research_basis':'official_manufacturer_product_spec_page',
                'manufacturer_source_capture':manufacturer,'review_required':True}
            if attempted_manufacturer:
                evidence['manufacturer_source_attempted_at']=datetime.now(timezone.utc).isoformat()
            if enrich_approved_title:
                evidence['previous_approved_facts']={field:getattr(existing,field) for field in
                    ('socket','chipset','ram_type','ram_slots','max_ram_gb','pcie_x16_slots',
                     'm2_slots','sata_ports','form_factor','wifi')}
            if existing:
                row=existing;updated.append({'canonical_model':row.canonical_model,'source_title':title})
            else:
                prefix=re.split(r'\b(?:motherboard|mother\s+board|mainboard|socket|supports|supporting)\b',
                    title,maxsplit=1,flags=re.I)[0].strip(' ,:-')
                brand=next((value for value in ('MSI','ASUS','GIGABYTE','ASRock','BIOSTAR')
                    if value.casefold() in title.casefold()),None)
                canonical=prefix[:200] or manufacturer.get('source_title') or title[:200]
                canonical_key=_normalize(canonical)
                collision=next((row for row in known if _normalize(row.canonical_model)==canonical_key),None)
                if collision:
                    if collision.reviewed or collision.source not in {'ai_generated','manufacturer_capture','listing_title'}:
                        skipped+=1;continue
                    row=collision;updated.append({'canonical_model':row.canonical_model,'source_title':title})
                else:
                    row=MotherboardSpec(canonical_model=canonical,brand=brand,source='manufacturer_capture',
                        reviewed=False,raw_ai_response=evidence)
                    db.add(row);created.append({'canonical_model':canonical,'source_title':title})
                    known.append(row);known_keys.add(canonical_key);pending_titles.add(normalized)
            row.source='manufacturer_capture';row.ai_confidence=None
            if enrich_approved_title:
                row.reviewed=False;row.reviewed_by=None
            row.ai_reasoning='Captured from the linked official manufacturer specification page; pending operator review.'
            row.raw_ai_response=evidence
            for field in ('socket','chipset','ram_type','ram_slots','max_ram_gb','pcie_x16_slots',
                    'm2_slots','sata_ports','form_factor','wifi'):
                setattr(row,field,facts.get(field))
            if existing and not any(item.get('canonical_model')==row.canonical_model for item in updated):
                updated.append({'canonical_model':row.canonical_model,'source_title':title})
            known_keys.add(_normalize(row.canonical_model));pending_titles.add(normalized)
            known_by_title[normalized]=row;manufacturer_captured+=1
            continue
        if attempted_manufacturer:
            manufacturer_unresolved.append(title)
            if enrich_approved_title and existing:
                existing.raw_ai_response={**existing_evidence,
                    'manufacturer_source_attempted_at':datetime.now(timezone.utc).isoformat()}
                skipped+=1;continue
        elif enrich_approved_title:
            # Do not rewrite an approved title-based record when the bounded
            # manufacturer-capture budget is exhausted. Its evidence must be
            # explicitly re-reviewed if any captured fact changes.
            skipped+=1;continue
        title_facts=title_verified_motherboard_facts(title)
        canonical=_model_name_prefix(title)[:200]
        if (title_facts.get('socket') and title_facts.get('ram_type')
                and len(title_facts)>=3 and canonical
                and _normalize(canonical) in normalized):
            canonical_key=_normalize(canonical)
            collision=next((row for row in known if _normalize(row.canonical_model)==canonical_key),None)
            if collision and (collision.reviewed or collision.source not in
                    {'ai_generated','manufacturer_capture','listing_title'}):
                skipped+=1;continue
            row=collision or existing
            is_new=row is None
            if is_new:
                brand=next((value for value in ('MSI','ASUS','GIGABYTE','ASRock','BIOSTAR')
                    if value.casefold() in title.casefold()),None)
                row=MotherboardSpec(canonical_model=canonical,brand=brand,source='listing_title',
                    reviewed=False,raw_ai_response={})
                db.add(row);known.append(row)
                created.append({'canonical_model':canonical,'source_title':title})
            else:
                row.canonical_model=canonical
                row.source='listing_title'
                updated.append({'canonical_model':canonical,'source_title':title})
            field_evidence={field:f'Literal in exact linked catalogue title: {title}'
                for field in title_facts}
            title_capture={'facts':title_facts,'field_evidence':field_evidence,
                'source_title':title,'source_url':part.get('source_url'),'review_required':True}
            row.ai_confidence=None
            row.ai_reasoning='Literal compatibility facts captured from the exact linked catalogue title; pending operator review.'
            row.raw_ai_response={'playbook_source_title':title,'playbook_source_url':part.get('source_url'),
                'research_basis':'exact_catalogue_listing_title',
                'listing_title_fact_capture':title_capture,'review_required':True}
            if attempted_manufacturer:
                row.raw_ai_response['manufacturer_source_attempted_at']=datetime.now(timezone.utc).isoformat()
            for field in ('socket','chipset','ram_type','ram_slots','max_ram_gb','pcie_x16_slots',
                    'm2_slots','sata_ports','form_factor','wifi'):
                setattr(row,field,title_facts.get(field))
            known_keys.add(canonical_key);pending_titles.add(normalized);known_by_title[normalized]=row
            listing_titled.append(title)
            continue
        if existing or any(key and key in normalized for key in known_keys) or normalized in pending_titles:
            skipped+=1;continue
        try:
            result=await extract_motherboard_spec(title,free_only=True)
        except Exception:
            result=None
        if not result or not result.recognised or not result.canonical_model:
            unresolved.append(title);continue
        if _normalize(result.canonical_model) not in normalized:
            unresolved.append(title);continue
        verified=title_verified_motherboard_facts(title)
        if not verified:
            unresolved.append(title);continue
        canonical_key=_normalize(result.canonical_model)
        if canonical_key in known_keys or canonical_key in pending_titles:
            skipped+=1;continue
        evidence={**result.raw,'playbook_source_title':title,
            'playbook_source_url':part.get('source_url'),'research_basis':'exact_catalogue_listing_title',
            'review_required':True}
        row=MotherboardSpec(canonical_model=result.canonical_model,brand=result.brand,
            socket=verified.get('socket'),chipset=verified.get('chipset'),ram_type=verified.get('ram_type'),
            ram_slots=verified.get('ram_slots'),max_ram_gb=verified.get('max_ram_gb'),
            pcie_x16_slots=verified.get('pcie_x16_slots'),m2_slots=verified.get('m2_slots'),
            sata_ports=verified.get('sata_ports'),form_factor=verified.get('form_factor'),wifi=verified.get('wifi'),
            source='ai_generated',ai_confidence=result.confidence,ai_reasoning=str(result.reasoning or '')[:500],
            reviewed=False,raw_ai_response=evidence)
        db.add(row);created.append({'canonical_model':row.canonical_model,'source_title':title})
        known_keys.add(canonical_key);pending_titles.add(normalized)
    await db.flush()
    return {'created':created,'created_count':len(created),'updated':updated,
        'manufacturer_capture':{'attempted':manufacturer_attempted,'captured':manufacturer_captured,
            'unresolved':max(0,manufacturer_attempted-manufacturer_captured),
            'unresolved_titles':manufacturer_unresolved},
        'listing_title':{'captured':len(listing_titled),
            'titles':listing_titled,'reviewed':False},
        'skipped':skipped,'unresolved':unresolved,'reviewed':False,'published':False}


async def approve_playbook_motherboard_spec(db,spec_id,actor):
    from app.models.motherboard_spec import MotherboardSpec
    row=await db.get(MotherboardSpec,spec_id)
    evidence=row.raw_ai_response if row and isinstance(row.raw_ai_response,dict) else {}
    if row is None or row.source not in {'ai_generated','manufacturer_capture','listing_title'} or row.reviewed or not evidence.get('playbook_source_url'):
        raise HTTPException(404,'Unreviewed Playbook motherboard research not found')
    captured=evidence.get('manufacturer_source_capture')
    if row.source=='manufacturer_capture' and (not isinstance(captured,dict)
            or captured.get('review_required') is not True or not captured.get('source_url')
            or not captured.get('field_evidence')):
        raise HTTPException(409,'Official manufacturer evidence is incomplete; refresh the source before reviewing')
    if row.source=='manufacturer_capture':
        from app.services.playbook_motherboard_sources import _allowed_official_url,_manufacturer_domains
        source_title=evidence.get('playbook_source_title','')
        facts=captured.get('facts') or {}
        expected_fields=('socket','chipset','ram_type','ram_slots','max_ram_gb','pcie_x16_slots',
            'm2_slots','sata_ports','form_factor','wifi')
        if (not _allowed_official_url(captured['source_url'],_manufacturer_domains(source_title))
                or len(facts)<3 or facts.get('socket') is None or facts.get('ram_type') is None
                or any(getattr(row,field)!=facts.get(field) for field in expected_fields)):
            raise HTTPException(409,'Manufacturer facts no longer match the exact captured source; refresh before reviewing')
    if row.source=='listing_title':
        from app.services.motherboard_spec_ai import title_verified_motherboard_facts
        captured=evidence.get('listing_title_fact_capture')
        source_title=evidence.get('playbook_source_title','')
        facts=title_verified_motherboard_facts(source_title)
        expected_fields=('socket','chipset','ram_type','ram_slots','max_ram_gb','pcie_x16_slots',
            'm2_slots','sata_ports','form_factor','wifi')
        if (not isinstance(captured,dict) or captured.get('review_required') is not True
                or captured.get('source_title')!=source_title
                or captured.get('source_url')!=evidence.get('playbook_source_url')
                or captured.get('facts')!=facts or len(facts)<3
                or not facts.get('socket') or not facts.get('ram_type')
                or any(getattr(row,field)!=facts.get(field) for field in expected_fields)):
            raise HTTPException(409,'Exact listing-title facts changed or are incomplete; refresh before reviewing')
    from app.services.motherboard_matching import _normalize
    source_title=evidence.get('playbook_source_title','')
    if not source_title or _normalize(row.canonical_model) not in _normalize(source_title):
        raise HTTPException(409,'The research model does not exactly match its catalogue source title')
    row.reviewed=True;row.reviewed_by=getattr(actor,'email',str(actor))
    await db.flush()
    return {'id':row.id,'canonical_model':row.canonical_model,'reviewed':True,'published':False}


async def reject_proposal(db, proposal_id, revision, actor_id):
    await db.execute(text('SELECT pg_advisory_xact_lock(61311, 1)'))
    proposal=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.id==proposal_id)
        .with_for_update())).scalar_one_or_none()
    if proposal is None or (proposal.demand_signals or {}).get('source')!=SOURCE:
        raise HTTPException(404,'Generated Playbook proposal not found')
    if proposal.status!='pending' or (proposal.proposed_data or {}).get('revision_sha256')!=revision:
        raise HTTPException(409,'The proposal changed; reload before reviewing')
    proposal.status='rejected'
    proposal.resolved_at=datetime.utcnow()
    proposal.resolved_by=str(actor_id)
    proposal.rejection_reason='Operator rejected the generated build proposal'
    await db.flush()
    return {'proposal_id':proposal.id,'status':proposal.status,'published':False}


async def run_playbook_refresh(actor_id=0,progress=None):
    import asyncio
    from time import perf_counter
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        from app.services.amazon_bestsellers import scrape_amazon_component_bestsellers
        from app.services.bestseller_catalogue_sync import sync_bestseller_catalogues
        from app.services.playbook_product_capture import refresh_selected_product_facts
        stage_seconds={}
        async def timed_stage(name,operation):
            started=perf_counter()
            try:
                return await operation()
            finally:
                stage_seconds[name]=round(perf_counter()-started,3)

        try:
            # Amazon remains the hardware demand/catalogue source. OS licence
            # costs are sourced from the selected specialist key catalogue.
            bestseller_refresh=await timed_stage('amazon_bestsellers_seconds',lambda:
                scrape_amazon_component_bestsellers(
                    categories=['cpu','gpu','ram','storage','motherboard','psu','cooler','case'], reconcile_catalogue=False))
        except Exception as error:
            # Keep the existing catalogue usable when Amazon blocks a refresh;
            # no approval or publication is implied by source collection.
            bestseller_refresh={'errors':1,'categories':0,'error':type(error).__name__}
        if progress: progress('Refreshing selected Gamers Outlet software offers')
        from app.models.listing import Listing
        software_listings=(await db.execute(select(Listing).where(
            Listing.status=='active',Listing.source_name=='Gamers Outlet'))).scalars().all()
        software_ids=[row.id for row in software_listings
            if ((row.raw_specs or {}).get('gamers_outlet') or {}).get('category') in {'os','office'}]
        gamers_outlet_refresh=await timed_stage('gamers_outlet_seconds',lambda:
            refresh_selected_product_facts(db,limit=max(8,len(software_ids)),listing_ids=software_ids,force=True)
            if software_ids else asyncio.sleep(0,result={'attempted':0,'captured':0,'retained':0,
                'unresolved':0,'published':False,'reason':'No selected Gamers Outlet software listings'}))
        await db.commit()
        if progress: progress('Linking captured source products into Playbook catalogues')
        catalogue_sync=await timed_stage('catalogue_sync_seconds',lambda:sync_bestseller_catalogues(db))
        await db.commit()
        if progress: progress('Finding exact Amazon identities for missing authored requirements')
        from app.services.playbook_requirement_sources import discover_missing_requirement_sources
        requirement_discovery = await timed_stage('requirement_discovery_seconds',lambda:discover_missing_requirement_sources(db))
        await db.commit()
        if progress: progress('Refreshing exact supplier prices, stock and delivery facts')
        capture=await timed_stage('exact_product_capture_seconds',lambda:refresh_selected_product_facts(db))
        await db.commit()
        if progress: progress('Linking newly captured offers into Playbook catalogues')
        catalogue_sync_after_capture=await timed_stage('catalogue_sync_after_capture_seconds',
            lambda:sync_bestseller_catalogues(db,check_free_software=False))
        await db.commit()
        if progress: progress('Rebuilding all segment proposals and compatibility checks')
        result=await timed_stage('proposal_rebuild_seconds',lambda:
            asyncio.wait_for(refresh_playbooks(db,actor_id),timeout=300))
        await db.commit()
        # Compatibility research is part of Playbook's refresh loop. Store
        # generated motherboard facts only as review-required suggestions; this
        # never marks them verified and cannot publish a build.
        try:
            if progress: progress('Researching missing motherboard compatibility references')
            engineering_research=await timed_stage('engineering_research_seconds',lambda:asyncio.wait_for(
                research_playbook_motherboard_specs(db,progress=progress),timeout=300))
            await db.commit()
        except asyncio.TimeoutError:
            await db.rollback()
            engineering_research={'created_count':0,'unresolved':[],
                'reviewed':False,'published':False,'status':'timed_out'}
        except Exception as error:
            await db.rollback()
            engineering_research={'created_count':0,'unresolved':[],
                'reviewed':False,'published':False,'status':type(error).__name__}
        return {**{key:value for key,value in result.items() if key not in {'offers','catalogue_sync'}},
            'catalogue_sync':catalogue_sync,'catalogue_sync_after_capture':catalogue_sync_after_capture,
            'bestseller_refresh':bestseller_refresh,
            'gamers_outlet_refresh':gamers_outlet_refresh,'product_capture':capture,'requirement_discovery':requirement_discovery,
            'engineering_research':engineering_research,'stage_seconds':stage_seconds}
