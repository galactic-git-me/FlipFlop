"""Owner-requested DEV reconciliation; uses real retailer/market providers."""
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select
from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.models.playbook import PlaybookProposal
from app.services.playbook_service import run_playbook_rebuild
from app.services.playbook_product_capture import refresh_selected_product_facts

async def main():
    assert get_settings().app_env.lower() == 'dev', 'DEV only'
    report = {}
    print('Rebuilding drafts with corrected identity and source selection', flush=True)
    report['before_capture_rebuild'] = await run_playbook_rebuild(0, progress=lambda m: print(m, flush=True))
    async with AsyncSessionLocal() as db:
        proposals = (await db.execute(select(PlaybookProposal).where(PlaybookProposal.action=='UPDATE').order_by(PlaybookProposal.id.desc()))).scalars().all()
        seen, targets, voyager = set(), set(), None
        for proposal in proposals:
            offer = proposal.proposed_data or {}
            cell = offer.get('cell_id')
            if not cell or cell in seen: continue
            seen.add(cell)
            if cell == 'FF-GVG-03': voyager = proposal.playbook_id
            for part in offer.get('components', []):
                source = part.get('source_observation') or {}
                if (part.get('supplier_postage_gbp') is None or not source.get('fresh')
                        or source.get('stock_status') != 'available' or not source.get('active_listing')
                        or cell == 'FF-GVG-01' and part['role'] in ('cpu','motherboard')):
                    targets.add(part['listing_id'])
        print('Refreshing real exact-product offers for '+str(sorted(targets)), flush=True)
        report['source_targets'] = sorted(targets)
        report['captures'] = await refresh_selected_product_facts(db, listing_ids=targets, limit=64, force=True)
        await db.commit()
        print('Exact supplier capture finished: '+json.dumps(report['captures'], default=str), flush=True)
    print('Recalculating all pending proposals from refreshed supplier evidence', flush=True)
    report['after_capture_rebuild'] = await run_playbook_rebuild(0, progress=lambda m: print(m, flush=True))
    if voyager:
        print('Collecting real sold/active complete-PC comparisons for Voyager', flush=True)
        try:
            from app.services.playbook_market import collect
            async with AsyncSessionLocal() as db:
                result = await collect(db, voyager, 'FF-GVG-03', 0)
                report['voyager_market'] = result
                batch = result.get('batch') or {}
                print('Voyager comparisons: '+json.dumps({'batch_id':result.get('batch_id'),'rows':len(batch.get('candidates',[])),'errors':batch.get('errors')}),flush=True)
        except Exception as error:
            report['voyager_market_error'] = str(error)
            print('Voyager market collection did not complete: '+str(error),flush=True)
    path=Path('output')/('playbook-commercial-repair-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report,default=str,indent=2),encoding='utf-8')
    print('REPORT '+str(path.resolve()),flush=True)
    await engine.dispose()

if __name__=='__main__':
    asyncio.run(main())
