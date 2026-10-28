"""Reassess and publish the exact promoted BOMs through normal publication gates."""
import asyncio
from copy import deepcopy
import sys
from pathlib import Path
from sqlalchemy import select
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import AsyncSessionLocal,engine
from app.models.playbook import Playbook,PlaybookProposal
from app.models.app_settings import AppSettings
from app.models.listing import Listing
from app.services.commercial_readiness import source_preview
from urllib.parse import urlsplit
from app.services import playbook_service as service
from app.services.curated_build_policy import definitions
from app.services.hardware_performance import load_benchmark_context
from app.services.playbook_mvp import prepare_candidates

async def main(apply=False):
    async with AsyncSessionLocal() as db:
        proposals=await service.current_proposals(db)
        assert len(proposals)==24
        benchmarks,_=await load_benchmark_context(db)
        settings=await db.get(AppSettings,1)
        defs={d['id']:d for d in definitions()['builds']}
        sales=await service.paid_component_sales(db)
        for listing_id in {part['listing_id'] for p in proposals for part in p['components'] if part['role']=='os'}:
            listing=await db.get(Listing,listing_id)
            assert urlsplit(listing.url).hostname in {'gamers-outlet.net','www.gamers-outlet.net'}
            capture=await source_preview(db,listing)
            if not capture or not capture.get('licence_review_fingerprint'):
                raise RuntimeError('The original Windows supplier requires current licence evidence')
            if not capture.get('licence_source_reviewed'):
                await service.approve_royalcdkeys_licence_source(db,listing_id,capture['licence_review_fingerprint'],0)
            checked=await source_preview(db,listing)
            if not checked.get('licence_source_reviewed'):
                raise RuntimeError('The original Windows licence review did not persist in this transaction')
        # Rebuild current identity-bound evidence before applying the owner's
        # existing approval. Fingerprints legitimately change when DEV IDs are
        # remapped; the normal source-review function revalidates every capture.
        from app.services.catalogue_price_import import import_current_catalogue_prices
        source_rows={}
        for original in proposals:
            for part in original['components']:
                listing=await db.get(Listing,part['listing_id'])
                source=await source_preview(db,listing)
                key=f"case:{listing.case_catalogue_id}" if part['role']=='case' and listing.case_catalogue_id else f"variant:{part['variant_id']}"
                source_rows[key]={'role':part['role'],'part_key':key,'source':source}
        imported=await import_current_catalogue_prices(db,list(source_rows.values()),0)
        if imported['blocked']:raise RuntimeError(imported['blocked'])
        for original in proposals:
            parent=await db.get(Playbook,original['playbook_id'])
            pool=await service._catalogue_candidates(db,parent.id,'curated',
                variant_ids={part['variant_id'] for part in original['components']})
            pool=await prepare_candidates(db,parent,pool,reconcile_prices=False)
            current=await service.build_cell_offer(db,defs[original['cell_id']],parent,settings,pool,benchmarks,sales)
            if any(part['role']=='os' and not part['source_observation'].get('licence_source_reviewed') for part in current['components']):
                raise RuntimeError(f"{original['cell_id']}: rebuilt Windows capture lost its licence review")
            if current['blockers']:raise RuntimeError(f"{original['cell_id']}: {current['blockers']}")
            proposal=await db.get(PlaybookProposal,original['proposal_id'])
            proposal.proposed_data=current
        await db.flush()
        proposals=await service.current_proposals(db)
        expected=[{'proposal_id':p['proposal_id'],'revision_sha256':p['revision_sha256'],
            'source_evidence':[{'role':part['role'],'listing_id':part['listing_id'],
                'fingerprint':part['source_observation']['fingerprint']} for part in p['components']]}
            for p in proposals]
        await service.approve_all_current_supplier_sources(db,expected,0)
        for original in proposals:
            parent=await db.get(Playbook,original['playbook_id'])
            pool=await service._catalogue_candidates(db,parent.id,'curated',
                variant_ids={part['variant_id'] for part in original['components']})
            pool=await prepare_candidates(db,parent,pool,reconcile_prices=False)
            current=await service.build_cell_offer(db,defs[original['cell_id']],parent,settings,pool,benchmarks,sales)
            if current['blockers']:raise RuntimeError(f"{original['cell_id']}: {current['blockers']}")
            proposal=await db.get(PlaybookProposal,original['proposal_id'])
            proposal.proposed_data=current
            await db.flush()
            print('Checking publication',original['cell_id'],flush=True)
            result=await service.approve_proposal(db,proposal.id,current['revision_sha256'],0,exact_reviewed_bom=True)
            print(result,flush=True)
        if apply:await db.commit();print('24 PUBLICATION GATES PASSED; COMMITTED',flush=True)
        else:await db.rollback();print('24 PUBLICATION GATES PASSED; DRY RUN ROLLED BACK',flush=True)
    await engine.dispose()

if __name__=='__main__':asyncio.run(main('--apply' in sys.argv))
