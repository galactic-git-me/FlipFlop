"""Focused image-search checks with no live provider calls."""
import asyncio
import io
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from PIL import Image

from app.services import catalogue_image_search as service


def test_short_title_preserves_model():
    assert service.short_product_title("NZXT H3 Flow Black, panoramic PC case with extras") == "NZXT H3 Flow Black"
    assert len(service.short_product_title("word " * 100).split()) == 12


def test_photo_is_validated_and_saved_once():
    stream = io.BytesIO()
    Image.new("RGBA", (160, 200), (20, 40, 60, 0)).save(stream, format="PNG")
    data = stream.getvalue()
    with tempfile.TemporaryDirectory() as directory, patch.object(service, "PHOTO_ROOT", Path(directory)):
        first = service.save_catalogue_photo(data)
        assert first == service.save_catalogue_photo(data)
        assert len(list(Path(directory).glob("*.png"))) == 1
        assert next(Path(directory).glob("*.png")).read_bytes() == data
        try:
            service.save_catalogue_photo(b"<svg>not a raster image</svg>")
        except ValueError:
            pass
        else:
            raise AssertionError("Unsupported content was accepted")


async def test_provider_results_and_failure():
    original_client = httpx.AsyncClient
    def response(request):
        assert request.url.host == "google.serper.dev"
        assert request.headers["X-API-KEY"] == "fixture-key"
        return httpx.Response(200, json={"images": [
            {"imageUrl": "https://example.test/hardware.png", "thumbnailUrl": "https://example.test/thumb.png", "link": "https://example.test/product", "title": "Hardware"},
            {"imageUrl": "http://example.test/insecure.jpg"},
        ]})
    settings = SimpleNamespace(serper_api_key="fixture-key", google_custom_search_api_key="", google_custom_search_engine_id="")
    with patch.object(service, "get_settings", return_value=settings), patch.object(service.httpx, "AsyncClient", side_effect=lambda **kwargs: original_client(transport=httpx.MockTransport(response), **kwargs)):
        rows = await service.google_image_results("Exact model")
        assert len(rows) == 1 and len(rows[0]["id"]) == 64
        assert rows[0]["source_page"] == "https://example.test/product"
    def refused(request):
        return httpx.Response(403, json={"error": "rejected"})
    with patch.object(service, "get_settings", return_value=settings), patch.object(service.httpx, "AsyncClient", side_effect=lambda **kwargs: original_client(transport=httpx.MockTransport(refused), **kwargs)):
        try:
            await service.google_image_results("Exact model")
        except HTTPException as exc:
            assert exc.status_code == 503 and "fixture-key" not in exc.detail
        else:
            raise AssertionError("Provider rejection was hidden")


async def test_private_image_download_is_rejected():
    with patch("app.services.channel_images.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
        try:
            await service.download_catalogue_photo("https://example.test/photo.jpg")
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("Private-network image download was permitted")


if __name__ == "__main__":
    test_short_title_preserves_model()
    test_photo_is_validated_and_saved_once()
    asyncio.run(test_provider_results_and_failure())
    asyncio.run(test_private_image_download_is_rejected())
    print("PASS: shortened titles, validated original bytes, shared-file cache, Google result parsing, safe provider errors")
