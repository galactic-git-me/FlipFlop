"""Resolve every curated Playbook cell's component specs to real, fresh offers.

Why this exists
---------------
``scripts/sync_curated_definitions.py`` fills each Playbook cell slot with a
placeholder Listing (price 0.0, URL pointing back at theflipflop.shop/builds).
Nothing ever replaced those placeholders with scraped vendor offers, so the 24
curated builds never received real component prices. This script closes that
gap using only live data already captured by Gem Radar.

What it does
------------
1. Reads ``data/curated_build_definitions.json`` (24 cells x component slots).
2. Loads recent Gem Radar observations (latest sighting per listing) with
   their URLs and CPKs.
3. Matches each slot spec against those titles:
     * named parts (CPU, GPU, motherboard, PSU, cooler, case) -> exact model
       tokens with variant guards (5600 != 5600X, 9070 != 9070 XT, 5060 Ti !=
       5060, RM750e != RM750x, WIFI/non-WIFI boards kept apart);
     * generic parts (RAM, SSD) -> parsed spec requirements (DDR generation,
       kit layout, speed >= spec, CL <= spec; capacity, NVMe, PCIe gen >= spec)
       restricted to known brands.
   Full systems, bundles, faulty/spares and accessory listings are rejected.
4. Keeps offers that are new-condition, fixed-price, seen within
   ``--max-age-days`` and not from excluded sources, then picks the cheapest
   delivered price (after dropping implausibly low outliers).
5. Writes a CSV + JSON report and prints per-cell coverage, including WHY
   empty slots are empty (never scraped / only stale / only used / only from
   excluded sources).
6. With ``--apply``: upserts the winning offer as a Listing + CatalogueVariant
   in the matching Playbook slot, points the CuratedBuildSegment component at
   it, and retires the 0.0 placeholder listing for that slot. Selling prices
   and publishing are NOT touched: the admin curated-builds page proposes a
   new selling price from the new component total, and component approval
   (curated_for_builds) stays a human decision.

Usage (from flipflop-api/, with the project venv active)
--------------------------------------------------------
    python scripts/resolve_curated_offers.py                    # dry run + report
    python scripts/resolve_curated_offers.py --apply            # link offers
    python scripts/resolve_curated_offers.py --cell FF-GVG-02   # one cell
    python scripts/resolve_curated_offers.py --max-age-days 7 --conditions new,open_box
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFINITIONS_PATH = ROOT / "data" / "curated_build_definitions.json"
REPORT_DIR = ROOT / "output" / "curated_offers"

# --------------------------------------------------------------------------
# Matching rules (pure functions: no database or app imports)
# --------------------------------------------------------------------------

SLOT_CATEGORIES: dict[str, set[str]] = {
    "cpu": {"cpu", "processor"},
    "gpu": {"gpu", "graphics", "graphics_card"},
    "motherboard": {"motherboard", "mobo"},
    "ram": {"ram", "memory"},
    "storage": {"ssd", "storage", "nvme", "hdd"},
    "psu": {"psu", "power_supply"},
    "cooling": {"cooler", "cooling", "cpu_cooler", "aio"},
    "case": {"case", "chassis"},
}
SOFTWARE_SLOTS = {"os"}
# Specs describing parts that ship inside another product (mini-PC/APU builds,
# boxed coolers) rather than a separately purchasable retail component.
INTEGRATED_PATTERN = re.compile(
    r"\b(integrated|included|oem|lpddr\d?x?|external\s+\d+w\s+power\s+adapter|"
    r"-style|mini-pc\s+chassis|wraith\s+(stealth|spire|prism))\b",
    re.I,
)
GENERIC_SLOTS = {"ram", "storage"}

# Words that add nothing to identity and are often missing from vendor titles.
OPTIONAL_TOKENS = {
    "amd", "intel", "nvidia", "geforce", "radeon", "processor", "cpu", "graphics",
    "card", "the", "with", "and", "for", "desktop", "gaming", "edition",
    "80", "plus80", "bronze", "gold", "platinum", "titanium", "modular", "fully",
    "semi", "atx", "psu", "power", "supply", "cooler", "case", "mid", "tower",
}
# Tokens that change the SKU. If a title carries one the spec lacks (or the
# reverse), it is a different product.
VARIANT_TOKENS = {
    "ti", "super", "xt", "xtx", "gre", "x3d", "plus", "v2", "v3", "v4", "lite",
    "mini", "digital", "max", "wifi", "wifi7", "elite", "pro", "xl", "flow",
}
SYSTEM_PATTERN = re.compile(
    r"\b(gaming\s+pc|desktop\s+pc|pc\s+build|computer|tower\s+pc|prebuilt|pre-built|"
    r"bundle|combo|laptop|notebook|full\s+system|system\s+unit|workstation|"
    r"mini\s+pc|all[\s-]in[\s-]one)\b",
    re.I,
)
REJECT_PATTERN = re.compile(
    r"\b(faulty|broken|spares|for\s+parts|not\s+working|repair|box\s+only|empty\s+box|"
    r"bracket|backplate|cable|adapter|riser|waterblock|water\s+block|sticker|"
    r"heatsink\s+only|mount(?:ing)?\s+kit|replacement\s+fan|fan\s+only|dust\s+filter|"
    r"enclosure|caddy|shroud|keychain|replica|dummy)\b",
    re.I,
)
RAM_BRANDS = {
    "corsair", "gskill", "g.skill", "kingston", "crucial", "teamgroup", "team",
    "patriot", "adata", "xpg", "lexar", "pny", "silicon power", "klevv",
    "thermaltake", "mushkin", "samsung", "hynix", "sk hynix", "micron", "netac",
}
SSD_BRANDS = {
    "samsung", "wd", "western digital", "wd_black", "wdblack", "crucial", "kingston",
    "sk hynix", "hynix", "solidigm", "lexar", "teamgroup", "team", "corsair",
    "seagate", "sabrent", "kioxia", "adata", "xpg", "pny", "gigabyte", "aorus",
    "msi", "patriot", "transcend", "acer predator", "predator", "silicon power",
    "netac", "fikwot", "ediloca", "fanxiang", "biwin",
}


def normalise(text: str) -> str:
    t = (text or "").lower()
    t = t.replace("g.skill", "gskill").replace("wd_black", "wdblack")
    t = t.replace("80+", " plus80 ").replace("80 plus", " plus80 ")
    t = re.sub(r"\b(rtx|gtx|rx|arc)(\d)", r"\1 \2", t)
    t = re.sub(r"\b(\d{4})(xtx|xt|ti|super|gre)\b", r"\1 \2", t)
    t = re.sub(r"\bwi-?fi\s?7\b", " wifi7 ", t)
    t = re.sub(r"\bwi-?fi\b", " wifi ", t)
    return t


def tokens(text: str) -> list[str]:
    out = []
    for tok in re.split(r"[^a-z0-9]+", normalise(text)):
        if not tok:
            continue
        m = re.fullmatch(r"(\d+)g(?:b)?", tok)
        if m and int(m.group(1)) <= 256:  # 16G -> 16gb, but keep CPU codes like 5600g
            tok = f"{m.group(1)}gb"
        out.append(tok)
    return out


def is_system_or_junk(title: str) -> bool:
    return bool(SYSTEM_PATTERN.search(title or "") or REJECT_PATTERN.search(title or ""))


def required_model_tokens(slot: str, spec: str) -> list[str]:
    req = []
    for tok in tokens(spec):
        if tok in OPTIONAL_TOKENS:
            continue
        if slot == "psu" and re.fullmatch(r"\d+w", tok):
            continue  # wattage is implied by the model code (RM750e, CX650...)
        req.append(tok)
    return req


def matches_named_part(slot: str, spec: str, title: str) -> bool:
    if is_system_or_junk(title):
        return False
    title_tokens = set(tokens(title))
    spec_tokens = set(tokens(spec))
    required = required_model_tokens(slot, spec)
    if not required or not all(tok in title_tokens for tok in required):
        return False
    # Variant guard: title must not introduce an SKU-changing token.
    for tok in VARIANT_TOKENS:
        if tok in title_tokens and tok not in spec_tokens:
            return False
    return True


@dataclass
class RamReq:
    ddr: Optional[int]
    total_gb: Optional[int]
    sticks: Optional[int]
    stick_gb: Optional[int]
    speed: Optional[int]
    cl: Optional[int]
    brand: Optional[str]


def _first_int(pattern: str, text: str) -> Optional[int]:
    m = re.search(pattern, text, re.I)
    return int(m.group(1)) if m else None


def _brand_in(text: str, brands: Iterable[str]) -> Optional[str]:
    t = normalise(text)
    for b in sorted(brands, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(b)}(?![a-z0-9])", t):
            return b
    return None


def parse_ram(text: str) -> RamReq:
    t = normalise(text)
    kit = re.search(r"\b(\d)\s?x\s?(\d{1,3})\s?gb?\b", t)
    sticks, stick_gb = (int(kit.group(1)), int(kit.group(2))) if kit else (None, None)
    total = sticks * stick_gb if kit else None
    if total is None:
        sizes = [int(x) for x in re.findall(r"\b(\d{1,3})\s?gb\b", t) if int(x) <= 256]
        total = max(sizes) if sizes else None
    speed = _first_int(r"ddr[345][\s-]?(\d{4})", t) or _first_int(r"\b(\d{4})\s?(?:mhz|mt/?s)\b", t)
    cl = _first_int(r"\bc(?:l|as)?\s?-?(\d{2})\b", t)
    return RamReq(
        ddr=_first_int(r"\bddr\s?([345])", t),
        total_gb=total, sticks=sticks, stick_gb=stick_gb, speed=speed, cl=cl,
        brand=_brand_in(t, RAM_BRANDS),
    )


def matches_ram(spec: str, title: str) -> bool:
    if is_system_or_junk(title) or re.search(r"so-?dimm|laptop|notebook", title, re.I):
        return False
    wants_server = bool(re.search(r"\becc\b|rdimm|registered", spec, re.I))
    is_server = bool(re.search(r"\becc\b|rdimm|registered|server", title, re.I))
    if wants_server != is_server:
        return False
    want, got = parse_ram(spec), parse_ram(title)
    if got.brand is None:
        return False
    if want.brand and want.brand != got.brand:
        return False
    if want.ddr and got.ddr != want.ddr:
        return False
    if want.total_gb and got.total_gb != want.total_gb:
        return False
    if want.sticks and (got.sticks, got.stick_gb) != (want.sticks, want.stick_gb):
        return False
    if want.speed and (got.speed is None or got.speed < want.speed):
        return False
    if want.cl and (got.cl is None or got.cl > want.cl):
        return False
    return True


@dataclass
class SsdReq:
    capacity_gb: Optional[int]
    gen: Optional[int]
    nvme: bool
    brand: Optional[str]


def parse_ssd(text: str) -> SsdReq:
    t = normalise(text)
    cap = None
    m = re.search(r"\b(\d+(?:\.\d+)?)\s?(tb|gb)\b", t)
    if m:
        value = float(m.group(1))
        cap = int(round(value * 1000)) if m.group(2) == "tb" else int(value)
    gen = _first_int(r"(?:pcie|pci-e|gen)\s?([345])(?:\.0)?\b", t)
    gen = gen or _first_int(r"\bgen\s?([345])x4\b", t)
    nvme = bool(re.search(r"nvme|pcie|pci-e", t))
    return SsdReq(capacity_gb=cap, gen=gen, nvme=nvme, brand=_brand_in(t, SSD_BRANDS))


def matches_ssd(spec: str, title: str) -> bool:
    if is_system_or_junk(title) or re.search(r"\bsata\b|external|portable|usb|2\.5\"|hdd|hard\s+drive", title, re.I):
        return False
    want, got = parse_ssd(spec), parse_ssd(title)
    if got.brand is None:
        return False
    if want.brand and want.brand != got.brand:
        return False
    if want.capacity_gb and got.capacity_gb != want.capacity_gb:
        return False
    if want.nvme and not got.nvme:
        return False
    if want.gen:
        if got.gen is None:
            return want.gen <= 3
        if got.gen < want.gen:
            return False
    return True


def spec_matches(slot: str, spec: str, title: str) -> bool:
    if slot == "ram":
        return matches_ram(spec, title)
    if slot == "storage":
        return matches_ssd(spec, title)
    return matches_named_part(slot, spec, title)


def category_ok(slot: str, category: Optional[str]) -> bool:
    if not category:
        return True
    return category.lower() in SLOT_CATEGORIES.get(slot, {slot})


def tier_key(value: str) -> str:
    value = (value or "").lower()
    if "high" in value:
        return "high"
    if "mid" in value:
        return "mid"
    return "budget"


# --------------------------------------------------------------------------
# Offer selection
# --------------------------------------------------------------------------

@dataclass
class Offer:
    listing_id: str
    title: str
    category: Optional[str]
    condition: Optional[str]
    listing_type: Optional[str]
    price: float
    source: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    seller: Optional[str]
    cpk: Optional[str]
    seen_at: datetime

    @property
    def age_days(self) -> float:
        seen = self.seen_at if self.seen_at.tzinfo else self.seen_at.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - seen).total_seconds() / 86400


@dataclass
class SlotResult:
    cell_id: str
    segment: str
    tier: str
    slot: str
    spec: str
    status: str  # ready | no_offer | no_url | software | integrated
    reason: str = ""
    eligible_count: int = 0
    diagnostics: dict = field(default_factory=dict)
    best: Optional[dict] = None
    alternatives: list = field(default_factory=list)
    applied: str = ""


def choose_offers(slot: str, spec: str, pool: list[Offer], args) -> tuple[list[Offer], Counter]:
    diag: Counter = Counter()
    eligible: list[Offer] = []
    allowed_conditions = {c.strip().lower() for c in args.conditions.split(",") if c.strip()}
    excluded_sources = {s.strip().lower() for s in args.exclude_sources.split(",") if s.strip()}
    for offer in pool:
        if not category_ok(slot, offer.category):
            continue
        if not spec_matches(slot, spec, offer.title):
            continue
        diag["matched_any"] += 1
        if (offer.source or "").lower() in excluded_sources:
            diag["excluded_source"] += 1
            continue
        if "auction" in (offer.listing_type or "").lower() or "sold" in (offer.listing_type or "").lower():
            diag["auction_or_sold"] += 1
            continue
        if (offer.condition or "unknown").lower() not in allowed_conditions:
            diag["wrong_condition"] += 1
            continue
        if offer.age_days > args.max_age_days:
            diag["stale"] += 1
            continue
        eligible.append(offer)
    # Drop implausible lows (accessories / mis-scrapes that slipped through).
    if len(eligible) >= 3:
        median = statistics.median(o.price for o in eligible)
        kept = [o for o in eligible if o.price >= median * args.outlier_floor]
        diag["outlier_dropped"] = len(eligible) - len(kept)
        eligible = kept
    # One offer per listing, cheapest first, freshest breaks ties.
    eligible.sort(key=lambda o: (o.price, o.age_days))
    return eligible, diag


def explain_empty(diag: Counter) -> str:
    if not diag.get("matched_any"):
        return "never scraped or title never matched the spec"
    parts = [f"{k}={v}" for k, v in diag.items() if k != "matched_any" and v]
    return "matches exist but none eligible (" + ", ".join(parts) + ")"


def offer_dict(o: Offer) -> dict:
    return {
        "listing_id": o.listing_id, "title": o.title, "price": round(o.price, 2),
        "source": o.source, "seller": o.seller, "url": o.url,
        "condition": o.condition, "age_days": round(o.age_days, 1), "cpk": o.cpk,
    }


# --------------------------------------------------------------------------
# Database access (imports deferred so the matcher stays importable in tests)
# --------------------------------------------------------------------------

POOL_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (o.listing_id)
           o.listing_id, o.title, o.category, o.condition_normalised, o.listing_type,
           o.delivered_price, o.source, o.image_url, o.seller_name,
           GREATEST(o.observed_at, COALESCE(o.updated_at, o.observed_at)) AS seen_at
    FROM gem_radar_listing_observations o
    WHERE GREATEST(o.observed_at, COALESCE(o.updated_at, o.observed_at))
          >= NOW() - make_interval(days => :window_days)
      AND o.delivered_price > 0
    ORDER BY o.listing_id, GREATEST(o.observed_at, COALESCE(o.updated_at, o.observed_at)) DESC
)
SELECT l.listing_id, l.title, l.category, l.condition_normalised, l.listing_type,
       l.delivered_price, l.source, l.image_url, l.seller_name, l.seen_at,
       s.url, c.cpk
FROM latest l
LEFT JOIN LATERAL (
    SELECT url FROM gem_radar_scored_listings s
    WHERE s.listing_id = l.listing_id AND s.url IS NOT NULL
    ORDER BY s.id DESC LIMIT 1
) s ON TRUE
LEFT JOIN gem_radar_listing_cpk c ON c.listing_id = l.listing_id
"""


async def load_pool(db, window_days: int) -> list[Offer]:
    from sqlalchemy import text

    rows = (await db.execute(text(POOL_SQL), {"window_days": window_days})).fetchall()
    pool = []
    for r in rows:
        url = r.url
        if not url and str(r.listing_id).startswith("http"):
            url = str(r.listing_id)
        pool.append(Offer(
            listing_id=str(r.listing_id), title=r.title or "", category=r.category,
            condition=r.condition_normalised, listing_type=r.listing_type,
            price=float(r.delivered_price), source=r.source, url=url,
            image_url=r.image_url, seller=r.seller_name, cpk=r.cpk, seen_at=r.seen_at,
        ))
    return pool


async def apply_cell(db, cell: dict, results: list[SlotResult], lookups: dict) -> None:
    from sqlalchemy import select
    from app.models.catalogue import CatalogueVariant
    from app.models.listing import Listing, ListingStatus

    segment = lookups["segments"].get((cell["segment"].casefold(), tier_key(cell["tier"])))
    playbook = lookups["playbooks"].get(cell["segment"].casefold())
    if segment is None:
        for r in results:
            if r.status == "ready":
                r.applied = "skipped: no CuratedBuildSegment row for this cell"
        return
    components = dict(segment.components or {})
    changed = False
    now = datetime.utcnow()
    for r in results:
        if r.status != "ready" or not r.best:
            continue
        slot = lookups["slots"].get((playbook.id, r.slot)) if playbook else None
        if slot is None:
            r.applied = "skipped: Playbook has no slot of this type"
            continue
        best = r.best
        listing = (await db.execute(select(Listing).where(Listing.external_id == best["listing_id"]))).scalar_one_or_none()
        if listing is None:
            listing = Listing(
                external_id=best["listing_id"], source_id=0,
                source_name=f"{best['source'] or 'unknown'} (Gem Radar)",
                title=best["title"][:500], price=best["price"], url=best["url"][:1000],
                status=ListingStatus.active, condition=best["condition"],
                image_urls=[best["image_url"]] if best.get("image_url") else [],
            )
            db.add(listing)
            await db.flush()
        else:
            listing.title = best["title"][:500]
            listing.price = best["price"]
            listing.url = best["url"][:1000]
            listing.status = ListingStatus.active
            listing.last_seen_at = now
        variant = (await db.execute(select(CatalogueVariant).where(
            CatalogueVariant.slot_id == slot.id, CatalogueVariant.listing_id == listing.id,
        ))).scalar_one_or_none()
        if variant is None:
            variant = CatalogueVariant(
                listing_id=listing.id, slot_id=slot.id, status="active",
                display_price=best["price"], tier=tier_key(cell["tier"]),
            )
            db.add(variant)
            await db.flush()
        else:
            variant.status = "active"
            variant.display_price = best["price"]
        previous = components.get(r.slot)
        components[r.slot] = variant.id
        changed = changed or previous != variant.id
        placeholder = (await db.execute(select(Listing).where(
            Listing.external_id == f"curated-definition:{cell['id']}:{r.slot}"
        ))).scalar_one_or_none()
        if placeholder is not None and placeholder.status != ListingStatus.removed:
            placeholder.status = ListingStatus.removed
        r.applied = f"linked variant {variant.id} (was {previous})"
    if changed:
        segment.components = components


async def build_lookups(db) -> dict:
    from sqlalchemy import select
    from app.models.catalogue import PlaybookSlot
    from app.models.curated_build_segment import CuratedBuildSegment
    from app.models.playbook import Playbook

    segments = {}
    for seg in (await db.execute(select(CuratedBuildSegment))).scalars().all():
        segments[(seg.customer_type.casefold(), tier_key(seg.budget_level))] = seg
    playbooks = {}
    for pb in (await db.execute(select(Playbook))).scalars().all():
        key = pb.name.casefold()
        if key not in playbooks or getattr(pb, "status", "") == "active":
            playbooks[key] = pb
    slots = {(s.playbook_id, s.slot_type): s for s in (await db.execute(select(PlaybookSlot))).scalars().all()}
    return {"segments": segments, "playbooks": playbooks, "slots": slots}


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def write_reports(results: list[SlotResult], args) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = REPORT_DIR / f"curated_offers_{stamp}.csv"
    json_path = REPORT_DIR / f"curated_offers_{stamp}.json"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cell", "segment", "tier", "slot", "spec", "status", "eligible_offers",
                    "best_price", "best_source", "best_title", "best_url", "best_age_days",
                    "alt_2_price", "alt_2_source", "alt_3_price", "alt_3_source", "reason", "applied"])
        for r in results:
            b = r.best or {}
            alts = r.alternatives + [{}, {}]
            w.writerow([r.cell_id, r.segment, r.tier, r.slot, r.spec, r.status, r.eligible_count,
                        b.get("price", ""), b.get("source", ""), b.get("title", ""), b.get("url", ""),
                        b.get("age_days", ""), alts[0].get("price", ""), alts[0].get("source", ""),
                        alts[1].get("price", ""), alts[1].get("source", ""), r.reason, r.applied])
    json_path.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "settings": {k: v for k, v in vars(args).items()},
        "results": [asdict(r) for r in results],
    }, indent=2, default=str), encoding="utf-8")
    return csv_path, json_path


def print_summary(cells: list[dict], results: list[SlotResult]) -> None:
    by_cell = defaultdict(list)
    for r in results:
        by_cell[r.cell_id].append(r)
    print()
    print(f"{'Cell':<11} {'Build':<26} {'Filled':>7} {'Parts £':>9}  Missing")
    print("-" * 100)
    total_filled = total_slots = 0
    for cell in cells:
        rows = [r for r in by_cell[cell["id"]] if r.status not in {"software", "integrated"}]
        filled = [r for r in rows if r.status == "ready"]
        cost = sum(r.best["price"] for r in filled)
        missing = ", ".join(r.slot for r in rows if r.status != "ready") or "-"
        total_filled += len(filled)
        total_slots += len(rows)
        cost_txt = f"{cost:,.2f}" if len(filled) == len(rows) else f"({cost:,.2f})"
        print(f"{cell['id']:<11} {cell.get('name', '')[:26]:<26} {len(filled):>3}/{len(rows):<3} {cost_txt:>9}  {missing}")
    print("-" * 100)
    print(f"Slots filled with fresh real offers: {total_filled}/{total_slots}")
    print("Parts £ in brackets = incomplete build (sum of filled slots only). OS is priced by the software playbook.")
    integrated = sorted({r.cell_id for r in results if r.status == "integrated"})
    if integrated:
        print("Cells with integrated (non-retail) parts, which need a whole mini-PC/barebone offer: " + ", ".join(integrated))
    gaps = Counter()
    for r in results:
        if r.status in {"no_offer", "no_url"}:
            gaps["never scraped / no title match" if "never scraped" in r.reason else "matched but ineligible"] += 1
    if gaps:
        print("Gap causes:", ", ".join(f"{k}: {v}" for k, v in gaps.items()))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

async def main(args) -> None:
    from app.database import AsyncSessionLocal

    cells = json.loads(DEFINITIONS_PATH.read_text(encoding="utf-8"))["builds"]
    if args.cell:
        wanted = {c.strip().upper() for c in args.cell.split(",")}
        cells = [c for c in cells if c["id"].upper() in wanted]
        if not cells:
            raise SystemExit(f"No cells matched {args.cell}")

    async with AsyncSessionLocal() as db:
        pool = await load_pool(db, max(args.max_age_days, args.diagnostic_window_days))
        print(f"Loaded {len(pool):,} recent listing observations "
              f"(diagnostic window {max(args.max_age_days, args.diagnostic_window_days)} days, "
              f"eligibility window {args.max_age_days} days).")

        results: list[SlotResult] = []
        cell_results: dict[str, list[SlotResult]] = {}
        for cell in cells:
            rows = []
            for slot, spec in cell["components"].items():
                r = SlotResult(cell["id"], cell["segment"], cell["tier"], slot, spec, status="no_offer")
                if slot in SOFTWARE_SLOTS:
                    r.status, r.reason = "software", "software licence: priced by the software playbook"
                    rows.append(r)
                    continue
                if INTEGRATED_PATTERN.search(spec):
                    r.status = "integrated"
                    r.reason = "not a separate retail part: priced with the host product (mini-PC/APU/boxed cooler)"
                    rows.append(r)
                    continue
                note = ""
                if slot == "storage" and "+" in spec:
                    note = "only the primary drive is priced; the secondary drive after '+' needs its own offer. "
                eligible, diag = choose_offers(slot, spec, pool, args)
                r.eligible_count = len(eligible)
                r.diagnostics = dict(diag)
                with_url = [o for o in eligible if o.url]
                r.reason = note
                if with_url:
                    r.status = "ready"
                    r.best = offer_dict(with_url[0])
                    r.best["image_url"] = with_url[0].image_url
                    r.alternatives = [offer_dict(o) for o in with_url[1:3]]
                elif eligible:
                    r.status, r.reason = "no_url", note + "eligible offers exist but none has a stored product URL"
                else:
                    r.reason = note + explain_empty(diag)
                rows.append(r)
            cell_results[cell["id"]] = rows
            results.extend(rows)

        if args.apply:
            lookups = await build_lookups(db)
            for cell in cells:
                await apply_cell(db, cell, cell_results[cell["id"]], lookups)
            await db.commit()
            print("Applied: segment components now point at real offers. "
                  "Review proposed selling prices and approve components in the admin.")
        else:
            print("Dry run: nothing written to the database. Re-run with --apply to link offers.")

    print_summary(cells, results)
    csv_path, json_path = write_reports(results, args)
    print(f"\nReport: {csv_path}\n        {json_path}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true", help="link winning offers into curated segments")
    p.add_argument("--cell", help="comma-separated cell IDs, e.g. FF-GVG-01,FF-AIW-02")
    p.add_argument("--max-age-days", type=int, default=14, help="offer must have been seen within N days (default 14)")
    p.add_argument("--diagnostic-window-days", type=int, default=90, help="older sightings used only to explain gaps")
    p.add_argument("--conditions", default="new", help="allowed conditions, comma-separated (default: new)")
    p.add_argument("--exclude-sources", default="temu,aliexpress,alibaba,vinted,wish",
                   help="sources never used for curated pricing")
    p.add_argument("--outlier-floor", type=float, default=0.4,
                   help="drop offers below this fraction of the median eligible price (default 0.4)")
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
