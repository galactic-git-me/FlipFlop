#!/usr/bin/env python3
"""
Seed default PlaybookSlot rows for all active playbooks.

Run once after Task 6 is deployed:
    cd pc-flipper-backend
    python scripts/seed_catalogue_slots.py

Safe to re-run — uses upsert logic (insert if not exists).
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.playbook import Playbook
from app.models.catalogue import PlaybookSlot

# Slot visibility per playbook keyword.
# Matches on playbook.name (case-insensitive substring).
# Playbooks NOT matched here get the "generic" slot set.
PLAYBOOK_PROFILES = {
    "gaming": {
        "tier_names": {"budget": "Starter", "mid": "Battle-Ready", "high": "Beast Mode"},
        "visible": {"cpu", "gpu", "ram", "storage", "cooling", "os"},
    },
    "ai": {
        "tier_names": {"budget": "Foundation", "mid": "Accelerator", "high": "Powerhouse"},
        "visible": {"cpu", "gpu", "ram", "storage", "cooling", "os"},
    },
    "creative": {
        "tier_names": {"budget": "Essentials", "mid": "Professional", "high": "Elite"},
        "visible": {"cpu", "gpu", "ram", "storage", "cooling", "os"},
    },
    "build": {  # "Build Your Own"
        "tier_names": {"budget": "Budget", "mid": "Mid-Range", "high": "High End"},
        "visible": {"cpu", "gpu", "ram", "storage", "cooling", "os"},
    },
    "home": {
        "tier_names": {"budget": "Basic", "mid": "Balanced", "high": "Premium"},
        "visible": {"cpu", "ram", "storage", "os"},
    },
    "business": {
        "tier_names": {"budget": "Basic", "mid": "Balanced", "high": "Premium"},
        "visible": {"cpu", "ram", "storage", "os"},
    },
    "student": {
        "tier_names": {"budget": "Essential", "mid": "Capable", "high": "Top of Class"},
        "visible": {"cpu", "ram", "storage", "os"},
    },
}

ALL_SLOTS = ["cpu", "gpu", "ram", "storage", "cooling", "os"]

DEFAULT_SCORE_BANDS = {
    "score_band_budget": [40, 65],
    "score_band_mid": [65, 80],
    "score_band_high": [80, 100],
}


def get_profile(playbook_name: str) -> dict:
    name_lower = playbook_name.lower()
    for key, profile in PLAYBOOK_PROFILES.items():
        if key in name_lower:
            return profile
    return {
        "tier_names": {"budget": "Budget", "mid": "Mid-Range", "high": "High End"},
        "visible": {"cpu", "ram", "storage", "os"},
    }


async def seed():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Playbook).where(Playbook.status == "active"))
        playbooks = result.scalars().all()

        if not playbooks:
            print("No active playbooks found. Run the playbook seeder first.")
            return

        created = 0
        skipped = 0

        for pb in playbooks:
            profile = get_profile(pb.name)
            for slot_type in ALL_SLOTS:
                # Skip if already exists
                existing = await db.execute(
                    select(PlaybookSlot).where(
                        PlaybookSlot.playbook_id == pb.id,
                        PlaybookSlot.slot_type == slot_type,
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                slot = PlaybookSlot(
                    playbook_id=pb.id,
                    slot_type=slot_type,
                    is_customer_visible=(slot_type in profile["visible"]),
                    tier_names=profile["tier_names"],
                    **DEFAULT_SCORE_BANDS,
                )
                db.add(slot)
                created += 1
                print(f"  + {pb.name} / {slot_type} (visible={slot_type in profile['visible']})")

        await db.commit()
        print(f"\nDone. Created {created} slots, skipped {skipped} existing.")


if __name__ == "__main__":
    asyncio.run(seed())
