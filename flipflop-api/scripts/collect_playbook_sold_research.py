"""Bounded, resumable eBay research export. Never approves or publishes offers."""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bs4 import BeautifulSoup
from app.gem_radar.adapters.sold_comps import PlaywrightSoldCompsAdapter

class CapturingAdapter(PlaywrightSoldCompsAdapter):
    def __init__(self):
        self.cards=[]
        self._MAX_PRICE=50000
    def _extract_comps_from_html(self, html, condition):
        # Only public listing-card text and canonical URLs are archived. No
        # authenticated page HTML, headers, cookies or account data is saved.
        soup=BeautifulSoup(html,'lxml')
        for card in soup.select('.s-card[data-listingid], .s-item:not(.s-item--placeholder)'):
            link=card.select_one('a[href*="/itm/"]')
            if link:
                self.cards.append({'text':card.get_text(' ',strip=True),'url':link['href'].split('?')[0]})
        return super()._extract_comps_from_html(html,condition)

def query_blockers(query,title):
    blockers=[]
    # Preserve suffixes even when written separately or after RTX/RX.
    models = re.findall(r'(?<![0-9])(\d{4,5})\s*(X3D|XTX|XT|WX|GT|Ti(?:\s+SUPER)?|SUPER|KS|KF|K|F|X|G)?(?![a-z0-9])', query, re.I)
    for number, suffix in models:
        token = number + suffix.replace(' ', '')
        pattern = r'(?<![0-9])' + number
        if suffix:
            pattern += r'\s*' + r'\s*'.join(re.escape(part) for part in suffix.split())
        pattern += r'(?![a-z0-9])'
        if not re.search(pattern, title, re.I):
            blockers.append('query_model_not_evidenced:' + token)
    if re.search(r'\b(?:refurb(?:ished)?|faulty|spares|repair|untested|barebone|bundle|no gpu|without ram)\b',title,re.I):
        blockers.append('incomplete_defective_or_condition_conflict')
    if re.search(r'(?<![a-z0-9])\d+\s*(?:[-–/])\s*\d+\s*(?:GB|TB)\b',title,re.I):
        blockers.append('configuration_range_in_title')
    return blockers

async def main(args):
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    for query in args.query:
        adapter=CapturingAdapter()
        result=await adapter.fetch(query,'new')
        observed=datetime.now(timezone.utc)
        rows=[]
        for comp in {row.url:row for row in result.comps}.values():
            row=asdict(comp)
            blockers=['complete_specification_and_component_condition_review_pending',
                      'seller_service_and_price_basis_review_pending']
            blockers.extend(query_blockers(query,comp.title or ''))
            if not comp.delivery_cost_known:blockers.append('postage_unknown')
            try:
                date=datetime.strptime(' '.join((comp.sold_date_text or '').split()),'Sold %d %b %Y').replace(tzinfo=timezone.utc)
                row['transaction_date']=date.date().isoformat()
                if not observed-timedelta(days=30)<=date<=observed:blockers.append('outside_30_day_window')
            except ValueError:blockers.append('transaction_date_unknown')
            row.update(status='context_only',blockers=blockers)
            rows.append(row)
        report={'query':query,'observed_at':observed.isoformat(),'publishable':False,
                'provider_available':result.available,'unavailable_reason':result.unavailable_reason,
                'public_cards':adapter.cards,'fixed_price_matching_condition_candidates':rows}
        target=output/('sold-'+hashlib.sha256(query.encode()).hexdigest()[:12]+'-'+observed.strftime('%Y%m%dT%H%M%SZ')+'.json')
        target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'query':query,'cards':len(adapter.cards),'candidates':len(rows),
              'recent_known_delivery':sum(len(r['blockers'])==2 for r in rows),'reason':result.unavailable_reason,'report':str(target)}),flush=True)
        if result.unavailable_reason and any(word in result.unavailable_reason.lower() for word in ('sign-in','verification','login')):
            break

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query',action='append',required=True)
    parser.add_argument('--output',default='../docs/playbook/specifications/2026-10-22/release')
    asyncio.run(main(parser.parse_args()))
