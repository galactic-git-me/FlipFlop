from types import SimpleNamespace

from app.services.bestseller_catalogue_sync import (
    _case_catalogue_price,
    _importable_bestseller_observation,
    _observation_catalogue_price,
)
from app.services.amazon_bestsellers import OPERATING_SYSTEM_BESTSELLER_LIST_NAME
from app.services.playbook_product_capture import valid_unpriced_os_capture


def observation(*, category="os", title="Microsoft Windows 11 Home", price=None,
                list_name=OPERATING_SYSTEM_BESTSELLER_LIST_NAME):
    return SimpleNamespace(
        category=category,
        title=title,
        price=price,
        list_name=list_name,
        asin="B09XJ8VSRB",
        url="https://www.amazon.co.uk/dp/B09XJ8VSRB",
        image_url="https://images.example.test/windows.jpg",
    )


def test_amazon_windows_bestsellers_never_become_playbook_licence_inventory():
    assert not _importable_bestseller_observation(observation())


def test_unpriced_hardware_bestsellers_can_be_captured_but_are_not_catalogue_costs():
    row=observation(category="gpu",title="NVIDIA GeForce RTX 5090 Graphics Card",price=None)
    assert _importable_bestseller_observation(row)
    assert _observation_catalogue_price(row) is None


def test_historical_authored_product_recovers_identity_but_not_old_rank_or_price():
    from datetime import datetime,timedelta
    from app.services.bestseller_catalogue_sync import _historical_target_identities
    from app.services.benchmark_normaliser import normalise_gpu
    row=observation(category='gpu',title='Sparkle Intel Arc B580 Titan OC 12GB GDDR6',price=347)
    row.id=7;row.cpk='exact-product';row.captured_at=datetime.utcnow()-timedelta(days=2);row.rank=42
    targets={'cpu':set(),'gpu':{normalise_gpu('Intel Arc B580 12GB')}}
    recovered=_historical_target_identities([row,row],set(),targets)
    assert len(recovered)==1
    assert recovered[0].asin==row.asin and recovered[0].captured_at==row.captured_at
    assert recovered[0].price is None and recovered[0].rank is None
    assert _observation_catalogue_price(recovered[0]) is None
    assert row.price==347 and row.rank==42
    assert _historical_target_identities([row],{('gpu',row.asin)},targets)==[]
    assert _historical_target_identities([row],set(),{'cpu':set(),'gpu':{'another-model'}})==[]


def test_historical_identity_requires_fresh_exact_page_price_before_catalogue_materialization():
    from datetime import datetime,timedelta,timezone
    from app.services.bestseller_catalogue_sync import _historical_offer_is_current
    url='https://www.amazon.co.uk/dp/B09XJ8VSRB'
    listing=SimpleNamespace(url=url,price=347,raw_specs={})
    assert not _historical_offer_is_current(listing)
    capture={'status':'captured','url':url,'item_gbp':'347.00','observed_at':datetime.now(timezone.utc).isoformat()}
    listing.raw_specs={'playbook_product_capture':capture}
    assert _historical_offer_is_current(listing)
    for changed in ({'item_gbp':'340'},{'url':'https://www.amazon.co.uk/dp/B000000000'},
            {'observed_at':(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()},
            {'observed_at':datetime.now().isoformat()}):
        listing.raw_specs={'playbook_product_capture':{**capture,**changed}}
        assert not _historical_offer_is_current(listing)


def test_case_candidate_waits_for_an_exact_positive_listing_price():
    assert _case_catalogue_price(SimpleNamespace(price=None)) is None
    assert _case_catalogue_price(SimpleNamespace(price=0)) is None
    assert _case_catalogue_price(SimpleNamespace(price=149.99)) == 149.99


def test_misclassified_hardware_and_non_os_bestseller_pages_are_not_imported():
    assert not _importable_bestseller_observation(observation(category="gpu", title="RTX 5060 Ti"))
    assert not _importable_bestseller_observation(observation(list_name="Amazon Software Best Sellers"))


def test_priced_hardware_bestseller_still_requires_exact_image_and_asin():
    row=observation(category="gpu",title="RTX 5060 Ti Graphics Card",price=429.99)
    assert _importable_bestseller_observation(row)
    row.url="https://www.amazon.co.uk/dp/B000000000"
    assert not _importable_bestseller_observation(row)


def test_unpriced_os_capture_requires_exact_asin_and_edition_and_positive_price():
    row=observation()
    capture={"status":"captured","url":row.url,"sku":row.asin,
        "title":"Microsoft Windows 11 Home","item_gbp":"119.99"}
    assert valid_unpriced_os_capture(row,capture)
    assert not valid_unpriced_os_capture(row,{**capture,"title":"Microsoft Windows 11 Pro"})
    assert not valid_unpriced_os_capture(row,{**capture,"sku":"B000000000"})
    assert not valid_unpriced_os_capture(row,{**capture,"item_gbp":None})


def test_os_capture_accepts_exact_authored_ubuntu_version_and_rejects_other_releases():
    row=observation(title='Ubuntu 24.04 LTS Desktop')
    capture={'status':'captured','url':row.url,'sku':row.asin,
        'title':'Ubuntu 24.04.2 LTS Desktop 64-bit','item_gbp':'24.99'}
    assert valid_unpriced_os_capture(row,capture)
    assert not valid_unpriced_os_capture(row,{**capture,'title':'Ubuntu 22.04 LTS Desktop'})


def test_amazon_os_prices_never_enter_the_catalogue():
    row=observation(price=402.25)
    row.product_capture={'status':'captured','url':row.url,'sku':row.asin,
        'title':'Microsoft Windows 11 Home','item_gbp':'119.99'}
    assert _observation_catalogue_price(row) is None


def test_amazon_ubuntu_prices_never_enter_the_catalogue():
    row=observation(title='Ubuntu 24.04 LTS Desktop',price=None)
    row.product_capture={'status':'captured','url':row.url,'sku':row.asin,
        'title':'Ubuntu 24.04.2 LTS Desktop','item_gbp':'24.99'}
    assert _observation_catalogue_price(row) is None


def test_playbook_os_capture_rejects_unrelated_legacy_os_products():
    from app.services.playbook_product_capture import _playbook_os_identity_matches

    assert not _playbook_os_identity_matches('Microsoft Windows 7 Professional','Microsoft Windows 7 Professional')
    assert not _playbook_os_identity_matches('Linux Mint 21','Linux Mint 21')
    assert _playbook_os_identity_matches('Ubuntu - 24.04 LTS USB Edition','Ubuntu 24.04.1 LTS USB Edition')
