"""Vendor price history for products discovered in Amazon Best Sellers lists."""
from collections import defaultdict
from datetime import datetime
import json
import re

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_operator
from app.database import get_db
from app.services.amazon_bestsellers import COMPONENT_BESTSELLER_LISTS

router = APIRouter(prefix="/pricewatch", tags=["pricewatch"], dependencies=[Depends(require_operator)])

WATCHED_CATEGORIES = ("cpu", "motherboard", "ram", "storage")
STORAGE_TYPE_RE = re.compile(r"\b(?:nvme|nvm\s+express|pcie|pci-e|pci\s+express)\b", re.I)
SATA_TYPE_RE = re.compile(r"\bsata\b|\b2\.5\s*(?:inch|in\b)|\b2\.5\s*[\"″]", re.I)
VENDOR_LABELS = {
    "amazon": "Amazon", "ebay": "eBay", "overclockers": "Overclockers UK",
    "scan": "Scan", "awd_it": "AWD-IT", "computer_orbit": "Computer Orbit",
    "bargain_hardware": "Bargain Hardware", "cex": "CeX", "newegg_uk": "Newegg",
    "ebuyer": "eBuyer", "google_shopping": "Google Shopping", "other": "Other",
}


def _month_keys(count: int = 12, now: datetime | None = None) -> list[tuple[str, str]]:
    current = now or datetime.utcnow()
    end = current.year * 12 + current.month - 1
    values = []
    for offset in reversed(range(count)):
        year, zero_month = divmod(end - offset, 12)
        month = zero_month + 1
        values.append((f"{year:04d}-{month:02d}", datetime(year, month, 1).strftime("%b %Y")))
    return values


def _storage_type(title: str) -> str:
    if STORAGE_TYPE_RE.search(title):
        return "nvme"
    if SATA_TYPE_RE.search(title):
        return "sata"
    return "unclassified"


def _mpn_keys(data: dict | None) -> set[tuple[str, str]]:
    if not isinstance(data, dict):
        return set()
    return {
        (str(claim.get("namespace") or "").strip().casefold(), str(claim.get("value") or "").strip().upper())
        for claim in data.get("identity_claims", [])
        if isinstance(claim, dict) and claim.get("kind") == "mpn" and claim.get("namespace") and claim.get("value")
    }


def _mpn_display(data: dict | None) -> str | None:
    keys = sorted(_mpn_keys(data))
    return keys[0][1] if keys else None


def _add_month_stats(target: dict, cpk: str, month_key: str, vendor: str,
                     median: float | None, average: float | None,
                     low: float | None, observations: int) -> None:
    if median is None:
        return
    name = VENDOR_LABELS.get(vendor.casefold(), vendor.replace("_", " ").replace("-", " ").title())
    group = target[cpk][month_key]
    # A product can have multiple CPK aliases for the same MPN. Retain raw
    # observations before taking medians in SQL, so the alias merge stays exact.
    group.setdefault(name, []).append((float(median), float(average or median),
                                      float(low if low is not None else median), int(observations)))


@router.get("")
async def get_pricewatch(db: AsyncSession = Depends(get_db)) -> dict:
    """Use Best Sellers to select products, then price by CPK and verified MPN aliases."""
    months = _month_keys()
    first_month = datetime.strptime(months[0][0], "%Y-%m").replace(day=1)
    categories = []

    for category in WATCHED_CATEGORIES:
        list_name, source_url = COMPONENT_BESTSELLER_LISTS[category]
        latest = (await db.execute(text("""
            SELECT MAX(captured_at) FROM amazon_bestseller_observations WHERE category = :category
        """), {"category": category})).scalar_one_or_none()
        current_rows = []
        unlinked_count = 0
        if latest:
            current_rows = (await db.execute(text("""
                SELECT DISTINCT ON (cpk) cpk, title, url, image_url, rank, captured_at
                FROM amazon_bestseller_observations
                WHERE category = :category AND captured_at >= CAST(:latest AS timestamp) - INTERVAL '1 second'
                  AND cpk IS NOT NULL
                ORDER BY cpk, rank ASC, captured_at DESC, id DESC
            """), {"category": category, "latest": latest})).mappings().all()
            unlinked_count = int((await db.execute(text("""
                SELECT COUNT(*) FROM amazon_bestseller_observations
                WHERE category = :category AND captured_at >= CAST(:latest AS timestamp) - INTERVAL '1 second'
                  AND cpk IS NULL
            """), {"category": category, "latest": latest})).scalar_one() or 0)

        cpks = [str(row["cpk"]) for row in current_rows]
        products_by_cpk = {cpk: {"cpk": cpk, "title": row["title"], "url": row["url"],
                                  "image_url": row["image_url"], "rank": row["rank"],
                                  "mpn": None, "storage_type": _storage_type(row["title"] or "") if category == "storage" else None,
                                  "months": {}}
                           for cpk, row in zip(cpks, current_rows)}

        price_rows: dict[str, dict[str, dict[str, list[tuple[float, float, float, int]]]]] = defaultdict(lambda: defaultdict(dict))
        alias_targets: dict[str, str] = {cpk: cpk for cpk in cpks}
        if cpks:
            identity_rows = (await db.execute(text("""
                SELECT cpk, listing_id, cpk_data FROM gem_radar_listing_cpk WHERE cpk = ANY(:cpks)
            """), {"cpks": cpks})).mappings().all()
            target_mpns: dict[tuple[str, str], set[str]] = defaultdict(set)
            data_by_cpk: dict[str, dict] = {}
            for row in identity_rows:
                cpk = str(row["cpk"])
                data = row["cpk_data"] if isinstance(row["cpk_data"], dict) else {}
                data_by_cpk.setdefault(cpk, data)
                for key in _mpn_keys(data):
                    target_mpns[key].add(cpk)
            for cpk, product in products_by_cpk.items():
                product["mpn"] = _mpn_display(data_by_cpk.get(cpk))

            mpn_values = sorted({value for _, value in target_mpns})
            alias_rows = identity_rows
            if mpn_values:
                alias_rows = (await db.execute(text("""
                    SELECT cpk, listing_id, cpk_data FROM gem_radar_listing_cpk
                    WHERE cpk = ANY(:cpks) OR EXISTS (
                        SELECT 1 FROM jsonb_array_elements(COALESCE(cpk_data->'identity_claims', '[]'::jsonb)) claim
                        WHERE claim->>'kind' = 'mpn' AND upper(claim->>'value') = ANY(:mpns)
                    )
                """), {"cpks": cpks, "mpns": mpn_values})).mappings().all()

            linked_listings: dict[str, set[str]] = defaultdict(set)
            for row in alias_rows:
                source_cpk = str(row["cpk"])
                target_cpk = source_cpk if source_cpk in products_by_cpk else None
                data = row["cpk_data"] if isinstance(row["cpk_data"], dict) else {}
                if target_cpk is None:
                    matches = {candidate for key in _mpn_keys(data) for candidate in target_mpns.get(key, set())}
                    if len(matches) == 1:
                        target_cpk = next(iter(matches))
                if target_cpk is None:
                    continue
                alias_targets[source_cpk] = target_cpk
                if row.get("listing_id"):
                    linked_listings[target_cpk].add(str(row["listing_id"]))

            alias_payload = json.dumps([{"cpk": alias, "target_cpk": target}
                                        for alias, target in alias_targets.items()])
            amazon_rows = (await db.execute(text("""
                WITH aliases AS (
                    SELECT * FROM jsonb_to_recordset(CAST(:aliases AS jsonb)) AS x(cpk text, target_cpk text)
                )
                SELECT aliases.target_cpk, to_char(date_trunc('month', a.captured_at), 'YYYY-MM') AS month_key,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY a.price) AS median_price,
                       AVG(a.price) AS average_price, MIN(a.price) AS low_price, COUNT(*) AS observations
                FROM aliases JOIN amazon_bestseller_observations a ON a.cpk = aliases.cpk
                WHERE a.captured_at >= :first_month AND a.price > 0
                GROUP BY aliases.target_cpk, date_trunc('month', a.captured_at)
            """), {"aliases": alias_payload, "first_month": first_month})).mappings().all()
            for row in amazon_rows:
                _add_month_stats(price_rows, str(row["target_cpk"]), str(row["month_key"]), "amazon",
                                 row["median_price"], row["average_price"], row["low_price"], row["observations"])

            listing_payload = json.dumps([{"listing_id": listing_id, "target_cpk": cpk}
                                          for cpk, listing_ids in linked_listings.items() for listing_id in listing_ids])
            if linked_listings:
                market_rows = (await db.execute(text("""
                    WITH linked AS (
                        SELECT * FROM jsonb_to_recordset(CAST(:linked AS jsonb)) AS x(listing_id text, target_cpk text)
                    ), observations AS (
                        SELECT linked.target_cpk,
                               COALESCE(NULLIF(o.source, ''), NULLIF(split_part(o.listing_id, ':', 1), ''), 'other') AS vendor,
                               o.delivered_price, o.observed_at
                        FROM linked JOIN gem_radar_listing_observations o ON o.listing_id = linked.listing_id
                        WHERE o.observed_at >= :first_month AND o.delivered_price > 0
                          AND o.condition_normalised = 'new'
                          AND COALESCE(NULLIF(o.source, ''), NULLIF(split_part(o.listing_id, ':', 1), ''), 'other')
                              NOT IN ('temu', 'vinted')
                    )
                    SELECT target_cpk, vendor, to_char(date_trunc('month', observed_at), 'YYYY-MM') AS month_key,
                           percentile_cont(0.5) WITHIN GROUP (ORDER BY delivered_price) AS median_price,
                           AVG(delivered_price) AS average_price, MIN(delivered_price) AS low_price,
                           COUNT(*) AS observations
                    FROM observations GROUP BY target_cpk, vendor, date_trunc('month', observed_at)
                """), {"linked": listing_payload, "first_month": first_month})).mappings().all()
                for row in market_rows:
                    _add_month_stats(price_rows, str(row["target_cpk"]), str(row["month_key"]), str(row["vendor"]),
                                     row["median_price"], row["average_price"], row["low_price"], row["observations"])

        for cpk, product in products_by_cpk.items():
            for month_key, vendor_rows in price_rows.get(cpk, {}).items():
                combined = {}
                for vendor, summaries in vendor_rows.items():
                    # An MPN may have more than one historical CPK alias. Combine
                    # the alias observations conservatively at the median-summary level.
                    combined[vendor] = sorted(summaries, key=lambda value: value[0])[0]
                if not combined:
                    continue
                best_vendor, best = min(combined.items(), key=lambda item: item[1][0])
                product["months"][month_key] = {
                    "median": round(best[0], 2),
                    "best_vendor": best_vendor,
                    "average": round(sum(value[1] for value in combined.values()) / len(combined), 2),
                    "low": round(min(value[2] for value in combined.values()), 2),
                    "observations": sum(value[3] for value in combined.values()),
                    "vendor_medians": {vendor: round(value[0], 2) for vendor, value in sorted(combined.items())},
                }

        products = sorted(products_by_cpk.values(), key=lambda product: (product["rank"] or 999999, product["title"] or ""))
        categories.append({
            "category": category,
            "name": {"cpu": "CPUs", "motherboard": "Motherboards", "ram": "RAM", "storage": "Storage"}[category],
            "list_name": list_name,
            "source_url": source_url,
            "last_captured_at": latest.isoformat() if latest else None,
            "products": products,
            "unlinked_product_count": unlinked_count,
            "unclassified_storage_count": sum(1 for product in products if product["storage_type"] == "unclassified"),
        })

    return {"months": [{"key": key, "label": label} for key, label in months],
            "categories": categories, "generated_at": datetime.utcnow().isoformat(),
            "price_basis": "Lowest median among Amazon and linked vendor listings per product and month; exact CPK and MPN aliases only."}
