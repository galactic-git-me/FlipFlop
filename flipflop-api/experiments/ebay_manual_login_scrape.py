"""EXPERIMENT — not wired into production.

Opens a REAL, visible Chromium window with a persistent profile directory so
you can sign into eBay UK manually (your credentials go directly into eBay's
own page — this script never sees them). Once signed in, the same browser
context is reused to hit the sold/completed-listings search
(&LH_Sold=1&LH_Complete=1) that both direct_http() and the headless
Playwright launch in ebay_sold_scrape_experiment.py got redirected away from
into a "Sign in or Register" wall.

The profile directory persists on disk under experiments/.ebay-profile-<name>,
so once you've signed in once under a given profile name, subsequent runs
should already be authenticated (until the session cookie expires) and skip
straight to the scrape.

IMPORTANT — do not ever launch headless=True against a profile dir this
script has used. Empirically, mixing one headless request into an
authenticated session's cookie jar caused eBay's fraud detection to flag
that session and force a CAPTCHA loop on the real account. Keep each
profile strictly headed-only.

Usage:
    cd flipflop-api
    .venv\\Scripts\\python.exe -m experiments.ebay_manual_login_scrape "gaming pc i5-9600k rtx 3060" [profile-name]

profile-name defaults to "default" -- pass a different name (e.g. "alt") to
use an isolated profile/login, e.g. for a throwaway account instead of your
main one.

A visible Chrome window opens. Sign in if prompted, then leave it — the
script polls for a signed-in indicator and continues automatically once
detected (or after a 5-minute timeout).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from experiments.ebay_sold_scrape_experiment import _build_sold_url, _extract_comps

_LOGIN_POLL_TIMEOUT_S = 300
_LOGIN_POLL_INTERVAL_S = 3


def _profile_dir(name: str) -> Path:
    return Path(__file__).parent / f".ebay-profile-{name}"


async def _is_signed_in(page) -> bool:
    """#gh-ug (the old signed-out-state selector guess) doesn't exist on
    current eBay markup at all, and raw signed-in-greeting text search is
    unreliable since eBay's account nav is client-rendered. Instead: hit a
    protected account-only page and check whether eBay bounces us to signin —
    the same check eBay itself makes, so it can't drift out of sync with
    their markup."""
    try:
        await page.goto(
            "https://www.ebay.co.uk/myb/WatchList", wait_until="domcontentloaded", timeout=15000
        )
        final_url = page.url
        return "signin" not in final_url.lower()
    except Exception:
        return False


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "gaming pc i5-9600k rtx 3060"
    profile_name = sys.argv[2] if len(sys.argv) > 2 else "default"
    profile_dir = _profile_dir(profile_name)
    profile_dir.mkdir(parents=True, exist_ok=True)
    print(f"Using profile: {profile_dir}")

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--window-size=1366,900"],
            viewport={"width": 1366, "height": 900},
            locale="en-GB",
            timezone_id="Europe/London",
        )
        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto("https://www.ebay.co.uk/", wait_until="domcontentloaded", timeout=30000)

        if await _is_signed_in(page):
            print("Already signed in (persisted profile) — skipping manual login step.")
        else:
            print("Please sign into eBay in the browser window that just opened.")
            print(f"Waiting up to {_LOGIN_POLL_TIMEOUT_S}s for sign-in to complete...")
            waited = 0
            while waited < _LOGIN_POLL_TIMEOUT_S:
                if await _is_signed_in(page):
                    print("Signed in — continuing.")
                    break
                await asyncio.sleep(_LOGIN_POLL_INTERVAL_S)
                waited += _LOGIN_POLL_INTERVAL_S
            else:
                print("Timed out waiting for sign-in. Exiting without scraping.")
                await context.close()
                return

        url = _build_sold_url(query)
        print(f"\nNavigating to sold-listings search:\n  {url}")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        title = await page.title()
        print(f"Page title: {title!r}")

        html = await page.content()
        debug_path = Path(__file__).parent / "_last_sold_page.html"
        debug_path.write_text(html, encoding="utf-8")

        comps = _extract_comps(html)
        print(f"\n{len(comps)} comps extracted")
        for c in comps[:10]:
            print(f"  £{c.price:>7.2f}  {c.title[:70] or '(blank title — selector needs fixing)'}")

        if not comps:
            snippet_marker = "sign in" if "sign in" in title.lower() else None
            if snippet_marker:
                print("\nStill on a sign-in wall — login likely didn't persist for this specific search.")
            else:
                print("\nReached a results-shaped page but selectors found 0 comps — markup may have "
                      "changed (check for .s-card vs .s-item, same issue noted in "
                      "FlipFlopXtension/src/content/ebay-extractor.ts).")

        print(f"\nProfile persisted at: {profile_dir}")
        print(f"Full page HTML saved to: {debug_path}")
        print("Browser window left open — close it manually when done inspecting.")
        print("\nDo NOT run this experiment's headless variant against this same profile dir.")


if __name__ == "__main__":
    asyncio.run(main())
