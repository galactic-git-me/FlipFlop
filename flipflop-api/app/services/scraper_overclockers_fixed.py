import asyncio
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import structlog

log = structlog.get_logger(__name__)
ua = UserAgent()

async def scrape_overclockers_cases_httpx(min_price: float = 10.0, max_price: float = 500.0) -> list:
    """Scrape Overclockers using direct GET requests to ?page=N URLs with proper session"""
    results = []
    seen = set()

    headers = {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.9',
        'Referer': 'https://www.overclockers.co.uk/',
        'Cookie': 'PHPSESSID=test; path=/'
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for page_num in range(1, 12):  # Pages 1-11
            url = f"https://www.overclockers.co.uk/cases-and-modding/pc-cases/pc-cases-by-brand?page={page_num}"

            try:
                print(f"Fetching page {page_num}...")
                resp = await client.get(url, headers=headers)

                if resp.status_code != 200:
                    print(f"  Status {resp.status_code} - stopping")
                    break

                soup = BeautifulSoup(resp.text, "lxml")

                # Find all product links
                product_links = soup.select('a[href*="/product/"]')
                print(f"  Found {len(product_links)} product links")

                if not product_links:
                    print(f"  No products on page {page_num} - stopping")
                    break

                for link in product_links:
                    try:
                        href = link.get("href", "").strip()
                        if not href.startswith("http"):
                            if href.startswith("/"):
                                href = "https://www.overclockers.co.uk" + href
                            else:
                                continue

                        key = href.split("?")[0]
                        if key in seen:
                            continue
                        seen.add(key)

                        # Find price in card
                        card = link.find_parent("li") or link.find_parent("div")
                        price_text = card.get_text() if card else ""
                        price_match = __import__('re').search(r"£\s*([\d,]+\.?\d*)", price_text)

                        if not price_match:
                            continue

                        try:
                            price = float(price_match.group(1).replace(",", ""))
                        except ValueError:
                            continue

                        if price < min_price or price > max_price:
                            continue

                        title = link.get_text(strip=True)[:250]
                        if not title or len(title) < 5:
                            continue

                        results.append({
                            "title": title,
                            "price": price,
                            "url": href,
                            "source": "Overclockers"
                        })

                    except Exception as e:
                        continue

            except Exception as e:
                print(f"  Error on page {page_num}: {e}")
                break

    return results

if __name__ == "__main__":
    async def main():
        results = await scrape_overclockers_cases_httpx()
        print(f"\n✓ Found {len(results)} total cases")
        for i, r in enumerate(results[:10], 1):
            print(f"  {i}. {r['title'][:50]} - £{r['price']}")

    asyncio.run(main())
