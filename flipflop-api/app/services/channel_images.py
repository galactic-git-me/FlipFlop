"""Owned masters and deterministic, reviewed channel image derivatives."""
import asyncio
import hashlib
import io
import ipaddress
import json
import socket
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

import httpx
from PIL import Image, ImageOps, ImageCms, ImageChops

API_ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = API_ROOT.parent / "builds"
MEDIA_ROOT = API_ROOT / "data" / "uploads" / "channel-images"
PUBLIC_BASE = "https://www.theflipflop.shop/api/uploads/channel-images"
POLICY_VERSION = 1
PROFILES = {
    "marketplace": (1600, 1600), "amazon": (1600, 1600),
    "etsy": (3000, 2250), "website_card": (1600, 1600),
    "website_hero": (1920, 1080), "social": (1080, 1350),
}
ALIASES = {"ebay": "marketplace", "ebay_uk": "marketplace", "google": "marketplace",
           "google_shopping": "marketplace", "facebook": "marketplace", "facebook_marketplace": "marketplace",
           "facebook_catalog": "marketplace", "gumtree": "marketplace", "onbuy": "marketplace",
           "vinted": "marketplace", "storefront": "website_card", "flipflop_shop": "website_card"}


def profile_for(channel: str) -> str:
    profile = ALIASES.get(channel, channel)
    if profile not in PROFILES:
        raise ValueError(f"Unsupported image channel: {channel}")
    return profile


def render_variant(original: bytes, profile: str) -> tuple[bytes, dict]:
    """Contain the complete photograph. Etsy also survives a square crop."""
    profile = profile_for(profile)
    with Image.open(io.BytesIO(original)) as source:
        if source.width * source.height > 40_000_000:
            raise ValueError("Photograph exceeds the 40 megapixel processing limit")
        source = ImageOps.exif_transpose(source)
        if source.info.get("icc_profile"):
            source = ImageCms.profileToProfile(source, ImageCms.ImageCmsProfile(io.BytesIO(source.info["icc_profile"])), ImageCms.createProfile("sRGB"), outputMode="RGBA" if "A" in source.getbands() else "RGB")
        rgba = source.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, "white")
        flattened.paste(rgba, mask=rgba.getchannel("A"))
        if profile == "amazon":
            # Trim only empty white margins, never a centre crop of the PC.
            # Room/background replacement still requires a reviewed source.
            difference = ImageChops.difference(flattened, Image.new("RGB", flattened.size, "white"))
            bounds = difference.getbbox()
            if bounds:
                flattened = flattened.crop(bounds)
        size = PROFILES[profile]
        safe = (size[1], size[1]) if profile == "etsy" else size
        # A small uniform margin preserves framing and avoids edge clipping.
        box = (int(safe[0] * .95), int(safe[1] * .95))
        scale = min(box[0] / flattened.width, box[1] / flattened.height)
        resized = flattened.resize((max(1, round(flattened.width * scale)), max(1, round(flattened.height * scale))), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, "white")
        canvas.paste(resized, ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2))
        output = io.BytesIO()
        canvas.save(output, "JPEG", quality=92, optimize=True, subsampling=0)
        return output.getvalue(), {"width": size[0], "height": size[1], "source_width": source.width,
            "source_height": source.height, "upscaled": scale > 1, "fit": "contain",
            "square_crop_safe": profile == "etsy", "background_review_required": profile == "amazon"}


def save_master(original: bytes) -> dict:
    if not original or len(original) > 15 * 1024 * 1024:
        raise ValueError("Photograph must be nonempty and at most 15 MB")
    digest = hashlib.sha256(original).hexdigest()
    folder = MEDIA_ROOT / digest
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("policy_version") == POLICY_VERSION:
            return manifest
    with Image.open(io.BytesIO(original)) as image:
        suffix = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(image.format)
        if not suffix:
            raise ValueError("Use a JPEG, PNG or WebP photograph")
    master_name = f"original.{suffix}"
    (folder / master_name).write_bytes(original)
    manifest = {"id": digest, "policy_version": POLICY_VERSION, "original_url": f"{PUBLIC_BASE}/{digest}/{master_name}", "variants": {}}
    for profile in PROFILES:
        data, metadata = render_variant(original, profile)
        filename = f"{profile}-v{POLICY_VERSION}.jpg"
        (folder / filename).write_bytes(data)
        manifest["variants"][profile] = {**metadata, "url": f"{PUBLIC_BASE}/{digest}/{filename}", "reviewed": False}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def local_image_path(url: str) -> Path | None:
    parts = urlsplit(url)
    if parts.netloc and parts.hostname not in {"www.theflipflop.shop", "theflipflop.shop", "localhost", "127.0.0.1"}:
        return None
    path = unquote(parts.path)
    for prefix, root in (("/api/builds/", BUILD_ROOT), ("/api/uploads/", API_ROOT / "data" / "uploads")):
        if path.startswith(prefix):
            relative_parts = Path(path[len(prefix):]).parts
            if prefix == "/api/builds/" and (len(relative_parts) < 3 or relative_parts[1] != "Media"):
                raise ValueError("Only original product photographs may be prepared for channels")
            if Path(path).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                raise ValueError("Unsupported product photograph file")
            candidate = (root / path[len(prefix):]).resolve()
            if not candidate.is_relative_to(root.resolve()):
                raise ValueError("Invalid image path")
            if candidate.is_file():
                return candidate
    return None


async def load_original(url: str) -> bytes:
    local = local_image_path(url)
    if local:
        return await asyncio.to_thread(local.read_bytes)
    return await load_remote_image(url)


async def load_remote_image(url: str) -> bytes:
    """Fetch from the public network even when a local copy exists."""
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        for _ in range(4):
            parts = urlsplit(url)
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
                raise ValueError("Remote photographs must use public HTTPS URLs")
            addresses = await asyncio.to_thread(socket.getaddrinfo, parts.hostname, 443)
            if any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
                raise ValueError("Private network image URLs are not allowed")
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = str(response.url.join(response.headers["location"]))
                    continue
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 15 * 1024 * 1024:
                        raise ValueError("Photograph exceeds 15 MB")
                return bytes(data)
    raise ValueError("Too many image redirects")


async def image_manifest(url: str) -> dict:
    local = local_image_path(url)
    if local and local.parent.parent == MEDIA_ROOT and (local.parent / "manifest.json").is_file():
        cached = json.loads((local.parent / "manifest.json").read_text(encoding="utf-8"))
        if cached.get("policy_version") == POLICY_VERSION:
            return cached
        original = local.parent / Path(urlsplit(cached["original_url"]).path).name
        return await asyncio.to_thread(save_master, original.read_bytes())
    try:
        return await asyncio.to_thread(save_master, await load_original(url))
    except (httpx.HTTPError, socket.gaierror) as exc:
        raise ValueError("Could not retrieve the source photograph; publishing has been stopped") from exc


def cached_variant_url(url: str | None, channel: str) -> str | None:
    """Read an already-generated variant without network access or writes."""
    if not url:
        return None
    try:
        local = local_image_path(url)
        if not local:
            return None
        folder = local.parent if local.parent.parent == MEDIA_ROOT else MEDIA_ROOT / hashlib.sha256(local.read_bytes()).hexdigest()
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("policy_version") != POLICY_VERSION:
            return None
        return manifest["variants"][profile_for(channel)]["url"]
    except (ValueError, OSError, KeyError):
        return None


def approve_variant(image_id: str, channel: str, *, white_background: bool = False) -> None:
    if len(image_id) != 64 or any(c not in "0123456789abcdef" for c in image_id):
        raise ValueError("Invalid image identifier")
    profile = profile_for(channel)
    path = MEDIA_ROOT / image_id / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if profile == "amazon" and not white_background:
        raise ValueError("Amazon needs a reviewed pure-white background and strong product coverage")
    manifest["variants"][profile]["reviewed"] = True
    manifest["variants"][profile]["review"] = {
        "source_sha256": image_id, "policy_version": POLICY_VERSION, "channel": channel,
        "reviewed_at": datetime.now(timezone.utc).isoformat(), "clean_photographs": True,
    }
    if profile == "amazon":
        manifest["variants"][profile]["white_background_approved"] = True
    path.write_text(json.dumps(manifest), encoding="utf-8")


async def prepare_channel_urls(urls: list[str], channel: str, *, require_review: bool = True) -> list[str]:
    profile = profile_for(channel)
    result = []
    for url in urls:
        manifest = await image_manifest(url)
        variant = manifest["variants"][profile]
        if require_review and not variant.get("reviewed"):
            raise ValueError(f"Preview and approve the {channel} photograph before publishing")
        result.append(variant["url"])
    if not result:
        raise ValueError("At least one product photograph is required")
    return result


async def require_public_images(urls: list[str], channel: str) -> None:
    """A local preview must never stand in for public image delivery."""
    expected_size = PROFILES[profile_for(channel)]
    for url in urls:
        try:
            data = await load_remote_image(url)
            with Image.open(io.BytesIO(data)) as image:
                if image.size != expected_size:
                    raise ValueError("Published image dimensions differ from the reviewed format")
            local = local_image_path(url)
            if local and hashlib.sha256(data).digest() != hashlib.sha256(local.read_bytes()).digest():
                raise ValueError("Public image differs from the reviewed derivative")
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise ValueError(f"The reviewed {channel} image is not publicly available in its approved format. Publish/sync the image assets before submitting the listing.") from exc
