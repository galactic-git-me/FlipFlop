"""Use original-size copies of the same approved photos, never different photos."""
import io
import asyncio
import base64
import re
from urllib.parse import urlsplit, urlunsplit
import httpx
from PIL import Image, UnidentifiedImageError

_CDNS = {"m.media-amazon.com", "images-na.ssl-images-amazon.com", "images-eu.ssl-images-amazon.com", "i.ebayimg.com"}
_MAX_BYTES = 20 * 1024 * 1024
_MIN_LONG_EDGE = 256


async def meshy_reference_inputs(image_urls: list[str]) -> list[str]:
    """Send owned local images as bytes; external services cannot fetch localhost."""
    from app.services.channel_images import local_image_path
    inputs = []
    for index, url in enumerate(image_urls, 1):
        path = local_image_path(url)
        if path is None:
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError(f"Photo {index} is not an accessible owned image or public HTTPS URL")
            inputs.append(url)
            continue
        if path.stat().st_size > _MAX_BYTES:
            raise ValueError(f"Photo {index} exceeds the 20 MB reference limit")
        content = await asyncio.to_thread(path.read_bytes)
        try:
            with Image.open(io.BytesIO(content)) as image:
                mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
                # Imported photos are approved at >=100px. Do not reject a
                # valid saved 225px reference using the CDN-original threshold.
                if not mime or min(image.size) < 100:
                    raise ValueError(f"Photo {index} must be a clear JPEG, PNG or WebP image")
                image.verify()
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f"Could not validate saved photo {index}") from exc
        inputs.append(f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}")
    return inputs


def original_image_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return url
    host = (parsed.hostname or "").lower()
    path = parsed.path
    if host in _CDNS - {"i.ebayimg.com"}:
        path = re.sub(r"(/images/I/[^/]+?)\._[^/]+_\.(jpe?g|png|webp)$", r"\1.\2", path, flags=re.I)
    elif host == "i.ebayimg.com":
        path = re.sub(r"/s-l(\d+)\.(jpe?g|png|webp)$", lambda match: f"/s-l{max(1600,int(match[1]))}.{match[2]}", path, flags=re.I)
    return urlunsplit(parsed._replace(path=path)) if path != parsed.path else url


async def prepare_reference_images(image_urls: list[str]) -> list[str]:
    resolved = [original_image_url(url) for url in image_urls]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Two selected references are different sizes of the same photo. Choose distinct views.")
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        for index, url in enumerate(resolved, 1):
            parsed = urlsplit(url)
            # Only known public image CDNs are downloaded by the API. Other
            # sources keep their original provider-fetch flow; no arbitrary
            # new server-side URL fetch or redirect is introduced here.
            if parsed.scheme != "https" or parsed.hostname not in _CDNS or parsed.username or parsed.password:
                continue
            try:
                content = bytearray()
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > _MAX_BYTES:
                            raise ValueError(f"Photo {index} exceeds the 20 MB reference limit")
                with Image.open(io.BytesIO(content)) as image:
                    if max(image.size) < _MIN_LONG_EDGE or min(image.size) < 64:
                        raise ValueError(f"Photo {index} is only {image.width} × {image.height} pixels at original size. Choose a clearer product photo before generation.")
                    if image.format not in {"JPEG", "PNG", "WEBP"}:
                        raise ValueError(f"Photo {index} is not a supported JPEG, PNG or WebP image")
            except (httpx.HTTPError, UnidentifiedImageError, Image.DecompressionBombError) as error:
                raise ValueError(f"Could not validate original-size photo {index}. Choose another captured photo or try again.") from error
    return resolved
