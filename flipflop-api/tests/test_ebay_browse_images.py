from app.services.ebay_browse import _extract_listing_image_url


def test_primary_browse_image_is_preferred() -> None:
    assert _extract_listing_image_url({
        "image": {"imageUrl": "https://img.example/primary.jpg"},
        "thumbnailImages": [{"imageUrl": "https://img.example/thumb.jpg"}],
    }) == "https://img.example/primary.jpg"


def test_thumbnail_and_additional_images_are_fallbacks() -> None:
    assert _extract_listing_image_url({
        "thumbnailImages": [{"imageUrl": "https://img.example/thumb.jpg"}],
        "additionalImages": [{"imageUrl": "https://img.example/extra.jpg"}],
    }) == "https://img.example/thumb.jpg"
    assert _extract_listing_image_url({
        "additionalImages": [{"imageUrl": "https://img.example/extra.jpg"}],
    }) == "https://img.example/extra.jpg"


def test_missing_or_malformed_image_candidates_return_none() -> None:
    assert _extract_listing_image_url({"image": None, "thumbnailImages": [None, {}]}) is None
