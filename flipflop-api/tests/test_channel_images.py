import io
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.services import channel_images as media


def photograph(size=(800, 1200)):
    image = Image.new("RGB", size, "#f00000")
    image.putpixel((0, 0), (0, 0, 255))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


@pytest.mark.parametrize("channel,size", [("ebay", (1600, 1600)), ("amazon", (1600, 1600)),
    ("google_shopping", (1600, 1600)), ("facebook_marketplace", (1600, 1600)),
    ("gumtree", (1600, 1600)), ("etsy", (3000, 2250)), ("website_hero", (1920, 1080)), ("social", (1080, 1350))])
def test_formats_preserve_portrait_product(channel, size):
    data, metadata = media.render_variant(photograph(), channel)
    with Image.open(io.BytesIO(data)) as image:
        assert image.size == size
        # The product's red rectangle survives in its original 2:3 shape.
        pixels = image.load()
        red_points = [(x, y) for y in range(0, size[1], 10) for x in range(0, size[0], 10)
                      if pixels[x, y][0] > 200 and pixels[x, y][1] < 50]
        width = max(x for x, _ in red_points) - min(x for x, _ in red_points)
        height = max(y for _, y in red_points) - min(y for _, y in red_points)
        assert abs(width / height - 2 / 3) < .03
        if channel == "etsy":
            assert min(x for x, _ in red_points) >= (size[0] - size[1]) / 2
            assert max(x for x, _ in red_points) <= (size[0] + size[1]) / 2
    assert metadata["fit"] == "contain"


def test_master_is_exact_and_approval_survives_reuse(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    original = photograph()
    manifest = media.save_master(original)
    assert (tmp_path / manifest["id"] / "original.png").read_bytes() == original
    media.approve_variant(manifest["id"], "ebay")
    assert media.save_master(original)["variants"]["marketplace"]["reviewed"]


def test_amazon_requires_background_review(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    manifest = media.save_master(photograph())
    with pytest.raises(ValueError, match="pure-white"):
        media.approve_variant(manifest["id"], "amazon")
    media.approve_variant(manifest["id"], "amazon", white_background=True)
    assert media.save_master(photograph())["variants"]["amazon"]["white_background_approved"]


def test_new_policy_requires_fresh_review_and_keeps_original(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    original = photograph()
    manifest = media.save_master(original)
    media.approve_variant(manifest["id"], "ebay")
    monkeypatch.setattr(media, "POLICY_VERSION", media.POLICY_VERSION + 1)
    refreshed = media.save_master(original)
    assert not refreshed["variants"]["marketplace"]["reviewed"]
    assert refreshed["policy_version"] == media.POLICY_VERSION
    assert (tmp_path / manifest["id"] / "original.png").read_bytes() == original


@pytest.mark.asyncio
async def test_publishing_uses_reviewed_derivative_not_original():
    manifest = {"variants": {"marketplace": {"url": "https://example.com/square.jpg", "reviewed": False}}}
    with patch.object(media, "image_manifest", AsyncMock(return_value=manifest)):
        with pytest.raises(ValueError, match="Preview and approve"):
            await media.prepare_channel_urls(["https://example.com/original.jpg"], "ebay")
        manifest["variants"]["marketplace"]["reviewed"] = True
        assert await media.prepare_channel_urls(["https://example.com/original.jpg"], "ebay") == ["https://example.com/square.jpg"]


def test_private_build_evidence_cannot_be_used_as_listing_image():
    with pytest.raises(ValueError, match="original product"):
        media.local_image_path("https://www.theflipflop.shop/api/builds/1/Customer%20Hub/private.jpg")
    with pytest.raises(ValueError, match="Invalid image path"):
        media.local_image_path("/api/uploads/../../secrets.jpg")


@pytest.mark.asyncio
async def test_live_publisher_checks_image_review_before_inventory_reservation():
    from app.services.live_publisher import LivePublisher
    build = type("Build", (), {"photos": [{"kind": "photo", "url": "https://example.com/original.jpg"}]})()
    db = AsyncMock()
    db.get.return_value = build
    reserve = AsyncMock()
    with patch("app.services.live_publisher.is_enabled", return_value=True), \
         patch.object(media, "prepare_channel_urls", AsyncMock(side_effect=ValueError("Preview and approve"))), \
         patch("app.services.live_publisher.InventoryReservationManager.reserve_inventory", reserve):
        result = await LivePublisher.publish_to_channel(db, 1, "ebay")
    assert not result.success
    assert "Preview and approve" in result.error
    reserve.assert_not_awaited()


@pytest.mark.asyncio
async def test_amazon_payload_contains_the_prepared_image():
    import httpx
    from app.services.amazon_sp_api import AmazonSPAPI
    client = AmazonSPAPI()
    client._request = AsyncMock(return_value=httpx.Response(200, json={"status": "ACCEPTED"}))
    with patch.object(media, "prepare_channel_urls", AsyncMock(return_value=["https://example.com/amazon-square.jpg"])) as prepare, \
         patch.object(media, "require_public_images", AsyncMock()):
        await client.upsert_listing(sku="TEST", title="PC", description="Test PC", bullet_points=[], price=100,
                                    quantity=1, condition="new", images=["https://example.com/original.jpg"])
    prepare.assert_awaited_once_with(["https://example.com/original.jpg"], "amazon")
    assert client._request.call_args.kwargs["json"]["attributes"]["main_product_image_locator"][0]["media_location"] == "https://example.com/amazon-square.jpg"


@pytest.mark.asyncio
async def test_unavailable_public_image_stops_amazon_submission():
    from app.services.amazon_sp_api import AmazonSPAPI, AmazonSPAPIError
    client = AmazonSPAPI()
    client._request = AsyncMock()
    with patch.object(media, "prepare_channel_urls", AsyncMock(return_value=["https://example.com/missing.jpg"])), \
         patch.object(media, "require_public_images", AsyncMock(side_effect=ValueError("not publicly available"))):
        with pytest.raises(AmazonSPAPIError, match="not publicly available"):
            await client.upsert_listing(sku="TEST", title="PC", description="PC", bullet_points=[],
                price=100, quantity=1, condition="new", images=["https://example.com/original.jpg"])
    client._request.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_image_404_is_actionable():
    import httpx
    response = httpx.Response(404, request=httpx.Request("GET", "https://example.com/missing.jpg"))
    with patch.object(media, "load_remote_image", AsyncMock(side_effect=httpx.HTTPStatusError("missing", request=response.request, response=response))):
        with pytest.raises(ValueError, match="Publish/sync"):
            await media.require_public_images(["https://example.com/missing.jpg"], "amazon")


@pytest.mark.asyncio
async def test_ebay_draft_payload_contains_the_prepared_image():
    import httpx
    from app.services.ebay_listing_poster import EbayListingPoster
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = httpx.Response(201, json={"itemDraftId": "test-draft"})
    with patch.object(media, "prepare_channel_urls", AsyncMock(return_value=["https://example.com/ebay-square.jpg"])), \
         patch("app.services.ebay_media.prepare_listing_images", AsyncMock(return_value=["https://example.com/ebay-square.jpg"])), \
         patch("app.services.ebay_listing_poster.httpx.AsyncClient", return_value=client):
        result = await EbayListingPoster(environment="sandbox", access_token="test-token").create_item_draft(
            title="PC", description="Test PC", price=100, image_urls=["https://example.com/original.jpg"])
    assert result["success"]
    assert client.post.call_args.kwargs["json"]["product"]["imageUrls"] == ["https://example.com/ebay-square.jpg"]


@pytest.mark.asyncio
async def test_preview_rejects_photographs_owned_by_another_build():
    from fastapi import HTTPException
    from app.api.cross_listing import ChannelImagesIn, preview_channel_images
    db = AsyncMock()
    db.get.return_value = type("Build", (), {"photos": [{"kind": "photo", "url": "https://example.com/owned.jpg"}]})()
    with patch.object(media, "image_manifest", AsyncMock()) as fetch:
        with pytest.raises(HTTPException) as error:
            await preview_channel_images(ChannelImagesIn(build_id=1, channel="ebay", urls=["https://example.com/other-build.jpg"]), db)
    assert error.value.status_code == 422
    fetch.assert_not_awaited()


def test_listing_processor_does_not_add_watermarks_by_default():
    from app.services.image_processor import process_image_bytes
    with Image.open(io.BytesIO(process_image_bytes(photograph()))) as image:
        assert image.size == (1600, 1600)


@pytest.mark.asyncio
async def test_approval_cannot_confirm_a_source_changed_since_preview():
    from fastapi import HTTPException
    from app.api.cross_listing import ChannelImagesIn, approve_channel_images
    with patch("app.api.cross_listing._channel_image_previews", AsyncMock(return_value=[{"id": "new-content"}])), \
         patch.object(media, "approve_variant") as approve:
        with pytest.raises(HTTPException) as error:
            await approve_channel_images(ChannelImagesIn(build_id=1, channel="ebay", clean_photographs=True,
                image_ids=["old-content"], policy_version=media.POLICY_VERSION), AsyncMock())
    assert error.value.status_code == 409
    approve.assert_not_called()
