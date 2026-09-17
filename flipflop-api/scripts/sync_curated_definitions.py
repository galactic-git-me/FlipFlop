"""Publish the static curated-build definitions into the live catalogue.

This is intentionally idempotent. It creates one active catalogue variant for
each exact component title in data/curated_build_definitions.json and makes
those variants public for the matching playbook slot.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing, ListingStatus
from app.models.playbook import Playbook


def tier_key(value: str) -> str:
    value = value.lower()
    if "high" in value:
        return "high"
    if "mid" in value:
        return "mid"
    return "budget"


async def main() -> None:
    definitions = json.loads(
        (Path(__file__).resolve().parents[1] / "data/curated_build_definitions.json")
        .read_text(encoding="utf-8")
    )

    async with AsyncSessionLocal() as db:
        playbooks = {
            row.name: row
            for row in (await db.execute(select(Playbook).where(Playbook.status == "active")))
            .scalars()
            .all()
        }
        slots = {
            (row.playbook_id, row.slot_type): row
            for row in (await db.execute(select(PlaybookSlot))).scalars().all()
        }
        created = 0
        published = 0

        for build in definitions["builds"]:
            playbook = playbooks.get(build["segment"])
            if not playbook:
                continue
            tier = tier_key(build["tier"])
            for slot_type, title in build["components"].items():
                if slot_type == "case":
                    continue
                slot = slots.get((playbook.id, slot_type))
                if not slot:
                    continue
                external_id = f"curated-definition:{build['id']}:{slot_type}"
                listing = (
                    await db.execute(select(Listing).where(Listing.external_id == external_id))
                ).scalar_one_or_none()
                if listing is None:
                    listing = Listing(
                        external_id=external_id,
                        source_id=0,
                        source_name="FlipFlop curated definitions",
                        title=title,
                        price=0.0,
                        url="https://www.theflipflop.shop/builds",
                        status=ListingStatus.active,
                    )
                    db.add(listing)
                    await db.flush()
                    created += 1
                else:
                    listing.title = title
                    listing.status = ListingStatus.active

                variant = (
                    await db.execute(
                        select(CatalogueVariant).where(
                            CatalogueVariant.slot_id == slot.id,
                            CatalogueVariant.listing_id == listing.id,
                        )
                    )
                ).scalar_one_or_none()
                if variant is None:
                    variant = CatalogueVariant(
                        listing_id=listing.id,
                        slot_id=slot.id,
                        status="active",
                        display_price=0.0,
                        tier=tier,
                    )
                    db.add(variant)
                    await db.flush()
                else:
                    variant.status = "active"
                    variant.tier = tier

                visibility = (
                    await db.execute(
                        select(ConfiguratorCatalogueVisibility).where(
                            ConfiguratorCatalogueVisibility.playbook_slot_id == slot.id,
                            ConfiguratorCatalogueVisibility.catalogue_variant_id == variant.id,
                        )
                    )
                ).scalar_one_or_none()
                if visibility is None:
                    visibility = ConfiguratorCatalogueVisibility(
                        playbook_slot_id=slot.id,
                        catalogue_variant_id=variant.id,
                    )
                    db.add(visibility)
                visibility.is_publicly_visible = True
                visibility.display_order = 0
                published += 1

        await db.commit()
        print(f"Synced {published} curated component variants ({created} listings created)")


if __name__ == "__main__":
    asyncio.run(main())
