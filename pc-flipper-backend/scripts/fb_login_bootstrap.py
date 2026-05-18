#!/usr/bin/env python3
"""
One-time Facebook Marketplace login bootstrap.

What it does:
1. Launches Chromium in headed mode with a persistent profile directory.
2. Opens Facebook Marketplace (UK).
3. Lets you manually log in (including 2FA if needed).
4. Saves cookies to fb_cookies.json for backend reuse.

Run:
  cd pc-flipper-backend
  . .venv/bin/activate
  python scripts/fb_login_bootstrap.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
COOKIES_PATH = ROOT / "fb_cookies.json"
PROFILE_DIR = ROOT / ".fb-profile"

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-infobars",
    "--window-size=1366,768",
    "--lang=en-GB",
]


async def main() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=STEALTH_ARGS,
            locale="en-GB",
            timezone_id="Europe/London",
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()
        await page.goto(
            "https://www.facebook.com/marketplace/london/search/?query=desktop%20pc",
            wait_until="domcontentloaded",
            timeout=45000,
        )

        print("\nManual step required:")
        print("1) Log in to Facebook in the opened browser window.")
        print("2) Complete any verification prompts.")
        print("3) Ensure Marketplace page is visible.")
        input("\nPress ENTER here when done to save session cookies... ")

        cookies = await context.cookies()
        fb_cookies = [c for c in cookies if "facebook.com" in (c.get("domain") or "")]
        COOKIES_PATH.write_text(json.dumps(fb_cookies, indent=2))

        print(f"\nSaved {len(fb_cookies)} Facebook cookies to: {COOKIES_PATH}")
        print(f"Persistent profile directory: {PROFILE_DIR}")
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())

