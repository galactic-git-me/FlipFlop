from app.services.ebay_listing_poster import (
    EBAY_PRODUCT_DESCRIPTION_MAX_LENGTH,
    _inventory_product_description,
)


def test_inventory_description_is_plain_text_and_within_limit():
    html = "<div><h1>Prometheus</h1><p>Powerful &amp; quiet — £1,299.</p></div>" * 500

    result = _inventory_product_description(html, "Fallback title")

    assert len(result.encode("utf-8")) <= EBAY_PRODUCT_DESCRIPTION_MAX_LENGTH
    assert "<" not in result
    assert "&amp;" not in result
    assert "Prometheus" in result


def test_inventory_description_falls_back_when_html_has_no_text():
    assert _inventory_product_description("<br><hr>", "Prometheus Gaming PC") == (
        "Prometheus Gaming PC"
    )
