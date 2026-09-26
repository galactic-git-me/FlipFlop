"""Assign the 24 curated builds from captured Amazon bestseller products.

Selections are product identities (CPKs), not supplier offers or approvals.
Run without arguments to audit the exact matches; pass --apply to persist.
"""

import argparse
import asyncio
import json
import re
from pathlib import Path

from sqlalchemy import text

from app.database import AsyncSessionLocal


# Each expression identifies a specific product or a clearly equivalent spec.
# The first valid ranked Amazon product wins within an expression.
PRODUCTS = {
    "cpu": {
        "5600x": r"\b5600x\b", "8600g": r"\b8600g\b", "9600x": r"\b9600x\b",
        "9700x": r"\b9700x\b", "7800x3d": r"\b7800x3d\b",
        "9800x3d": r"\b9800x\s*3d\b|\b9800x3d\b", "9850x3d": r"\b9850x3d\b",
        "9950x": r"\b9950x\b(?!3d)", "9950x3d": r"\b9950x3d\b",
        "250k": r"\b250k\s+plus\b", "270k": r"\b270k\s+plus\b",
    },
    "motherboard": {
        "b550m": r"\bB550M\s+PRO.VDH\s+WIFI\b",
        "b850m": r"\bPRIME\s+B850M.A\s+Wi.Fi\b",
        "b850": r"\bB850\s+GAMING\s+PLUS\s+WIFI(?:6E)?\b",
        "b850_tomahawk": r"\bB850\s+TOMAHAWK\s+MAX\s+WIFI\b",
        "x870": r"\bX870.PLUS\s+WIFI\b",
        "x870e": r"\bProArt\s+X870E.Creator\s+WiFi\b",
        "z890": r"\bPRO\s+Z890.A\s+WIFI\b|\bPRIME\s+Z890.P\s+WIFI\b",
    },
    "ram": {
        "ddr4_32": r"(?:DDR4.{0,30}32GB|32GB.{0,30}DDR4).{0,50}3200",
        "ddr5_16": r"(?:DDR5.{0,30}16GB|16GB.{0,30}DDR5).{0,50}(?:5600|6000)",
        "ddr5_32": r"(?:DDR5.{0,30}32GB|32GB.{0,30}DDR5).{0,50}6000.{0,20}CL30",
        "ddr5_64": r"(?:DDR5.{0,30}64GB|64GB.{0,30}DDR5).{0,50}6000.{0,20}CL30",
        "ddr5_96": r"(?:DDR5.{0,30}96GB|96GB.{0,30}DDR5).{0,50}6000",
    },
    "gpu": {
        "5050": r"\bRTX\s+5050\b.{0,50}\b8G(?:B)?\b",
        "b580": r"\bArc\s+B580\b.{0,50}\b12G(?:B)?\b",
        "9060xt": r"\bRX\s+9060\s+XT\b.{0,60}\b16G(?:B)?\b",
        "9070": r"\bRX\s+9070\b(?!\s*XT).{0,60}\b16G(?:B)?\b",
        "9070xt": r"\bRX\s+9070\s+XT\b.{0,60}\b16G(?:B)?\b",
        "5060ti16": r"\bRTX\s+5060\s+Ti\b.{0,60}\b16G(?:B)?\b",
        "5070ti16": r"\bRTX\s+5070\s+Ti\b.{0,60}\b16G(?:B)?\b",
        "5080": r"\bRTX\s+5080\b.{0,60}\b16G(?:B)?\b",
        "5090": r"\bRTX\s+5090\b.{0,60}\b32G(?:B)?\b(?!.*\bBOX\b)",
        "r9700": r"\bR9700\b.{0,60}\b32G(?:B)?\b",
    },
    "storage": {
        "512gb": r"\b512GB\b.{0,55}\bNVMe\b|\bNVMe\b.{0,55}\b512GB\b",
        "1tb": r"\b1TB\b.{0,65}\b(?:NVMe|PCIe\s*(?:Gen)?\s*4)\b",
        "2tb": r"\b2TB\b.{0,65}\b(?:NVMe|PCIe\s*(?:Gen)?\s*4)\b",
        "4tb": r"\b4TB\b.{0,65}\b(?:NVMe|PCIe\s*(?:Gen)?\s*4)\b",
    },
    "case": {
        "office": r"\bCiT\s+Work\s+Office\s+PC\s+Case\b",
        "compact": r"\bLian\s+Li\s+A3\s+mATX\s+PC\s+Case\b",
        "h3": r"\bNZXT\s+H3\s+Flow\b",
        "h5": r"\bNZXT\s+H5\s+Flow\b",
        "corsair3500": r"\bCORSAIR\s+3500X\b",
        "northxl": r"\bFractal\s+Design\s+North\s+XL\b",
        "quiet": r"\bbe\s+quiet!\s+Pure\s+Base\s+501\b",
    },
    "psu": {
        "650bronze": r"\bMSI\s+MAG\s+A650BN\b",
        "750gold": r"\bCORSAIR\s+RM750e\b",
        "850gold": r"\bCORSAIR\s+RM850e\b",
        "1000gold": r"\bCORSAIR\s+RM1000x\b(?!\s+SHIFT)",
        "1200plat": r"\bCORSAIR\s+HX1200i\b",
        "1600titanium": r"\bSeasonic\s+PRIME\s+TX.1600\b",
    },
    "cooler": {
        "assassin": r"\bThermalright\s+Assassin\s+X\s+120R\s+SE\b",
        "peerless": r"\bThermalright\s+Peerless\s+Assassin\s+120\s+SE\b",
        "phantom": r"\bPhantom\s+Spirit\s+120\s+(?:SE|EVO)\b",
        "freezer36": r"\bARCTIC\s+Freezer\s+36\b",
        "aio240": r"\bbe\s+quiet!\s+Pure\s+Loop\s+3\s+240mm\b",
        "aio360": r"\bARCTIC\s+Liquid\s+Freezer\s+III\s+Pro\s+360\b",
    },
}


# Customer purpose is reflected in CPU/GPU/RAM, cooling, acoustics and case.
# "integrated" means the chosen CPU supplies graphics; no separate card is bought.
PROFILES = {
    "Galileo": ("5600x", "b550m", "ddr4_32", "5050", "1tb", "h3", "650bronze", "assassin"),
    "Cerritos": ("9600x", "b850", "ddr5_32", "9060xt", "2tb", "h5", "750gold", "peerless"),
    "Voyager": ("9800x3d", "x870", "ddr5_32", "9070", "2tb", "northxl", "850gold", "aio360"),
    "Columbus": ("250k", "z890", "ddr5_32", "5060ti16", "1tb", "h5", "750gold", "phantom"),
    "Defiant": ("7800x3d", "b850_tomahawk", "ddr5_32", "9070xt", "2tb", "corsair3500", "850gold", "aio240"),
    "Titan": ("9850x3d", "x870e", "ddr5_64", "5090", "4tb", "northxl", "1200plat", "aio360"),
    "Copernicus": ("8600g", "b850m", "ddr5_16", "integrated", "512gb", "compact", "650bronze", "assassin"),
    "Equinox": ("9600x", "b850", "ddr5_32", "b580", "2tb", "h5", "650bronze", "assassin"),
    "Discovery": ("270k", "z890", "ddr5_64", "5070ti16", "2tb", "northxl", "850gold", "aio240"),
    "Hawking": ("8600g", "b850m", "ddr5_16", "integrated", "512gb", "office", "650bronze", "assassin"),
    "Reliant": ("250k", "z890", "ddr5_32", "integrated", "2tb", "quiet", "650bronze", "freezer36"),
    "Excelsior": ("9700x", "b850m", "ddr5_64", "integrated", "2tb", "compact", "650bronze", "peerless"),
    "Goddard": ("250k", "z890", "ddr5_64", "5060ti16", "2tb", "corsair3500", "750gold", "aio240"),
    "Stargazer": ("270k", "z890", "ddr5_64", "5080", "4tb", "northxl", "1000gold", "aio360"),
    "Odyssey": ("9950x", "x870e", "ddr5_96", "5090", "4tb", "northxl", "1200plat", "aio360"),
    "Chaffee": ("9600x", "b850", "ddr5_64", "5060ti16", "2tb", "h5", "750gold", "peerless"),
    "Rhode Island": ("9950x", "x870e", "ddr5_96", "r9700", "4tb", "northxl", "1000gold", "aio360"),
    "Enterprise": ("9950x3d", "x870e", "ddr5_96", "5090", "4tb", "northxl", "1600titanium", "aio360"),
    "Sakharov": ("9600x", "b850", "ddr5_64", "b580", "2tb", "h5", "750gold", "peerless"),
    "Protostar": ("270k", "z890", "ddr5_96", "5060ti16", "4tb", "northxl", "850gold", "phantom"),
    "Prometheus": ("9950x", "x870e", "ddr5_96", "5080", "4tb", "northxl", "1000gold", "aio360"),
    "Cochrane": ("8600g", "b850m", "ddr5_16", "integrated", "512gb", "office", "650bronze", "assassin"),
    "Grissom": ("9600x", "b850", "ddr5_32", "9060xt", "2tb", "h5", "750gold", "assassin"),
    "Galaxy": ("9700x", "x870", "ddr5_64", "9070", "4tb", "corsair3500", "850gold", "aio240"),
}

SLOTS = ("cpu", "motherboard", "ram", "gpu", "storage", "case", "psu", "cooling")
CATEGORY = {"cooling": "cooler", **{slot: slot for slot in SLOTS if slot != "cooling"}}


async def main(apply: bool) -> None:
    builds = json.loads((Path(__file__).resolve().parents[2] / "tmp" / "curated-playbooks-v1-stub.json").read_text(encoding="utf-8"))["playbooks"]
    if {b["name"] for b in builds} != set(PROFILES):
        raise RuntimeError("Profile names must exactly match the 24 playbooks")
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT DISTINCT ON (category, cpk) category, cpk, title, rank, price
            FROM amazon_bestseller_observations
            WHERE cpk IS NOT NULL
            ORDER BY category, cpk, captured_at DESC
        """))).mappings().all()
        segments = {(r.customer_type, r.budget_level): r for r in (await db.execute(text(
            "SELECT id, customer_type, budget_level, budget_min, budget_max FROM curated_build_segments"
        ))).all()}
        missing = []
        plan = []
        for build in builds:
            segment = segments.get((build["customer_type"], build["budget_tier"]))
            if segment is None:
                missing.append((build["name"], "segment missing"))
                continue
            choices = {}
            observed_total = 0.0
            missing_prices = 0
            for slot, key in zip(SLOTS, PROFILES[build["name"]], strict=True):
                if key == "integrated":
                    continue
                category = CATEGORY[slot]
                expression = PRODUCTS[category][key]
                candidates = [r for r in rows if r["category"] == category and re.search(expression, r["title"], re.I)]
                if not candidates:
                    missing.append((build["name"], slot, key))
                    continue
                candidates.sort(key=lambda r: (r["price"] is None, r["rank"] or 999, r["price"] or 0))
                chosen = candidates[0]
                choices[slot] = {"category": category, "cpk": chosen["cpk"]}
                observed_total += chosen["price"] or 0
                missing_prices += chosen["price"] is None
                print(f"{build['name']:16} {slot:12} #{chosen['rank']:3} {chosen['title'][:95]}")
            plan.append((segment.id, build["name"], choices))
            print(f"TOTAL {build['name']:16} Amazon £{observed_total:.2f} ({missing_prices} unpriced); customer range £{segment.budget_min or 0:.0f}–{segment.budget_max or 'open'}")
        print(f"\n{len(plan)} builds; {sum(len(c) for _, _, c in plan)} component selections; {len(missing)} missing choices")
        for gap in missing:
            print("MISSING", *gap)
        if apply:
            if missing:
                raise RuntimeError("Refusing partial playbook assignment; resolve missing bestseller products first")
            for segment_id, _, choices in plan:
                await db.execute(text("""
                    UPDATE curated_build_segments
                    SET bestseller_components = CAST(:choices AS json), is_live = false
                    WHERE id = :id
                """), {"choices": json.dumps(choices), "id": segment_id})
            await db.commit()
            print("Applied all 24 builds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
