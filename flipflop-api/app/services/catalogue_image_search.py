"""Google image candidates and validated, content-addressed local photographs."""
import hashlib
import asyncio
import io
import os
import re
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.config import get_settings
from app.services.channel_images import load_remote_image

PHOTO_ROOT = Path(__file__).resolve().parents[2] / "data" / "uploads" / "catalogue-photos"


def short_product_title(title):
    value = re.split(r"\s[–—|]\s|,|\(", str(title), maxsplit=1)[0]
    value = re.sub(r"[™®©]", "", value)
    return " ".join(value.split()[:12])[:160]


async def google_image_results(query):
    settings = get_settings()
    if not settings.serper_api_key and (not settings.google_custom_search_api_key or not settings.google_custom_search_engine_id):
        raise HTTPException(503, "Add SERPER_API_KEY to the server configuration to enable Google image results.")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            if settings.serper_api_key:
                response = await client.post("https://google.serper.dev/images", headers={"X-API-KEY": settings.serper_api_key},
                    json={"q": query, "gl": "gb", "hl": "en", "num": 20})
            else:
                response = await client.get("https://customsearch.googleapis.com/customsearch/v1", headers={"X-Goog-Api-Key": settings.google_custom_search_api_key}, params={
                    "cx": settings.google_custom_search_engine_id,
                    "q": query, "searchType": "image", "safe": "active", "num": 10, "imgType": "photo",
                })
            if response.status_code != 200:
                raise HTTPException(503 if response.status_code in (403, 429) else 502,
                    "Google image search access or quota is unavailable. Configure SERPER_API_KEY on the server or check the configured provider account.")
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Google image search could not be reached. Please retry.") from exc
    results = []
    seen = set()
    for item in (payload.get("images") if settings.serper_api_key else payload.get("items")) or []:
        url = item.get("imageUrl") if settings.serper_api_key else item.get("link")
        if not isinstance(url, str) or not url.startswith("https://") or url in seen:
            continue
        seen.add(url)
        meta = item.get("image") or {}
        results.append({"id": hashlib.sha256(url.encode()).hexdigest(), "url": url,
            "thumbnail_url": item.get("thumbnailUrl") or meta.get("thumbnailLink") or url, "title": str(item.get("title") or query)[:300],
            "source_page": item.get("link") if settings.serper_api_key else meta.get("contextLink"), "source": "google"})
    return results[:20]


def save_catalogue_photo(content):
    try:
        with Image.open(io.BytesIO(content)) as picture:
            if picture.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Choose a JPEG, PNG or WebP photograph.")
            if min(picture.size) < 100 or picture.width * picture.height > 40_000_000:
                raise ValueError("Choose a clear product photo between 100 pixels and 40 megapixels.")
            extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[picture.format]
            picture.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("The selected result is not a usable product photograph.") from exc
    filename = f"{hashlib.sha256(content).hexdigest()}.{extension}"
    PHOTO_ROOT.mkdir(parents=True, exist_ok=True)
    path = PHOTO_ROOT / filename
    if not path.is_file():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=PHOTO_ROOT, suffix=".tmp", delete=False) as destination:
                temporary = Path(destination.name)
                destination.write(content)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    base = "http://127.0.0.1:4311" if get_settings().app_env == "dev" else "https://theflipflop.shop"
    return f"{base}/api/uploads/catalogue-photos/{filename}"


async def download_catalogue_photo(url, *, thumbnail_url=None):
    """Prefer the original; use only this result's preview if its host blocks us.

    Bound DNS, redirects and streaming together so a blocked origin cannot
    consume the admin request's entire timeout. Both copies retain the same
    public-network and raster-image validation.
    """
    candidates = [(url, 8)]
    if thumbnail_url and thumbnail_url != url:
        candidates.append((thumbnail_url, 6))
    for source, seconds in candidates:
        try:
            content = await asyncio.wait_for(load_remote_image(source), timeout=seconds)
            return await asyncio.to_thread(save_catalogue_photo, content)
        except (TimeoutError, httpx.HTTPError, OSError, ValueError):
            continue
    raise HTTPException(422, "This image host blocked or timed out the download, or supplied an unusable photo. Its preview could not be saved either. Choose another result.")
