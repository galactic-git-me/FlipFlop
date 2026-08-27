import httpx
from bs4 import BeautifulSoup
import random
import time
import re
from datetime import datetime, timedelta

class EbayScraper:
    def __init__(self, api_credentials=None):
        self.api_credentials = api_credentials
        self.consecutive_blocks = 0
        self.circuit_breaker_until = None
        
        # Fallback settings matching your specs
        self.cooldown_minutes = 15
        self.normal_delay_range = (2, 5)
        self.block_jitter_range = (8, 25)
        
        # Sample User-Agents to simulate fake_useragent functionality
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]

    def _get_random_headers(self):
        """Generates realistic browser headers."""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    def _is_circuit_broken(self):
        """Checks if the scraper is currently in a cooldown window."""
        if self.circuit_breaker_until and datetime.now() < self.circuit_breaker_until:
            return True
        if self.circuit_breaker_until and datetime.now() >= self.circuit_breaker_until:
            # Cooldown over, reset circuit
            self.circuit_breaker_until = None
            self.consecutive_blocks = 0
        return False

    def _trigger_circuit_breaker(self):
        """Trips the circuit breaker and sets the cooldown window."""
        self.circuit_breaker_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        print(f"[-] Circuit breaker tripped! Cooldown active until {self.circuit_breaker_until.strftime('%H:%M:%S')}")

    def _check_block_detection(self, response):
        """Scans status codes and body content for anti-bot markers."""
        if response.status_code in (401, 403, 429):
            return True
            
        body_lower = response.text.lower()
        markers = ["akamai", "access denied", "captcha", "security check", "robot check"]
        for marker in markers:
            if marker in body_lower:
                return True
        return False

    def _shape_retry_term(self, term):
        """Reshapes blocked phrases to dodge exact-phrase pattern matching."""
        # Simple generic reshaping mapping example
        reshaping_rules = {
            "pc tower": "desktop tower pc",
            "gaming laptop": "laptop computer for gaming",
            "iphone": "apple iphone smartphone"
        }
        return reshaping_rules.get(term.lower(), f"buy {term}")

    def _try_ebay_api(self, term):
        """Tier 1: Primary path using official eBay Browse API (Mocked)."""
        if not self.api_credentials:
            # Simulate an authentication error / failure to trigger fallback chain
            raise httpx.HTTPStatusError("No API credentials provided", request=None, response=None)
        
        print(f"[+] Tier 1: Querying eBay Browse API for '{term}'...")
        # (Actual production OAuth logic and HTTP call would execute here)
        return {"source": "api", "results": []} 

    def _try_http_scrape(self, term):
        """Tier 2: Plain HTTP scraping fallback via HTTPX and BeautifulSoup."""
        print(f"[!] Tier 2: API failed. Falling back to HTTP scraping for '{term}'...")
        
        # Build search URL (Example using production eBay search structure)
        url = f"https://www.ebay.co.uk/sch/i.html?_nkw={term.replace(' ', '+')}"
        headers = self._get_random_headers()
        
        try:
            with httpx.Client(headers=headers, timeout=10.0) as client:
                response = client.get(url)
                
                # Check for blocks
                if self._check_block_detection(response):
                    print(f"[-] Block detected for term '{term}'")
                    return {"status": "blocked", "response": response}
                
                # Parse layout selectors if response is clean
                soup = BeautifulSoup(response.text, 'html.parser')
                items = []
                
                # Target both .s-card and .s-item wrappers matching scraper.py:912
                listings = soup.select(".s-item, .s-card")
                for listing in listings:
                    title_el = listing.select_one(".s-item__title")
                    price_el = listing.select_one(".s-item__price")
                    if title_el and price_el:
                        items.append({
                            "title": title_el.text.strip(),
                            "price": price_el.text.strip()
                        })
                
                return {"status": "success", "source": "scrape", "results": items}
                
        except httpx.RequestError as e:
            print(f"[-] Network connection error: {e}")
            return {"status": "error", "reason": str(e)}

    def execute_search(self, term, is_retry=False):
        """Manages the full execution cycle, retry states, and delays."""
        if self._is_circuit_broken():
            print(f"[~] Skipping '{term}': Circuit breaker active. Marked as 'retry later'.")
            return {"status": "skipped", "reason": "cooldown"}

        # Introduce standard padding delay before a fresh request
        if not is_retry:
            time.sleep(random.uniform(*self.normal_delay_range))

        try:
            # Always execute primary path first
            return self._try_ebay_api(term)
        except Exception:
            # Fallback path executing on API exceptions or non-200 errors
            result = self._try_http_scrape(term)
            
            if result["status"] == "success":
                self.consecutive_blocks = 0 # Clear counter on successful layout parsing
                return result
                
            if result["status"] == "blocked":
                self.consecutive_blocks += 1
                
                # Extra jitter sleep window specifically on block detection
                jitter_sleep = random.uniform(*self.block_jitter_range)
                print(f"[~] Block Jitter: Sleeping for {jitter_sleep:.2f}s...")
                time.sleep(jitter_sleep)
                
                # Handle Circuit Breaker triggering threshold
                if self.consecutive_blocks >= 2:
                    self._trigger_circuit_breaker()
                    return {"status": "failed", "reason": "circuit_broken"}
                
                # Second-pass retry logic
                if not is_retry:
                    reshaped_term = self._shape_retry_term(term)
                    print(f"[*] Reshaping phrase: '{term}' -> '{reshaped_term}'. Executing second-pass...")
                    return self.execute_search(reshaped_term, is_retry=True)

            return result


if __name__ == "__main__":
    # Initialize without API credentials to intentionally force the HTTP fallback path
    scraper = EbayScraper(api_credentials=None)

    search_terms = ["pc tower", "gaming laptop", "unrelated term A", "unrelated term B"]

    for term in search_terms:
        output = scraper.execute_search(term)
        if output.get("status") == "success":
            print(f"[+] Found {len(output['results'])} items via fallback scraper.")
        print("-" * 50)
