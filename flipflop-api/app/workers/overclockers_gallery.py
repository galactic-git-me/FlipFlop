"""Fetch Overclockers product galleries, with matching Amazon fallback."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlparse

import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.case import Case
from app.services.browser_pool import managed_playwright
from app.services.case_product_key import case_product_key
from app.services.proxy import playwright_proxy_config

log = structlog.get_logger(__name__)
_RETRY_AFTER = timedelta(minutes=30)
_CACHE_VALIDITY = timedelta(days=30)
_GALLERY_CACHE_VERSION = 2


def _gallery_cache_is_fresh(product_stage: dict, now: datetime | None = None) -> bool:
    """Keep successful retailer galleries for a month, including legacy captures."""
    images = product_stage.get("overclockers_gallery")
    if not isinstance(images, list) or not images or product_stage.get("overclockers_gallery_cache_version") != _GALLERY_CACHE_VERSION:
        return False
    timestamp = product_stage.get("overclockers_gallery_cached_at") or product_stage.get("overclockers_gallery_attempted_at")
    try:
        captured_at = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return False
    return captured_at > (now or datetime.utcnow()) - _CACHE_VALIDITY


async def _collect_gallery(context, product_url: str, retailer: str) -> list[str]:
    page = await context.new_page()
    try:
        await page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
        gallery_selector = "img.zoom-image" if retailer == "overclockers" else "img"
        try:
            await page.wait_for_function(
                "selector => document.querySelectorAll(selector).length > 1",
                gallery_selector,
                timeout=12000,
            )
        except Exception:
            pass
        # Scroll in increments so lazy-loaded gallery images are all requested.
        for fraction in (0.35, 0.7, 1):
            await page.evaluate("fraction => window.scrollTo(0, document.body.scrollHeight * fraction)", fraction)
            await asyncio.sleep(0.4)
        return await page.evaluate(r"""(retailer) => {
          // OcUK's main product carousel uses zoom-image; the thumbnail strip
          // and related-product carousels use separate Swiper wrappers.
          const mainCarousel = retailer === 'overclockers'
            ? [...document.querySelectorAll('.swiper-wrapper img.zoom-image')]
            : [];
          const roots = [...document.querySelectorAll(
            '[class*=gallery], [id*=gallery], [data-gallery], [class*=product-image], [class*=product__media], #altImages, #main-image-container'
          )];
          const nodes = roots.flatMap(root => [...root.querySelectorAll('img')]);
          const images = mainCarousel.length ? mainCarousel : (nodes.length ? nodes : [...document.querySelectorAll('img')]);
          const values = [];
          for (const img of images) {
            const srcsetCandidates = (img.getAttribute('srcset') || '')
              .split(',')
              .map(candidate => {
                const match = candidate.trim().match(/^(\S+)\s+(\d+)w$/);
                return match ? { url: match[1], width: Number(match[2]) } : null;
              })
              .filter(Boolean)
              .sort((a, b) => b.width - a.width);
            const raw = srcsetCandidates[0]?.url || img.currentSrc || img.src || img.dataset.src || img.dataset.lazySrc || img.dataset.original;
            if (!raw) continue;
            let url;
            try { url = new URL(raw, location.href); } catch { continue; }
            const host = url.hostname.toLowerCase();
            const retailerImage = retailer === 'amazon'
              ? /(^|[.])amazon[.]co[.]uk$/.test(host) || /(^|[.])media-amazon[.]com$/.test(host)
              : /(^|[.])overclockers[.]co[.]uk$/.test(host);
            if (!/^https?:$/.test(url.protocol) || !retailerImage) continue;
            if (/logo|icon|sprite|badge|payment|trustpilot/i.test(url.href)) continue;
            if (!/[.](jpe?g|png|webp)(?:$|[?#])/i.test(url.href)) continue;
            values.push(url.href);
          }
          return [...new Set(values)];
        }""", retailer)
    finally:
        await page.close()


async def capture_case_gallery(case_id: int) -> dict:
    """Capture one case gallery on demand and persist it for the review UI."""
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
        if not case:
            return {"ok": False, "detail": "Case not found"}
        product_stage = (((case.sourcing_3d_evidence or {}).get("stages") or {}).get("product_images") or {})
        if _gallery_cache_is_fresh(product_stage, now):
            return {"ok": True, "count": len(product_stage["overclockers_gallery"]), "cached": True}
        offers = (await db.execute(select(Case).where(Case.source_site.ilike("%overclockers%")))).scalars().all()
        key = case_product_key(case.name, case.brand, case.model)
        urls = list(dict.fromkeys(
            offer.source_url for offer in offers
            if offer.source_url and case_product_key(offer.name, offer.brand, offer.model) == key
            and urlparse(offer.source_url).hostname in {"overclockers.co.uk", "www.overclockers.co.uk"}
        ))
    if not urls:
        await _save_gallery_capture(case_id, [], "not_found")
        return {"ok": True, "count": 0}

    images: list[str] = []
    try:
        async with managed_playwright(engine="patchright") as p:
            browser = await p.chromium.launch(headless=True, proxy=playwright_proxy_config())
            try:
                context = await browser.new_context(viewport={"width": 1366, "height": 768}, locale="en-GB", timezone_id="Europe/London")
                try:
                    for url in urls:
                        try:
                            for image in await _collect_gallery(context, url, "overclockers"):
                                if image not in images:
                                    images.append(image)
                        except Exception as exc:
                            log.info("overclockers_gallery.on_demand_offer_unavailable", case_id=case_id, error=str(exc))
                finally:
                    await context.close()
            finally:
                await browser.close()
    except Exception as exc:
        log.warning("overclockers_gallery.on_demand_capture_failed", case_id=case_id, error=str(exc))
        await _save_gallery_capture(case_id, [], "retry_pending")
        return {"ok": True, "count": 0, "status": "retry_pending"}

    await _save_gallery_capture(case_id, images, "found" if images else "not_found")
    return {"ok": True, "count": len(images)}


async def _save_gallery_capture(case_id: int, images: list[str], status: str) -> None:
    attempted_at = datetime.utcnow().isoformat()
    async with AsyncSessionLocal() as db:
        case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
        if not case:
            return
        evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
        stages = dict(evidence.get("stages") or {})
        product_stage = dict(stages.get("product_images") or {})
        if images:
            product_stage["overclockers_gallery"] = images
            product_stage["overclockers_gallery_cached_at"] = attempted_at
            product_stage["overclockers_gallery_cache_version"] = _GALLERY_CACHE_VERSION
        product_stage["overclockers_gallery_attempted_at"] = attempted_at
        product_stage["overclockers_gallery_status"] = status
        stages["product_images"] = product_stage
        evidence["stages"] = stages
        case.sourcing_3d_evidence = evidence
        await db.commit()


async def run_overclockers_gallery_sourcing() -> dict:
    """Fetch galleries for every listed Overclockers case and refresh old captures."""
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        cases = (await db.execute(
            select(Case)
            .where(Case.source_site.ilike("%overclockers%"), Case.source_url.is_not(None))
            .order_by(Case.created_at.desc())
        )).scalars().all()
        todo = []
        todo_keys: set[str] = set()
        for case in cases:
            product_stage = (((case.sourcing_3d_evidence or {}).get("stages") or {}).get("product_images") or {})
            attempted = product_stage.get("overclockers_gallery_attempted_at")
            try:
                if _gallery_cache_is_fresh(product_stage, now):
                    continue
                if not product_stage.get("overclockers_gallery") and attempted and datetime.fromisoformat(attempted) > now - _RETRY_AFTER:
                    continue
            except (TypeError, ValueError):
                pass
            if urlparse(case.source_url).hostname not in {"overclockers.co.uk", "www.overclockers.co.uk"}:
                continue
            key = case_product_key(case.name, case.brand, case.model)
            if key in todo_keys:
                continue
            offers = [offer for offer in cases if case_product_key(offer.name, offer.brand, offer.model) == key]
            offers.sort(key=lambda offer: 0 if offer.id == case.id else 1)
            todo.append((case.id, [(offer.source_url, "overclockers") for offer in offers if offer.source_url]))
            todo_keys.add(key)

    if not todo:
        return {"ok": True, "queued": 0, "saved": 0}

    saved = 0
    failures: list[str] = []
    async with managed_playwright(engine="patchright") as p:
        browser = await p.chromium.launch(headless=True, proxy=playwright_proxy_config())
        try:
            context = await browser.new_context(viewport={"width": 1366, "height": 768}, locale="en-GB", timezone_id="Europe/London")
            try:
                for case_id, product_pages in todo:
                    async with AsyncSessionLocal() as db:
                        case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
                        if not case:
                            continue
                        try:
                            all_images: list[str] = []
                            gallery_sources: list[str] = []
                            for product_url, retailer in product_pages:
                                if retailer == "overclockers" and urlparse(product_url).hostname not in {"overclockers.co.uk", "www.overclockers.co.uk"}:
                                    continue
                                try:
                                    images = await _collect_gallery(context, product_url, retailer)
                                except Exception as exc:
                                    log.info("overclockers_gallery.offer_unavailable", case_id=case_id, retailer=retailer, error=str(exc))
                                    continue
                                if images:
                                    gallery_sources.append(product_url)
                                    for image in images:
                                        if image not in all_images:
                                            all_images.append(image)
                            evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
                            stages = dict(evidence.get("stages") or {})
                            product_stage = dict(stages.get("product_images") or {})
                            product_stage["overclockers_gallery_attempted_at"] = datetime.utcnow().isoformat()
                            if all_images:
                                product_stage["overclockers_gallery"] = all_images
                                product_stage["overclockers_gallery_cached_at"] = datetime.utcnow().isoformat()
                                product_stage["overclockers_gallery_cache_version"] = _GALLERY_CACHE_VERSION
                                product_stage["gallery_sources"] = gallery_sources
                                product_stage["overclockers_gallery_status"] = "found"
                                saved += 1
                            else:
                                product_stage["overclockers_gallery_status"] = "retry_pending"
                            stages["product_images"] = product_stage
                            evidence["stages"] = stages
                            case.sourcing_3d_evidence = evidence
                            await db.commit()
                        except Exception as exc:
                            failures.append(f"{case_id}: {type(exc).__name__}")
                            evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
                            stages = dict(evidence.get("stages") or {})
                            product_stage = dict(stages.get("product_images") or {})
                            product_stage["overclockers_gallery_attempted_at"] = datetime.utcnow().isoformat()
                            product_stage["overclockers_gallery_status"] = "retry_pending"
                            stages["product_images"] = product_stage
                            evidence["stages"] = stages
                            case.sourcing_3d_evidence = evidence
                            await db.commit()
                            log.warning("overclockers_gallery.case_failed", case_id=case_id, error=str(exc))
            finally:
                await context.close()
        finally:
            await browser.close()

    result = {"ok": not failures, "queued": len(todo), "saved": saved, "failures": failures[:5]}
    log.info("overclockers_gallery.complete", **result)
    return result
