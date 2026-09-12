import pytest
from app.services.listing_3d_references import select_listing_references


def test_uses_distinct_views_from_same_listing():
    urls = [f"https://i.ebayimg.com/view-{i}.jpg" for i in range(6)]
    assert select_listing_references([None, urls[0], *urls]) == urls[:4]


def test_cannot_mix_products():
    with pytest.raises(ValueError, match="belong"):
        select_listing_references(["https://example.com/gpu.jpg"], ["https://example.com/other.jpg"])


def test_owner_can_select_and_order_views():
    urls = ["https://example.com/front.jpg", "https://example.com/back.jpg"]
    assert select_listing_references(urls, urls[::-1]) == urls[::-1]


def test_missing_photos_do_not_fall_back_to_text():
    with pytest.raises(ValueError, match="no usable"):
        select_listing_references([None, "file:///private/image.jpg", "http://example.com/a.jpg"])
