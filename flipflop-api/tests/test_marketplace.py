from app.gem_radar.marketplace import usable_listing_url


def test_overclockers_homepage_falls_back_to_product_search() -> None:
    result = usable_listing_url(
        "https://www.overclockers.co.uk/",
        "legacy-id",
        "overclockers",
        "Gigabyte GeForce RTX 5060 EAGLE MAX",
    )

    assert result == (
        "https://www.overclockers.co.uk/search?"
        "sSearch=Gigabyte+GeForce+RTX+5060+EAGLE+MAX"
    )


def test_item_level_url_is_preserved() -> None:
    product_url = "https://www.overclockers.co.uk/example-product-gra-12345.html"

    assert usable_listing_url(
        product_url,
        "legacy-id",
        "overclockers",
        "Example product",
    ) == product_url


def test_search_url_is_preserved() -> None:
    search_url = "https://www.overclockers.co.uk/search?q=RTX+5060"

    assert usable_listing_url(
        search_url,
        "legacy-id",
        "overclockers",
        "RTX 5060",
    ) == search_url
