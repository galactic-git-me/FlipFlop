from app.gem_radar.market_links import market_endpoint_links


def test_low_and_high_use_nearest_included_comparable():
    market = {"market": {"comparable_urls": ["https://shop.test/a", "https://shop.test/b"]}}
    candidates = [
        ("https://shop.test/a", "https://shop.test/a", 40),
        ("https://shop.test/b", "https://shop.test/b", 100),
        ("https://shop.test/other", "https://shop.test/other", 10),
    ]
    assert market_endpoint_links(market, 45, 90, candidates) == {
        "market_lower_url": "https://shop.test/a", "market_upper_url": "https://shop.test/b",
    }


def test_missing_or_unsafe_comparable_is_not_linked():
    market = {"market": {"comparable_urls": ["javascript:alert(1)"]}}
    assert market_endpoint_links(market, 10, 20, [("javascript:alert(1)", "javascript:alert(1)", 10)]) == {
        "market_lower_url": None, "market_upper_url": None,
    }
