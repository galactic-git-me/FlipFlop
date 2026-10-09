"""Assign deterministic case CPKs to historical Amazon bestseller observations.

Run from flipflop-api: python -m scripts.backfill_case_bestseller_cpks --apply
Without --apply, only reports the number of rows that would change.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.services.case_product_key import case_product_key


async def run(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AmazonBestsellerObservation).where(AmazonBestsellerObservation.category == "case")
        )).scalars().all()
        changed = 0
        for row in rows:
            cpk = case_product_key(row.title)
            if row.cpk != cpk:
                changed += 1
                if apply:
                    row.cpk = cpk
        if apply:
            await db.commit()
        print(f"Case observations: {len(rows)}; CPKs {'updated' if apply else 'to update'}: {changed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
