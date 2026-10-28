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
        for original in proposals:
            parent=await db.get(Playbook,original['playbook_id'])
            pool=deepcopy(original['components'])
            pool=await prepare_candidates(db,parent,pool,reconcile_prices=False)
            current=await service.build_cell_offer(db,defs[original['cell_id']],parent,settings,pool,benchmarks,sales)
            if current['blockers']:raise RuntimeError(f"{original['cell_id']}: {current['blockers']}")
            proposal=await db.get(PlaybookProposal,original['proposal_id'])
            proposal.proposed_data=current
            await db.flush()
            result=await service.approve_proposal(db,proposal.id,current['revision_sha256'],0,exact_reviewed_bom=True)
            print(result,flush=True)
        if apply:await db.commit();print('24 PUBLICATION GATES PASSED; COMMITTED',flush=True)
        else:await db.rollback();print('24 PUBLICATION GATES PASSED; DRY RUN ROLLED BACK',flush=True)
    await engine.dispose()

if __name__=='__main__':asyncio.run(main('--apply' in sys.argv))
