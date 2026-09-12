"""Keep multi-view reconstruction tied to one catalogue listing."""
from urllib.parse import urlparse


def select_listing_references(stored: list | None, requested: list[str] | None = None) -> list[str]:
    available = []
    for value in stored or []:
        if not isinstance(value, str):
            continue
        url = urlparse(value)
        if url.scheme == "https" and url.hostname and value not in available:
            available.append(value)
    if requested and any(value not in available for value in requested):
        raise ValueError("Reference photos must belong to this product's listing")
    selected = list(dict.fromkeys(requested or available))[:4]
    if not selected:
        raise ValueError("This listing has no usable HTTPS reference photos")
    return selected
