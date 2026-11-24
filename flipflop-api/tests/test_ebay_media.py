"""
eBay Sell Media API client (row 41). Not verifiable against live eBay (no
network egress to any eBay domain in this environment) — tested against
mocked HTTP responses shaped like eBay's documented Media API contract.
The exact schema is unconfirmed against a real response, see module
docstring in app/services/ebay_media.py.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.services import ebay_media


async def test_upload_video_success_full_flow():
    create_resp = AsyncMock(status_code=201)
    create_resp.json = lambda: {"videoId": "vid-1", "uploadUrl": "https://upload.example/vid-1"}
    put_resp = AsyncMock(status_code=200)
    status_resp = AsyncMock(status_code=200)
    status_resp.json = lambda: {"status": "PUBLISHED"}

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__.return_value.post = AsyncMock(return_value=create_resp)
        instance.__aenter__.return_value.put = AsyncMock(return_value=put_resp)
        instance.__aenter__.return_value.get = AsyncMock(return_value=status_resp)

        result = await ebay_media.upload_video_to_ebay(b"fake video bytes", "video/mp4", "token-1")

    assert result["success"] is True
    assert result["video_id"] == "vid-1"
    assert result["status"] == "PUBLISHED"


async def test_upload_video_create_failure():
    create_resp = AsyncMock(status_code=400)
    create_resp.text = "bad request"

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=create_resp)
        result = await ebay_media.upload_video_to_ebay(b"bytes", "video/mp4", "token-1")

    assert result["success"] is False
    assert result["video_id"] is None


async def test_upload_video_bytes_upload_failure():
    create_resp = AsyncMock(status_code=201)
    create_resp.json = lambda: {"videoId": "vid-2", "uploadUrl": "https://upload.example/vid-2"}
    put_resp = AsyncMock(status_code=500)

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__.return_value.post = AsyncMock(return_value=create_resp)
        instance.__aenter__.return_value.put = AsyncMock(return_value=put_resp)
        result = await ebay_media.upload_video_to_ebay(b"bytes", "video/mp4", "token-1")

    assert result["success"] is False
    assert result["video_id"] == "vid-2"
    assert result["status"] == "error"
