from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.playbook_product_capture import (max_working_days_for_calendar_duration,
    parse_product_capture, supported_product_url)
from app.services.playbook_service import _verified_windows_licence_listing


def amazon_offer_html(url, *, availability='Usually dispatched within 3 to 4 days', price='£402.25'):
    today=datetime.now(timezone.utc).date()
    start=today+timedelta(days=1)
    end=today+timedelta(days=4)
    delivery=f'{start.day} - {end.day} {end.strftime("%B")}'
    asin=url.rsplit('/',1)[-1]
    return f'''<!doctype html><html><body>
      <input name="ASIN" value="{asin}">
      <div id="productTitle">Microsoft Windows 11 Pro</div>
      <div id="corePrice_feature_div"><span class="a-offscreen">{price}</span></div>
      <div id="availability">{availability}</div>
      <div id="sellerProfileTriggerId">coseon-de</div>
      <div id="deliveryBlockContainer">
        <div data-csa-c-delivery-type="delivery" data-csa-c-mir-variant="DEFAULT"
          data-csa-c-delivery-price="FREE" data-csa-c-delivery-time="{delivery}">FREE delivery {delivery}</div>
      </div>
      <table id="productDetails_techSpec_section_1"><tr><th>Product Dimensions</th><td>14.8 x 11.1 x 2.1 cm; 50 g</td>
      <tr><th>Manufacturer</th><td>Microsoft Software</td></tr><tr><th>Best Sellers Rank</th>
      <td>328 in Software (10 in Operating Systems)</td></tr></table>
    </body></html>'''


def test_amazon_dom_capture_uses_exact_offer_seller_stock_and_latest_arrival_day():
    url='https://www.amazon.co.uk/dp/B09XJ8PM2X'

    result=parse_product_capture(amazon_offer_html(url),url)

    assert result['status']=='captured'
    assert result['sku']=='B09XJ8PM2X'
    assert result['item_gbp']=='402.25'
    assert result['merchant_name']=='coseon-de'
    assert result['stock_status']=='available'
    assert 'Usually dispatched within 3 to 4 days' in result['stock_evidence']
    assert result['postage_verified'] is True
    assert result['delivery_gbp']=='0'
    assert result['delivery_calendar_days']==4
    assert result['delivery_working_days']==max_working_days_for_calendar_duration(4)


def test_exact_fact_queue_includes_base_and_upsell_products_but_uses_the_licence_source():
    from app.services.playbook_product_capture import playbook_capture_listing_ids
    proposals=[SimpleNamespace(demand_signals={'source':'catalogue_playbook_service_v1'},proposed_data={
        'components':[{'listing_id':11,'role':'cpu'},{'listing_id':12,'role':'os','source_url':'https://amazon.co.uk/dp/B000000001'}],
        'upsells':[{'component':{'listing_id':13,'role':'gpu'}},
            {'component':{'listing_id':14,'role':'os','source_url':'https://royalcdkeys.com/en-gb/products/win-11'}}]}),
        SimpleNamespace(demand_signals={'source':'unrelated'},proposed_data={'components':[{'listing_id':99}]})]
    assert playbook_capture_listing_ids(proposals)=={11,13,14}


def test_exact_fact_queue_honours_explicit_listing_ids_outside_the_automatic_queue():
    from app.services.playbook_product_capture import playbook_capture_listing_ids
    proposals=[]

    assert playbook_capture_listing_ids(proposals,requested_listing_ids={13219})=={13219}


def test_retained_capture_uses_the_last_failed_attempt_for_retry_cooldown():
    from app.services.playbook_product_capture import PARSER_VERSION, product_capture_refresh_due
    now=datetime(2026,10,15,12,tzinfo=timezone.utc)
    previous={'parser_version':PARSER_VERSION,'status':'captured',
        'attempted_at':(now-timedelta(hours=4)).isoformat(),
        'last_capture_attempt':{'status':'unresolved',
            'attempted_at':(now-timedelta(minutes=30)).isoformat()}}

    assert not product_capture_refresh_due(previous,now)
    previous['last_capture_attempt']['attempted_at']=(now-timedelta(hours=2)).isoformat()
    assert not product_capture_refresh_due(previous,now)
    previous['last_capture_attempt']['attempted_at']=(now-timedelta(days=2)).isoformat()
    assert product_capture_refresh_due(previous,now)


def test_unresolved_product_capture_still_retries_hourly():
    from app.services.playbook_product_capture import PARSER_VERSION, product_capture_refresh_due
    now=datetime(2026,10,15,12,tzinfo=timezone.utc)
    previous={'parser_version':PARSER_VERSION,'status':'unresolved',
        'attempted_at':(now-timedelta(hours=2)).isoformat()}

    assert product_capture_refresh_due(previous,now)


def test_unattempted_product_page_precedes_a_recently_retried_page():
    from app.services.playbook_product_capture import _product_capture_attempt_epoch
    untouched=SimpleNamespace(raw_specs={},title='Untouched')
    retried=SimpleNamespace(raw_specs={'playbook_product_capture':{
        'parser_version':10,'status':'unresolved','attempted_at':'2026-10-15T11:45:00+00:00'}},
        title='Retried')

    assert _product_capture_attempt_epoch(untouched) < _product_capture_attempt_epoch(retried)


def test_capture_prioritises_same_socket_integrated_cpu_alternative_at_equal_or_better_benchmark():
    from app.services.playbook_product_capture import _benchmark_qualified_missing_alternative
    target=SimpleNamespace(benchmark_source='passmark',confidence_score=.8,
        overall_score=19620,vram_gb=None)
    faster=SimpleNamespace(benchmark_source='passmark',confidence_score=.8,
        overall_score=20102,vram_gb=None)
    listing=SimpleNamespace(title='AMD Ryzen 5 5600GT with integrated Radeon Graphics, AM4 Socket',
        raw_specs={'bestseller':{'category':'cpu'}})
    missing={'cpu':{'amd_ryzen_5_5600g'},'gpu':set()}
    benchmarks={('cpu','amd_ryzen_5_5600g'):target,('cpu','amd_ryzen_5_5600gt'):faster}
    constraints={'cpu':{'amd_ryzen_5_5600g':{
        'sockets':{'am4'},'integrated_graphics_required':True}},'gpu':{}}

    assert _benchmark_qualified_missing_alternative(listing,missing,benchmarks,constraints)
    listing.title='AMD Ryzen 5 5600GT AM4 processor'
    assert not _benchmark_qualified_missing_alternative(listing,missing,benchmarks,constraints)
    listing.title='AMD Ryzen 5 5600GT with integrated Radeon Graphics, AM5 Socket'
    assert not _benchmark_qualified_missing_alternative(listing,missing,benchmarks,constraints)
    listing.title='AMD Ryzen 5 5600GT with integrated Radeon Graphics, AM4 Socket'
    benchmarks[('cpu','amd_ryzen_5_5600gt')]=SimpleNamespace(
        benchmark_source='other-source',confidence_score=.8,overall_score=30000,vram_gb=None)
    assert not _benchmark_qualified_missing_alternative(listing,missing,benchmarks,constraints)


def test_current_amazon_accordion_and_overview_tables_become_reviewable_facts():
    from app.services.playbook_service import _source_engineering_values
    url='https://www.amazon.co.uk/dp/B09XJ8PM2X'
    tables='''<div id="productOverview_feature_div"><table><tr><th>Processor Socket</th><td>Socket AM5</td></tr></table></div>
    <div id="productDetails_expanderSectionTables"><div style="display:none"><table class="prodDetTable">
    <tr><th>RAM Memory Technology</th><td>DDR5</td></tr><tr><th>Memory Slots</th><td>4</td></tr>
    <tr><th>M.2 Slots</th><td>2</td></tr></table></div></div>'''
    html=amazon_offer_html(url).replace('</body>',tables+'</body>')
    captured=parse_product_capture(html,url)
    assert captured['engineering_reviewed'] is False
    specs=_source_engineering_values('motherboard',captured['product_properties'])
    assert specs=={'socket':'am5','ram_type':'ddr5','ram_slots':4,'m2_slots':2}


def test_structured_offer_keeps_dom_specs_and_excludes_conflicting_socket_even_with_title_hint():
    import json
    from app.services.playbook_service import _source_engineering_values
    url='https://www.amazon.co.uk/dp/B09XJ8PM2X'
    product={'@type':'Product','url':url,'name':'Example AM5 DDR5 motherboard',
        'offers':{'url':url,'priceCurrency':'GBP','price':'100'},
        'additionalProperty':[{'name':'Processor Socket','value':'Socket AM4'}]}
    html='<script type="application/ld+json">'+json.dumps(product)+'</script>'+'''
    <div id="productDetails_expanderSectionTables"><table class="prodDetTable">
    <tr><th>Processor Socket</th><td>Socket AM5</td></tr>
    <tr><th>RAM Memory Technology</th><td>DDR5</td></tr></table></div>'''
    captured=parse_product_capture(html,url)
    assert captured['status']=='captured'
    assert captured['product_properties']['Processor Socket']==['Socket AM4','Socket AM5']
    assert _source_engineering_values('motherboard',captured['product_properties'],captured['title'])=={'ram_type':'ddr5'}


def test_amazon_dom_capture_does_not_invent_stock_or_price():
    url='https://www.amazon.co.uk/dp/B09XJ8PM2X'

    unknown_stock=parse_product_capture(amazon_offer_html(url,availability=''),url)
    missing_price=parse_product_capture(amazon_offer_html(url,price=''),url)

    assert unknown_stock['stock_status']=='unknown'
    assert unknown_stock['stock_evidence'] is None
    assert missing_price['status']=='unresolved'
    assert 'price' in missing_price['reason'].lower()
    unavailable=parse_product_capture(amazon_offer_html(url,availability='Currently unavailable',price=''),url)
    assert unavailable['status']=='unresolved'
    assert unavailable['stock_status']=='unavailable'
    assert unavailable['sku']=='B09XJ8PM2X'
    assert 'currently unavailable' in unavailable['reason'].lower()


def test_amazon_technical_facts_survive_when_exact_seller_price_is_missing():
    from app.services.playbook_product_capture import persist_product_source_capture
    from app.services.playbook_service import _playbook_engineering_suggestion

    class CaptureSession:
        async def flush(self):
            pass
        async def refresh(self, _listing, *, with_for_update=False):
            assert with_for_update is True

    url='https://www.amazon.co.uk/dp/B09XJ8PM2X'
    html=amazon_offer_html(url,price='').replace('Microsoft Windows 11 Pro','AMD Ryzen 5 5600G')
    html=html.replace('</body>','''<table id="productDetails_techSpec_section_1">
      <tr><th>CPU Socket</th><td>AM4</td></tr><tr><th>TDP</th><td>65 W</td></tr></table></body>''')
    attempt=parse_product_capture(html,url)
    listing=SimpleNamespace(id=91,title='AMD Ryzen 5 5600G',url=url,price=None,raw_specs={})

    assert attempt['status']=='unresolved'
    assert attempt['product_properties']['CPU Socket']=='AM4'
    assert attempt['product_properties']['TDP']=='65 W'
    awaitable=persist_product_source_capture(CaptureSession(),listing,'playbook_product_capture',attempt,role='cpu')
    import asyncio
    asyncio.run(awaitable)

    assert listing.price is None
    assert listing.raw_specs['playbook_product_capture']['status']=='unresolved'
    suggestion=_playbook_engineering_suggestion(listing,'cpu')
    assert suggestion['status']=='review_ready'
    assert suggestion['capture_status']=='unresolved'
    assert suggestion['suggested_specs']=={'socket':'am4','power_w':65}


def test_amazon_physical_windows_capture_is_not_a_catalogue_licence_candidate():
    url='https://www.amazon.co.uk/dp/B09XJ8PM2X'
    capture=parse_product_capture(amazon_offer_html(url),url)
    listing=SimpleNamespace(title=capture['title'],url=url,raw_specs={
        'bestseller':{'category':'os','list_name':'Amazon Operating Systems Best Sellers'},
        'playbook_product_capture':capture,
    })

    assert _verified_windows_licence_listing(listing) is False
    listing.raw_specs['playbook_product_capture']['sku']='B000000000'
    assert _verified_windows_licence_listing(listing) is False


def test_overclockers_exact_product_urls_allow_decimal_points_in_the_slug():
    assert supported_product_url(
        'https://www.overclockers.co.uk/tp-link-archer-tx3000e-dual-band-wireless-ax3000-wifi-6-bluetooth-5.0-pci-e-adapter/NW-21U-TP.html')
    assert not supported_product_url(
        'https://www.overclockers.co.uk/search/tp-link-wifi-6-bluetooth-5.0.html')


