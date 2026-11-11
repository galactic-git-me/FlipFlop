"""Discover and cache exact Playbook component guides from manufacturer sites.

Search results are treated as untrusted pointers. Downloads are restricted to
known manufacturer domains, PDF headers and size are validated, and candidate
titles/URLs must identify the exact component before a file enters the library.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.component_manual import ComponentManual
from app.models.listing import Listing
from app.models.playbook import Playbook
from app.services.component_manual_library import normalize_manual_key, matching_manuals
from app.services.component_research_search import discover_component_sources

_MAX_PDF_BYTES = 25_000_000
_RETRY_DAYS = 30
_MANUAL_ROOT = Path(__file__).resolve().parents[2] / "data" / "getting-ready-packages" / "manual-library"
_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "component-manual-discovery.json"
_LOCK = asyncio.Lock()
_MANUAL_WORDS = re.compile(r"manual|user[\s_-]?guide|instruction|quick[\s_-]?start", re.I)

_MANUFACTURER_DOMAINS: dict[str, tuple[str, ...]] = {
    "amd": ("amd.com",), "intel": ("intel.com",), "nvidia": ("nvidia.com",),
    "asus": ("asus.com",), "msi": ("msi.com",), "gigabyte": ("gigabyte.com",),
    "asrock": ("asrock.com",), "corsair": ("corsair.com",), "kingston": ("kingston.com",),
    "g.skill": ("gskill.com",), "gskill": ("gskill.com",), "crucial": ("crucial.com",),
    "samsung": ("samsung.com",), "western digital": ("westerndigital.com", "wd.com"),
    "wd": ("westerndigital.com", "wd.com"), "seagate": ("seagate.com",),
    "noctua": ("noctua.at", "noctua.com"), "thermalright": ("thermalright.com",),
    "arctic": ("arctic.de",), "be quiet": ("bequiet.com",), "lian li": ("lian-li.com",),
    "fractal design": ("fractal-design.com",), "nzxt": ("nzxt.com",), "hyte": ("hyte.com",),
    "phanteks": ("phanteks.com",), "cooler master": ("coolermaster.com",),
    "deepcool": ("deepcool.com",), "adata": ("adata.com",), "teamgroup": ("teamgroupinc.com",),
    "pny": ("pny.com",), "sapphire": ("sapphiretech.com",), "zotac": ("zotac.com",),
    "evga": ("evga.com",), "palit": ("palit.com",), "gainward": ("gainward.com",),
    "inno3d": ("inno3d.com",), "patriot": ("patriotmemory.com",),
}


def _raw_identity(listing: Listing) -> dict[str, Any]:
    raw = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
    props = raw.get("product_properties") if isinstance(raw.get("product_properties"), dict) else {}
    identity = raw.get("identity") if isinstance(raw.get("identity"), dict) else {}

    def first(*keys: str) -> Any:
        for source in (identity, raw, props):
            for key in keys:
                value = source.get(key)
                if isinstance(value, (str, int)) and str(value).strip():
                    return str(value).strip()
        return None

    manufacturer = first("manufacturer", "brand", "Manufacturer", "Brand")
    if not manufacturer:
        title = listing.title.casefold()
        manufacturer = next((name for name in sorted(_MANUFACTURER_DOMAINS, key=len, reverse=True)
                             if re.search(rf"\b{re.escape(name)}\b", title)), None)
    model = first("model", "model_number", "modelNumber", "Model", "Model Number")
    mpn = first("mpn", "manufacturer_part_number", "manufacturerPartNumber", "part_number", "sku", "MPN", "Part Number")
    gtin = first("gtin", "GTIN", "upc", "UPC", "ean", "EAN")
    key = mpn if len(normalize_manual_key(mpn or "")) >= 8 else model if len(normalize_manual_key(model or "")) >= 8 else listing.title
    return {
        "manufacturer": manufacturer,
        "model": model,
        "model_number": first("model_number", "modelNumber", "Model Number") or model,
        "mpn": mpn,
        "manufacturer_part_number": mpn,
        "gtin": gtin,
        "component_name": listing.title,
        "component_key": key,
    }


def _domains_for(manufacturer: str | None) -> tuple[str, ...]:
    if not manufacturer:
        return ()
    name = re.sub(r"\s+", " ", manufacturer.casefold()).strip()
    if name in _MANUFACTURER_DOMAINS:
        return _MANUFACTURER_DOMAINS[name]
    for key in sorted(_MANUFACTURER_DOMAINS, key=len, reverse=True):
        if key in name:
            return _MANUFACTURER_DOMAINS[key]
    return ()


def _is_official(url: str, domains: tuple[str, ...]) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold().rstrip(".")
        return parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in domains)
    except ValueError:
        return False


def _component_match(text: str, identity: dict[str, Any]) -> bool:
    haystack = normalize_manual_key(text)
    strong_ids = [identity.get("mpn"), identity.get("model_number")]
    for identifier in strong_ids:
        normalized = normalize_manual_key(str(identifier or ""))
        if len(normalized) >= 5 and normalized in haystack:
            return True
    model = normalize_manual_key(str(identity.get("model") or ""))
    return len(model) >= 7 and model in haystack


async def _get_same_domain(client: httpx.AsyncClient, url: str, domains: tuple[str, ...]) -> httpx.Response | None:
    current = url
    for _ in range(5):
        if not _is_official(current, domains):
            return None
        async with client.stream("GET", current, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    return None
                current = urljoin(current, location)
                continue
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                payload.extend(chunk)
                if len(payload) > _MAX_PDF_BYTES:
                    return None
            return httpx.Response(response.status_code, headers=response.headers,
                                  content=bytes(payload), request=response.request)
    return None


async def _candidate_pdf(client: httpx.AsyncClient, result: dict[str, str], identity: dict[str, Any], domains: tuple[str, ...]) -> tuple[bytes, str] | None:
    source_url = result["source_url"]
    title = result.get("title", "")
    if not _is_official(source_url, domains) or not _component_match(title + " " + source_url, identity):
        return None
    response = await _get_same_domain(client, source_url, domains)
    if not response or response.status_code >= 400:
        return None
    content_type = response.headers.get("content-type", "").casefold()
    if response.content.startswith(b"%PDF-") or "application/pdf" in content_type or source_url.casefold().endswith(".pdf"):
        pdf = response.content
        if pdf.startswith(b"%PDF-") and 8 <= len(pdf) <= _MAX_PDF_BYTES and _MANUAL_WORDS.search(title + " " + source_url):
            return pdf, source_url
        return None
    if "html" not in content_type and not response.text.lstrip().startswith("<"):
        return None
    soup = BeautifulSoup(response.text[:2_000_000], "html.parser")
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if not _component_match(page_title + " " + response.url.path, identity):
        return None
    candidates = []
    for anchor in soup.select("a[href]"):
        href = urljoin(str(response.url), str(anchor.get("href") or ""))
        label = anchor.get_text(" ", strip=True)
        if _is_official(href, domains) and _MANUAL_WORDS.search(label + " " + href):
            candidates.append((label, href))
    for label, pdf_url in candidates[:8]:
        pdf_response = await _get_same_domain(client, pdf_url, domains)
        if not pdf_response or pdf_response.status_code >= 400:
            continue
        pdf = pdf_response.content
        if pdf.startswith(b"%PDF-") and 8 <= len(pdf) <= _MAX_PDF_BYTES:
            return pdf, str(pdf_response.url)
    return None


def _load_state() -> dict[str, dict[str, str]]:
    try:
        value = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, dict[str, str]]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = _STATE_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(_STATE_PATH)


async def discover_playbook_component_manuals(db: AsyncSession, *, batch_size: int = 3) -> dict[str, Any]:
    """Fetch a bounded batch; recurring runs discover newly added Playbook parts."""
    async with _LOCK:
        rows = (await db.execute(
            select(Listing).join(CatalogueVariant, CatalogueVariant.listing_id == Listing.id)
            .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
            .join(Playbook, Playbook.id == PlaybookSlot.playbook_id)
            .where(
                Playbook.status == "active", CatalogueVariant.status == "active",
                CatalogueVariant.curated_for_builds.is_(True), Listing.status == "active",
                PlaybookSlot.slot_type.not_in(("os", "os_secondary")),
            ).order_by(Listing.id)
        )).scalars().unique().all()
        manuals = (await db.execute(select(ComponentManual))).scalars().all()
        # Release the catalogue read transaction before slow network work.
        await db.commit()
        state = _load_state()
        now = datetime.utcnow()
        existing = {normalize_manual_key(item.component_key) for item in manuals}
        checked_keys: set[str] = set()
        scanned = attempted = downloaded = deferred = 0
        search_unavailable = False
        not_found: list[str] = []

        async with httpx.AsyncClient(
            headers={"User-Agent": "FlipFlop-ManualLibrary/1.0", "Accept-Language": "en-GB,en;q=0.8"},
            timeout=httpx.Timeout(20.0, connect=6.0), follow_redirects=False,
        ) as client:
            for listing in rows:
                identity = _raw_identity(listing)
                component_key = normalize_manual_key(str(identity.get("component_key") or ""))
                if len(component_key) < 8 or component_key in checked_keys:
                    continue
                checked_keys.add(component_key)
                if component_key in existing or matching_manuals([identity], manuals):
                    continue
                state_key = hashlib.sha256(component_key.encode()).hexdigest()
                previous = state.get(state_key, {})
                if previous.get("status") in {"not_found", "retry"} and previous.get("retry_after", "") > now.isoformat():
                    deferred += 1
                    continue
                scanned += 1
                if attempted >= max(1, min(batch_size, 50)):
                    break
                attempted += 1
                domains = _domains_for(identity.get("manufacturer"))
                if not domains:
                    state[state_key] = {"status": "not_found", "reason": "manufacturer_domain_unknown",
                                        "component": listing.title, "retry_after": (now + timedelta(days=_RETRY_DAYS)).isoformat()}
                    not_found.append(listing.title)
                    continue
                label = " ".join(str(value) for value in (identity.get("manufacturer"), identity.get("mpn") or identity.get("model_number") or identity.get("model") or listing.title, "user manual") if value)[:240]
                try:
                    suggestions = await discover_component_sources(label, "manual", publisher_domains=domains, client=client)
                    stored = None
                    for suggestion in suggestions:
                        stored = await _candidate_pdf(client, suggestion, identity, domains)
                        if stored:
                            break
                    if not stored:
                        state[state_key] = {"status": "not_found", "reason": "no_exact_official_pdf",
                                            "component": listing.title, "retry_after": (now + timedelta(days=_RETRY_DAYS)).isoformat()}
                        not_found.append(listing.title)
                        continue
                    pdf, source_url = stored
                    digest = hashlib.sha256(pdf).hexdigest()
                    _MANUAL_ROOT.mkdir(parents=True, exist_ok=True)
                    path = _MANUAL_ROOT / f"{digest}.pdf"
                    if not path.exists():
                        temporary = path.with_suffix(".pdf.tmp")
                        temporary.write_bytes(pdf)
                        temporary.replace(path)
                    normalized_name = normalize_manual_key(str(identity["component_key"]))
                    item = ComponentManual(
                        component_key=normalized_name,
                        component_name=listing.title[:300],
                        source_url=source_url[:1000],
                        storage_key=f"manual-library/{digest}.pdf",
                        filename=Path(urlsplit(source_url).path).name[:255] or "user-manual.pdf",
                        sha256=digest,
                        size_bytes=len(pdf),
                        is_active=True,
                    )
                    db.add(item)
                    await db.commit()
                    manuals.append(item)
                    existing.add(normalized_name)
                    downloaded += 1
                    state[state_key] = {"status": "downloaded", "component": listing.title,
                                        "manual_id": str(item.id), "checked_at": now.isoformat()}
                except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                    rate_limited = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {403, 429}
                    state[state_key] = {
                        "status": "retry" if rate_limited else "not_found",
                        "reason": f"search_http_{exc.response.status_code}" if rate_limited else type(exc).__name__,
                        "component": listing.title,
                        "retry_after": (now + (timedelta(hours=6) if rate_limited else timedelta(days=_RETRY_DAYS))).isoformat(),
                    }
                    if not rate_limited:
                        not_found.append(listing.title)
                    else:
                        search_unavailable = True
                        break
        _save_state(state)
        return {"scanned": scanned, "attempted": attempted, "downloaded": downloaded,
                "deferred": deferred, "not_found": not_found, "batch_limit": batch_size,
                "search_unavailable": search_unavailable}
