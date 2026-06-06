"""
Manual listing scraper — turns a URL or an image into a RawListing
that feeds directly into the standard pipeline.

Supported URL sources:
  ✅ eBay item pages (ebay.co.uk/itm/...)
  ✅ Gumtree ad pages
  ✅ Preloved ad pages
  ✅ Facebook Marketplace (best-effort, JS-heavy — extracts from OG meta)
  ✅ Generic HTML pages (best-effort from OG / meta / first heading + price)

Image support:
  ✅ Ollama vision (any multimodal model: llava, gemma3, etc.)
  ✅ Plain text fallback — user-supplied title + price if AI unavailable
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.services.scraper import RawListing, classify_seller, _parse_ebay_time_left

settings = get_settings()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ─── URL scraping ─────────────────────────────────────────────────────────────

async def scrape_url(url: str, price_override: Optional[float] = None) -> RawListing:
    """
    Fetch a listing URL and return a RawListing.
    For eBay URLs: tries the Browse API first (bot-safe), falls back to HTML.
    Raises ValueError if the page can't be parsed sensibly.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "ebay.co.uk" in host or "ebay.com" in host:
        item_id_match = re.search(r"/itm/(?:[^/]+/)?(\d+)", url)
        if item_id_match:
            try:
                result = await _ebay_api_fetch_item(
                    item_id_match.group(1), url, price_override
                )
                if result:
                    return result
            except ValueError:
                raise  # price-not-found errors should surface to the caller
            except Exception:
                pass  # network / auth failure → fall through to HTML scraping

        # HTML fallback (e.g. no eBay credentials configured)
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=15
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                raise ValueError(f"HTTP {resp.status_code} fetching {url}")
            html = resp.text
        return _parse_ebay_item(html, url, price_override)

    # Non-eBay: HTML scraping
    async with httpx.AsyncClient(
        headers=_HEADERS, follow_redirects=True, timeout=15
    ) as client:
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise ValueError(f"HTTP {resp.status_code} fetching {url}")
        html = resp.text

    if "gumtree.com" in host:
        return _parse_gumtree_item(html, url, price_override)
    if "preloved.co.uk" in host:
        return _parse_preloved_item(html, url, price_override)
    if "facebook.com" in host or "fb.com" in host:
        return _parse_facebook_item(html, url, price_override)
    return _parse_generic(html, url, price_override)


def _make_id(url: str) -> str:
    return "manual_" + hashlib.md5(url.encode()).hexdigest()[:12]


def _clean_price(text: str) -> Optional[float]:
    """Extract a float from a messy price string like '£ 149.99' or 'GBP 149'."""
    m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    return float(m.group().replace(",", "")) if m else None


def _first_image(soup: BeautifulSoup, base_url: str) -> list[str]:
    imgs = []
    for og in soup.find_all("meta", property="og:image"):
        src = og.get("content", "")
        if src and src.startswith("http"):
            imgs.append(src)
    if not imgs:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src and src.startswith("http") and any(
                x in src for x in ["item", "photo", "listing", "product", "image"]
            ):
                imgs.append(src)
    return imgs[:5]


def _parse_ebay_item(html: str, url: str, price_override: Optional[float] = None) -> RawListing:
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = (
        soup.find("h1", class_="x-item-title__mainTitle")
        or soup.find("h1", id="itemTitle")
        or soup.find("meta", property="og:title")
    )
    title = (
        title_tag.get("content", "") if title_tag and title_tag.name == "meta"
        else title_tag.get_text(strip=True) if title_tag
        else "eBay Listing"
    )

    # Price — try multiple selectors
    price = price_override
    if price is None:
        for sel in [
            {"class": "x-price-primary"},
            {"class": "notranslate"},
            {"itemprop": "price"},
        ]:
            tag = soup.find(attrs=sel)
            if tag:
                p = _clean_price(tag.get_text())
                if p and 5 < p < 5000:
                    price = p
                    break
        if price is None:
            meta_price = soup.find("meta", itemprop="price")
            if meta_price:
                price = _clean_price(meta_price.get("content", ""))

    if not price:
        raise ValueError("Could not extract price from eBay page")

    # Description
    desc_tag = soup.find("div", id="viTabs_0_is") or soup.find("div", class_="itemAttr")
    description = desc_tag.get_text(" ", strip=True)[:1000] if desc_tag else ""

    # Images
    images = []
    for tag in soup.find_all("img", attrs={"data-zoom-src": True}):
        src = tag.get("data-zoom-src", "")
        if src.startswith("http"):
            images.append(src)
    if not images:
        images = _first_image(soup, url)

    # Condition
    cond_tag = soup.find(class_="x-item-condition-text") or soup.find(itemprop="itemCondition")
    condition = cond_tag.get_text(strip=True) if cond_tag else None

    # Location
    loc_tag = soup.find("span", class_="ux-textspans--PSEUDOLINK")
    location = loc_tag.get_text(strip=True) if loc_tag else "UK"

    # Seller
    seller_tag = soup.find("span", class_="mbg-nw") or soup.find(class_="x-sellercard-atf__info__about-seller")
    seller_name = seller_tag.get_text(strip=True) if seller_tag else None

    # Listing type / time left
    listing_type = "buy_it_now"
    listing_ends_at = None
    time_tag = soup.find(class_="x-endtime-value") or soup.find(class_="timeMs")
    if time_tag:
        listing_type = "auction"
        listing_ends_at = _parse_ebay_time_left(time_tag.get_text())

    # eBay item ID from URL
    item_id_match = re.search(r"/itm/(?:[^/]+/)?(\d+)", url)
    external_id = f"ebay_{item_id_match.group(1)}" if item_id_match else _make_id(url)

    return RawListing(
        external_id=external_id,
        title=title.replace("eBay item number:", "").strip(),
        price=price,
        url=url,
        location=location,
        condition=condition,
        description=description,
        image_urls=images,
        source_name="Manual Submission",
        listing_type=listing_type,
        listing_ends_at=listing_ends_at,
        seller_name=seller_name,
        seller_type=classify_seller(seller_name, None, title),
    )


async def _ebay_api_fetch_item(
    item_id: str, url: str, price_override: Optional[float] = None
) -> "RawListing | None":
    """
    Fetch a single eBay listing via Browse API getItemByLegacyId.
    Returns None if credentials are missing or the API call fails —
    caller falls back to HTML scraping.
    """
    from app.services.scraper import _get_ebay_access_token, _ebay_base_url

    async with httpx.AsyncClient(timeout=15) as client:
        token = await _get_ebay_access_token(client)
        if not token:
            return None

        endpoint = f"{_ebay_base_url()}/buy/browse/v1/item/get_item_by_legacy_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
            "Content-Type": "application/json",
        }
        resp = await client.get(
            endpoint,
            params={"legacy_item_id": item_id},
            headers=headers,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()

    title = str(data.get("title") or "eBay Listing").strip()

    # Price
    price = price_override
    if price is None:
        price_obj = data.get("price") or data.get("currentBidPrice") or {}
        try:
            price = float(price_obj.get("value") or 0) or None
        except (TypeError, ValueError):
            price = None
    if not price:
        raise ValueError("Could not extract price from eBay API response")

    # Images — primary + additionalImages
    images: list[str] = []
    if primary_url := (data.get("image") or {}).get("imageUrl"):
        images.append(primary_url)
    for extra in data.get("additionalImages") or []:
        if src := extra.get("imageUrl"):
            images.append(src)

    # Location
    loc_obj = data.get("itemLocation") or {}
    location = loc_obj.get("city") or loc_obj.get("country")

    # Description — strip HTML tags
    desc_html = data.get("description") or data.get("shortDescription") or ""
    description = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)[:1000] if desc_html else ""

    # Condition
    condition = data.get("condition")

    # Seller
    seller = data.get("seller") or {}
    seller_name = seller.get("username")
    feedback_score: Optional[int] = None
    _fs = seller.get("feedbackScore")
    if _fs is not None:
        try:
            feedback_score = int(_fs)
        except (TypeError, ValueError):
            pass
    feedback_pct: Optional[float] = None
    try:
        pct_str = str(seller.get("feedbackPercentage") or "")
        feedback_pct = float(pct_str.replace("%", "")) if pct_str else None
    except (TypeError, ValueError):
        pass

    # Listing type
    buying_options = data.get("buyingOptions") or []
    listing_type = "auction" if "AUCTION" in buying_options else "buy_it_now"

    # Auction end datetime
    listing_ends_at = None
    if end_date_str := data.get("itemEndDate"):
        try:
            listing_ends_at = datetime.fromisoformat(
                end_date_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            pass

    return RawListing(
        external_id=f"ebay_{item_id}",
        title=title,
        price=price,
        url=url,
        location=location,
        condition=condition,
        description=description,
        image_urls=images[:5],
        source_name="Manual Submission",
        source_confidence="official_api",
        listing_type=listing_type,
        listing_ends_at=listing_ends_at,
        seller_name=seller_name,
        seller_feedback_count=feedback_score,
        seller_feedback_pct=feedback_pct,
        seller_type=classify_seller(seller_name, feedback_score, title),
    )


def _parse_gumtree_item(html: str, url: str, price_override: Optional[float] = None) -> RawListing:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1", class_="listing-title") or soup.find("meta", property="og:title")
    title = (
        title_tag.get("content", "") if title_tag and title_tag.name == "meta"
        else title_tag.get_text(strip=True) if title_tag
        else "Gumtree Listing"
    )

    price = price_override
    if price is None:
        price_tag = soup.find(class_="listing-price") or soup.find(attrs={"data-q": "price"})
        if price_tag:
            price = _clean_price(price_tag.get_text())

    if not price:
        raise ValueError("Could not extract price from Gumtree page")

    desc_tag = soup.find(class_="ad-description") or soup.find(itemprop="description")
    description = desc_tag.get_text(" ", strip=True)[:1000] if desc_tag else ""

    loc_tag = soup.find(class_="listing-location") or soup.find(attrs={"data-q": "location"})
    location = loc_tag.get_text(strip=True) if loc_tag else "UK"

    images = _first_image(soup, url)

    # Gumtree ad ID
    ad_id = re.search(r"/(\d+)(?:\?|$)", url)
    external_id = f"gumtree_{ad_id.group(1)}" if ad_id else _make_id(url)

    return RawListing(
        external_id=external_id,
        title=title,
        price=price,
        url=url,
        location=location,
        condition=None,
        description=description,
        image_urls=images,
        source_name="Manual Submission",
        listing_type="classified",
    )


def _parse_preloved_item(html: str, url: str, price_override: Optional[float] = None) -> RawListing:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1") or soup.find("meta", property="og:title")
    title = (
        title_tag.get("content", "") if title_tag and title_tag.name == "meta"
        else title_tag.get_text(strip=True) if title_tag
        else "Preloved Listing"
    )

    price = price_override
    if price is None:
        price_tag = soup.find(class_=re.compile(r"price", re.I))
        if price_tag:
            price = _clean_price(price_tag.get_text())

    if not price:
        raise ValueError("Could not extract price from Preloved page")

    images = _first_image(soup, url)
    desc_tag = soup.find(class_=re.compile(r"descr|detail", re.I))
    description = desc_tag.get_text(" ", strip=True)[:1000] if desc_tag else ""

    ad_id = re.search(r"/(\d+)", url)
    external_id = f"preloved_{ad_id.group(1)}" if ad_id else _make_id(url)

    return RawListing(
        external_id=external_id,
        title=title,
        price=price,
        url=url,
        location=None,
        condition=None,
        description=description,
        image_urls=images,
        source_name="Manual Submission",
        listing_type="classified",
    )


def _parse_facebook_item(html: str, url: str, price_override: Optional[float] = None) -> RawListing:
    """Facebook Marketplace — JS-rendered, extract from OG meta tags only."""
    soup = BeautifulSoup(html, "html.parser")

    og_title = soup.find("meta", property="og:title")
    title = og_title.get("content", "Facebook Listing") if og_title else "Facebook Listing"

    og_desc = soup.find("meta", property="og:description")
    description = og_desc.get("content", "") if og_desc else ""

    price = price_override
    if price is None:
        # Try to extract price from title or description (FB often includes "£XXX")
        for text in [title, description]:
            p = _clean_price(re.sub(r"[^£\d.,]", " ", text))
            if p and 5 < p < 5000:
                price = p
                break

    if not price:
        raise ValueError("Could not extract price from Facebook page — please enter price manually")

    images = _first_image(soup, url)

    return RawListing(
        external_id=_make_id(url),
        title=title,
        price=price,
        url=url,
        location=None,
        condition=None,
        description=description,
        image_urls=images,
        source_name="Manual Submission",
        listing_type="classified",
    )


def _parse_generic(html: str, url: str, price_override: Optional[float] = None) -> RawListing:
    """Best-effort extraction from any HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    og_title = soup.find("meta", property="og:title")
    h1 = soup.find("h1")
    title = (
        og_title.get("content", "") if og_title
        else h1.get_text(strip=True) if h1
        else soup.title.get_text(strip=True) if soup.title
        else "Manual Listing"
    )

    price = price_override
    if price is None:
        # Look for price patterns in the page text
        text = soup.get_text(" ")
        matches = re.findall(r"£\s*([\d,]+\.?\d*)", text)
        candidates = [float(m.replace(",", "")) for m in matches if 5 < float(m.replace(",", "")) < 5000]
        price = candidates[0] if candidates else None

    if not price:
        raise ValueError("Could not find a price on this page — please enter price manually")

    og_desc = soup.find("meta", property="og:description")
    desc_tag = soup.find(itemprop="description") or soup.find(class_=re.compile(r"descr|detail|content|body", re.I))
    description = (
        og_desc.get("content", "") if og_desc
        else desc_tag.get_text(" ", strip=True)[:1000] if desc_tag
        else ""
    )

    images = _first_image(soup, url)

    return RawListing(
        external_id=_make_id(url),
        title=title[:200],
        price=price,
        url=url,
        location=None,
        condition=None,
        description=description[:1000],
        image_urls=images,
        source_name="Manual Submission",
        listing_type="classified",
    )


# ─── Image analysis via Ollama vision ────────────────────────────────────────

_VISION_PROMPT = """You are a PC hardware identification system.

Look at this image and extract the following information about the PC or computer parts shown.

Respond with ONLY a JSON object — no markdown, no explanation:
{
  "title": "concise descriptive title for this listing (max 80 chars)",
  "description": "brief description of what you can see",
  "cpu": "CPU model if visible (e.g. Intel Core i7-8700, null if not visible)",
  "gpu": "GPU model if present (e.g. GTX 1080, null if not present or not visible)",
  "ram_gb": numeric GB of RAM if visible or null,
  "has_gpu": true or false,
  "has_psu": true or false (does it look like a complete tower with PSU?),
  "condition_notes": "any visible damage, missing components, dust etc",
  "estimated_price_gbp": your best estimate of fair market asking price in GBP as integer, or null
}"""


async def analyse_image(
    image_bytes: bytes,
    content_type: str = "image/jpeg",
    user_title: Optional[str] = None,
    user_price: Optional[float] = None,
) -> RawListing:
    """
    Run Ollama vision on an image and return a RawListing.
    Falls back to a minimal listing if vision is unavailable.
    """
    s = get_settings()
    extracted: dict = {}

    # Try Ollama vision
    if s.ollama_base_url:
        b64 = base64.b64encode(image_bytes).decode()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{s.ollama_base_url.rstrip('/')}/api/chat",
                    json={
                        "model": s.ollama_model,
                        "stream": False,
                        "messages": [
                            {
                                "role": "user",
                                "content": _VISION_PROMPT,
                                "images": [b64],
                            }
                        ],
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("message", {}).get("content", "")
                    # Extract JSON from response
                    m = re.search(r"\{[\s\S]*\}", content)
                    if m:
                        extracted = json.loads(m.group())
        except Exception as e:
            print(f"[manual_scraper] Ollama vision failed: {e}")

    # Build title from extracted data or user override
    title = user_title or extracted.get("title") or "Manual Photo Submission"
    price = user_price or extracted.get("estimated_price_gbp")

    if not price:
        raise ValueError(
            "Could not determine price from image. Please enter a price manually."
        )

    description = extracted.get("description", "")
    if extracted.get("cpu"):
        description += f" CPU: {extracted['cpu']}."
    if extracted.get("gpu"):
        description += f" GPU: {extracted['gpu']}."
    if extracted.get("condition_notes"):
        description += f" Notes: {extracted['condition_notes']}."

    external_id = "manual_photo_" + hashlib.md5(image_bytes[:256]).hexdigest()[:12]

    return RawListing(
        external_id=external_id,
        title=title[:200],
        price=float(price),
        url="",   # no URL for photo submissions
        location=None,
        condition=extracted.get("condition_notes"),
        description=description[:1000],
        image_urls=[],   # image stored client-side; no hosted URL yet
        source_name="Manual Photo",
        listing_type="classified",
    )
