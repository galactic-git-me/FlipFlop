"""
eBay Sell Media API — row 41 (boot-up/benchmark video attached to a listing).

Distinct from the local upload step (app/api/flips.py's /upload-video, which
just stores the file so it can be reviewed and attached to the description
manually if needed): this pushes the video to eBay itself so it can be
attached to the live listing via the video's returned videoId.

Not verifiable against live eBay from this environment (no network egress
to any eBay domain here) — this is a genuinely higher-uncertainty
integration than the OAuth/Trading API code: eBay's Media API is a two-step
upload (create a video record, then PUT the raw bytes to a returned upload
URL, then poll status until PUBLISHED) and the exact request/response shape
below is implemented to the best of available documentation, not confirmed
against a real response. Flag for verification before the first live push.
"""
from __future__ import annotations

import asyncio
import structlog
import httpx
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from app.api.ebay_compliance import _ebay_api_root

log = structlog.get_logger(__name__)

_MAX_POLL_ATTEMPTS = 10
_POLL_INTERVAL_SECONDS = 3


async def prepare_listing_images(image_urls: list[str], token: str, environment: str) -> list[str]:
    """Upload reviewed local derivatives through the current Media image API.

    eBay receives EPS URLs, so DEV photos need no production-file deployment.
    Token-scoped, expiring cache avoids duplicate uploads on publication retries.
    """
    from app.services.channel_images import load_original
    if environment not in {"sandbox", "production"} or not token:
        raise ValueError("A valid eBay listing environment and seller token are required")
    root = "https://api.sandbox.ebay.com" if environment == "sandbox" else "https://api.ebay.com"
    cache_dir = Path(__file__).resolve().parents[3] / ".run-logs" / "ebay-image-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    hosted = []
    async with httpx.AsyncClient(timeout=30) as client:
        for url in image_urls:
            data = await load_original(url)
            cache_key = hashlib.sha256(environment.encode() + token.encode() + data).hexdigest()
            path = cache_dir / f"{cache_key}.json"
            if path.is_file():
                try:
                    cached = json.loads(path.read_text(encoding="utf-8"))
                    expires = datetime.fromisoformat(cached["expirationDate"].replace("Z", "+00:00"))
                    if expires > datetime.now(timezone.utc) + timedelta(minutes=10):
                        hosted.append(cached["url"])
                        continue
                except (ValueError, OSError, KeyError):
                    pass
            response = await client.post(f"{root}/commerce/media/v1_beta/image/create_image_from_file",
                headers={"Authorization": f"Bearer {token}"}, files={"image": ("product.jpg", data, "image/jpeg")})
            if response.status_code not in (200, 201):
                raise ValueError(f"eBay image hosting returned HTTP {response.status_code}; listing submission stopped")
            payload = response.json()
            public_url = payload.get("maxDimensionImageUrl") or payload.get("imageUrl")
            parts = urlsplit(public_url or "")
            if parts.scheme != "https" or not (parts.hostname or "").endswith(".ebayimg.com"):
                raise ValueError("eBay did not return a valid hosted image URL")
            cache = {"url": public_url, "expirationDate": payload.get("expirationDate"), "image_resource": response.headers.get("location")}
            if cache["expirationDate"]:
                path.write_text(json.dumps(cache), encoding="utf-8")
            hosted.append(public_url)
    return hosted


async def upload_video_to_ebay(video_bytes: bytes, content_type: str, token: str) -> dict:
    """
    Two-step eBay Media API upload: create a video record, PUT the bytes to
    the returned upload URL, then poll until eBay finishes processing.
    Returns {"success": bool, "video_id": str | None, "status": str, "error": str | None}.
    """
    root = _ebay_api_root()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    create_body = {"videoMetadata": {"title": "Build boot/benchmark clip"}}
    async with httpx.AsyncClient(timeout=30) as client:
        create_resp = await client.post(f"{root}/sell/media/v1/video", json=create_body, headers=headers)

    if create_resp.status_code not in (200, 201):
        log.warning("ebay_media.create_failed", status=create_resp.status_code, body=create_resp.text[:300])
        return {"success": False, "video_id": None, "status": "error", "error": f"create failed: {create_resp.status_code}"}

    created = create_resp.json()
    video_id = created.get("videoId")
    upload_url = created.get("uploadUrl") or created.get("_links", {}).get("upload", {}).get("href")
    if not video_id or not upload_url:
        return {"success": False, "video_id": None, "status": "error", "error": "no videoId/uploadUrl in create response"}

    async with httpx.AsyncClient(timeout=60) as client:
        put_resp = await client.put(
            upload_url, content=video_bytes,
            headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
        )
    if put_resp.status_code not in (200, 201, 204):
        log.warning("ebay_media.upload_bytes_failed", status=put_resp.status_code)
        return {"success": False, "video_id": video_id, "status": "error", "error": f"upload failed: {put_resp.status_code}"}

    status = await _poll_video_status(video_id, token)
    return {"success": status == "PUBLISHED", "video_id": video_id, "status": status, "error": None}


async def _poll_video_status(video_id: str, token: str) -> str:
    root = _ebay_api_root()
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(_MAX_POLL_ATTEMPTS):
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{root}/sell/media/v1/video/{video_id}", headers=headers)
        if resp.status_code == 200:
            status = resp.json().get("status", "UNKNOWN")
            if status in ("PUBLISHED", "FAILED", "REJECTED"):
                return status
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    return "TIMEOUT"
