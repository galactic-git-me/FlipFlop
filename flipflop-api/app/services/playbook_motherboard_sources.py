"""Exact, review-only motherboard fact capture from official manufacturer pages."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup


_MANUFACTURER_HOSTS = {
    "msi": ("msi.com",),
    "asus": ("asus.com",),
    "gigabyte": ("gigabyte.com",),
    "asrock": ("asrock.com",),
    "biostar": ("biostar.com.tw", "biostar.com.cn"),
}
_IDENTITY_NOISE = {
    "motherboard", "motherboards", "mainboard", "mainboards", "board",
    "socket", "supports", "support", "amd", "intel", "ryzen", "processors",
    "processor", "desktop", "memory", "wifi", "wi-fi", "atx", "micro",
    "matx", "ddr4", "ddr5", "ddr", "sata", "pcie", "pci", "express",
    "generation", "gen", "mother", "m", "for", "with", "the", "and", "lga",
}


def _manufacturer_domains(title: str) -> tuple[str, ...]:
    lowered = title.casefold()
    for brand, domains in _MANUFACTURER_HOSTS.items():
        if brand in lowered:
            return domains
    return ()


def _known_official_candidates(title: str) -> list[dict[str, str]]:
    """Return deterministic official URLs for manufacturer paths we know."""
    model = _model_name_prefix(title)
    normalized = model.casefold()
    if re.match(r"^asus\s+rog\s+strix\b", normalized):
        slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^asus\s+", "", model, flags=re.I).casefold()).strip("-")
        slugs = [slug]
        if not slug.endswith("-model"):
            slugs.append(f"{slug}-model")
        return [{"title": model, "source_url": f"https://rog.asus.com/motherboards/rog-strix/{item}/spec/",
            "publisher": "rog.asus.com"} for item in slugs]
    if re.match(r"^asus\s+prime\b", normalized):
        tail = re.sub(r"^asus\s+", "", model, flags=re.I)
        slug = re.sub(r"[^a-z0-9]+", "-", tail.casefold()).strip("-")
        return [{"title": model, "source_url": f"https://www.asus.com/motherboards-components/motherboards/prime/{slug}/techspec/",
            "publisher": "www.asus.com"}]
    if re.match(r"^asus\s+tuf\s+gaming\b", normalized):
        tail = re.sub(r"^asus\s+", "", model, flags=re.I)
        slug = re.sub(r"[^a-z0-9]+", "-", tail.casefold()).strip("-")
        return [{"title": model, "source_url": f"https://www.asus.com/motherboards-components/motherboards/tuf-gaming/{slug}/techspec/",
            "publisher": "www.asus.com"}]
    return []


def _allowed_official_url(url: str, domains: tuple[str, ...]) -> bool:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold().rstrip(".")
    return bool(
        parsed.scheme == "https"
        and port in (None, 443)
        and not parsed.username
        and not parsed.password
        and any(host == domain or host.endswith("." + domain) for domain in domains)
    )


def _model_name_prefix(listing_title: str) -> str:
    return re.split(
        r"[,|]|\b(?:motherboard|mother\s+board|mainboard|socket|supports|supporting|intel|amd|"
        r"lga\s*\d{4,5}|ddr\s*[345]|e?\s*[- ]?atx|micro\s*[- ]?atx|mini\s*[- ]?itx)\b",
        listing_title, maxsplit=1, flags=re.I,
    )[0].strip(" ,:-")


def _board_identity_matches(listing_title: str, page_identity: str) -> bool:
    prefix = _model_name_prefix(listing_title)
    tokens = [token for token in re.findall(r"[a-z0-9]+", prefix.casefold())
        if token.casefold() not in _IDENTITY_NOISE]
    if len(tokens) < 2:
        return False
    identity = " ".join(re.findall(r"[a-z0-9]+", page_identity.casefold()))
    # Require the vendor's distinctive model tokens, not just a chipset match.
    return all(re.search(rf"\b{re.escape(token)}\b", identity) for token in tokens)


def _snippet(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    return re.sub(r"\s+", " ", text[max(0, match.start() - 80):match.end() + 100]).strip()[:240]


def extract_official_board_facts(markup: str, listing_title: str, source_url: str) -> dict | None:
    """Parse only literal specifications from a model-matching maker page."""
    soup = BeautifulSoup(markup, "html.parser")
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    headings = " ".join(node.get_text(" ", strip=True) for node in soup.select("h1, h2")[:8])
    publisher = urlsplit(source_url).hostname or ""
    identity = " ".join((page_title, headings, publisher))
    if not _board_identity_matches(listing_title, identity):
        return None
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:250_000]
    facts: dict[str, object] = {}
    evidence: dict[str, str] = {}

    socket = re.search(r"\b(?:AMD\s+)?Socket\s*(AM[45])\b|\bLGA\s*(\d{4,5})\b", text, re.I)
    if socket:
        facts["socket"] = (socket.group(1) or f"lga{socket.group(2)}").casefold()
        evidence["socket"] = _snippet(text, socket.group(0)) or socket.group(0)

    chipset = re.search(r"\b(?:AMD|Intel)\s+([ABXZ H]\s?\d{3,4}E?|B\d{3,4}E?)\b", text, re.I)
    if chipset:
        facts["chipset"] = re.sub(r"\s+", "", chipset.group(1)).casefold()
        evidence["chipset"] = _snippet(text, chipset.group(0)) or chipset.group(0)
    else:
        chipset = re.search(r"\b([ABXZ]\d{3,4}E?)\b", listing_title, re.I)
        if chipset:
            facts["chipset"] = chipset.group(1).casefold()
            evidence["chipset"] = f"Exact chipset model in linked listing title: {chipset.group(1)}"

    memory = re.search(r"\bDDR\s*([345])\b", text, re.I)
    if memory:
        facts["ram_type"] = f"ddr{memory.group(1)}"
        evidence["ram_type"] = _snippet(text, memory.group(0)) or memory.group(0)

    slots = re.search(r"\b(\d+)\s*[x×]\s*(?:DDR\s*[345]\s*)?U?DIMM(?:\s+(?:slots?|sockets?))?\b|\b(\d+)\s+DIMM\s+(?:slots?|sockets?)\b", text, re.I)
    if slots:
        facts["ram_slots"] = int(slots.group(1) or slots.group(2))
        evidence["ram_slots"] = _snippet(text, slots.group(0)) or slots.group(0)

    capacity = re.search(r"(?:maximum\s+(?:memory\s+)?capacity|supporting\s+up\s+to|up\s+to)\D{0,80}(\d{2,3})\s*GB\b", text, re.I)
    if capacity:
        facts["max_ram_gb"] = int(capacity.group(1))
        evidence["max_ram_gb"] = _snippet(text, capacity.group(0)) or capacity.group(0)

    form = re.search(r"\b(E\s*[- ]?ATX|Micro\s*[- ]?ATX|Mini\s*[- ]?ITX|ATX)\s+(?:Form\s+Factor|Motherboard)\b|\bPCB\s+Info\s*[:|]?\s*(E\s*[- ]?ATX|Micro\s*[- ]?ATX|Mini\s*[- ]?ITX|ATX)\b", text, re.I)
    if form:
        value = re.sub(r"\s+", "", form.group(1) or form.group(2)).replace("-", "").casefold()
        facts["form_factor"] = {"eatx": "eatx", "microatx": "matx", "miniitx": "itx"}.get(value, value)
        evidence["form_factor"] = _snippet(text, form.group(0)) or form.group(0)

    m2_labels = {int(value) for value in re.findall(r"\bM[._ ]?2[_ -](\d+)\b", text, re.I)}
    m2_explicit = re.search(r"\b(\d+)\s*[x×]\s*M[._ ]?2\s+(?:slots?|connectors?)\b", text, re.I)
    if m2_explicit:
        facts["m2_slots"] = int(m2_explicit.group(1))
        evidence["m2_slots"] = _snippet(text, m2_explicit.group(0)) or m2_explicit.group(0)
    elif m2_labels:
        facts["m2_slots"] = max(m2_labels)
        evidence["m2_slots"] = f"Manufacturer lists M.2 connector labels 1 through {max(m2_labels)}"

    sata = re.search(r"\b(\d+)\s*[x×]\s*SATA(?:\s+[\d.]+\s*Gb/s)?\b|\bSATA\s+(\d+)\s+(?:ports|connectors)\b", text, re.I)
    if sata:
        facts["sata_ports"] = int(sata.group(1) or sata.group(2))
        evidence["sata_ports"] = _snippet(text, sata.group(0)) or sata.group(0)

    wifi = re.search(r"\bWi\s*[- ]?Fi\s*[4567]\b", text, re.I)
    if wifi:
        facts["wifi"] = True
        evidence["wifi"] = _snippet(text, wifi.group(0)) or wifi.group(0)

    if not facts.get("socket") or not facts.get("ram_type") or len(facts) < 3:
        return None
    return {"facts": facts, "field_evidence": evidence, "source_url": source_url,
        "source_title": page_title or headings[:300], "review_required": True}


async def _fetch_official_page(client: httpx.AsyncClient, url: str, domains: tuple[str, ...]) -> tuple[str, str] | None:
    current = url
    for _ in range(4):
        if not _allowed_official_url(current, domains):
            return None
        response = await client.get(current, follow_redirects=False)
        if response.is_redirect:
            target = response.headers.get("location")
            if not target:
                return None
            current = urljoin(current, target)
            continue
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", "text/html").casefold():
            return None
        return response.text[:1_500_000], str(response.url)
    return None


async def capture_official_motherboard_facts(title: str) -> dict | None:
    """Find one exact maker specification page and capture source-backed facts."""
    domains = _manufacturer_domains(title)
    if not domains:
        return None
    from app.services.component_research_search import discover_component_sources

    model_name = _model_name_prefix(title)[:120]
    if len(model_name) < 5:
        return None

    candidates = _known_official_candidates(title)
    try:
        candidates.extend(await discover_component_sources(
            model_name, "compatibility", publisher_domains=domains))
    except Exception:
        # Keep trying a deterministic first-party product URL if discovery is
        # blocked or unavailable in this environment.
        pass
    candidates = [item for item in candidates if _allowed_official_url(item["source_url"], domains)]
    if not candidates:
        return None
    headers = {"User-Agent": "FlipFlop-PlaybookResearch/1.0 (+https://theflipflop.shop)",
        "Accept-Language": "en-GB,en;q=0.8"}
    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        for item in candidates[:2]:
            try:
                fetched = await _fetch_official_page(client, item["source_url"], domains)
            except (httpx.HTTPError, ValueError):
                continue
            if not fetched:
                continue
            markup, final_url = fetched
            captured = extract_official_board_facts(markup, title, final_url)
            if captured:
                captured["publisher"] = urlsplit(final_url).hostname
                captured["captured_at"] = datetime.now(timezone.utc).isoformat()
                return captured
    return None
