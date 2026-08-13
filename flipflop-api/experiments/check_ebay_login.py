"""Startup-script helper — checks whether the manually-authenticated eBay CDP
browser (see experiments/ebay_manual_login_scrape.py and the README note in
ebay_sold_scrape_experiment.py) is still signed in, without touching the
login flow itself (no automation ever touches the CAPTCHA/sign-in page here
unless not signed in, in which case it just navigates to the sign-in URL for
convenience — never fills in credentials).

Prints exactly one of these as the LAST line of stdout, for the calling
PowerShell script to parse:
    SIGNED_IN
    NOT_SIGNED_IN
    NOT_RUNNING       (nothing listening on the CDP port at all)

Usage:
    .venv\\Scripts\\python.exe -m experiments.check_ebay_login
"""
from __future__ import annotations

import asyncio

_CDP_URL = "http://localhost:9222"


async def main() -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("playwright not installed")
        print("NOT_RUNNING")
        return

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(_CDP_URL, timeout=5000)
        except Exception as exc:
            print(f"CDP connect failed: {exc}")
            print("NOT_RUNNING")
            return

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(
                "https://www.ebay.co.uk/myb/WatchList", wait_until="domcontentloaded", timeout=15000
            )
            signed_in = "signin" not in page.url.lower()
        except Exception as exc:
            print(f"Check navigation failed: {exc}")
            signed_in = False

        if signed_in:
            print("eBay CDP session is signed in.")
            await page.close()
            print("SIGNED_IN")
        else:
            print("eBay CDP session is NOT signed in — navigating to sign-in page for you.")
            try:
                await page.goto("https://signin.ebay.co.uk/ws/eBayISAPI.dll?SignIn&sgfl=gh&ru=https%3A%2F%2Fwww.ebay.co.uk%2F", wait_until="domcontentloaded", timeout=15000)
                await page.bring_to_front()
            except Exception:
                pass
            print("NOT_SIGNED_IN")


if __name__ == "__main__":
    asyncio.run(main())
