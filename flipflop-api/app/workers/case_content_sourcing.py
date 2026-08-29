"""Resumable full-queue photo and YouTube sourcing for the frozen case campaign."""
from __future__ import annotations

import asyncio
import html
import json
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup
from sqlalchemy import or_, select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.case import Case

log = structlog.get_logger(__name__)
settings = get_settings()

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
_NOISE = {"case", "computer", "gaming", "tower", "mid", "pc", "black", "white", "argb", "rgb"}


def _query(case: Case) -> str:
    structured = " ".join(part for part in (case.brand, case.model) if part)
    return structured.strip() or re.split(r"\s+[-–|]\s+", case.name, maxsplit=1)[0][:120]


def _identity_tokens(case: Case) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", _query(case).lower())
    useful = [token for token in tokens if token not in _NOISE and len(token) > 1]
    return useful[:8] or tokens[:4]


def _looks_exact(case: Case, text: str) -> bool:
    haystack = re.sub(r"[^a-z0-9]+", " ", text.lower())
    tokens = _identity_tokens(case)
    if not tokens:
        return False
    distinctive = [token for token in tokens if any(char.isdigit() for char in token)]
    required = distinctive or tokens[:2]
    return all(re.search(rf"\b{re.escape(token)}\b", haystack) for token in required)


def _unwrap_ddg_url(url: str) -> str:
    parsed = urlparse(urljoin("https://html.duckduckgo.com", url))
    if "duckduckgo.com" in parsed.netloc:
        encoded = parse_qs(parsed.query).get("uddg", [""])[0]
        if encoded:
            return unquote(encoded)
    return url


def _search_result_urls(markup: str) -> list[str]:
    soup = BeautifulSoup(markup, "html.parser")
    urls: list[str] = []
    for anchor in soup.select("a.result__a, a[data-testid='result-title-a']"):
        target = _unwrap_ddg_url(str(anchor.get("href") or ""))
        if target.startswith("http") and target not in urls:
            urls.append(target)
    return urls


def _page_images(page_url: str, markup: str) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(markup, "html.parser")
    candidates: list[tuple[str, str]] = []
    for selector, attribute in (
        ("meta[property='og:image']", "content"),
        ("meta[name='twitter:image']", "content"),
        ("link[rel='image_src']", "href"),
    ):
        for node in soup.select(selector):
            candidates.append((str(node.get(attribute) or ""), str(node.get("alt") or "")))
    for node in soup.select("img[src], img[data-src], img[data-lazy-src]"):
        src = node.get("src") or node.get("data-src") or node.get("data-lazy-src") or ""
        candidates.append((str(src), str(node.get("alt") or "")))

    found: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for raw_url, label in candidates:
        url = html.unescape(urljoin(page_url, raw_url.strip()))
        clean_path = urlparse(url).path.lower()
        if not url.startswith("http") or url in seen or not clean_path.endswith(_IMAGE_EXTENSIONS):
            continue
        if any(word in url.lower() for word in ("logo", "icon", "sprite", "avatar", "badge")):
            continue
        seen.add(url)
        found.append({"url": url, "source": urlparse(page_url).netloc, "source_page": page_url, "label": label[:160] or None})
    return found[:16]


def _youtube_candidates(markup: str, case: Case) -> list[dict[str, str]]:
    decoded = html.unescape(markup)
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r'"videoId":"([\w-]{11})".{0,900}?"title":\{"runs":\[\{"text":"(.*?)"', re.DOTALL)
    for video_id, raw_title in pattern.findall(decoded):
        title = bytes(raw_title, "utf-8").decode("unicode_escape", errors="ignore")
        if video_id in seen or not _looks_exact(case, title):
            continue
        seen.add(video_id)
        results.append({"url": f"https://www.youtube.com/watch?v={video_id}", "title": title[:200]})
        if len(results) >= 6:
            break
    return results


def _stage(case: Case, name: str) -> dict:
    return dict((((case.sourcing_3d_evidence or {}).get("stages") or {}).get(name)) or {})


def _needs_stage(case: Case, name: str, now: datetime) -> bool:
    stage = _stage(case, name)
    status = stage.get("status", "not_started")
    if status in {"not_started", "not_found"}:
        return True
    if status != "searching":
        return False
    try:
        return datetime.fromisoformat(stage.get("updated_at", "")) < now - timedelta(hours=2)
    except (TypeError, ValueError):
        return True


def _save_stage(case: Case, name: str, status: str, attempt: dict, **fields) -> None:
    now = datetime.utcnow().isoformat()
    evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
    stages = dict(evidence.get("stages") or {})
    stage = dict(stages.get(name) or {})
    attempts = list(stage.get("attempts") or [])
    attempts.append({**attempt, "recorded_at": now})
    stage.update({"status": status, "attempts": attempts[-20:], "updated_at": now, **fields})
    stages[name] = stage
    evidence.update({"schema_version": 1, "stages": stages})
    case.sourcing_3d_evidence = evidence
    case.status = "sourcing"


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    if "text/html" not in response.headers.get("content-type", "text/html"):
        return ""
    return response.text[:3_000_000]


async def _source_images(client: httpx.AsyncClient, case: Case) -> tuple[list[dict], list[str]]:
    pages: list[str] = [case.source_url] if case.source_url else []
    errors: list[str] = []
    try:
        search_html = await _fetch(client, f"https://html.duckduckgo.com/html/?q={quote_plus(_query(case) + ' PC case product')}")
        pages.extend(_search_result_urls(search_html)[:5])
    except Exception as exc:
        errors.append(f"search: {type(exc).__name__}: {exc}")
    images: list[dict] = []
    if case.image_url:
        images.append({"url": case.image_url, "source": case.source_site, "source_page": case.source_url, "label": "Catalogue image"})
    for page_url in dict.fromkeys(url for url in pages if url):
        try:
            markup = await _fetch(client, page_url)
            title = BeautifulSoup(markup, "html.parser").title
            trusted_source = page_url == case.source_url
            if trusted_source or _looks_exact(case, title.get_text(" ", strip=True) if title else markup[:1000]):
                images.extend(_page_images(page_url, markup))
        except Exception as exc:
            errors.append(f"{page_url}: {type(exc).__name__}")
        await asyncio.sleep(settings.case_content_request_delay_seconds)
    unique = {item["url"]: item for item in images}
    return list(unique.values())[:24], errors[:8]


async def _source_youtube(client: httpx.AsyncClient, case: Case) -> tuple[list[dict], list[str]]:
    url = f"https://www.youtube.com/results?search_query={quote_plus(_query(case) + ' PC case review')}&hl=en-GB"
    try:
        return _youtube_candidates(await _fetch(client, url), case), []
    except Exception as exc:
        return [], [f"{type(exc).__name__}: {exc}"]


async def _process_case(case_id: int, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore, AsyncSessionLocal() as db:
        case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one()
        now = datetime.utcnow()
        do_images = _needs_stage(case, "product_images", now)
        do_youtube = _needs_stage(case, "youtube_video", now)
        if not do_images and not do_youtube:
            return {"case_id": case_id, "skipped": True}
        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=20) as client:
            if do_images:
                images, errors = await _source_images(client, case)
                existing = {item.get("url"): item for item in _stage(case, "product_images").get("candidate_images", []) if isinstance(item, dict)}
                existing.update({item["url"]: item for item in images})
                _save_stage(case, "product_images", "found" if existing else "not_found", {
                    "worker": "full_queue", "query": _query(case), "candidate_count": len(images), "errors": errors,
                }, candidate_images=list(existing.values()), selection_required=bool(existing))
                await db.commit()
            if do_youtube:
                videos, errors = await _source_youtube(client, case)
                _save_stage(case, "youtube_video", "found" if videos else "not_found", {
                    "worker": "full_queue", "query": _query(case), "candidate_videos": videos, "errors": errors,
                }, candidate_videos=videos, selection_required=bool(videos))
                await db.commit()
        return {"case_id": case_id, "images": len(images) if do_images else None, "videos": len(videos) if do_youtube else None}


async def run_case_content_sourcing() -> dict:
    """Process every unfinished priority case, bounded only by the configured batch size."""
    if not settings.case_content_sourcing_enabled:
        return {"ok": True, "disabled": True}
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Case.id).where(
                Case.priority_3d_rank.is_not(None),
                or_(Case.name.is_(None), ~Case.name.ilike("%raspberry pi%")),
            ).order_by(Case.priority_3d_rank).limit(settings.case_content_sourcing_batch_size)
        )).scalars().all()
    semaphore = asyncio.Semaphore(max(1, settings.case_content_sourcing_concurrency))
    results = await asyncio.gather(*(_process_case(case_id, semaphore) for case_id in rows), return_exceptions=True)
    failures = [str(result) for result in results if isinstance(result, Exception)]
    processed = [result for result in results if isinstance(result, dict) and not result.get("skipped")]
    summary = {"ok": not failures, "queued": len(rows), "processed": len(processed), "failed": len(failures), "failures": failures[:5]}
    log.info("case_content_sourcing.complete", **summary)
    return summary
