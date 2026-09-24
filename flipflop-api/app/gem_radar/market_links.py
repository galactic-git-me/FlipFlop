"""Resolve displayed market quantiles to the closest real cohort listings."""
from urllib.parse import urlparse


def market_endpoint_links(explanation: dict | None, lower: float | None, upper: float | None,
                          candidates: list[tuple[str, str, float]]) -> dict[str, str | None]:
    market = (explanation or {}).get("market") or {}
    included = set(market.get("comparable_urls") or ())
    valid = [
        (url, price) for key, url, price in candidates
        if key in included and price > 0 and urlparse(url).scheme in {"http", "https"}
        and urlparse(url).netloc
    ]
    def closest(target: float | None) -> str | None:
        return min(valid, key=lambda item: abs(item[1] - target))[0] if target is not None and valid else None
    return {"market_lower_url": closest(lower), "market_upper_url": closest(upper)}
