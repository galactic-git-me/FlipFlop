"""Owner-authorised DEV source reconciliation. Never publishes or buys.

Run from flipflop-api with its venv. Default is a read-only evidence export;
--refresh captures missing/stale exact Curated product offers in bounded batches.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select, text
from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.models.listing import Listing
from app.services.commercial_readiness import source_preview_many

OUTPUT = Path(__file__).resolve().parents[2] / 'docs/playbook/specifications/2026-10-22/release'


async def export():
    async with AsyncSessionLocal() as db:
        await db.execute(text('SET TRANSACTION READ ONLY'))
        variants = [dict(r) for r in (await db.execute(text('''
            SELECT v.id,v.listing_id,v.status,s.slot_type,v.slot_id,
              v.asset_media_review IS NOT NULL AS media_review_present
            FROM catalogue_variants v JOIN playbook_slots s ON s.id=v.slot_id
            WHERE v.curated_for_builds AND v.status IN ('active','pending_review')
            ORDER BY v.id
        '''))).mappings()]
        ids = {r['listing_id'] for r in variants}
        listings = (await db.execute(select(Listing).where(Listing.id.in_(ids))
                                    .order_by(Listing.id))).scalars().all()
        previews = await source_preview_many(db, listings)
        products = []
        for listing in listings:
            raw = listing.raw_specs or {}
            capture = raw.get('playbook_product_capture') or {}
            engineering = raw.get('playbook_product_engineering_capture') or {}
            products.append({
                'listing_id': listing.id, 'title': listing.title,
                'source': listing.source_name, 'url': listing.url,
                'external_id': listing.external_id, 'listing_price_gbp': listing.price,
                'last_seen_at': listing.last_seen_at, 'listing_status': str(listing.status.value),
                'roles': sorted({v['slot_type'] for v in variants if v['listing_id'] == listing.id}),
                'variants': [v for v in variants if v['listing_id'] == listing.id],
                'bestseller': raw.get('bestseller'), 'range': raw.get('curated_range'),
                'capture': {k: v for k, v in capture.items() if k not in ('product_image_urls',)},
                'engineering_properties': engineering.get('product_properties'),
                'source_preview': previews.get(listing.id),
            })
        # Preserve exact counterpart candidates; a CPK match is a research lead,
        # not authority to import price/condition or approve a seller.
        cpks = {str((p.get('bestseller') or {}).get('cpk')) for p in products
                if (p.get('bestseller') or {}).get('cpk')}
        counterparts = [dict(r) for r in (await db.execute(text('''
            SELECT p.listing_id,p.cpk,p.price,p.updated_at,
              s.title,s.url,s.source
            FROM gem_radar_cpk_listing_price p
            LEFT JOIN gem_radar_scored_listings s ON s.listing_id=p.listing_id
            WHERE p.cpk=ANY(:cpks) ORDER BY p.cpk,p.price
        '''), {'cpks': list(cpks)})).mappings()]
        result = {'observed_at': datetime.now(timezone.utc).isoformat(), 'environment': 'dev',
                  'products': products, 'counterpart_candidates': counterparts,
                  'summary': {'products': len(products),
                    'positive_listing_prices': sum(bool(p['listing_price_gbp'] and p['listing_price_gbp'] > 0) for p in products),
                    'null_listing_prices': sum(p['listing_price_gbp'] is None for p in products),
                    'capture_status': dict(Counter(p['capture'].get('status', 'not_captured') for p in products)),
                    'counterpart_rows': len(counterparts)}}
        OUTPUT.mkdir(parents=True, exist_ok=True)
        target = OUTPUT / ('catalogue-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
        target.write_text(json.dumps(result, default=str, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'report': str(target), **result['summary']}), flush=True)
        return products


async def main(args):
    assert get_settings().app_env.lower() == 'dev', 'DEV only; no production mutation'
    try:
        products = await export()
        if args.refresh:
            from app.services.playbook_product_capture import refresh_selected_product_facts
            targets = [p['listing_id'] for p in products if p['roles'] != ['os_secondary']
                       and not all((p.get('source_preview') or {}).get(k)
                                   for k in ('fresh', 'commercial_capture_verified', 'postage_verified'))]
            if args.ids:
                targets = [int(x) for x in args.ids.split(',')]
            print('Refresh exact product IDs: ' + json.dumps(targets), flush=True)
            # Persist small batches so an interrupted retailer/browser request
            # cannot discard an entire catalogue's completed observations.
            targets = targets[:args.limit]
            for offset in range(0, len(targets), args.batch_size):
                batch = targets[offset:offset + args.batch_size]
                print('Capturing batch ' + str(offset // args.batch_size + 1) + ': ' + json.dumps(batch), flush=True)
                async with AsyncSessionLocal() as db:
                    result = await refresh_selected_product_facts(db, listing_ids=set(batch),
                                                                 limit=len(batch), force=True)
                    await db.commit()
                    output = OUTPUT / ('refresh-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
                    output.write_text(json.dumps({'listing_ids': batch, **result}, default=str, indent=2) + '\n', encoding='utf-8')
                    print(json.dumps({'refresh_report': str(output), **result}), flush=True)
            await export()
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--limit', type=int, default=96)
    parser.add_argument('--batch-size', type=int, default=6)
    parser.add_argument('--ids')
    args = parser.parse_args()
    if args.limit < 1 or args.batch_size < 1:
        parser.error('limits and batch size must be positive')
    asyncio.run(main(args))
