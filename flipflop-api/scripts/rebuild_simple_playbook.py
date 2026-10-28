"""Rebuild local DEV suggestions from stored data; never scrape or publish.

Run from flipflop-api: .venv/Scripts/python.exe scripts/rebuild_simple_playbook.py
Add --apply to save catalogue membership and pending proposals.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.environment import load_application_environment
load_application_environment(Path(__file__).resolve().parents[1])
from app.config import get_settings
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine
from app.services.bestseller_catalogue_sync import sync_bestseller_catalogues
from app.services.playbook_service import refresh_playbooks, _plausible_role_candidate
from app.services.playbook_book import operational_book


def export_cell(cell):
    result = {key: cell.get(key) for key in
              ('cell_id','customer_type','budget_tier','name','pricing_guidance')}
    offer = cell.get('offer') or {}
    result['intended_use']=offer.get('intended_use') or (cell.get('definition') or {}).get('use')
    result['offer'] = {key: offer.get(key) for key in
                       ('cell_id','proposal_id','revision_sha256','complete_hardware','blockers','compatibility','compatibility_review','planning_compatibility','required_extras','delivery_products','component_pace_options')}
    result['offer']['components'] = [{key: part.get(key) for key in
        ('role','title','variant_id','listing_id','source_url','amazon_listing_url','cpk','asin','rank','supplier_offers',
         'listing_price_gbp','supplier_postage_gbp','price_observed_at','suggested_supplier_offer',
         'quantity','unit_price_gbp','manufacturer_facts','planning_engineering',
         'source_observation','catalogue_approved','draft_software_candidate','photo_ready','media_ready')}
        for part in offer.get('components', []) if part.get('role')!='wireless_adapter']
    return result


def render(book):
    lines = ['# Simple Playbook — captured-data suggestions', '',
             f"Generated: {book['observed_at']}. Saved to DEV: {book['saved_to_dev']}.", '',
             'Amazon top ten per hardware category define the shared catalogue (NVMe/SATA separately); '
             'cases use all eligible products in the Amazon top 100. '
             'Existing authored requirements supply exceptions where the top ten cannot fill a role. '
             'Stored exact supplier matches supply costs. Prices use matching complete-PC sold evidence, '
             'then component sold medians, then recorded full cost plus 10% profit on cost. '
             'Unknown buying postage defaults to £0; selling-build delivery defaults to £15. '
             'Recorded charges take precedence. These are suggestions, not published customer offers.', '',
             '| Segment | Tier | Suggested price | Basis | Missing components/costs |',
             '|---|---|---:|---|---|']
    for cell in book['cells']:
        guidance = cell['pricing_guidance']
        gaps = [gap for gap in guidance['gaps'] if 'postage unknown' not in gap]
        price = guidance.get('estimated_price_gbp')
        blockers=(cell.get('offer') or {}).get('blockers') or []
        summary_gaps=list(dict.fromkeys([*gaps,*blockers]))
        lines.append(f"| {cell['customer_type']} | {cell['budget_tier']} | {'£'+price if price else 'Incomplete'} | {guidance['price_basis']} | {'; '.join(summary_gaps) or 'None'} |")
    for cell in book['cells']:
        guidance = cell['pricing_guidance']
        lines += ['', f"## {cell['cell_id']} — {cell['name']}", '',
                  f"Use: {cell.get('intended_use') or cell['customer_type']}", '',
                  guidance['market_advice']['summary'], '',
                  '| Role | Selected product / recorded supplier | Item cost | Supplier postage |',
                  '|---|---|---:|---:|']
        for part in (cell.get('offer') or {}).get('components', []):
            supplier = part.get('suggested_supplier_offer') or {}
            price = supplier.get('item_gbp', part.get('listing_price_gbp'))
            postage = supplier.get('delivery_gbp', part.get('supplier_postage_gbp'))
            if (part.get('quantity') or 1)>1:
                price=part.get('listing_price_gbp')
                postage=part.get('supplier_postage_gbp')
            title = ' '.join(str(part['title']).replace('|', '/').split())
            if (part.get('quantity') or 1)>1:
                title=f"{part['quantity']} × {title}"
            url = supplier.get('url') or part.get('source_url')
            amazon_url=part.get('amazon_listing_url')
            product=f"[{title}]({url})" if url else title
            if amazon_url:
                product+=f" · [Amazon listing]({amazon_url})"
            vendor_links=[f"[{entry.get('source') or 'Vendor'} £{entry.get('item_gbp')}]({entry.get('url')})"
                for entry in part.get('supplier_offers',[]) if entry.get('url')]
            if vendor_links:
                product+="<br>Matched offers: "+", ".join(vendor_links)
            lines.append(f"| {part['role']} | {product} | {price or 'Unknown'} | {postage if postage is not None else '0.00 (default)'} |")
        for extra in (cell.get('offer') or {}).get('required_extras') or []:
            title=' '.join(str(extra.get('title') or extra.get('role') or 'Required extra').replace('|','/').split())
            supplier=extra.get('suggested_supplier_offer') or {}
            url=supplier.get('url') or extra.get('source_url')
            product=f"[{title}]({url})" if url else f"{title} (source not linked)"
            vendor_links=[f"[{entry.get('source') or 'Vendor'} £{entry.get('item_gbp')}]({entry.get('url')})"
                for entry in extra.get('supplier_offers',[]) if entry.get('url')]
            if vendor_links:
                product+=" · Matched offers: "+", ".join(vendor_links)
            price=supplier.get('item_gbp') or extra.get('listing_price_gbp') or 'Not captured'
            lines.append(f"| {extra.get('role','required_extra')} | {product} | {price} | 0.00 (fallback if unknown) |")
        lines += ['', f"Known parts: £{guidance['known_parts_subtotal_gbp']}. Suggested price: {guidance.get('estimated_price_gbp') or 'Incomplete'}. Estimated profit: {guidance.get('estimated_profit_gbp') or 'Unknown'}.", '']
        standard=(((cell.get('offer') or {}).get('delivery_products') or {}).get('standard') or {})
        if standard.get('recommended_price_gbp') is not None:
            lines += [f"Standard commercial quote: £{standard['recommended_price_gbp']}. Estimated contribution after the recorded operating costs and reserves: £{standard.get('estimated_profit_gbp') or 'Unknown'}.", '']
        lines += ['Customer selects Fast Track, Standard or Flexible. Flexible has no promised delivery date.', '',
                  '| Component | Fast Track source | Standard source | Flexible source (no delivery promise) |',
                  '|---|---|---|---|']
        pace_options=(cell.get('offer') or {}).get('component_pace_options') or {}
        for part in [*(cell.get('offer') or {}).get('components',[]),
                     *((cell.get('offer') or {}).get('required_extras') or [])]:
            choices=[]
            for mode in ('fast_track','standard','flexible'):
                option=next((row for row in pace_options.get(mode,[]) if row['role']==part['role']),{})
                sources=option.get('sources') or []
                choices.append(', '.join(f"[{source.get('source') or 'Supplier'} £{source['item_gbp']}]({source['url']})"
                    for source in sources) if sources else option.get('reason') or 'Awaiting sourcing assessment')
            lines.append('| '+part['role']+' | '+' | '.join(choices)+' |')
        lines.append('')
        lines += [f"- {gap}" for gap in guidance['gaps']]
        errors = [check['message'] for check in (cell.get('offer') or {}).get('compatibility', {}).get('checks', []) if check['severity']=='error']
        lines += [f'- Compatibility: {error}' for error in errors]
        planning=(cell.get('offer') or {}).get('planning_compatibility') or {}
        lines += ['',f"Planning checks: {planning.get('status','not assessed')}.",'']
        lines += [f"- {row['check']}: {row['status']} — {row['detail']}" for row in planning.get('checks',[])]
        lines += [f'- Assembly: {note}' for note in planning.get('assembly_notes',[])]
        blockers=(cell.get('offer') or {}).get('blockers') or []
        lines += ['',f"Publication: {'blocked' if blockers else 'ready for owner approval'}.",'']
        lines += [f'- {message}' for message in blockers]
    return '\n'.join(lines)+'\n'


async def main(args):
    assert get_settings().app_env=='dev', 'DEV only'
    if engine.url.host not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('This command is for the local DEV database only')
    args.output.mkdir(parents=True, exist_ok=True)
    async with AsyncSessionLocal() as db:
        target=dict((await db.execute(text('SELECT current_database() AS database,current_schema() AS schema'))).mappings().one())
        assert target=={'database':'pcflipper','schema':'public'},target
        if args.apply:
            backup = {table: [dict(row) for row in (await db.execute(text(sql))).mappings()]
                      for table, sql in {
                          'catalogue_variants': 'SELECT id,curated_for_builds FROM catalogue_variants',
                          'proposals': "SELECT * FROM playbook_proposals WHERE action='UPDATE' AND status='pending'",
                      }.items()}
            backup_path = args.output/'before-dev-rebuild.json'
            if not backup_path.exists():
                backup_path.write_text(json.dumps(backup, default=str), encoding='utf-8')
        sync = await sync_bestseller_catalogues(db, check_free_software=False)
        result = await refresh_playbooks(db, catalogue_sync=sync, maintain_live_offers=False,
                                        defer_compatibility=args.defer_compatibility,
                                        resolve_missing=not args.stored_only, cell_ids=args.cells,
                                        progress=lambda message: print(message, flush=True))
        raw = await operational_book(db)
        sync['total_hardware_products']=(await db.execute(text("""
            SELECT count(distinct v.listing_id) FROM catalogue_variants v
            JOIN playbook_slots s ON s.id=v.slot_id
            WHERE v.curated_for_builds IS TRUE AND s.slot_type NOT IN ('os','os_secondary')
        """))).scalar()
        book = {'observed_at': str(raw['observed_at']), 'saved_to_dev': args.apply,
                'catalogue_sync': sync, 'cells': [export_cell(cell) for cell in raw['cells']]}
        priced = [cell for cell in book['cells'] if cell['pricing_guidance'].get('estimated_price_gbp')]
        for cell in book['cells']:
            for part in (cell.get('offer') or {}).get('components', []):
                assert _plausible_role_candidate(part['role'], part['title']), part['title']
        if args.require_complete:
            assert len({cell['customer_type'] for cell in priced}) == 8, 'Every segment must have a priced draft'
            assert len(priced)==len(book['cells'])==24, 'All 24 cells need complete costs and prices'
            assert all(not cell['offer']['planning_compatibility']['errors'] for cell in book['cells']), 'Resolve planning compatibility errors'
            assert all(cell['pricing_guidance']['profit_check']['passes_on_recorded_costs'] for cell in priced), 'Every proposed price must meet the recorded-cost profit rule'
        encoded = json.dumps(book, default=str, indent=2, ensure_ascii=False)
        report = render(book)
        # Materialize reviewable output before committing any DEV changes.
        (args.output/'playbook.json').write_text(encoded, encoding='utf-8')
        (args.output/'playbook.md').write_text(report, encoding='utf-8')
        if args.apply:
            await db.commit()
        else:
            await db.rollback()
        print(json.dumps({'saved_to_dev': args.apply, 'cells': result['cells'],
                          'priced': len(priced), 'segments': 8, 'source_products': sync['source_products'],
                          'provider_requests': 0 if args.stored_only and args.defer_compatibility else 'not instrumented',
                          'published': False, 'output': str(args.output)}, indent=2))
    await engine.dispose()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8',errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--stored-only',action='store_true',help='Use saved captures only; do not fetch missing supplier pages')
    parser.add_argument('--defer-compatibility',action='store_true',help='Reuse/queue compatibility review without making model calls in this command')
    parser.add_argument('--cells', nargs='+', help='Rebuild only these cell IDs; the output and completeness checks still cover the whole Playbook')
    parser.add_argument('--require-complete', action='store_true', help='Verify all 24 cells before saving the completed Playbook')
    parser.add_argument('--output', type=Path, default=Path('../docs/playbook/generated-simple'))
    asyncio.run(main(parser.parse_args()))
