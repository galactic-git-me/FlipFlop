"""Fetch and persist Overclockers product galleries for newly ingested cases."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlparse

import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.case import Case
from app.services.browser_pool import BACKGROUND_HEADED_ARGS, managed_playwright
from app.services.proxy import playwright_proxy_config

log = structlog.get_logger(__name__)
_BATCH_SIZE = 8
_RETRY_AFTER = timedelta(minutes=30)


async def _collect_gallery(context, case: Case) -> list[str]:
    page = await context.new_page()
    try:
        await page.goto(case.source_url, wait_until="domcontentloaded", timeout=60000)
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
            '[class*=gallery], [id*=gallery], [data-gallery], [class*=product-image], [class*=product__media]'
          )];
          const nodes = roots.flatMap(root => [...root.querySelectorAll('img')]);
          const images = nodes.length ? nodes : [...document.querySelectorAll('img')];
          const values = [];
          for (const img of images) {
            const raw = img.currentSrc || img.src || img.dataset.src || img.dataset.lazySrc || img.dataset.original;
            if (!raw) continue;
            let url;
            try { url = new URL(raw, location.href); } catch { continue; }
            if (!/^https?:$/.test(url.protocol) || !/overclockers[.]co[.]uk$/i.test(url.hostname)) continue;
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
            .where(Case.source_site.ilike("%overclockers%"), Case.source_url.is_not(None))
            .order_by(Case.created_at.desc())
            .limit(300)
        )).scalars().all()
        todo = []
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
            if urlparse(case.source_url).hostname not in {"overclockers.co.uk", "www.overclockers.co.uk"}:
                continue
            todo.append(case.id)
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
                for case_id in todo:
                    async with AsyncSessionLocal() as db:
                        case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
                        if not case:
                            continue
                        try:
                            images = await _collect_gallery(context, case)
                            evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
                            stages = dict(evidence.get("stages") or {})
                            product_stage = dict(stages.get("product_images") or {})
                            product_stage["overclockers_gallery_attempted_at"] = datetime.utcnow().isoformat()
                            if images:
                                product_stage["overclockers_gallery"] = images
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
