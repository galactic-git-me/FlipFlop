"""Amazon product detail capture through seller SP-API Catalog Items."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.amazon_sp_api import AmazonSPAPI, AmazonSPAPIError


def _scalar_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for row in value for item in _scalar_values(row)]
    if isinstance(value, dict):
        if value.get("value") is not None and not isinstance(value["value"], (dict, list)):
            return [str(value["value"])]
        return [item for row in value.values() for item in _scalar_values(row)]
    if value is None or isinstance(value, bool):
        return []
    return [str(value)]


def _catalog_capture(item: dict[str, Any], asin: str) -> dict[str, Any]:
    specifications: dict[str, list[str]] = {}
    identifiers: dict[str, str] = {"asin": asin}
    identifier_names = {
        "upc": "gtin", "ean": "gtin", "gtin": "gtin",
        "manufacturer_part_number": "mpn", "part_number": "mpn",
        "model_number": "modelNumber", "model": "modelNumber",
        "brand": "brand",
    }
    for name, raw in (item.get("attributes") or {}).items():
        values = list(dict.fromkeys(value.strip() for value in _scalar_values(raw) if value.strip()))
        if not values:
            continue
        label = " ".join(part.capitalize() for part in str(name).split("_"))
        specifications[label] = values
        key = identifier_names.get(str(name).casefold())
        if key and key not in identifiers:
            identifiers[key] = values[0]
    for row in item.get("identifiers") or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("identifierType") or "").casefold()
        value = str(row.get("identifier") or "").strip()
        key = identifier_names.get(kind)
        if key and value and key not in identifiers:
            identifiers[key] = value
    return {
        "status": "ok",
        "sourceUrl": f"https://www.amazon.co.uk/dp/{asin}",
        "sourceMethod": "amazon_sp_api_catalog",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "specifications": specifications,
        "identifiers": identifiers,
        "conflicts": [],
    }


async def fetch_amazon_item_details(client: AmazonSPAPI, asin: str) -> dict[str, Any]:
    """Return API sourced catalogue facts; retail offers remain separate data."""
    if not client.configured:
        raise AmazonSPAPIError("Amazon SP-API credentials are not configured on the API service.", status_code=503)
    item = await client.get_catalog_item_by_asin(asin)
    return _catalog_capture(item, asin)
