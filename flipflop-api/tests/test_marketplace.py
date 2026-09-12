from app.gem_radar.marketplace import is_malformed_awdit_listing, usable_listing_url


def test_awdit_discount_badge_is_not_a_listing() -> None:
    assert is_malformed_awdit_listing(
        "https://www.awd-it.co.uk/example-product.html", "SAVE 6%"
    )
    assert is_malformed_awdit_listing(
        "https://www.awd-it.co.uk/example-product.html", "save 17.5%"
    )


def test_awdit_real_title_is_kept() -> None:
    assert not is_malformed_awdit_listing(
        "https://www.awd-it.co.uk/intel-core-i5-12400f.html",
        "Intel Core i5-12400F Processor",
    )


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
