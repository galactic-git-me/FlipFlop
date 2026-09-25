"""Fetch Overclockers product galleries, with matching Amazon fallback."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlparse

import structlog
from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.case import Case
from app.services.browser_pool import BACKGROUND_HEADED_ARGS, managed_playwright
from app.services.case_product_key import case_product_key
from app.services.proxy import playwright_proxy_config

log = structlog.get_logger(__name__)
_BATCH_SIZE = 8
_RETRY_AFTER = timedelta(minutes=30)


async def _collect_gallery(context, product_url: str, retailer: str) -> list[str]:
    page = await context.new_page()
    try:
        await page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)
        try:
            await page.wait_for_selector("img", timeout=12000)
        except Exception:
            pass
        # Let lazy-loaded gallery thumbnails populate before reading the page.
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
        return await page.evaluate("""() => {
          const roots = [...document.querySelectorAll(
            '[class*=gallery], [id*=gallery], [data-gallery], [class*=product-image], [class*=product__media], #altImages, #main-image-container'
          )];
          const nodes = roots.flatMap(root => [...root.querySelectorAll('img')]);
          const images = nodes.length ? nodes : [...document.querySelectorAll('img')];
          const values = [];
          for (const img of images) {
            const raw = img.currentSrc || img.src || img.dataset.src || img.dataset.lazySrc || img.dataset.original;
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
          return [...new Set(values)].slice(0, 80);
        }""")
    finally:
        await page.close()


async def run_overclockers_gallery_sourcing() -> dict:
    """Fetch a small batch of unprocessed product galleries on each scheduler tick."""
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        cases = (await db.execute(
            select(Case)
            .where(or_(Case.source_site.ilike("%overclockers%"), Case.source_site == "Amazon"), Case.source_url.is_not(None))
            .order_by(Case.created_at.desc())
            .limit(800)
        )).scalars().all()
        todo = []
        todo_keys: set[str] = set()
        for case in cases:
            product_stage = (((case.sourcing_3d_evidence or {}).get("stages") or {}).get("product_images") or {})
            if product_stage.get("overclockers_gallery"):
                continue
            attempted = product_stage.get("overclockers_gallery_attempted_at")
            try:
                if attempted and datetime.fromisoformat(attempted) > now - _RETRY_AFTER:
                    continue
            except (TypeError, ValueError):
                pass
            if urlparse(case.source_url).hostname not in {"overclockers.co.uk", "www.overclockers.co.uk", "amazon.co.uk", "www.amazon.co.uk"}:
                continue
            key = case_product_key(case.name, case.brand, case.model)
            if key in todo_keys:
                continue
            offers = [offer for offer in cases if case_product_key(offer.name, offer.brand, offer.model) == key]
            offers.sort(key=lambda offer: 0 if "overclockers" in offer.source_site.lower() else 1)
            todo.append((case.id, [(offer.source_url, "amazon" if offer.source_site.lower() == "amazon" else "overclockers") for offer in offers if offer.source_url]))
            todo_keys.add(key)
            if len(todo) >= _BATCH_SIZE:
                break

    if not todo:
        return {"ok": True, "queued": 0, "saved": 0}

    saved = 0
    failures: list[str] = []
    async with managed_playwright(engine="patchright") as p:
        browser = await p.chromium.launch(headless=False, args=BACKGROUND_HEADED_ARGS, proxy=playwright_proxy_config())
        try:
            context = await browser.new_context(viewport={"width": 1366, "height": 768}, locale="en-GB", timezone_id="Europe/London")
            try:
                for case_id, product_pages in todo:
                    async with AsyncSessionLocal() as db:
                        case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
                        if not case:
                            continue
                        try:
                            images: list[str] = []
                            gallery_source = None
                            for product_url, retailer in product_pages:
                                if retailer == "amazon" and urlparse(product_url).hostname not in {"amazon.co.uk", "www.amazon.co.uk"}:
                                    continue
                                if retailer == "overclockers" and urlparse(product_url).hostname not in {"overclockers.co.uk", "www.overclockers.co.uk"}:
                                    continue
                                try:
                                    images = await _collect_gallery(context, product_url, retailer)
                                except Exception as exc:
                                    log.info("overclockers_gallery.offer_unavailable", case_id=case_id, retailer=retailer, error=str(exc))
                                    continue
                                if images:
                                    gallery_source = retailer
                                    break
                            evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
                            stages = dict(evidence.get("stages") or {})
                            product_stage = dict(stages.get("product_images") or {})
                            product_stage["overclockers_gallery_attempted_at"] = datetime.utcnow().isoformat()
                            if images:
                                product_stage["overclockers_gallery"] = images
                                product_stage["gallery_source"] = gallery_source
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
