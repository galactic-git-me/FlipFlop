#!/usr/bin/env python3
"""Safely repair sold-observation CPK links from canonical identity fields.

Only exact, uniquely resolving normalised brand/model keys are applied. The
script deliberately refuses fuzzy prefix matching because a false comparable
is more damaging than a missing one on the buying decision surface.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import AsyncSessionLocal


def normalise(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


async def run(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        identities = (await db.execute(text("""
            SELECT DISTINCT cpk, cpk_data->>'brand', cpk_data->>'model'
            FROM gem_radar_listing_cpk
            WHERE cpk_data->>'brand' IS NOT NULL AND cpk_data->>'model' IS NOT NULL
        """))).all()
        candidates: dict[str, set[str]] = defaultdict(set)
        for cpk, brand, model in identities:
            for key in {normalise(model), normalise(f"{brand}{model}")}:
                if len(key) >= 5:
                    candidates[key].add(cpk)
        unambiguous = {key: next(iter(cpks)) for key, cpks in candidates.items() if len(cpks) == 1}
        sold_keys = (await db.execute(text("""
            SELECT match_key, COUNT(*) FROM gem_radar_sold_observations
            WHERE cpk IS NULL GROUP BY match_key
        """))).all()
        matches = [(key, unambiguous[key], count) for key, count in sold_keys if key in unambiguous]
        print(f"unambiguous_identity_keys={len(unambiguous)}")
        print(f"matched_sold_keys={len(matches)} observations={sum(row[2] for row in matches)}")
        if not apply:
            print("dry_run=true; pass --apply to write changes")
            return
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup = f"gem_radar_sold_observations_cpk_backup_{stamp}"
        await db.execute(text(f"CREATE TABLE {backup} AS TABLE gem_radar_sold_observations"))
        for key, cpk, _ in matches:
            await db.execute(text("""
                UPDATE gem_radar_sold_observations SET cpk=:cpk
                WHERE match_key=:key AND cpk IS NULL
            """), {"cpk": cpk, "key": key})
        await db.commit()
        print(f"applied=true backup={backup}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
