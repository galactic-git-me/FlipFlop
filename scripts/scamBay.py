import random
import time
import webbrowser

SEARCH_TERMS = [
    "pc tower",
    "gaming laptop",
    "wireless mouse",
    "mechanical keyboard",
    "graphics card",
    "monitor 27 inch",
    "desk lamp",
    "office chair",
    "usb hub",
    "external hard drive",
]

DELAY_RANGE_SECONDS = (5, 15)


def open_random_ebay_search():
    term = random.choice(SEARCH_TERMS)
    url = f"https://www.ebay.co.uk/sch/i.html?_nkw={term.replace(' ', '+')}"
    print(f"[+] Opening eBay search: '{term}' -> {url}")
    webbrowser.open(url)


if __name__ == "__main__":
    for _ in range(5):
        open_random_ebay_search()
        delay = random.uniform(*DELAY_RANGE_SECONDS)
        print(f"[~] Waiting {delay:.1f}s before next search...")
        time.sleep(delay)
