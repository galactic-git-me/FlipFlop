"""Recommend Amazon bestseller CPKs for the curated playbook.

Dry run by default. Only ``--apply`` writes selections, and only selections
with a strong model/spec match are written. Approval remains a separate step.
"""

import argparse
import asyncio
import json
import math
import re
from pathlib import Path

from rapidfuzz import fuzz
from sqlalchemy import text

from app.database import AsyncSessionLocal


CATEGORIES = {
    "CPU / APU": ("cpu", "cpu"),
    "Motherboard": ("motherboard", "motherboard"),
    "Memory": ("ram", "ram"),
    "Graphics": ("gpu", "gpu"),
    "Primary storage": ("storage", "storage"),
    "Case": ("case", "case"),
    "Power supply": ("psu", "psu"),
    "CPU cooling": ("cooling", "cooler"),
}


def normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def model(value: str, category: str) -> str | None:
    value = normalise(value)
    patterns = {
        "cpu": r"\b(?:\d{4,5}(?:x3d|xt|x|g|f|wx)?|(?:250|270)k plus)\b",
        "gpu": r"\b(?:r9700|b580|(?:5050|5060|5070|5080|5090|9060|9070)(?: ti| xt)?)\b",
        "motherboard": r"\b(?:[abxzq]\d{3,4}[a-z]?)\b",
    }
    match = re.search(patterns.get(category, r"a^"), value)
    return match.group(0).replace(" ", "") if match else None


def capacity(value: str, category: str) -> int | None:
    value = normalise(value)
    if category == "ram":
        match = re.search(r"\b(16|32|64|96|128|256)gb\b", value)
        return int(match.group(1)) if match else None
    if category == "storage":
        match = re.search(r"\b(1|2|4|8)tb\b", value)
        return int(match.group(1)) if match else None
    if category == "psu":
        match = re.search(r"\b(450|500|550|600|650|700|750|850|1000|1200|1500|1600)w\b", value)
        return int(match.group(1)) if match else None
    return None


def compatibility_score(target: str, candidate: str, category: str) -> tuple[float, list[str]]:
    a, b = normalise(target), normalise(candidate)
    score = fuzz.token_set_ratio(a, b) * 0.55
    issues = []
    wanted_model, actual_model = model(target, category), model(candidate, category)
    if wanted_model:
        if wanted_model == actual_model:
            score += 65
        else:
            score -= 45
            issues.append(f"model {wanted_model} → {actual_model or 'unknown'}")
    wanted_capacity, actual_capacity = capacity(target, category), capacity(candidate, category)
    if wanted_capacity:
        if wanted_capacity == actual_capacity:
            score += 35
        else:
            score -= 35
            issues.append(f"capacity {wanted_capacity} → {actual_capacity or 'unknown'}")
    if category == "ram":
        for generation in ("ddr4", "ddr5", "lpddr5"):
            if generation in a and generation not in b:
                score -= 70
                issues.append(f"{generation} unavailable")
                break
    if category == "storage" and "nvme" in a and "nvme" not in b:
        score -= 60
        issues.append("not NVMe")
    if category == "gpu" and any(word in b for word in ("enclosure", "box", "laptop")):
        score -= 100
        issues.append("not a desktop card")
    if category == "cpu" and any(word in b for word in ("laptop", "mini pc", "desktop computer")):
        score -= 100
        issues.append("not a standalone CPU")
    if category == "case" and any(word in b for word in ("fan only", "cpu cooler")):
        score -= 100
    return score, issues


async def main(apply: bool) -> None:
    playbooks = json.loads((Path(__file__).resolve().parents[2] / "tmp" / "curated-playbooks-v1-stub.json").read_text(encoding="utf-8"))["playbooks"]
    async with AsyncSessionLocal() as db:
        candidates = (await db.execute(text("""
            SELECT DISTINCT ON (a.category, a.cpk) a.category, a.cpk, a.title,
                a.rank, a.price
            FROM amazon_bestseller_observations a
            WHERE a.cpk IS NOT NULL AND EXISTS (
                SELECT 1 FROM gem_radar_scored_listings s
                WHERE s.cpk = a.cpk AND s.delivered_price > 0
            )
            ORDER BY a.category, a.cpk, a.captured_at DESC
        """))).mappings().all()
        by_category = {category: [row for row in candidates if row["category"] == category] for _, category in CATEGORIES.values()}
        segments = {(row.customer_type, row.budget_level): row for row in (await db.execute(text("SELECT id, customer_type, budget_level, bestseller_components FROM curated_build_segments"))).all()}
        assignments = 0
        gaps = []
        for build in playbooks:
            key = (build["customer_type"], build["budget_tier"])
            segment = segments.get(key)
            if not segment:
                gaps.append((build["name"], "missing segment"))
                continue
            choices = dict(segment.bestseller_components or {})
            for component in build["core_components"]:
                spec = CATEGORIES.get(component["category"])
                if not spec:
                    continue
                slot, category = spec
                target = component["sku_name"]
                if "integrated" in target.casefold() or "included" in target.casefold():
                    gaps.append((build["name"], slot, "integrated or included in another component"))
                    continue
                ranked = sorted(by_category[category], key=lambda row: (
                    compatibility_score(target, row["title"], category)[0]
                    - math.log1p(max(row["rank"] or 1, 1))
                ), reverse=True)
                if not ranked:
                    gaps.append((build["name"], slot, "no bestseller match"))
                    continue
                best = ranked[0]
                score, issues = compatibility_score(target, best["title"], category)
                if issues or score < 75:
                    gaps.append((build["name"], slot, target, best["title"], round(score), issues))
                    continue
                choices[slot] = {"category": category, "cpk": best["cpk"]}
                assignments += 1
                print(f"{build['name']:16} {slot:12} #{best['rank']:3} {best['title'][:85]}")
            if apply:
                await db.execute(text("UPDATE curated_build_segments SET bestseller_components = :choices, is_live = false WHERE id = :id"), {"choices": json.dumps(choices), "id": segment.id})
        if apply:
            await db.commit()
        print(f"\n{'Applied' if apply else 'Dry run'}: {assignments} high-confidence assignments, {len(gaps)} gaps")
        for gap in gaps:
            print("GAP", *gap)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
