"""Select one captured physical component photo for a curated Meshy draft.

Local Qwen checks captured photos against the exact catalogue title. The first
verified original image is passed to Meshy's single-image endpoint.
"""
from __future__ import annotations

import io
import json
from contextlib import aclosing
from typing import AsyncIterator, Awaitable, Callable
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from app.services.model_selection_service import ModelSelectionError, model_selection_service
from app.services.model_reference_images import original_image_url

# Photo review is run inside the API process. Bound its sequential image input.
_MAX_CANDIDATES = 6
_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_ALLOWED_IMAGE_HOSTS = {
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "images-eu.ssl-images-amazon.com",
    "i.ebayimg.com",
}


class MediaPipelineError(RuntimeError):
    pass


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MediaPipelineError("Local Qwen returned an unreadable photo decision") from exc
    if not isinstance(value, dict):
        raise MediaPipelineError("Local Qwen returned an invalid photo decision")
    return value


async def _review_image(title: str, image_bytes: bytes, content_type: str) -> dict:
    prompt = (
        "Inspect this captured product photo for the exact catalogue item. Return only JSON with keys: "
        "physical_component (boolean), matches_title (boolean), packaging_or_diagram (boolean), "
        "quality (integer 1-5), reason (short string). Only mark physical_component=true when the "
        "actual component hardware is visible, not its retail box, packaging, diagram or an unrelated item. "
        "Set packaging_or_diagram=true if ANY retail box or packaging is visible, even alongside hardware. "
        "Reject accessories or spare parts when the title category expects a complete component. "
        f"Compare visible identity to this exact title: {title}"
    )
    try:
        result = await model_selection_service.complete(
            task="curated component photo selection",
            messages=[{"role": "user", "content": prompt}],
            images=[(image_bytes, content_type)],
            max_tokens=200,
            timeout=60,
            json_mode=True,
            require_vision=True,
            local_only=True,
        )
    except ModelSelectionError as exc:
        raise MediaPipelineError(f"Local Qwen photo review failed: {exc}") from exc

    decision = _parse_json(result.text)
    for key in ("physical_component", "matches_title", "packaging_or_diagram"):
        if not isinstance(decision.get(key), bool):
            raise MediaPipelineError(f"Local Qwen omitted the required {key} decision")
    try:
        decision["quality"] = max(1, min(5, int(decision.get("quality", 1))))
    except (TypeError, ValueError):
        decision["quality"] = 1
    return decision


async def _download_candidates(urls: list[str]) -> AsyncIterator[tuple[str, bytes, str]]:
    seen: set[str] = set()
    downloaded = 0
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        for url in urls:
            if downloaded >= _MAX_CANDIDATES:
                break
            resolved = original_image_url(url)
            try:
                parsed = urlsplit(resolved)
            except ValueError:
                continue
            if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_IMAGE_HOSTS or parsed.username or parsed.password:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                chunks: list[bytes] = []
                content_size = 0
                async with client.stream("GET", resolved) as response:
                    response.raise_for_status()
                    content_length = response.headers.get("content-length", "")
                    if content_length.isdigit() and int(content_length) > _MAX_SOURCE_BYTES:
                        continue
                    async for chunk in response.aiter_bytes():
                        content_size += len(chunk)
                        if content_size > _MAX_SOURCE_BYTES:
                            chunks.clear()
                            break
                        chunks.append(chunk)
                if not chunks or content_size > _MAX_SOURCE_BYTES:
                    continue
                content = b"".join(chunks)
                chunks.clear()
                with Image.open(io.BytesIO(content)) as image:
                    image.verify()
                    width, height = image.size
                    content_type = Image.MIME.get(image.format or "", "image/jpeg")
                if min(width, height) < 160:
                    continue
                downloaded += 1
                yield resolved, content, content_type
                del content
            except (httpx.HTTPError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
                continue


Progress = Callable[[str, int, str | None], Awaitable[None]]


async def select_component_photo(
    *,
    title: str,
    candidate_urls: list[str],
    progress: Progress,
) -> tuple[str, dict]:
    """Return one Qwen-verified original photo URL and its selection evidence."""
    reviewed = 0
    async with aclosing(_download_candidates(candidate_urls)) as candidates:
        async for url, content, content_type in candidates:
            reviewed += 1
            await progress("reviewing_source_photos", min(75, reviewed * 75 // _MAX_CANDIDATES), None)
            decision = await _review_image(title, content, content_type)
            if decision["physical_component"] and decision["matches_title"] and not decision["packaging_or_diagram"]:
                await progress("single_photo_selected", 90, None)
                return url, {
                    "selection_method": "local_qwen_exact_component_photo_review",
                    "selected_source_url": url,
                    "source_decision": decision,
                    "candidate_count_reviewed": reviewed,
                }
            del content
    if reviewed == 0:
        raise MediaPipelineError("No supported, full-size captured product photos are available")
    raise MediaPipelineError("Local Qwen could not verify a captured image as the exact physical component")
