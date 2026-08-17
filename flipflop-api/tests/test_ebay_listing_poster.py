from app.services.ebay_listing_poster import (
    EBAY_PRODUCT_DESCRIPTION_MAX_LENGTH,
    _inventory_product_description,
    prepare_ebay_listing_description,
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


def test_listing_description_inlines_dark_theme_and_removes_broken_images():
    html = """
    <style>.ff-section{color:white}</style>
    <div class="ff-page"><div class="ff-wrap">
      <div class="ff-section"><p>Readable copy</p></div>
      <div class="ff-image-section"><img src="{{MISSING_IMAGE_URL}}" alt="leak"></div>
      <img class="ff-heading" src="https://example.com/heading.png" alt="Heading">
    </div></div>
    """

    result = prepare_ebay_listing_description(html)

    assert "{{MISSING_IMAGE_URL}}" not in result
    assert 'alt="leak"' not in result
    assert "background:#0d1015" in result
    assert "color:#d8e2ee" in result
    assert "max-width:100%" in result
