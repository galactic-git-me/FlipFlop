"""Admin-triggered manufacturer-source discovery for Getting Ready.

Search results are untrusted suggestions only. This adapter never opens result
pages, downloads manuals/drivers, or marks a source as approved.
"""
from __future__ import annotations

import ipaddress
from typing import Literal
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup


ResearchTopic = Literal["driver_firmware", "manual", "rgb", "software", "compatibility"]

_TOPIC_QUERY = {
    "driver_firmware": "manufacturer official support drivers firmware downloads",
    "manual": "manufacturer official support user manual PDF",
    "rgb": "manufacturer official support RGB lighting software",
    "software": "manufacturer official support software downloads",
    "compatibility": "manufacturer official compatibility support",
}
_SEARCH_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": "FlipFlop-GettingReady/1.0 (+https://theflipflop.shop)",
    "Accept-Language": "en-GB,en;q=0.8",
}


def _external_https_url(raw_url: str) -> str | None:
    try:
        url = urljoin(_SEARCH_URL, raw_url.strip())
        parsed = urlsplit(url)
        if parsed.hostname and parsed.hostname.casefold() in {"duckduckgo.com", "www.duckduckgo.com"}:
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            if target:
                url = target
                parsed = urlsplit(url)
        hostname = parsed.hostname
        if hostname:
            try:
                ipaddress.ip_address(hostname)
                return None
            except ValueError:
                pass
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or not hostname
        or hostname.casefold() == "localhost"
        or parsed.username
        or parsed.password
        or hostname.casefold().endswith(".duckduckgo.com")
        or hostname.casefold() == "duckduckgo.com"
    ):
        return None
    return url


def parse_search_results(markup: str, *, limit: int = 8) -> list[dict[str, str]]:
    """Extract only result title, HTTPS URL and publisher host."""
    soup = BeautifulSoup(markup, "html.parser")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a.result__a, a[data-testid='result-title-a']"):
        raw_url = str(anchor.get("href") or "")
        url = _external_https_url(raw_url)
        title = anchor.get_text(" ", strip=True)[:300]
        if not url or not title or url in seen:
            continue
        seen.add(url)
        host = urlsplit(url).hostname or ""
        results.append({
            "title": title,
            "source_url": url,
            "publisher": host.removeprefix("www."),
        })
        if len(results) >= max(1, min(limit, 8)):
            break
    return results


async def discover_component_sources(
    component_name: str,
    topic: ResearchTopic,
    *,
    publisher_domains: tuple[str, ...] = (),
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, str]]:
    """Search for candidate sources without visiting or trusting result pages."""
    clean_name = " ".join(component_name.split())
    if not clean_name or len(clean_name) > 240:
        raise ValueError("Enter one exact component name (maximum 240 characters)")
    if topic not in _TOPIC_QUERY:
        raise ValueError("Unsupported research topic")
    domain_filter = " OR ".join(f"site:{domain}" for domain in publisher_domains)
    query = f'"{clean_name}" {f"({domain_filter}) " if domain_filter else ""}{_TOPIC_QUERY[topic]}'
    owns_client = client is None
    search_client = client or httpx.AsyncClient(
        headers=_HEADERS,
        timeout=httpx.Timeout(12.0, connect=5.0),
        follow_redirects=False,
    )
    try:
        response = await search_client.get(_SEARCH_URL, params={"q": query, "kl": "uk-en"})
        response.raise_for_status()
        if "text/html" not in response.headers.get("content-type", "text/html").casefold():
            raise RuntimeError("Search provider returned an unexpected content type")
        return parse_search_results(response.text[:1_000_000])
    finally:
        if owns_client:
            await search_client.aclose()
