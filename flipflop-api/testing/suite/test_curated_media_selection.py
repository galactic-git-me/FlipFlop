import pytest
from app.services.curated_media import media_urls, selected_gallery, validate_selection, own_build_media


def test_only_captured_photos_may_be_selected():
    captured = {"images": [{"url": "https://example.com/a.jpg"}], "videos": []}
    with pytest.raises(ValueError, match="Only captured"):
        validate_selection({"images": ["https://other.com/unrelated.jpg"], "videos": []}, captured)
    with pytest.raises(ValueError, match="at least one"):
        validate_selection({"images": [], "videos": []}, captured)
    validate_selection({"images": ["https://example.com/a.jpg"], "videos": []}, captured)


def test_selected_gallery_is_an_ordered_allowlist_and_never_includes_unselected_media():
    selected = {"images": ["https://example.com/3.jpg", "https://example.com/1.jpg"], "videos": []}
    assert [item["url"] for item in selected_gallery(selected, "images")] == selected["images"]
    assert selected_gallery(selected, "videos") == []


def test_candidate_urls_are_deduplicated_and_invalid_values_are_rejected():
    assert media_urls([None, {}, "javascript:alert(1)", "https://example.com/a.jpg", "https://example.com/a.jpg"]) == ["https://example.com/a.jpg"]


def test_broken_scraper_placeholders_are_not_gallery_candidates():
    invalid = [
        "https://m.media-amazon.com/images/I/214aTrUk8lL._RC",
        "https://www.google.com/iVBORw0KGgo" + "A" * 128,
        "https://computerorbit.com/%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E",
        "https://www.awd-it.co.uk/catalogsearch/result/?q=AMD%20CPU",
    ]
    assert media_urls(invalid) == []
    assert media_urls([
        "https://images-eu.ssl-images-amazon.com/images/I/51abc._AC_SL1000_.jpg",
        "https://encrypted-tbn0.gstatic.com/images?q=tbn:valid-photo",
    ]) == [
        "https://images-eu.ssl-images-amazon.com/images/I/51abc._AC_SL1000_.jpg",
        "https://encrypted-tbn0.gstatic.com/images?q=tbn:valid-photo",
    ]


def test_own_build_media_includes_original_photos_and_clips_only(tmp_path):
    media = tmp_path / "012" / "Media"
    media.mkdir(parents=True)
    (media / "original.jpg").write_bytes(b"photo")
    (media / "clip.mp4").write_bytes(b"video")
    private = tmp_path / "012" / "Dispatch"
    private.mkdir()
    (private / "private.jpg").write_bytes(b"private")
    result = own_build_media(12, [
        {"url": "https://example.com/photo.jpg", "kind": "photo"},
        {"url": "https://example.com/clip.webm", "kind": "video"},
        {"url": "https://example.com/card.jpg", "kind": "registration_plate"},
    ], tmp_path)
    assert result == {"images": ["https://example.com/photo.jpg", "/api/builds/012/Media/original.jpg"],
                      "videos": ["https://example.com/clip.webm", "/api/builds/012/Media/clip.mp4"]}
    assert media_urls(result["images"])[-1] == "/api/builds/012/Media/original.jpg"


@pytest.mark.asyncio
async def test_linked_owned_photos_enter_selectable_gallery(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.services import curated_media
    monkeypatch.setattr(curated_media, "BUILD_MEDIA_ROOT", tmp_path)
    rows = [{"image_url": "https://supplier.test/a.jpg", "image_urls": [],
             "video_urls": [], "source_url": "https://supplier.test/product", "source": "Supplier"}]
    builds = [{"id": 12, "name": "Owned PC", "photos": [
        {"url": "https://owned.test/original.jpg", "kind": "photo"},
        {"url": "https://owned.test/private.jpg", "kind": "registration_plate"}],
        "hero_photo_url": None}]
    def result(values):
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: values))
    db = SimpleNamespace(execute=AsyncMock(side_effect=[result(rows), result(builds)]))
    gallery = await curated_media.captured_media(db, "cpu", "exact-cpk")
    urls = [item["url"] for item in gallery["images"]]
    assert urls == ["https://supplier.test/a.jpg", "https://owned.test/original.jpg"]
    curated_media.validate_selection({"images": [urls[1]], "videos": []}, gallery)
