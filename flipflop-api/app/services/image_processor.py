"""
Image Processing Service - Process and brand product images for eBay listings.

Handles:
- Fetching images from source listings
- Adding FlipFlop watermark/branding
- Resizing and compressing for eBay optimal sizing
- Generating specs overlay images
"""

import io
import asyncio
from typing import Optional, List, TYPE_CHECKING
from pathlib import Path
import structlog
import httpx

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore

if TYPE_CHECKING:
    from PIL import Image as PILImage

log = structlog.get_logger(__name__)

# Image constants
EBAY_OPTIMAL_SIZE = (1500, 1500)  # eBay recommends 1500x1500 for best quality
QUALITY_COMPRESSION = 85
MAX_IMAGE_SIZE_KB = 150


class ImageProcessingError(Exception):
    """Raised when image processing fails."""
    pass


def _check_pil_available():
    """Verify PIL/Pillow is available."""
    if not PIL_AVAILABLE:
        raise ImageProcessingError("Pillow library required for image processing. Install: pip install Pillow")


async def fetch_image_bytes(url: str, timeout: int = 20) -> Optional[bytes]:
    """
    Fetch image bytes from a URL.

    Args:
        url: Image URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Image bytes or None if fetch fails
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return resp.content
            log.warning("image_processor.fetch_failed", url=url, status=resp.status_code)
            return None
    except Exception as e:
        log.warning("image_processor.fetch_error", url=url, error=str(e))
        return None


def process_image_bytes(
    image_bytes: bytes,
    target_size: tuple = EBAY_OPTIMAL_SIZE,
    quality: int = QUALITY_COMPRESSION,
    add_watermark: bool = True,
    watermark_text: Optional[str] = None,
) -> Optional[bytes]:
    """
    Process image bytes: resize, compress, add watermark.

    Args:
        image_bytes: Raw image bytes
        target_size: Target size tuple (width, height)
        quality: JPEG quality (0-95)
        add_watermark: Whether to add FlipFlop watermark
        watermark_text: Text for watermark (default "FlipFlop")

    Returns:
        Processed image bytes or None if processing fails
    """
    _check_pil_available()

    try:
        # Open image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Resize maintaining aspect ratio
        img.thumbnail(target_size, Image.Resampling.LANCZOS)

        # Create new image with target size, centered
        final_img = Image.new("RGB", target_size, color=(255, 255, 255))
        x = (target_size[0] - img.width) // 2
        y = (target_size[1] - img.height) // 2
        final_img.paste(img, (x, y))

        # Add watermark if requested
        if add_watermark:
            _add_watermark(final_img, watermark_text or "FlipFlop")

        # Compress to bytes
        out = io.BytesIO()
        final_img.save(out, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = out.getvalue()

        size_kb = len(compressed_bytes) / 1024
        if size_kb > MAX_IMAGE_SIZE_KB:
            log.warning("image_processor.size_exceeded", size_kb=size_kb, max_kb=MAX_IMAGE_SIZE_KB)

        log.info("image_processor.processed", input_size=len(image_bytes), output_size=len(compressed_bytes))
        return compressed_bytes

    except Exception as e:
        log.error("image_processor.processing_failed", error=str(e))
        return None


def _add_watermark(img: "Image.Image", text: str = "FlipFlop", opacity: float = 0.15):
    """
    Add watermark text to image (bottom-right corner).

    Args:
        img: PIL Image object
        text: Text to add
        opacity: Opacity of watermark (0-1)
    """
    try:
        # Create transparent layer for watermark
        watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)

        # Try to use a nice font, fallback to default
        font_size = img.height // 15
        try:
            # Try to find a font
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Position at bottom-right with padding
        padding = 20
        x = img.width - text_width - padding
        y = img.height - text_height - padding

        # Draw white text with shadow for visibility
        shadow_offset = 2
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text,
            fill=(0, 0, 0, int(255 * opacity * 0.5)),
            font=font,
        )
        draw.text(
            (x, y),
            text,
            fill=(255, 255, 255, int(255 * opacity)),
            font=font,
        )

        # Convert main image to RGBA if needed, apply watermark
        img_rgba = Image.new("RGBA", img.size)
        img_rgba.paste(img, (0, 0))
        img_rgba.alpha_composite(watermark)

        # Convert back to RGB
        final = Image.new("RGB", img.size, (255, 255, 255))
        final.paste(img_rgba, mask=img_rgba.split()[3])

        # Copy result back to original image
        img.paste(final)

    except Exception as e:
        log.warning("image_processor.watermark_failed", error=str(e))
        # Continue without watermark on error


async def process_images_for_listing(
    image_urls: List[str],
    max_concurrent: int = 3,
    add_watermark: bool = True,
) -> tuple[List[bytes], List[str]]:
    """
    Process multiple images for a listing.

    Args:
        image_urls: List of image URLs
        max_concurrent: Max concurrent downloads
        add_watermark: Whether to add FlipFlop branding

    Returns:
        Tuple of (processed_image_bytes_list, error_urls)
    """
    _check_pil_available()

    processed = []
    errors = []

    # Process in batches to limit concurrency
    for i in range(0, len(image_urls), max_concurrent):
        batch = image_urls[i : i + max_concurrent]
        tasks = [fetch_image_bytes(url) for url in batch]
        results = await asyncio.gather(*tasks)

        for url, image_bytes in zip(batch, results):
            if image_bytes:
                processed_bytes = process_image_bytes(
                    image_bytes,
                    add_watermark=add_watermark,
                )
                if processed_bytes:
                    processed.append(processed_bytes)
                else:
                    errors.append(url)
            else:
                errors.append(url)

    log.info("image_processor.batch_complete", processed=len(processed), errors=len(errors))
    return processed, errors


def get_image_size_kb(image_bytes: bytes) -> float:
    """Get size of image in KB."""
    return len(image_bytes) / 1024
