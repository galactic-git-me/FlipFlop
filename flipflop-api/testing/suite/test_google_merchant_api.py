from types import SimpleNamespace

import pytest

from app.services.google_merchant_api import GoogleMerchantError, product_input_for_build


@pytest.fixture
def merchant_settings():
    return SimpleNamespace(
        google_merchant_store_url="https://www.theflipflop.shop",
        google_merchant_content_language="en",
        google_merchant_feed_label="GB",
    )


@pytest.fixture
def build():
    return SimpleNamespace(
        id=2,
        status="listed",
        ebay_price=1400.00,
        generated_title="PROMETHEUS | Gaming PC",
        generated_description="<p>Built and tested.</p>",
        photos=[{"url": "https://cdn.theflipflop.shop/build-2.jpg", "kind": "photo"}],
        hero_photo_url="https://cdn.theflipflop.shop/hero-2.jpg",
        ebay_condition="USED_EXCELLENT",
    )


def test_product_input_uses_saved_price_public_page_and_selected_images(build, merchant_settings):
    payload, fingerprint = product_input_for_build(
        build,
        42,
        merchant_settings,
        ["https://cdn.theflipflop.shop/hero-2.jpg", "https://cdn.theflipflop.shop/build-2.jpg"],
    )

    attrs = payload["productAttributes"]
    assert payload["offerId"] == "FF-BUILD-2"
    assert attrs["price"] == {"amountMicros": "1400000000", "currencyCode": "GBP"}
    assert attrs["link"] == "https://www.theflipflop.shop/builds/42"
    assert attrs["condition"] == "USED"
    assert attrs["description"] == "Built and tested."
    assert attrs["imageLink"] == "https://cdn.theflipflop.shop/hero-2.jpg"
    assert attrs["additionalImageLinks"] == ["https://cdn.theflipflop.shop/build-2.jpg"]
    assert len(fingerprint) == 64


@pytest.mark.parametrize("availability", ["IN_STOCK", "OUT_OF_STOCK"])
def test_availability_is_part_of_synced_product_input(build, merchant_settings, availability):
    payload, _ = product_input_for_build(build, 42, merchant_settings, availability=availability)
    assert payload["productAttributes"]["availability"] == availability


def test_product_input_rejects_missing_price(build, merchant_settings):
    build.ebay_price = None
    with pytest.raises(GoogleMerchantError, match="saved listing price"):
        product_input_for_build(build, 42, merchant_settings)


def test_product_input_rejects_non_public_image(build, merchant_settings):
    with pytest.raises(GoogleMerchantError, match="publicly reachable HTTPS"):
        product_input_for_build(build, 42, merchant_settings, ["http://localhost/image.jpg"])


def test_product_input_rejects_sold_build(build, merchant_settings):
    build.status = "sold"
    with pytest.raises(GoogleMerchantError, match="Sold builds"):
        product_input_for_build(build, 42, merchant_settings)
