"""Capture reviewed-key candidates from the operator-selected software source.

RoyalCDKeys product facts remain catalogue candidates until an operator reviews
the exact listing and its licence terms. This module never approves or publishes
an OS offer.
"""
import asyncio
from datetime import datetime
from decimal import Decimal
import re
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.listing import Classification, Listing
from app.models.playbook import Playbook
from app.models.source import DataSource, SourceType
from app.services.playbook_product_capture import collect_product_capture, PARSER_VERSION

BESTSELLER_URL = "https://royalcdkeys.com/en-gb/collections/bestseller?country=GB&currency=GBP"
SOURCE_NAME = "RoyalCDKeys"
_WINDOWS_11 = re.compile(r"\bwindows\s+11\s+(home|pro)\b", re.I)
_CHANNEL = re.compile(r"\b(?:oem|retail)\b", re.I)
_OFFICE_2024 = re.compile(r"\bmicrosoft\s+office\s+2024\b", re.I)
_GOOGLE_AI_18M = re.compile(r"\bgoogle\s+ai\s+pro\b.*\b18[- ]month\b", re.I)
ROYALCDKEYS_CAPTURE_CONCURRENCY = 3


async def _capture_candidates(candidates):
    """Fetch exact product pages concurrently, keeping DB work out of tasks."""
    semaphore = asyncio.Semaphore(ROYALCDKEYS_CAPTURE_CONCURRENCY)

    async def capture(candidate):
        async with semaphore:
            try:
                result = await collect_product_capture(candidate["url"])
            except Exception as error:
                result = {"status": "unresolved", "reason": f"Product capture failed: {type(error).__name__}"}
            return candidate, result

    return await asyncio.gather(*(capture(candidate) for candidate in candidates))


def candidate_product_links(html, base_url=BESTSELLER_URL):
    """Select exact Windows, Office 2024, and 18-month Google AI Pro candidates.

    Generic Windows keys remain excluded because they do not identify an
    edition/channel. Office and subscription offers are captured for review
    only and are never linked into hardware slots.
    """
    soup = BeautifulSoup(html, "html.parser")
    selected = []
    seen = set()
    for anchor in soup.select('a[href*="/products/"]'):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        match = _WINDOWS_11.search(title)
        category = ("os" if match and _CHANNEL.search(title) else
            "office" if _OFFICE_2024.search(title) else
            "ai_subscription" if _GOOGLE_AI_18M.search(title) else None)
        if not category:
            continue
        href = urljoin(base_url, anchor.get("href", ""))
        parsed = urlsplit(href)
        handle = re.fullmatch(r"/en-gb/products/([a-z0-9][a-z0-9-]*)", parsed.path.casefold())
        if (parsed.scheme != "https" or parsed.hostname != "royalcdkeys.com" or not handle
                or parsed.username or parsed.password or href in seen):
            continue
        seen.add(href)
        selected.append({"title": title, "url": f"https://royalcdkeys.com{parsed.path}?country=GB&currency=GBP",
            "category": category, "edition": match.group(1).casefold() if match else None,
            "license_channel": _CHANNEL.search(title).group(0).upper() if match and _CHANNEL.search(title) else None,
            "handle": handle.group(1)})
    return selected


async def _source_data(db):
    row = (await db.execute(select(DataSource).where(DataSource.name == SOURCE_NAME))).scalar_one_or_none()
    if row is None:
        row = DataSource(name=SOURCE_NAME, url=BESTSELLER_URL, source_type=SourceType.scrape,
            enabled=True, config={"purpose": "Playbook Windows, Office and software subscription candidate discovery", "operator_approval_required": True})
        db.add(row)
        await db.flush()
    return row


async def refresh_royalcdkeys_os_catalogue(db, limit=8):
    """Capture exact RoyalCDKeys products; only Windows creates pending OS links."""
    now = datetime.utcnow()
    result = {"products_seen": 0, "products_captured": 0, "unresolved": 0,
        "created_listings": 0, "created_variants": 0, "pending_operator_review": 0,
        "pending_catalogue_links": 0,
        "review_only_products": 0, "excluded_untyped_keys": 0, "published": False, "errors": []}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.get(BESTSELLER_URL, headers={"Accept": "text/html"})
            if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
                raise ValueError(f"RoyalCDKeys bestseller page returned HTTP {response.status_code}")
            links = candidate_product_links(response.text)
            soup = BeautifulSoup(response.text, "html.parser")
            all_titles = [" ".join(a.get_text(" ", strip=True).split())
                for a in soup.select('a[href*="/products/"]')]
            result["excluded_untyped_keys"] = sum(bool(_WINDOWS_11.search(title)) and not _CHANNEL.search(title)
                for title in all_titles)
    except Exception as error:
        result["errors"].append(type(error).__name__)
        result["error_detail"] = str(error)[:300]
        return result

    result["products_seen"] = len(links)
    links = links[:max(0, limit)]
    if not links:
        return result

    source = await _source_data(db)
    parents = (await db.execute(select(Playbook).where(Playbook.status == "active"))).scalars().all()
    slots = (await db.execute(select(PlaybookSlot).where(
        PlaybookSlot.playbook_id.in_([parent.id for parent in parents]), PlaybookSlot.slot_type == "os",
    ))).scalars().all() if parents else []
    slots_by_parent = {slot.playbook_id: slot for slot in slots}

    # Capture network evidence in a small bounded pool, then persist each result
    # sequentially through this AsyncSession to avoid concurrent transaction use.
    captured_candidates = await _capture_candidates(links)
    for candidate, capture in captured_candidates:
        if capture.get("status") != "captured":
            result["unresolved"] += 1
            result["errors"].append(f"{candidate['handle']}: {capture.get('reason', 'capture unresolved')}")
            continue
        if (not capture.get("digital_product") or capture.get("licence_review_required") is not True
                or capture.get("licence_resale_rights_verified") is not False
                or capture.get("supplier_product_handle") != candidate["handle"]):
            result["unresolved"] += 1
            result["errors"].append(f"{candidate['handle']}: exact digital licence facts were not established")
            continue
        title = capture["title"]
        if candidate["category"] == "os":
            edition = _WINDOWS_11.search(title)
            if not edition or edition.group(1).casefold() != candidate["edition"]:
                result["unresolved"] += 1
                result["errors"].append(f"{candidate['handle']}: exact Windows edition did not match")
                continue
            unique_claim = (capture.get("product_properties") or {}).get("Key uniqueness (supplier claim)", "")
            if "not guaranteed" in unique_claim.casefold():
                result["unresolved"] += 1
                result["errors"].append(f"{candidate['handle']}: supplier does not guarantee a unique key per licence")
                continue
        elif candidate["category"] == "office" and not _OFFICE_2024.search(title):
            result["unresolved"] += 1
            result["errors"].append(f"{candidate['handle']}: exact Office 2024 product identity did not match")
            continue
        elif candidate["category"] == "ai_subscription" and not _GOOGLE_AI_18M.search(title):
            result["unresolved"] += 1
            result["errors"].append(f"{candidate['handle']}: exact Google AI Pro 18-month product identity did not match")
            continue
        try:
            price = Decimal(capture["item_gbp"])
        except Exception:
            result["unresolved"] += 1
            result["errors"].append(f"{candidate['handle']}: exact GBP price is invalid")
            continue
        result["products_captured"] += 1
        external_id = f"royalcdkeys:{candidate['handle']}"
        listing = (await db.execute(select(Listing).where(Listing.external_id == external_id)
            .with_for_update())).scalar_one_or_none()
        raw = {"royalcdkeys": {"category": candidate["category"], "handle": candidate["handle"],
                "discovery_url": BESTSELLER_URL, "license_channel": candidate["license_channel"],
                "operator_approval_required": True,
                "customer_offering_enabled": False},
            "playbook_product_capture": {**capture, "attempted_at": now.replace(tzinfo=None).isoformat() + "+00:00",
                "parser_version": PARSER_VERSION}}
        images = [capture["image_url"]] if capture.get("image_url") else []
        if listing is None:
            listing = Listing(external_id=external_id, source_id=source.id, source_name=SOURCE_NAME,
                source_confidence="playbook_supplier_capture", title=title,
                description=capture.get("seller_product_claims"), price=float(price), url=candidate["url"],
                image_urls=images, condition="new", listing_type="buy_it_now", status="active",
                classification=Classification.unclassified, gem_score=0.0, raw_specs=raw,
                last_seen_at=now)
            db.add(listing)
            await db.flush()
            result["created_listings"] += 1
        else:
            listing.source_id = source.id
            listing.source_name = SOURCE_NAME
            listing.source_confidence = "playbook_supplier_capture"
            listing.title = title
            listing.description = capture.get("seller_product_claims")
            listing.price = float(price)
            listing.url = candidate["url"]
            listing.image_urls = images
            listing.condition = "new"
            listing.listing_type = "buy_it_now"
            listing.raw_specs = {**(listing.raw_specs or {}), **raw}
            listing.last_seen_at = now
        pending_links = 0
        if candidate["category"] != "os":
            result["review_only_products"] += 1
            result["pending_operator_review"] += 1
            continue
        for parent in parents:
            slot = slots_by_parent.get(parent.id)
            if slot is None:
                slot = PlaybookSlot(playbook_id=parent.id, slot_type="os")
                db.add(slot)
                await db.flush()
                slots_by_parent[parent.id] = slot
            variant = (await db.execute(select(CatalogueVariant).where(
                CatalogueVariant.listing_id == listing.id, CatalogueVariant.slot_id == slot.id,
            ).with_for_update())).scalar_one_or_none()
            if variant is None:
                db.add(CatalogueVariant(listing_id=listing.id, slot_id=slot.id,
                    status="pending_review", display_price=float(price), tier="budget",
                    curated_for_builds=True, custom_for_builds=False))
                result["created_variants"] += 1
                pending_links += 1
            elif variant.status != "rejected":
                variant.last_seen_at = now.isoformat()
                # Keep customer-visible catalogue prices unchanged; the exact
                # captured supplier offer is reviewed independently below.
                if variant.status == "pending_review":
                    variant.display_price = float(price)
                    pending_links += 1
        result["pending_operator_review"] += 1
        result["pending_catalogue_links"] += pending_links
    source.listings_found_last_run = result["products_captured"]
    source.listings_found_total = (source.listings_found_total or 0) + result["products_captured"]
    source.last_scraped_at = now
    source.last_error = "; ".join(result["errors"][:8])[:2000] or None
    await db.flush()
    return result
