"""Export the top ten eligible captured Amazon products in each hardware bucket."""
import asyncio
import csv
import html
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select,text
from app.database import AsyncSessionLocal,engine
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.services.bestseller_catalogue_sync import _importable_bestseller_observation
from app.services.curated_catalogue_range import range_bucket
from app.services.catalogue_cpk import identity_is_usable
from app.services.playbook_service import _plausible_role_candidate
from app.services.playbook_stored_offers import stored_offers,offers_for_part,same_product

OUT=Path(__file__).resolve().parents[2]/'docs/playbook/audits/2026-10-26'
ORDER=['cpu','motherboard','gpu','ram','nvme','sata','psu','cooling','case']
LABEL={'cpu':'CPU','motherboard':'Motherboard','gpu':'Graphics card','ram':'RAM','nvme':'NVMe SSD','sata':'SATA SSD','psu':'Power supply','cooling':'CPU cooler','case':'Case'}

async def main():
    now=datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        observations=(await db.execute(select(AmazonBestsellerObservation).where(
            AmazonBestsellerObservation.category!='os',
            AmazonBestsellerObservation.captured_at>=now.replace(tzinfo=None)-timedelta(days=30))
            .order_by(AmazonBestsellerObservation.captured_at.desc(),AmazonBestsellerObservation.id.desc()))).scalars().all()
        batches={}
        for row in observations:batches[row.category]=max(batches.get(row.category,row.captured_at),row.captured_at)
        current={}
        for row in observations:
            if (batches[row.category]-row.captured_at).total_seconds()<60:
                current.setdefault((row.category,row.asin),row)
        buckets=defaultdict(list)
        for row in sorted(current.values(),key=lambda r:(r.rank,r.asin)):
            role={'cooler':'cooling'}.get(row.category,row.category)
            bucket=range_bucket(row.category,row.title)
            if bucket and len(buckets[bucket])<10 and _importable_bestseller_observation(row) and _plausible_role_candidate(role,row.title):
                buckets[bucket].append(row)
        registry=[dict(r) for r in (await db.execute(text('SELECT listing_id,cpk,cpk_data FROM gem_radar_listing_cpk'))).mappings()]
        by_listing={r['listing_id']:r for r in registry}
        by_cpk=defaultdict(list)
        for r in registry:by_cpk[r['cpk']].append(r)
        markets={r['cpk']:dict(r) for r in (await db.execute(text('SELECT * FROM gem_radar_cpk_market_price'))).mappings()}
        chosen=[]
        for bucket in ORDER:
            for row in buckets[bucket]:
                role={'cooler':'cooling'}.get(row.category,row.category)
                identity=by_listing.get(row.asin) or by_listing.get(f'amazon-bestseller:{row.asin}') or {}
                key=row.cpk or identity.get('cpk')
                metadata=identity.get('cpk_data') or {}
                if not metadata and key:
                    metadata=next((r['cpk_data'] for r in by_cpk[key] if identity_is_usable(row.title,r['cpk_data'] or {},{role})),{})
                chosen.append((bucket,row,key,metadata))
        index=await stored_offers(db,{key for _,_,key,_ in chosen if key})
        output=[]
        for bucket,row,key,metadata in chosen:
            role={'cooler':'cooling'}.get(row.category,row.category)
            part={'role':role,'title':row.title,'cpk':key,'cpk_data':metadata}
            matches=[offer for offer in offers_for_part(part,index) if same_product(part,offer)]
            vendors={'amazon'}|{offer['source'] for offer in matches}
            prices=[(Decimal(str(offer['item_gbp']))+Decimal(str(offer.get('delivery_gbp') or '0')),offer['url'],offer['observed_at'],offer.get('stock_status')) for offer in matches]
            if row.price is not None and row.price>0:
                prices.append((Decimal(str(row.price)),row.url,row.captured_at.isoformat()+'Z','bestseller_capture'))
            lowest=min(prices,key=lambda p:p[0]) if prices else None
            market=markets.get(key,{})
            warning=[]
            if not key:warning.append('CPK missing')
            elif not identity_is_usable(row.title,metadata,{role}):warning.append('CPK identity needs review')
            if metadata.get('cpk') and metadata['cpk']!=key:warning.append('CPK metadata hash differs')
            output.append({'component_type':LABEL[bucket],'amazon_rank':row.rank,'product':row.title,
                'asin':row.asin,'cpk':key,'linked_vendor_count':len(vendors),'linked_vendors':', '.join(sorted(vendors)),
                'lowest_recorded_gbp':str(lowest[0].quantize(Decimal('.01'))) if lowest else None,
                'lowest_url':lowest[1] if lowest else None,'lowest_observed_at':lowest[2] if lowest else None,
                'lowest_stock_status':lowest[3] if lowest else None,
                'linked_new_offer_min_gbp':str(min(p[0] for p in prices).quantize(Decimal('.01'))) if prices else None,
                'linked_new_offer_max_gbp':str(max(p[0] for p in prices).quantize(Decimal('.01'))) if prices else None,
                'cpk_market_min_gbp':market.get('min_price'),'cpk_market_median_gbp':market.get('median_price'),
                'cpk_market_max_gbp':market.get('max_price'),'cpk_market_listing_count':market.get('listing_count'),
                'cpk_market_updated_at':market.get('updated_at'),'amazon_url':row.url,
                'amazon_captured_at':row.captured_at,'warnings':'; '.join(warning),
                'vendor_offers':[{k:o.get(k) for k in ['source','title','url','item_gbp','delivery_gbp','observed_at','stock_status','commercial_capture_verified','match_basis']} for o in matches]})
        await db.rollback()
    OUT.mkdir(parents=True,exist_ok=True)
    snapshot={'observed_at':now,'category_batch_times':batches,'rows':output}
    (OUT/'amazon-top10-supplier-table.json').write_text(json.dumps(snapshot,indent=2,default=str),encoding='utf-8')
    with (OUT/'amazon-top10-supplier-table.csv').open('w',newline='',encoding='utf-8-sig') as f:
        flat=[{k:v for k,v in r.items() if k!='vendor_offers'} for r in output]
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    notes=('The latest captured list is used for each category. Top ten eligible components retain their original Amazon ranks; accessories are excluded. '
        'Vendor count includes Amazon, even if its price is missing. Lowest recorded price uses matched new offers captured in the past 30 days and the Amazon snapshot, with unknown inbound postage assumed £0. '
        'These are recorded prices, not a guarantee of current stock. CPK market range is the existing stored min–max aggregate; it can mix conditions and sources and is not an approved sold-price valuation. Missing values are shown as —.')
    money=lambda v:'£'+format(Decimal(str(v)),'.2f') if v is not None else '—'
    lines=['# Amazon top ten: supplier-link summary','',f'Generated: {now.isoformat()}.','',notes,'']
    for bucket in ORDER:
        lines += [f'## {LABEL[bucket]}','', '| Amazon rank | Product | ASIN | CPK | Vendors | Lowest recorded | Linked new price range | Stored CPK market range |','|---:|---|---|---|---:|---:|---:|---:|']
        for r in output:
            if r['component_type']!=LABEL[bucket]:continue
            title=r['product'].replace('|','/');title=title[:100]+('…' if len(title)>100 else '')
            market=f"{money(r['cpk_market_min_gbp'])}–{money(r['cpk_market_max_gbp'])}" if r['cpk_market_listing_count'] else '—'
            new_range=f"{money(r['linked_new_offer_min_gbp'])}–{money(r['linked_new_offer_max_gbp'])}" if r['linked_new_offer_min_gbp'] is not None else '—'
            low=f"[{money(r['lowest_recorded_gbp'])}]({r['lowest_url']})" if r['lowest_url'] else '—'
            lines.append(f"| {r['amazon_rank']} | [{title}]({r['amazon_url']}) | {r['asin']} | {r['cpk'] or 'Missing'} | {r['linked_vendor_count']} | {low} | {new_range} | {market} |")
        lines.append('')
    (OUT/'amazon-top10-supplier-table.md').write_text('\n'.join(lines),encoding='utf-8')
    headers=['Type','Amazon rank','Product','ASIN','CPK','Vendors','Lowest recorded','Linked new price range','Stored CPK market range']
    body=[]
    esc=lambda value:html.escape(str(value or '—'),quote=True)
    for r in output:
        mr=f"{money(r['cpk_market_min_gbp'])} – {money(r['cpk_market_max_gbp'])}" if r['cpk_market_listing_count'] else '—'
        nr=f"{money(r['linked_new_offer_min_gbp'])} – {money(r['linked_new_offer_max_gbp'])}" if r['linked_new_offer_min_gbp'] is not None else '—'
        body.append('<tr>'+''.join(f'<td>{v}</td>' for v in [esc(r['component_type']),r['amazon_rank'],f'<a href="{esc(r["amazon_url"])}">{esc(r["product"])}</a>',esc(r['asin']),esc(r['cpk']),f'<span title="{esc(r["linked_vendors"])}">{r["linked_vendor_count"]}</span>',f'<a href="{esc(r["lowest_url"])}">{money(r["lowest_recorded_gbp"])}</a>',nr,mr])+'</tr>')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><title>Amazon top 10 supplier links</title><style>body{font:14px system-ui;margin:24px;background:#0b1119;color:#e2e8f0}a{color:#67e8f9}p{max-width:1200px;line-height:1.6}table{border-collapse:collapse;width:100%}th{position:sticky;top:0;background:#182537}th,td{padding:10px;text-align:left;border-bottom:1px solid #334155;vertical-align:top}td:nth-child(3){min-width:280px;max-width:520px}td:nth-child(4),td:nth-child(5){font-family:monospace}tr:hover{background:#182537}</style><h1>Amazon top 10 — supplier links and prices</h1><p>'+esc(notes)+'</p><p>Captured data audit: '+esc(now.isoformat())+'</p><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></html>'
    (OUT/'amazon-top10-supplier-table.html').write_text(page,encoding='utf-8')
    print(json.dumps({'rows':len(output),'types':dict(Counter(r['component_type'] for r in output)),
        'with_cpk':sum(bool(r['cpk']) for r in output),'with_non_amazon_vendor':sum(r['linked_vendor_count']>1 for r in output),
        'with_lowest_price':sum(r['lowest_recorded_gbp'] is not None for r in output),'output':str(OUT)},indent=2))
    await engine.dispose()

if __name__=='__main__':asyncio.run(main())
