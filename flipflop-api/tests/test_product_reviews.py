from app.services.product_reviews import aggregate_cpk_reviews, review_vendor


def test_review_vendor_normalises_marketplace_labels():
    assert review_vendor("Amazon UK") == "amazon"
    assert review_vendor("eBay Browse API") == "ebay"


def test_cpk_reviews_add_counts_and_weight_stars_across_vendors():
    result = aggregate_cpk_reviews([
        ("cpk-1", "ebay", 4.0, 10),
        ("cpk-1", "ebay", 3.0, 2),  # duplicate vendor: do not add it
        ("cpk-1", "Amazon UK", 5.0, 90),
    ])
    assert result["cpk-1"] == (4.9, 100)


def test_cpk_reviews_do_not_mix_different_products():
    result = aggregate_cpk_reviews([
        ("cpk-1", "ebay", 4.0, 10),
        ("cpk-2", "amazon", 5.0, 20),
    ])
    assert result == {"cpk-1": (4.0, 10), "cpk-2": (5.0, 20)}
