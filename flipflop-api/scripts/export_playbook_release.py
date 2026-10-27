"""Export reviewed catalogue state only; excludes customer and order records."""
import asyncio
import json
import sys
from pathlib import Path
from sqlalchemy import select, text
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import AsyncSessionLocal, engine
from app.models.playbook import Playbook, PlaybookProposal
from app.models.catalogue import CatalogueVariant, PlaybookSlot, CaseCatalogue
from app.models.listing import Listing
from app.models.component_3d_asset import Component3DAsset
from app.models.commerce_evidence import SupplierOfferEvidence
from app.services.playbook_service import current_proposals

def record(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

async def main(output):
    assert engine.url.host in {'127.0.0.1', 'localhost', '::1'}
    async with AsyncSessionLocal() as db:
        proposals = await current_proposals(db)
        assert len(proposals) == 24 and all(not p['blockers'] for p in proposals)
        assets = (await db.execute(select(Component3DAsset))).scalars().all()
        vids = {c['variant_id'] for p in proposals for c in p['components']}
        vids.update(a.subject_id for a in assets if a.subject_type.value == 'variant')
        variants = (await db.execute(select(CatalogueVariant).where(
            (CatalogueVariant.curated_for_builds.is_(True) & (CatalogueVariant.status == 'active'))
            | CatalogueVariant.id.in_(vids)))).scalars().all()
        listings = (await db.execute(select(Listing).where(Listing.id.in_({v.listing_id for v in variants})))).scalars().all()
        cases = (await db.execute(select(CaseCatalogue).where(CaseCatalogue.id.in_({l.case_catalogue_id for l in listings if l.case_catalogue_id})))).scalars().all()
        slots = (await db.execute(select(PlaybookSlot).where(PlaybookSlot.id.in_({v.slot_id for v in variants})))).scalars().all()
        parents = (await db.execute(select(Playbook).where(Playbook.id.in_({s.playbook_id for s in slots})))).scalars().all()
        keys = {f'variant:{v.id}' for v in variants} | {f'case:{c.id}' for c in cases}
        evidence = (await db.execute(select(SupplierOfferEvidence).where(SupplierOfferEvidence.part_key.in_(keys)))).scalars().all()
        proposal_rows = (await db.execute(select(PlaybookProposal).where(PlaybookProposal.id.in_({p['proposal_id'] for p in proposals})))).scalars().all()
        bundle = {'schema_version': 1, 'source': 'owner-approved-dev-20261027'}
        for key, rows in [('parents',parents),('slots',slots),('cases',cases),('listings',listings),('variants',variants),('assets',assets),('supplier_evidence',evidence),('proposals',proposal_rows)]:
            bundle[key] = [record(row) for row in rows]
        bundle['benchmarks'] = [dict(r) for r in (await db.execute(text('SELECT * FROM hardware_benchmarks'))).mappings()]
        Path(output).write_text(json.dumps(bundle, default=lambda v: getattr(v,'value',str(v)), ensure_ascii=False), encoding='utf8')
        print({k:len(v) for k,v in bundle.items() if isinstance(v,list)})
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1]))
