import asyncio
from collections import Counter
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.gem_radar_observation import GemRadarListingObservation
from app.gem_radar import identity as identity_mod


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GemRadarListingObservation.title, GemRadarListingObservation.category)
            .limit(5000)
        )
        rows = result.all()
        print(f"Sampled {len(rows)} observations")

        no_model_by_category: Counter = Counter()
        total_by_category: Counter = Counter()
        no_model_examples: dict = {}

        for title, category in rows:
            cat_key = category or "UNCATEGORISED"
            total_by_category[cat_key] += 1
            if identity_mod.is_likely_accessory(title):
                continue
            resolved = identity_mod.resolve_identity(title)
            if not resolved.model:
                no_model_by_category[cat_key] += 1
                no_model_examples.setdefault(cat_key, []).append(title)

        print("\n=== Failure rate by category (no model resolved) ===")
        for cat, total in total_by_category.most_common():
            failed = no_model_by_category.get(cat, 0)
            pct = 100 * failed / total if total else 0
            print(f"  {cat:15s}  {failed:5d}/{total:5d}  ({pct:.0f}%)")

        print("\n=== Example titles that failed to resolve, per category ===")
        for cat, examples in no_model_examples.items():
            print(f"\n--- {cat} ({len(examples)} failures) ---")
            for t in examples[:6]:
                print(f"  {t}")

        print("\n\n=== Stress test: deliberate title-format variants ===")
        variants = [
            ("Intel Core i7-10850H", "Intel i7 10850H"),
            ("Intel Core i7-10850H", "Intel Core i7 10850H CPU Processor"),
            ("AMD Ryzen 5 5600X", "Ryzen 5 5600X AMD"),
            ("AMD Ryzen 5 5600X", "AMD Ryzen 5600X (no space before model)"),
            ("Nvidia RTX 3080", "RTX3080"),
            ("Nvidia GeForce RTX 3080", "NVIDIA GEFORCE RTX 3080 10GB"),
            ("Corsair Vengeance 32GB DDR4 3200", "32GB (2x16GB) DDR4 3200MHz Corsair Vengeance RAM"),
        ]
        for title_a, title_b in variants:
            model_a = identity_mod.resolve_identity(title_a).model
            model_b = identity_mod.resolve_identity(title_b).model
            match = "MATCH" if model_a == model_b and model_a is not None else "MISMATCH"
            print(f"  [{match}] {title_a!r} -> {model_a!r}")
            print(f"           {title_b!r} -> {model_b!r}")


asyncio.run(main())
