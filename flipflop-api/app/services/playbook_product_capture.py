"""Bounded retailer product-page capture; missing facts stay unknown."""
import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import httpx
from bs4 import BeautifulSoup

RETAILERS=('amazon.co.uk','overclockers.co.uk','royalcdkeys.com')
PARSER_VERSION=12


def max_working_days_for_calendar_duration(calendar_days):
    """Worst weekday count in any start-day window of N elapsed calendar days."""
    if not isinstance(calendar_days,int) or isinstance(calendar_days,bool) or calendar_days<0:
        return None
    return max(sum(1 for offset in range(1,calendar_days+1) if (start+offset)%7<5)
        for start in range(7))


def supported_product_url(url):
    try:
        parsed=urlsplit(url)
        host=(parsed.hostname or '').lower()
        secure=parsed.scheme=='https' and not parsed.username and not parsed.password and parsed.port in (None,443)
        if not secure:
            return False
        if host=='amazon.co.uk' or host.endswith('.amazon.co.uk'):
            return bool(re.search(r'/(?:dp|gp/product)/[A-Z0-9]{10}(?:/|$)',parsed.path,re.I))
        if host=='overclockers.co.uk' or host.endswith('.overclockers.co.uk'):
            path=parsed.path.casefold()
            legacy_product='/product/' in path and not path.startswith('/search')
            current_sku_page=bool(re.search(r'-[a-z0-9]+-\d{4,}\.html$',path)) and not path.startswith('/search')
            # Product slugs can contain literal decimal points (for example,
            # Bluetooth 5.0); the supplier SKU remains constrained separately.
            legacy_sku_page=bool(re.fullmatch(r'/[a-z0-9][a-z0-9.-]+/[a-z]{2,4}-[a-z0-9]{2,6}-[a-z0-9]{2,6}\.html',path))
            return legacy_product or current_sku_page or legacy_sku_page
        if host in {'gamers-outlet.net','www.gamers-outlet.net'}:
            return bool(re.fullmatch(r'/en/buy-[a-z0-9-]+',parsed.path.casefold()))
        if host=='royalcdkeys.com':
            return bool(re.fullmatch(r'/en-gb/products/[a-z0-9][a-z0-9-]*',parsed.path.casefold()))
        if host in {'awd-it.co.uk','www.awd-it.co.uk'}:
            return bool(re.fullmatch(r'/[a-z0-9][a-z0-9-]+\.html',parsed.path.casefold()))
        return False
    except ValueError:
        return False


def amount(value):
    try:
        number=Decimal(str(value))
        return str(number) if number.is_finite() and number>=0 else None
    except InvalidOperation:
        return None


def _price_from_text(value):
    matched=re.search(r'£\s*([\d,]+(?:\.\d{1,2})?)',str(value or ''))
    return amount(matched.group(1).replace(',','')) if matched else None


def _add_product_property(properties,name,value):
    name=str(name).strip().rstrip(':')[:120]
    if not name or value is None:return
    if isinstance(value,list):
        for item in value:_add_product_property(properties,name,item)
        return
    if isinstance(value,str):value=value.strip()[:500]
    if value=='':return
    if name not in properties:properties[name]=value
    elif properties[name]!=value:
        previous=properties[name] if isinstance(properties[name],list) else [properties[name]]
        if value not in previous:properties[name]=[*previous,value]


def _amazon_product_properties(soup):
    """Keep retailer-labelled technical facts without treating them as reviewed fit specs."""
    properties={}
    for table in soup.select('#productDetails_techSpec_section_1, #productDetails_techSpec_section_2, '
            '#productDetails_detailBullets_sections1, #productOverview_feature_div table, '
            '#productDetails_expanderSectionTables table.prodDetTable'):
        for row in table.select('tr'):
            cells=row.find_all(['th','td'],recursive=False)
            if len(cells)>=2:
                name=cells[0].get_text(' ',strip=True).rstrip(':')
                value=cells[1].get_text(' ',strip=True)
                if name and value:
                    _add_product_property(properties,name,value)
    for row in soup.select('#detailBullets_feature_div li, #detailBulletsWrapper_feature_div li'):
        value=row.get_text(' ',strip=True)
        match=re.match(r'\s*([^:]{2,120}):\s*(.{1,500})$',value)
        if match:
            _add_product_property(properties,match.group(1),match.group(2))
    return dict(list(properties.items())[:80])


def _amazon_product_image_urls(soup):
    """Capture distinct full-size image URLs exposed for the exact ASIN page."""
    urls=[]
    for image in soup.select('#altImages img, #landingImage, #imgBlkFront'):
        dynamic=image.get('data-a-dynamic-image')
        dynamic_urls=[]
        if dynamic:
            try:
                data=json.loads(dynamic)
                if isinstance(data,dict):
                    dynamic_urls=[value for value in data if isinstance(value,str) and value.startswith('https://')]
            except (TypeError,ValueError):
                pass
        if dynamic_urls:
            urls.extend(dynamic_urls)
        elif image.get('data-old-hires') and image.get('data-old-hires').startswith('https://'):
            urls.append(image.get('data-old-hires'))
        elif image.get('src','').startswith('https://'):
            urls.append(image.get('src'))
    return list(dict.fromkeys(urls))[:100]


def retain_last_good_capture(previous, attempt, url):
    """Keep a still-identical prior success when a retailer temporarily gates refresh."""
    if (attempt.get('status')!='captured' and previous.get('status')=='captured'
            and previous.get('url')==url):
        return {**previous,'attempted_at':attempt['attempted_at'],'parser_version':PARSER_VERSION,
            'last_capture_attempt':{'status':attempt.get('status'),'reason':attempt.get('reason'),
                'attempted_at':attempt['attempted_at']}}
    return attempt


def product_capture_refresh_due(previous, now):
    """Refresh new/expired captures; back off repeated failures on a retained success."""
    if previous.get('parser_version') != PARSER_VERSION:
        return True
    try:
        last_attempt=previous.get('last_capture_attempt')
        attempted_at=(last_attempt.get('attempted_at') if isinstance(last_attempt,dict) else None)
        checked=datetime.fromisoformat(attempted_at or previous.get('attempted_at',''))
        if not checked.tzinfo:
            return True
        age=(now-checked).total_seconds()
        # If a current successful capture is retained after a failed refresh,
        # retry daily rather than on every hourly Playbook refresh. New/unresolved
        # products still retry hourly so newly available offers enter promptly.
        retry_interval=86400 if last_attempt and previous.get('status')=='captured' else 3600
        return age>=retry_interval
    except (TypeError,ValueError):
        return True


def _product_capture_attempt_epoch(listing):
    """Use the latest attempt (including a failed refresh) for fair queue ordering."""
    previous=(listing.raw_specs or {}).get('playbook_product_capture') or {}
    last_attempt=previous.get('last_capture_attempt')
    attempted_at=(last_attempt.get('attempted_at') if isinstance(last_attempt,dict) else None)
    try:
        checked=datetime.fromisoformat(attempted_at or previous.get('attempted_at',''))
        if checked.tzinfo is None:
            return 0.0
        return checked.timestamp()
    except (TypeError,ValueError):
        return 0.0


def amazon_catalog_capture_refresh_due(previous,now):
    """Refresh Amazon catalogue attributes monthly, and retry access failures weekly."""
    try:
        checked=datetime.fromisoformat(previous.get('attempted_at',''))
        if not checked.tzinfo:return True
        age=(now-checked).total_seconds()
        return age >= (7*86400 if previous.get('status')=='unavailable' else 30*86400)
    except (TypeError,ValueError):
        return True


def retain_last_good_amazon_catalog_capture(previous,attempt,url):
    if (attempt.get('status')!='captured' and previous.get('status')=='captured'
            and previous.get('url')==url and previous.get('asin')==attempt.get('asin')):
        return {**previous,'last_capture_attempt':{'status':attempt.get('status'),
            'error_code':attempt.get('error_code'),'attempted_at':attempt.get('attempted_at')}}
    return attempt


async def refresh_amazon_catalogue_attributes(listings,now=None,*,db=None):
    """Fetch exact-ASIN technical attributes in supported batches of twenty."""
    from app.services.amazon_sp_api import AmazonSPAPI
    now=now or datetime.now(timezone.utc)
    client=AmazonSPAPI()
    if not client.configured:
        return {'attempted':0,'captured':0,'unresolved':0,'unavailable':0,'status':'not_configured'}
    matches={};cached_unavailable=0
    for listing in listings:
        if str(getattr(listing,'source_name','')).casefold()!='amazon':continue
        match=re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)',urlsplit(listing.url).path,re.I)
        if not match:continue
        previous=(listing.raw_specs or {}).get('playbook_amazon_catalog_capture') or {}
        if amazon_catalog_capture_refresh_due(previous,now):
            matches.setdefault(match.group(1).upper(),[]).append(listing)
        elif (previous.get('status')=='unavailable' and previous.get('asin')==match.group(1).upper()
                and previous.get('url')==listing.url):
            cached_unavailable+=1
    asins=list(matches)
    counts={'attempted':len(asins),'captured':0,'unresolved':0,'unavailable':cached_unavailable,
        'cached_unavailable':cached_unavailable,'status':'cached_access_denied' if cached_unavailable and not asins else 'completed'}
    for start in range(0,len(asins),20):
        batch=asins[start:start+20]
        try:
            payload=await client.search_catalog_items_by_asin(batch)
        except Exception as error:
            status='unavailable' if getattr(error,'status_code',None) in {401,403} else 'unresolved'
            counts[status]+=len(batch)
            counts['status']='partial' if counts['status']=='completed' else counts['status']
            result={'status':status,'asin':None,'source':'amazon_sp_api_catalog_items_v2022_04_01',
                'error_code':'access_denied' if status=='unavailable' else type(error).__name__,
                'attempted_at':now.isoformat()}
            for asin in batch:
                for listing in matches[asin]:
                    await _record_amazon_catalog_capture(db,listing,
                        {**result,'asin':asin,'url':listing.url})
            # A role/account error applies to the entire lookup; avoid repeating
            # the same denied call for the remaining batches in this refresh.
            if status=='unavailable':
                for remaining in asins[start+20:]:
                    counts['attempted']+=0;counts['unavailable']+=1
                    for listing in matches[remaining]:
                        await _record_amazon_catalog_capture(db,listing,
                            {**result,'asin':remaining,'url':listing.url})
                break
            continue
        by_asin={str(item.get('asin','')).upper():item for item in payload.get('items',[])
            if isinstance(item,dict) and item.get('asin')}
        for asin in batch:
            item=by_asin.get(asin)
            attributes=item.get('attributes') if isinstance(item,dict) else None
            if not isinstance(attributes,dict):
                counts['unresolved']+=1
                result={'status':'unresolved','asin':asin,'url':None,'source':'amazon_sp_api_catalog_items_v2022_04_01',
                    'error_code':'exact_asin_not_returned','attempted_at':now.isoformat()}
            else:
                selected={key:value for key,value in attributes.items()
                    if re.search(r'socket|form.factor|memory|ram|watt|power|thermal|length|height|cooler|graphics|gpu|interface|connector|module|ddr|storage|m2',key,re.I)}
                result={'status':'captured','asin':asin,'source':'amazon_sp_api_catalog_items_v2022_04_01',
                    'observed_at':now.isoformat(),'attempted_at':now.isoformat(),'attributes':dict(list(selected.items())[:40])}
                counts['captured']+=1
            for listing in matches[asin]:
                await _record_amazon_catalog_capture(db,listing,
                    {**result,'url':listing.url})
    return counts


async def _record_amazon_catalog_capture(db,listing,attempt):
    if db is not None:
        return await persist_product_source_capture(db,listing,'playbook_amazon_catalog_capture',attempt)
    # Lightweight callers may provide in-memory listing records. The production
    # refresh always passes its session so concurrent operator reviews are merged
    # under the row lock in persist_product_source_capture.
    raw=dict(listing.raw_specs or {})
    previous=raw.get('playbook_amazon_catalog_capture') or {}
    raw['playbook_amazon_catalog_capture']=retain_last_good_amazon_catalog_capture(
        previous,attempt,listing.url)
    listing.raw_specs=raw


def capture_refresh_outcome(attempt, stored):
    """Report a successful fetch separately from a retained last-good capture."""
    if attempt.get('status')=='captured': return 'captured'
    if stored.get('last_capture_attempt'): return 'retained'
    return 'unresolved'


async def persist_product_source_capture(db,listing,key,attempt,*,role=None):
    """Merge into the latest row so a slow fetch cannot overwrite an operator review."""
    if key not in {'playbook_product_capture','playbook_amazon_catalog_capture'}:
        raise ValueError('Unknown product source capture')
    await db.flush()
    await db.refresh(listing,with_for_update=True)
    if attempt.get('url') and attempt['url']!=listing.url:
        attempt={'status':'unresolved','reason':'Listing product URL changed while source facts were fetched',
            'url':listing.url,'attempted_at':attempt.get('attempted_at') or datetime.now(timezone.utc).isoformat(),
            'parser_version':PARSER_VERSION}
    previous=(listing.raw_specs or {}).get(key) or {}
    retain=retain_last_good_capture if key=='playbook_product_capture' else retain_last_good_amazon_catalog_capture
    stored=retain(previous,attempt,listing.url)
    raw={**(listing.raw_specs or {}),key:stored}
    # Compatibility facts can be useful even when an Amazon page has no
    # selected offer. Keep this separate from the last-good commercial capture
    # so unresolved price/stock evidence can never become a purchasable source.
    properties=attempt.get('product_properties')
    if (key=='playbook_product_capture' and attempt.get('url')==listing.url
            and isinstance(properties,dict) and properties):
        raw['playbook_product_engineering_capture']={
            'url':listing.url,'title':attempt.get('title') or listing.title,
            'sku':attempt.get('sku'),'observed_at':attempt.get('observed_at') or attempt.get('attempted_at'),
            'product_properties':properties,'engineering_reviewed':False}
    listing.raw_specs=raw
    if key=='playbook_product_capture' and stored.get('status')=='captured':
        listing.price=float(stored['item_gbp'])
        listing.last_seen_at=datetime.fromisoformat(stored['observed_at'].replace('Z','+00:00')).replace(tzinfo=None)
    raw=listing.raw_specs or {}
    role=role or (raw.get('configurator') or {}).get('source_role') or raw.get('gem_radar_category')
    role={'cooler':'cooling','ssd':'storage'}.get(role,role)
    if role:
        from app.services.playbook_service import invalidate_conflicting_product_engineering
        invalidate_conflicting_product_engineering(listing,role)
    return capture_refresh_outcome(attempt,stored)


def _playbook_os_identity_matches(observed_title, captured_title):
    observed=str(observed_title or '')
    captured=str(captured_title or '')
    windows=re.search(r'\bwindows\s+11\s+(home|pro)\b',observed,re.I)
    if windows:
        actual=re.search(r'\bwindows\s+11\s+(home|pro)\b',captured,re.I)
        return bool(actual and windows.group(1).casefold()==actual.group(1).casefold())
    ubuntu=re.search(r'\bubuntu\s*[-–]?\s*24\.04(?:\s+lts)?\b',observed,re.I)
    if ubuntu:
        return bool(re.search(r'\bubuntu\s*[-–]?\s*24\.04(?:\.\d+)?(?:\s+lts)?\b',captured,re.I))
    return False


def valid_unpriced_os_capture(observation, result):
    """Accept only a positive exact-ASIN capture matching a planned OS product."""
    if not isinstance(result,dict) or result.get('status')!='captured':
        return False
    from app.services.amazon_bestsellers import bestseller_item_matches_category
    from app.services.bestseller_catalogue_sync import amazon_asin
    asin=str(getattr(observation,'asin','') or '').upper()
    try:
        item=Decimal(str(result.get('item_gbp')))
    except (InvalidOperation,TypeError,ValueError):
        return False
    return bool(asin and str(result.get('sku') or '').upper()==asin
        and amazon_asin(result.get('url'))==asin
        and item.is_finite() and item>0
        and _playbook_os_identity_matches(getattr(observation,'title',''),result.get('title'))
        and bestseller_item_matches_category(result.get('title') or '', 'os'))


async def capture_unpriced_os_bestsellers(db, limit=12):
    """Capture exact pages for planned Windows 11 editions and Ubuntu 24.04.

    Priced bestseller observations still need exact-page stock, seller, postage
    and arrival evidence. Do not spend the bounded capture budget on unrelated
    legacy operating systems that no authored Playbook requires.
    """
    from sqlalchemy import select
    from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
    from app.services.amazon_bestsellers import (bestseller_item_matches_category,
        OPERATING_SYSTEM_BESTSELLER_LIST_NAME)
    from app.services.bestseller_catalogue_sync import amazon_asin

    now=datetime.now(timezone.utc)
    statement=(select(AmazonBestsellerObservation).where(
        AmazonBestsellerObservation.category=='os',
        AmazonBestsellerObservation.list_name==OPERATING_SYSTEM_BESTSELLER_LIST_NAME,
        AmazonBestsellerObservation.captured_at>=datetime.utcnow()-timedelta(hours=24),
        AmazonBestsellerObservation.url.is_not(None))
        .order_by(AmazonBestsellerObservation.category,AmazonBestsellerObservation.asin,
            AmazonBestsellerObservation.captured_at.desc(),AmazonBestsellerObservation.id.desc())
        .distinct(AmazonBestsellerObservation.category,AmazonBestsellerObservation.asin))
    observations=(await db.execute(statement)).scalars().all()
    planned=[row for row in observations if row.image_url and amazon_asin(row.url)==row.asin.upper()
        and _playbook_os_identity_matches(row.title,row.title)
        and bestseller_item_matches_category(row.title,'os')]
    planned.sort(key=lambda row:(
        0 if re.search(r'windows\s+11\s+home',row.title,re.I) else
        1 if re.search(r'windows\s+11\s+pro',row.title,re.I) else 2,
        row.rank,row.asin))
    eligible=[row for row in planned
        if product_capture_refresh_due(row.product_capture or {},now)][:limit]
    semaphore=asyncio.Semaphore(2)
    async def capture(row):
        async with semaphore:
            try:
                result=await collect_product_capture(row.url)
            except httpx.HTTPError as error:
                result={'status':'unresolved','reason':f'Retailer capture failed: {type(error).__name__}'}
            if result.get('status')=='captured' and not valid_unpriced_os_capture(row,result):
                result={'status':'unresolved','reason':'The exact retailer page did not confirm the observed Windows edition and ASIN'}
            result={**result,'attempted_at':now.isoformat(),'parser_version':PARSER_VERSION}
            return row,result
    attempts=await asyncio.gather(*(capture(row) for row in eligible))
    totals={'attempted':len(attempts),'captured':0,'retained':0,'unresolved':0}
    for row,attempt in attempts:
        stored=retain_last_good_capture(row.product_capture or {},attempt,row.url)
        outcome=capture_refresh_outcome(attempt,stored)
        totals[outcome]+=1
        row.product_capture=stored
    await db.flush()
    return totals


def _amazon_dom_capture(soup,url):
    """Read the selected Amazon ASIN's visible offer when JSON-LD is absent."""
    from urllib.parse import urlsplit
    page_text=soup.get_text(' ',strip=True)
    if re.search(r'continue shopping|enter the characters you see below|automated access|robot check',page_text,re.I):
        return {'status':'unresolved','reason':'Amazon returned a verification/interstitial page; no product facts were captured'}
    requested=re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)',urlsplit(url).path,re.I)
    page_asins={str(node.get('value','')).upper() for node in soup.select('input[name="ASIN"]') if node.get('value')}
    if not requested or page_asins!={requested.group(1).upper()}:
        return None
    price_node=(soup.select_one('#corePrice_feature_div .a-offscreen')
        or soup.select_one('#corePriceDisplay_desktop_feature_div .a-offscreen'))
    item= _price_from_text(price_node.get_text(' ',strip=True) if price_node else None)
    title_node=soup.select_one('#productTitle')
    availability_node=soup.select_one('#availability')
    delivery_container=soup.select_one('#deliveryBlockContainer')
    availability=availability_node.get_text(' ',strip=True) if availability_node else ''
    # Long back-order windows are not usable in-stock evidence for a current
    # Playbook supplier offer. Amazon sometimes renders these as
    # "Usually dispatched within 3 to 7 months"; the generic dispatched-within
    # matcher below must not turn that into an available listing.
    long_backorder=bool(re.search(
        r'\b(?:dispatch(?:ed)?|delivery)\b.{0,80}\b\d+\s*(?:to|[-–])\s*\d+\s+months?\b',
        availability,re.I))
    stock=('unavailable' if long_backorder or re.search(r'currently unavailable|out of stock|sold out',availability,re.I)
        else 'available' if re.search(r'\bin stock\b|only\s+\d+\s+left|available to ship|usually dispatched within\s+\d+',availability,re.I)
        else 'unknown')
    if item is None or title_node is None:
        technical_facts={'url':url,'sku':requested.group(1).upper(),
            'title':title_node.get_text(' ',strip=True) if title_node else None,
            'observed_at':datetime.now(timezone.utc).isoformat(),
            'product_properties':_amazon_product_properties(soup),
            'product_image_urls':_amazon_product_image_urls(soup),'engineering_reviewed':False}
        if title_node is not None and stock=='unavailable':
            return {'status':'unresolved','reason':'The exact Amazon ASIN is currently unavailable; no active seller offer or price was displayed',
                **technical_facts,'stock_status':'unavailable','stock_evidence':availability[:1000]}
        return {'status':'unresolved','reason':'The exact Amazon ASIN page did not expose one selected GBP price',
            **technical_facts}
    if not availability:
        stock_evidence=None
    else:
        stock_evidence=availability[:1000] if stock!='unknown' else None

    merchant_node=soup.select_one('#merchant-info')
    seller_node=soup.select_one('#sellerProfileTriggerId')
    merchant=merchant_node.get_text(' ',strip=True) if merchant_node else ''
    seller=seller_node.get_text(' ',strip=True) if seller_node else None
    title=title_node.get_text(' ',strip=True)
    used=bool(re.search(r'amazon resale|renewed|refurbished|\bused\b|second[- ]hand',merchant+' '+title,re.I))
    seller_match=re.search(r'Sold by\s+(.+?)(?:\s+and\s+Fulfilled by|\s+Fulfilled by|\s*\.)',merchant,re.I)
    seller=seller_match.group(1).strip() if seller_match else seller

    delivery_nodes=(delivery_container.select('[data-csa-c-delivery-time][data-csa-c-delivery-type="delivery"]')
        if delivery_container else [])
    defaults=[node for node in delivery_nodes if node.get('data-csa-c-mir-variant')=='DEFAULT']
    delivery=defaults[0] if defaults else (delivery_nodes[0] if delivery_nodes else None)
    postage=None;calendar_days=None;delivery_text=None
    if delivery:
        delivery_text=delivery.get_text(' ',strip=True)
        raw_price=(delivery.get('data-csa-c-delivery-price') or '').strip()
        if raw_price.upper()=='FREE' or re.search(r'\bFREE delivery\b',delivery_text,re.I):
            postage='0'
        else:
            postage=_price_from_text(raw_price) or _price_from_text(delivery_text)
        date_text=delivery.get('data-csa-c-delivery-time') or ''
        range_match=re.search(r'(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*)?(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)',date_text)
        date_match=re.search(r'(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*)?(\d{1,2}\s+[A-Za-z]+)',date_text)
        if date_match:
            try:
                today=datetime.now(timezone.utc).date()
                if range_match:
                    arrival=datetime.strptime(f"{range_match.group(2)} {range_match.group(3)} {today.year}",'%d %B %Y').date()
                else:
                    arrival=datetime.strptime(f"{date_match.group(1)} {today.year}",'%d %B %Y').date()
                if arrival<today: arrival=arrival.replace(year=today.year+1)
                calendar_days=(arrival-today).days
            except ValueError:
                calendar_days=None
    postage_verified=postage is not None and bool(delivery_text)
    # Only record Prime when Amazon marks the selected delivery promise as
    # Prime. Absence of a badge is unknown; the downstream listing fallback
    # treats unknown as the configured non-Prime Amazon default.
    prime_eligible=_amazon_prime_eligibility(soup)
    destination_text=delivery_container.get_text(' ',strip=True) if delivery_container else ''
    postcode=(re.search(r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b',destination_text,re.I)
        or re.search(r'\b[A-Z]{1,2}\d[A-Z\d]?\b',destination_text,re.I))
    return {'status':'captured','url':url,'observed_at':datetime.now(timezone.utc).isoformat(),
        'title':title,'sku':requested.group(1).upper(),'mpn':None,'merchant_name':seller,
        'condition':'used' if used else 'new','item_gbp':item,'delivery_gbp':postage,
        'postage_verified':postage_verified,'delivery_calendar_days':calendar_days,
        'delivery_working_days':max_working_days_for_calendar_duration(calendar_days),
        'delivery_estimate_source':'amazon_displayed_default_destination' if calendar_days is not None else None,
        'prime_eligible':prime_eligible,
        'delivery_destination':postcode.group(0).upper() if postcode else None,
        'stock_status':stock,'stock_evidence':stock_evidence,
        'product_properties':_amazon_product_properties(soup),
        'product_image_urls':_amazon_product_image_urls(soup),'engineering_reviewed':False,
        'merchant_text':merchant[:1000] if merchant else None}


def parse_product_capture(html,url):
    soup=BeautifulSoup(html,'html.parser')
    products=[]
    def visit(value):
        if isinstance(value,list):
            for item in value: visit(item)
        elif isinstance(value,dict):
            kind=value.get('@type',[])
            if 'Product' in ([kind] if isinstance(kind,str) else kind if isinstance(kind,list) else []): products.append(value)
            if '@graph' in value: visit(value['@graph'])
    for script in soup.select('script[type="application/ld+json"]'):
        try: visit(json.loads(script.string or script.get_text()))
        except (ValueError,TypeError): continue
    if len(products)!=1:
        if (urlsplit(url).hostname or '').casefold() in {'awd-it.co.uk','www.awd-it.co.uk'}:
            main=soup.select_one('.product-info-main')
            canonical=soup.select_one('link[rel="canonical"]')
            heading=soup.select_one('h1 [itemprop="name"]')
            prices=main.select('.price-including-tax[data-price-type="finalPrice"][data-price-amount]') if main else []
            currency=soup.select_one('meta[property="product:price:currency"]')
            availability=main.select_one('[itemprop="availability"]') if main else None
            availability_meta=soup.select_one('meta[property="product:availability"]')
            availability_value=availability.get('href') if availability else None
            if not availability_value and availability_meta:
                label=str(availability_meta.get('content') or '').strip().casefold()
                availability_value={'in stock':'https://schema.org/InStock',
                    'out of stock':'https://schema.org/OutOfStock'}.get(label)
            from app.services.commercial_readiness import same_listing_product
            if (canonical and heading and currency and currency.get('content')=='GBP'
                    and same_listing_product(canonical.get('href'),url) and len(prices)==1):
                product={'@type':'Product','url':url,'name':heading.get_text(' ',strip=True),
                    'offers':{'url':url,'price':prices[0].get('data-price-amount'),
                        'priceCurrency':'GBP','availability':availability_value}}
                sku=main.select_one('[itemprop="sku"]')
                if sku:product['sku']=sku.get_text(' ',strip=True)
                # Scope to the selected product and tax-inclusive final price;
                # recommendation grids and crossed-out RRPs are not offers.
                return parse_product_capture('<script type="application/ld+json">'+json.dumps(product)+'</script>',url)
        if 'amazon.co.uk' in (urlsplit(url).hostname or '').casefold():
            captured=_amazon_dom_capture(soup,url)
            if captured is not None: return captured
        return {'status':'unresolved','reason':'Exactly one identified product is required'}
    product=products[0]
    offers=product.get('offers',[])
    offers=offers if isinstance(offers,list) else [offers]
    # Do not choose an arbitrary seller or aggregate minimum price.
    if len(offers)!=1 or not isinstance(offers[0],dict):
        return {'status':'unresolved','reason':'An exact seller offer is required'}
    offer=offers[0]
    if offer.get('priceCurrency')!='GBP' or amount(offer.get('price')) is None:
        return {'status':'unresolved','reason':'Exact GBP offer price is missing'}
    identity=product.get('url') or offer.get('url')
    from app.services.commercial_readiness import same_listing_product
    if not identity or not same_listing_product(identity,url):
        return {'status':'unresolved','reason':'Product identity does not match the requested listing'}
    stock=(offer.get('availability') or '').rsplit('/',1)[-1]
    shipping=offer.get('shippingDetails',[])
    shipping=shipping if isinstance(shipping,list) else [shipping]
    postage=None;calendar_days=None
    if len(shipping)==1 and isinstance(shipping[0],dict):
        detail=shipping[0]
        rate=detail.get('shippingRate') or {}
        destination=detail.get('shippingDestination') or {}
        if destination.get('addressCountry')=='GB' and rate.get('currency')=='GBP':
            postage=amount(rate.get('value'))
        delivery=detail.get('deliveryTime') or {}
        intervals=[delivery.get(name) or {} for name in ('handlingTime','transitTime')]
        if all(item.get('unitCode')=='DAY' and isinstance(item.get('maxValue'),int) and not isinstance(item.get('maxValue'),bool) and item['maxValue']>=0 for item in intervals):
            calendar_days=sum(item['maxValue'] for item in intervals)
    properties=product.get('additionalProperty',[])
    properties=properties if isinstance(properties,list) else [properties]
    captured_properties={}
    for prop in properties[:80]:
        if isinstance(prop,dict) and prop.get('name'):
            _add_product_property(captured_properties,prop['name'],prop.get('value'))
    if (urlsplit(url).hostname or '').lower().endswith('amazon.co.uk'):
        for name,value in _amazon_product_properties(soup).items():
            _add_product_property(captured_properties,name,value)
    product_images=product.get('image',[])
    product_images=product_images if isinstance(product_images,list) else [product_images]
    product_images=[value if isinstance(value,str) else (value.get('url') or value.get('contentUrl'))
        for value in product_images if isinstance(value,(str,dict))]
    product_images=[value for value in product_images if isinstance(value,str) and value.startswith('https://')]
    if (urlsplit(url).hostname or '').lower().endswith('amazon.co.uk'):
        product_images.extend(_amazon_product_image_urls(soup))
    condition_evidence=offer.get('itemCondition') or product.get('itemCondition')
    condition=str(condition_evidence or 'unknown').rsplit('/',1)[-1]
    if condition=='unknown' and (urlsplit(url).hostname or '').casefold() in {
            'overclockers.co.uk','www.overclockers.co.uk','awd-it.co.uk','www.awd-it.co.uk'}:
        # These allowlisted first-party retail product pages sell ordinary
        # retail stock by default; second-hand/B-grade/refurbished stock is
        # separately labelled. Preserve the basis so source review can audit
        # the inference rather than silently treating every unknown as new.
        product_text=' '.join((str(product.get('name') or ''),
            str(product.get('description') or ''))).casefold()
        second_hand=r'\b(?:used|refurbished|refurb|pre[- ]?owned|open[- ]?box|b[- ]?grade|b[- ]?stock)\b'
        if not re.search(second_hand,product_text):
            condition='NewCondition'
            condition_evidence='first_party_retail_default_new_no_second_hand_designation'
    brand=product.get('brand') or {}
    brand=brand.get('name') if isinstance(brand,dict) else brand
    return {'status':'captured','url':url,'observed_at':datetime.now(timezone.utc).isoformat(),
        'title':product.get('name'),'sku':product.get('sku'),'mpn':product.get('mpn'),
        'product_brand':brand,'product_description':str(product.get('description') or '')[:4000],
        'condition':{'NewCondition':'new','UsedCondition':'used','RefurbishedCondition':'refurbished'}.get(condition,'unknown'),
        'condition_evidence':condition_evidence,
        'item_gbp':amount(offer['price']),'delivery_gbp':postage,'postage_verified':postage is not None,
        'delivery_calendar_days':calendar_days,
        'delivery_working_days':max_working_days_for_calendar_duration(calendar_days),
        'delivery_estimate_source':'structured_product_offer_calendar_days',
        'stock_status':{'InStock':'available','OutOfStock':'unavailable','SoldOut':'unavailable'}.get(stock,'unknown'),
        'stock_evidence':offer.get('availability'),
        'product_image_urls':list(dict.fromkeys(product_images))[:100],
        'product_properties':captured_properties,
        'engineering_reviewed':False,
        'prime_eligible':_amazon_prime_eligibility(soup) if (urlsplit(url).hostname or '').lower().endswith('amazon.co.uk') else None}


def _amazon_prime_eligibility(soup):
    """Return True only when the selected delivery option visibly says Prime."""
    container=soup.select_one('#deliveryBlockContainer')
    if not container:
        return None
    nodes=container.select('[data-csa-c-delivery-time][data-csa-c-delivery-type="delivery"]')
    defaults=[node for node in nodes if node.get('data-csa-c-mir-variant')=='DEFAULT']
    delivery=defaults[0] if defaults else (nodes[0] if nodes else None)
    text=delivery.get_text(' ',strip=True) if delivery else ''
    return True if re.search(r'\bprime\b',text,re.I) else None


def parse_royalcdkeys_capture(html,url,product_json):
    """Capture a single UK digital-key offer without treating seller claims as verified licence rights."""
    from decimal import Decimal
    soup=BeautifulSoup(html,'html.parser')
    parsed=urlsplit(url)
    requested=re.fullmatch(r'/en-gb/products/([a-z0-9][a-z0-9-]*)',parsed.path.casefold())
    if not requested or not isinstance(product_json,dict) or product_json.get('handle')!=requested.group(1):
        return {'status':'unresolved','reason':'The exact RoyalCDKeys product handle could not be confirmed'}
    currency=(soup.select_one('meta[property="og:price:currency"]') or {}).get('content')
    price_text=(soup.select_one('meta[property="og:price:amount"]') or {}).get('content')
    try:
        item=Decimal(str(price_text))
        shopify_price=Decimal(str(product_json.get('price')))/Decimal('100')
    except Exception:
        return {'status':'unresolved','reason':'The exact UK product page did not expose one GBP price'}
    if currency!='GBP' or not item.is_finite() or item<=0 or item!=item.quantize(Decimal('.01')) or shopify_price!=item:
        return {'status':'unresolved','reason':'The product page and UK product feed did not agree on one GBP price'}
    variants=product_json.get('variants')
    if not isinstance(variants,list) or len(variants)!=1 or not isinstance(variants[0],dict):
        return {'status':'unresolved','reason':'The product has multiple variants; no arbitrary key offer was selected'}
    variant=variants[0]
    if Decimal(str(variant.get('price')))/Decimal('100')!=item:
        return {'status':'unresolved','reason':'The selected product variant price does not match the product page'}
    description=' '.join(BeautifulSoup(str(product_json.get('description') or ''),'html.parser').get_text(' ',strip=True).split())
    page_text=' '.join(soup.get_text(' ',strip=True).split())
    combined=f'{product_json.get("title") or ""} {description} {page_text}'
    digital=bool(re.search(r'\binstant\s+(?:digital\s+)?delivery\b|\bdigital\s+delivery\b',combined,re.I)
        and re.search(r'\b(?:digital|email|e-mail|product\s+key|activation\s+key)\b',combined,re.I))
    available=product_json.get('available')
    stock='available' if available is True else 'unavailable' if available is False else 'unknown'
    stock_evidence=(f"RoyalCDKeys product feed reports available={str(available).lower()}; key quantity is not exposed"
        if isinstance(available,bool) else None)
    title=str(product_json.get('title') or '').strip()
    if not title:
        return {'status':'unresolved','reason':'The exact product title is missing'}
    license_type=('OEM' if re.search(r'\boem\b',combined,re.I) else
        'Retail' if re.search(r'\bretail\b',combined,re.I) else 'Not stated')
    device_scope=('One device (supplier claim)' if re.search(r'\b(?:one|1)\s+(?:computer|pc|device)\b',description,re.I)
        else 'Not stated by supplier')
    transferability=('Non-transferable (supplier claim)' if re.search(r'\bcannot be transferred\b|\bnon[- ]transferable\b',description,re.I)
        else 'Transfer rights not stated by supplier')
    key_reuse=('Supplier says a unique key per licence is not guaranteed' if re.search(
        r'\b(?:same|duplicate)\s+(?:activation\s+)?key\b.{0,120}\b(?:not guaranteed|multiple|more than one)\b|\bunique\s+key\b.{0,100}\bnot guaranteed\b',description,re.I)
        else 'No key-reuse statement captured')
    properties={
        'License type (supplier listing)':license_type,
        'Device scope (supplier claim)':device_scope,
        'Transferability (supplier claim)':transferability,
        'Key uniqueness (supplier claim)':key_reuse,
        'UK activation eligibility':'Not established by the captured listing',
        'Reseller / system-builder authorization':'Not established by the captured listing',
        'Product description (supplier text)':description[:1000],
    }
    licence_basis=json.dumps({'url':url,'handle':requested.group(1),'title':title,
        'properties':properties,'seller_product_claims':description[:2000]},
        sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
    image=(soup.select_one('meta[property="og:image"]') or {}).get('content')
    sku=str(variant.get('sku') or variant.get('id') or product_json.get('id') or requested.group(1))
    return {'status':'captured','url':url,'observed_at':datetime.now(timezone.utc).isoformat(),
        'title':title,'sku':sku,'mpn':None,'merchant_name':'RoyalCDKeys','condition':'new',
        'item_gbp':str(item),'delivery_gbp':'0' if digital else None,
        'postage_verified':digital,'delivery_calendar_days':0 if digital else None,
        'delivery_working_days':0 if digital else None,
        'delivery_estimate_source':'seller_claimed_instant_digital_delivery' if digital else None,
        'delivery_destination':'GB' if digital else None,'stock_status':stock,'stock_evidence':stock_evidence,
        'product_properties':properties,'engineering_reviewed':False,'digital_product':digital,
        'licence_resale_rights_verified':False,'licence_review_required':True,
        'licence_review_fingerprint':hashlib.sha256(licence_basis).hexdigest(),
        'supplier_product_handle':requested.group(1),'image_url':image,
        'seller_product_claims':description[:2000]}


async def _collect_royalcdkeys_capture(url):
    parsed=urlsplit(url)
    match=re.fullmatch(r'/en-gb/products/([a-z0-9][a-z0-9-]*)',parsed.path.casefold())
    if not match:
        return {'status':'unsupported','reason':'Only exact UK RoyalCDKeys product pages are supported'}
    handle=match.group(1)
    async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
        response=await client.get(url,headers={'Accept':'text/html'})
        if response.status_code!=200 or 'text/html' not in response.headers.get('content-type',''):
            return {'status':'unresolved','reason':f'RoyalCDKeys product page returned HTTP {response.status_code}'}
        product_response=await client.get(
            f'https://royalcdkeys.com/products/{handle}.js?country=GB&currency=GBP',
            headers={'Accept':'application/json'})
        if product_response.status_code!=200:
            return {'status':'unresolved','reason':f'RoyalCDKeys UK product feed returned HTTP {product_response.status_code}'}
        try:
            product_json=product_response.json()
        except ValueError:
            return {'status':'unresolved','reason':'RoyalCDKeys product feed returned invalid JSON'}
        return parse_royalcdkeys_capture(response.text,url,product_json)


async def _collect_gamers_outlet_capture(url, *, browser_runtime=None):
    """Capture an exact digital offer, with dated GBP conversion and unapproved rights."""
    import xml.etree.ElementTree as ET
    html=None;http_reason=None
    async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
        response=await client.get(url)
        if response.status_code==200 and 'text/html' in response.headers.get('content-type',''):
            html=response.text
        else:
            http_reason=f'Gamers Outlet returned HTTP {response.status_code}'
    if html is None and browser_runtime is not None:
        _,context=browser_runtime
        page=await context.new_page()
        try:
            response=await page.goto(url,wait_until='domcontentloaded',timeout=45000)
            if response is not None and response.status==200:
                try: await page.wait_for_selector('script[type="application/ld+json"]',timeout=8000)
                except Exception: pass
                html=await page.content()
        finally:
            await page.close()
    if html is None:
        return {'status':'unresolved','reason':http_reason or 'Gamers Outlet page could not be loaded'}
    soup=BeautifulSoup(html,'html.parser')
    products=[]
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            item=json.loads(script.get_text())
            if isinstance(item,dict) and item.get('@type')=='Product':products.append(item)
        except (ValueError,TypeError):pass
    if len(products)!=1:return {'status':'unresolved','reason':'One exact software product required'}
    product=products[0];offer=product.get('offers')
    if not isinstance(offer,dict):return {'status':'unresolved','reason':'One exact software offer required'}
    original_currency=offer.get('priceCurrency');original_price=amount(offer.get('price'))
    if original_price is None or original_currency not in {'EUR','GBP'}:
        return {'status':'unresolved','reason':'Software price or supported currency missing'}
    rate=Decimal(1);rate_date=None
    if original_currency=='EUR':
        async with httpx.AsyncClient(timeout=15) as client:
            rates=await client.get('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml')
        rates.raise_for_status();root=ET.fromstring(rates.text)
        rate_date=next(node.attrib['time'] for node in root.iter() if 'time' in node.attrib)
        rate=Decimal(next(node.attrib['rate'] for node in root.iter() if node.attrib.get('currency')=='GBP'))
        age=datetime.now(timezone.utc)-datetime.fromisoformat(rate_date).replace(tzinfo=timezone.utc)
        if not 0<=age.total_seconds()<=7*86400 or rate<=0:
            return {'status':'unresolved','reason':'Fresh ECB GBP conversion rate required'}
    offer['priceCurrency']='GBP';offer['price']=str((Decimal(original_price)*rate).quantize(Decimal('.01')))
    capture=parse_product_capture('<script type="application/ld+json">'+json.dumps(product)+'</script>',url)
    if capture.get('status')!='captured':return capture
    # Exact product page's bulk/edition notice; navigation options are not evidence.
    oem=any('OEM Version' in span.get_text(' ',strip=True) for span in soup.select('span')
            if 'big amount of copies' in span.get_text(' ',strip=True))
    properties={'License type (supplier listing)':'oem' if oem else 'unspecified',
        'Activation region (supplier claim)':'Global' if 'global' in str(product.get('name','')).casefold() else 'unspecified'}
    licence_facts={'url':url,'properties':properties,'product_name':product.get('name'),
        'rights_verified':False}
    capture.update(digital_product=True,delivery_gbp='0.00',postage_verified=True,
        delivery_working_days=0,delivery_estimate_source='digital_delivery',
        licence_review_required=True,licence_resale_rights_verified=False,
        supplier_product_handle=urlsplit(url).path.rsplit('/',1)[-1],
        product_properties=properties,seller_product_claims=product.get('description'),
        licence_review_fingerprint=hashlib.sha256(json.dumps(licence_facts,sort_keys=True).encode()).hexdigest(),
        source_currency=original_currency,source_item_price=str(original_price),exchange_rate=str(rate),
        exchange_rate_date=rate_date,exchange_rate_source='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml')
    return capture


async def collect_product_capture(url, *, browser_runtime=None):
    if not supported_product_url(url):
        return {'status':'unsupported','reason':'Only known HTTPS retailer product URLs are supported'}
    if (urlsplit(url).hostname or '').casefold() in {'gamers-outlet.net','www.gamers-outlet.net'}:
        return await _collect_gamers_outlet_capture(url,browser_runtime=browser_runtime)
    if (urlsplit(url).hostname or '').casefold()=='royalcdkeys.com':
        return await _collect_royalcdkeys_capture(url)
    http_reason=None
    async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
        async with client.stream('GET',url,headers={'Accept':'text/html'}) as response:
            if response.status_code==200 and 'text/html' in response.headers.get('content-type',''):
                payload=bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload)>3_000_000:
                        break
                if len(payload)<=3_000_000:
                    captured=parse_product_capture(payload.decode('utf-8',errors='replace'),url)
                    if captured.get('status')=='captured':
                        return captured
                    http_reason=captured.get('reason')
                else:
                    http_reason='Product page exceeds capture size limit'
            elif response.status_code!=200:
                http_reason=f'Retailer returned HTTP {response.status_code}'
            else:
                http_reason='Retailer response is not an HTML product page'
    # Amazon often renders the selected offer only after client-side scripts.
    # Retry unresolved pages through the serialized browser already used for
    # Amazon bestseller sourcing. Exact ASIN/offer checks still run in parser.
    if (urlsplit(url).hostname or '').lower().endswith('amazon.co.uk'):
        try:
            async def capture_in_context(context):
                page=await context.new_page()
                try:
                    response=await page.goto(url,wait_until='domcontentloaded',timeout=45000)
                    if response is None or response.status!=200:
                        return {'status':'unresolved','reason':'Browser retailer request did not return HTTP 200'}
                    try:
                        await page.wait_for_selector('#productTitle, input[name="ASIN"]',timeout=12000)
                    except Exception:
                        pass
                    return parse_product_capture(await page.content(),url)
                finally:
                    await page.close()
            if browser_runtime is not None:
                _,context=browser_runtime
                browser_result=await capture_in_context(context)
            else:
                from app.services.browser_pool import managed_playwright
                from app.swarms.cases import _make_pw_context
                async with managed_playwright() as playwright:
                    browser,context=await _make_pw_context(playwright)
                    try:
                        browser_result=await capture_in_context(context)
                    finally:
                        await context.close()
                        await browser.close()
            if browser_result.get('status')=='captured':
                browser_result['capture_method']='playwright_fallback'
                return browser_result
            return {**browser_result,'http_capture_reason':http_reason}
        except Exception as error:
            return {'status':'unresolved','reason':f'Browser product capture failed: {type(error).__name__}',
                'http_capture_reason':http_reason}
    return {'status':'unresolved','reason':http_reason}


def playbook_capture_listing_ids(proposals,requested_listing_ids=None):
    """Collect exact supplier targets from pending BOMs and upsell alternatives."""
    listing_ids=set(requested_listing_ids or ())
    for proposal in proposals:
        if (getattr(proposal,'demand_signals',None) or {}).get('source')!='catalogue_playbook_service_v1':
            continue
        data=getattr(proposal,'proposed_data',None) or {}
        parts=[*data.get('components',[]),*(item.get('component') or {} for item in data.get('upsells',[]))]
        for part in parts:
            listing_id=part.get('listing_id')
            if not listing_id:continue
            role=str(part.get('role') or '')
            if role.startswith('os') and not any(host in str(part.get('source_url') or '').casefold() for host in ('royalcdkeys.com','gamers-outlet.net')):
                continue
            listing_ids.add(listing_id)
    return listing_ids


def _benchmark_qualified_missing_alternative(listing, missing_targets, benchmark_index,
        target_constraints):
    """Prioritise exact-page capture for viable substitutes to a missing BOM role.

    This only expands source research. Assembly still requires reviewed
    compatibility facts, a current exact offer, and operator approval.
    """
    bestseller=(listing.raw_specs or {}).get('bestseller') or {}
    role=bestseller.get('category')
    if role not in {'cpu','gpu'}:
        return False
    from app.services.benchmark_normaliser import normalise_cpu,normalise_gpu
    normalise=normalise_cpu if role=='cpu' else normalise_gpu
    candidate_model=normalise(listing.title)
    if not candidate_model or candidate_model in missing_targets[role]:
        return False
    candidate=benchmark_index.get((role,candidate_model))
    if not candidate or not candidate.benchmark_source or (candidate.confidence_score or 0)<0.8:
        return False
    candidate_score=candidate.overall_score
    if candidate_score is None:
        return False
    for target_model in missing_targets[role]:
        target=benchmark_index.get((role,target_model))
        if (not target or target.benchmark_source!=candidate.benchmark_source
                or (target.confidence_score or 0)<0.8 or target.overall_score is None
                or candidate_score<target.overall_score):
            continue
        constraints=target_constraints.get(role,{}).get(target_model,{})
        if role=='cpu':
            from app.services.compatibility_engine import _infer_cpu_socket
            expected_sockets=constraints.get('sockets') or set()
            candidate_socket=_infer_cpu_socket(listing.title)
            if expected_sockets and candidate_socket not in expected_sockets:
                continue
            if constraints.get('integrated_graphics_required') and not re.search(
                    r'\b(?:integrated\s+(?:radeon|intel|uhd|iris)?\s*graphics|apu)\b',
                    listing.title,re.I):
                continue
        else:
            minimum_vram=constraints.get('minimum_vram_gb') or 0
            if minimum_vram:
                from app.services.curated_build_policy import _capacity_gb
                actual_vram=candidate.vram_gb or _capacity_gb(listing.title) or 0
                if actual_vram<minimum_vram:
                    continue
        return True
    return False


async def refresh_selected_product_facts(db, limit=64, *, listing_ids=None, force=False):
    """Advance persisted source work without publishing or approving stock."""
    from collections import defaultdict
    from time import perf_counter
    from sqlalchemy import select
    from app.models.listing import Listing
    from app.models.playbook import PlaybookProposal
    proposals=(await db.execute(select(PlaybookProposal).where(PlaybookProposal.status=='pending'))).scalars().all()
    source_roles={part['listing_id']:part.get('role') for proposal in proposals
        for part in [*(proposal.proposed_data or {}).get('components',[]),
            *(item.get('component') or {} for item in (proposal.proposed_data or {}).get('upsells',[]))]
        if part.get('listing_id')}
    ids=playbook_capture_listing_ids(proposals,requested_listing_ids=listing_ids)
    # Software offers are captured from the explicitly selected provider's
    # exact product pages. Keep legacy RoyalCDKeys records reviewable, while
    # ensuring the current Gamers Outlet Windows and Office offers are also
    # refreshed even when a proposal does not currently select them.
    catalogue_software=(await db.execute(select(Listing).where(
        Listing.status=='active',Listing.source_name.in_(('Gamers Outlet','RoyalCDKeys'))))).scalars().all()
    ids.update(row.id for row in catalogue_software
        if ((row.raw_specs or {}).get('gamers_outlet') or
            (row.raw_specs or {}).get('royalcdkeys') or {}).get('category') in {'os','office'})
    # Bestseller rows without a ranking-page price still represent real Amazon
    # products. Capture their exact selected offers before syncing them into
    # Playbook slots; never promote the ranking snapshot itself into cost.
    unpriced_bestsellers=(await db.execute(select(Listing).where(
        Listing.status=='active',Listing.source_name=='amazon',Listing.price.is_(None))
        .order_by(Listing.id))).scalars().all()
    ids.update(row.id for row in unpriced_bestsellers
        if ((row.raw_specs or {}).get('bestseller') or {}).get('category')
            in {'cpu','gpu','ram','storage','motherboard','psu','cooler','case'})
    rows=(await db.execute(select(Listing).where(Listing.id.in_(ids)).order_by(Listing.id))).scalars().all() if ids else []
    if listing_ids is not None:rows=[listing for listing in rows if listing.id in listing_ids]
    pending=[]
    now=datetime.now(timezone.utc)
    for listing in rows:
        previous=(listing.raw_specs or {}).get('playbook_product_capture') or {}
        if not force and not product_capture_refresh_due(previous,now): continue
        if supported_product_url(listing.url): pending.append(listing)
    # Prioritize Windows 11 catalogue products, then exact authored CPU/GPU
    # models whose bestseller pages omitted a price. Those exact pages can be
    # captured independently; rank price remains demand evidence only.
    from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu
    from app.services.curated_build_policy import definitions as playbook_definitions
    from app.models.benchmark import HardwareBenchmark
    from app.services.compatibility_engine import _infer_cpu_socket
    targets={'cpu':set(),'gpu':set()}
    missing_targets={'cpu':set(),'gpu':set()}
    target_constraints={'cpu':{},'gpu':{}}
    current_cells={(proposal.proposed_data or {}).get('cell_id'):proposal.proposed_data or {}
        for proposal in proposals if (proposal.demand_signals or {}).get('source')=='catalogue_playbook_service_v1'}
    for definition in playbook_definitions().get('builds',[]):
        components=definition.get('components') or {}
        for role,normalise in (('cpu',normalise_cpu),('gpu',normalise_gpu)):
            value=str(components.get(role) or '')
            if value and not (role=='gpu' and 'integrated' in value.casefold()):
                targets[role].add(normalise(value))
                proposal=current_cells.get(definition.get('id'))
                if proposal is not None and role not in {part.get('role') for part in proposal.get('components',[])}:
                    missing_targets[role].add(normalise(value))
                    requirement=target_constraints[role].setdefault(normalise(value),{
                        'sockets':set(),'integrated_graphics_required':False,'minimum_vram_gb':0})
                    if role=='cpu':
                        socket=_infer_cpu_socket(value)
                        if socket:requirement['sockets'].add(socket)
                        requirement['integrated_graphics_required'] |= 'integrated' in str(
                            components.get('gpu') or '').casefold()
                    else:
                        from app.services.curated_build_policy import _capacity_gb
                        requirement['minimum_vram_gb']=max(requirement['minimum_vram_gb'],
                            _capacity_gb(value) or 0)
    benchmark_rows=(await db.execute(select(HardwareBenchmark).where(
        HardwareBenchmark.component_type.in_(('cpu','gpu'))))).scalars().all()
    benchmark_index={(row.component_type,row.normalized_model):row for row in benchmark_rows}
    def exact_authored_target(listing,models=targets):
        bestseller=(listing.raw_specs or {}).get('bestseller') or {}
        category=bestseller.get('category')
        normalise=normalise_cpu if category=='cpu' else normalise_gpu if category=='gpu' else None
        return bool(normalise and normalise(listing.title) in models[category])
    def listing_rank(listing):
        try: return int(((listing.raw_specs or {}).get('bestseller') or {}).get('rank') or 10000)
        except (TypeError,ValueError): return 10000
    def capture_priority(listing):
        raw=listing.raw_specs or {}
        software=raw.get('gamers_outlet') or raw.get('royalcdkeys') or {}
        return (0 if software.get('category')=='os' and listing.source_name=='Gamers Outlet' else
            1 if software.get('category')=='office' and listing.source_name=='Gamers Outlet' else
            2 if (raw.get('bestseller') or {}).get('category')=='os'
                and 'windows 11' in listing.title.casefold() else
            3 if listing.price is None and exact_authored_target(listing,missing_targets) else
            4 if listing.price is None and _benchmark_qualified_missing_alternative(
                listing,missing_targets,benchmark_index,target_constraints) else
            5 if listing.price is None and exact_authored_target(listing) else 6)

    # Within each importance tier, give untouched and oldest-attempted pages
    # first access to the bounded capture budget. A gated page must not starve
    # other authored products on every hourly pass.
    pending.sort(key=lambda listing:(capture_priority(listing),
        _product_capture_attempt_epoch(listing),listing_rank(listing),listing.id))
    semaphore=asyncio.Semaphore(3)
    async def capture(listing,browser_runtime=None):
        queued_at=perf_counter()
        async with semaphore:
            started=perf_counter()
            try: result=await collect_product_capture(listing.url,browser_runtime=browser_runtime)
            except httpx.HTTPError as error:
                result={'status':'unresolved','reason':f'Retailer capture failed: {type(error).__name__}'}
            result={**result,'attempted_at':now.isoformat(),'parser_version':PARSER_VERSION,
                'capture_elapsed_seconds':round(perf_counter()-started,3),
                'queue_wait_seconds':round(started-queued_at,3)}
            return listing,result
    batch=pending[:limit]
    if batch and any((urlsplit(listing.url).hostname or '').lower().endswith('amazon.co.uk')
                     or (urlsplit(listing.url).hostname or '').lower().endswith('gamers-outlet.net')
                     for listing in batch):
        from app.services.browser_pool import managed_playwright
        from app.swarms.cases import _make_pw_context
        async with managed_playwright() as playwright:
            browser,context=await _make_pw_context(playwright)
            try:
                async def capture_with_shared_browser(listing):
                    queued_at=perf_counter()
                    async with semaphore:
                        started=perf_counter()
                        try: result=await collect_product_capture(listing.url,browser_runtime=(browser,context))
                        except httpx.HTTPError as error:
                            result={'status':'unresolved','reason':f'Retailer capture failed: {type(error).__name__}'}
                        result={**result,'attempted_at':now.isoformat(),'parser_version':PARSER_VERSION,
                            'capture_elapsed_seconds':round(perf_counter()-started,3),
                            'queue_wait_seconds':round(started-queued_at,3)}
                        return listing,result
                results=await asyncio.gather(*(capture_with_shared_browser(listing) for listing in batch))
            finally:
                await context.close()
                await browser.close()
    else:
        results=await asyncio.gather(*(capture(listing) for listing in batch))
    captured=retained=unresolved=0
    by_host=defaultdict(lambda:{'attempted':0,'captured':0,'retained':0,'unresolved':0,
        'capture_seconds_total':0.0,'capture_seconds_max':0.0,
        'queue_wait_seconds_total':0.0,'queue_wait_seconds_max':0.0,'unresolved_reasons':{}})
    for listing,result in results:
        host=(urlsplit(listing.url).hostname or 'unknown').lower()
        host_metrics=by_host[host]
        host_metrics['attempted']+=1
        elapsed=float(result.pop('capture_elapsed_seconds',0) or 0)
        queue_wait=float(result.pop('queue_wait_seconds',0) or 0)
        host_metrics['capture_seconds_total']+=elapsed
        host_metrics['capture_seconds_max']=max(host_metrics['capture_seconds_max'],elapsed)
        host_metrics['queue_wait_seconds_total']+=queue_wait
        host_metrics['queue_wait_seconds_max']=max(host_metrics['queue_wait_seconds_max'],queue_wait)
        outcome=await persist_product_source_capture(db,listing,'playbook_product_capture',result,
            role=source_roles.get(listing.id))
        if outcome=='captured':
            captured+=1
            host_metrics['captured']+=1
        elif outcome=='retained':
            retained+=1
            host_metrics['retained']+=1
        else:
            unresolved+=1
            host_metrics['unresolved']+=1
            reason=str(result.get('reason') or 'unspecified')
            host_metrics['unresolved_reasons'][reason]=host_metrics['unresolved_reasons'].get(reason,0)+1
    amazon_catalogue=await refresh_amazon_catalogue_attributes(rows,now,db=db)
    await db.flush()
    return {'attempted':len(results),'captured':captured,'retained':retained,
        'unresolved':unresolved,'by_host':{host:{**metrics,
            'capture_seconds_total':round(metrics['capture_seconds_total'],3),
            'capture_seconds_max':round(metrics['capture_seconds_max'],3),
            'queue_wait_seconds_total':round(metrics['queue_wait_seconds_total'],3),
            'queue_wait_seconds_max':round(metrics['queue_wait_seconds_max'],3)}
            for host,metrics in sorted(by_host.items())},
        'amazon_catalogue_attributes':amazon_catalogue,'published':False}
