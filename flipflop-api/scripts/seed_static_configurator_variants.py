"""Seed stable configurator choices that do not come from marketplace scans."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing, ListingStatus
from app.models.playbook import Playbook


STATIC_CHOICES = {
    "cooling": [("mid", "Quiet tower CPU cooler", 35.0)],
    "fan": [("mid", "3 × 120 mm PWM case fans", 24.0)],
    "os": [
        ("budget", "No operating system", 0.0),
        ("mid", "Windows 11 Home", 109.0),
        ("high", "Windows 11 Pro", 159.0),
    ],
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        playbooks = (await db.execute(
            select(Playbook).where(Playbook.status == "active")
        )).scalars().all()

        for playbook in playbooks:
            slots = (await db.execute(
                select(PlaybookSlot).where(PlaybookSlot.playbook_id == playbook.id)
            )).scalars().all()
            for slot in slots:
                choices = STATIC_CHOICES.get(slot.slot_type)
                if not choices:
                    continue
                for order, (tier, title, price) in enumerate(choices):
                    external_id = f"configurator:{slot.slot_type}:{title.lower().replace(' ', '-')}"
                    listing = (await db.execute(
                        select(Listing).where(Listing.external_id == external_id)
                    )).scalar_one_or_none()
                    if listing is None:
                        listing = Listing(
                            external_id=external_id,
                            source_id=0,
                            source_name="FlipFlop fixed catalogue",
                            title=title,
                            price=price,
                            url="https://theflipflop.shop/curated-builds",
                            status=ListingStatus.active,
                        )
                        db.add(listing)
                        await db.flush()

                    variant = (await db.execute(
                        select(CatalogueVariant).where(
                            CatalogueVariant.slot_id == slot.id,
                            CatalogueVariant.listing_id == listing.id,
                        )
                    )).scalar_one_or_none()
                    if variant is None:
                        variant = CatalogueVariant(
                            listing_id=listing.id,
                            slot_id=slot.id,
                            status="active",
                            display_price=price,
                            tier=tier,
                        )
                        db.add(variant)
                        await db.flush()
                    else:
                        variant.status = "active"
                        variant.display_price = price
                        variant.tier = tier

                    visibility = (await db.execute(
                        select(ConfiguratorCatalogueVisibility).where(
                            ConfiguratorCatalogueVisibility.playbook_slot_id == slot.id,
                            ConfiguratorCatalogueVisibility.catalogue_variant_id == variant.id,
                        )
                    )).scalar_one_or_none()
                    if visibility is None:
                        db.add(ConfiguratorCatalogueVisibility(
                            playbook_slot_id=slot.id,
                            catalogue_variant_id=variant.id,
                            is_publicly_visible=True,
                            display_order=order,
                        ))
                    else:
                        visibility.is_publicly_visible = True
                        visibility.display_order = order

        await db.commit()
        print(f"Seeded static choices for {len(playbooks)} active playbooks")


if __name__ == "__main__":
    asyncio.run(main())
