"""
Diagnostic test for cases scrapers.
Runs ONE search on each Playwright source and logs page title + first result.
Run with: cd pc-flipper-backend && python test_cases_scrapers.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from playwright.async_api import async_playwright

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-infobars",
    "--window-size=1366,768",
    "--lang=en-GB",
]
STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
"""

SEARCH = "rgb gaming pc case atx"


async def check_site(name: str, url: str, detect_fn):
    print(f"\n{'='*60}")
    print(f"Testing {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=STEALTH_ARGS)
        context = await browser.new_context(
            user_agent=STEALTH_UA,
            viewport={"width": 1366, "height": 768},
            locale="en-GB",
            timezone_id="Europe/London",
        )
        await context.add_init_script(STEALTH_JS)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
            title = await page.title()
            current_url = page.url
            body_text = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 300) : 'NO BODY'")
            print(f"Title: {title}")
            print(f"URL after nav: {current_url}")
            print(f"Body snippet: {body_text[:300]}")
            result = await detect_fn(page)
            print(f"Items found: {result}")
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await browser.close()


async def detect_amazon(page):
    return await page.evaluate("""() => {
        const items = document.querySelectorAll('[data-component-type="s-search-result"]');
        const links = document.querySelectorAll('h2 a');
        return {search_results: items.length, h2_links: links.length};
    }""")


async def detect_aliexpress(page):
    # Dismiss popups first
    for sel in ["button:has-text('Ship to')", ".close-btn", "[class*='close']"]:
        try:
            await page.click(sel, timeout=1500)
            await asyncio.sleep(0.3)
        except Exception:
            pass
    await asyncio.sleep(3)
    return await page.evaluate("""() => {
        const itemLinks = document.querySelectorAll("a[href*='/item/']");
        const allLinks = document.querySelectorAll("a[href]");
        return {item_links: itemLinks.length, all_links: allLinks.length, title: document.title};
    }""")


async def detect_temu(page):
    await asyncio.sleep(3)
    return await page.evaluate("""() => {
        const goodsLinks = document.querySelectorAll("a[href*='/goods']");
        const allLinks = document.querySelectorAll("a[href]");
        return {goods_links: goodsLinks.length, all_links: allLinks.length};
    }""")


async def detect_etsy(page):
    # Dismiss GDPR
    for sel in ["button:has-text('Accept')", "[data-gdpr-single-choice-accept]"]:
        try:
            await page.click(sel, timeout=2000)
            await asyncio.sleep(0.3)
        except Exception:
            pass
    await asyncio.sleep(3)
    return await page.evaluate("""() => {
        const listingLinks = document.querySelectorAll("a[href*='/listing/']");
        const allLinks = document.querySelectorAll("a[href]");
        return {listing_links: listingLinks.length, all_links: allLinks.length};
    }""")


async def main():
    q = SEARCH.replace(" ", "+")
    sites = [
        ("Amazon UK", f"https://www.amazon.co.uk/s?k={q}&i=computers", detect_amazon),
        ("AliExpress", f"https://www.aliexpress.com/wholesale?SearchText={q}&g=y&SortType=price_asc", detect_aliexpress),
        ("Temu", f"https://www.temu.com/search_result.html?search_key={q}&search_method=user", detect_temu),
        ("Etsy", f"https://www.etsy.com/uk/search?q={q}&explicit=1", detect_etsy),
    ]
    for name, url, fn in sites:
        await check_site(name, url, fn)


if __name__ == "__main__":
    asyncio.run(main())
