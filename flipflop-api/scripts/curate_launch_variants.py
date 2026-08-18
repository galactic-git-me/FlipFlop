"""Apply the launch visibility policy to Curated Build catalogue variants.

Core components expose one median-priced choice per playbook. RAM and storage
remain customer-selectable, so every active catalogue option is exposed.
"""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.playbook import Playbook
from app.models.listing import Listing


CUSTOMER_SELECTABLE = {"ram", "storage"}

INCLUDE = {
    "cpu": re.compile(r"\b(cpu|processor)\b", re.I),
    "gpu": re.compile(r"\b(gpu|graphics card|rtx|gtx|radeon|geforce)\b", re.I),
    "ram": re.compile(r"\b(ram|memory)\b", re.I),
    "storage": re.compile(r"\b(nvme|ssd|hdd|hard drive)\b", re.I),
    "motherboard": re.compile(r"\b(motherboard|mainboard)\b", re.I),
    "psu": re.compile(r"\b(psu|power supply)\b", re.I),
}
EXCLUDE = re.compile(
    r"\b(desktop pc|gaming pc|workstation pc|pc tower|thinkcentre|optiplex|"
    r"prodesk|elitedesk|acer aspire|job lot|cooler fan only)\b",
    re.I,
)


async def curate() -> None:
    async with AsyncSessionLocal() as db:
        playbook_ids = (
            await db.execute(select(Playbook.id).where(Playbook.status == "active"))
        ).scalars().all()
        slots = (
            await db.execute(
                select(PlaybookSlot).where(PlaybookSlot.playbook_id.in_(playbook_ids))
            )
        ).scalars().all()

        for slot in slots:
            rows = (
                await db.execute(
                    select(CatalogueVariant, Listing.title)
                    .join(Listing, CatalogueVariant.listing_id == Listing.id)
                    .where(CatalogueVariant.slot_id == slot.id)
                    .order_by(CatalogueVariant.display_price, CatalogueVariant.id)
                )
            ).all()
            variants = [variant for variant, _ in rows]
            if not variants:
                continue

            include = INCLUDE.get(slot.slot_type)
            eligible = [
                variant
                for variant, title in rows
                if include is not None
                and include.search(title)
                and not EXCLUDE.search(title)
                and (slot.slot_type != "ram" or re.search(r"\b(ddr[345]|pc[34]l?[- ])", title, re.I))
            ]

            visible_ids = (
                {variant.id for variant in eligible}
                if slot.slot_type in CUSTOMER_SELECTABLE
                else ({eligible[len(eligible) // 2].id} if eligible else set())
            )
            visibility_rows = (
                await db.execute(
                    select(ConfiguratorCatalogueVisibility).where(
                        ConfiguratorCatalogueVisibility.playbook_slot_id == slot.id
                    )
                )
            ).scalars().all()
            by_variant = {row.catalogue_variant_id: row for row in visibility_rows}

            for order, variant in enumerate(variants):
                variant.status = "active" if variant.id in visible_ids else "hidden"
                row = by_variant.get(variant.id)
                if row is None:
                    row = ConfiguratorCatalogueVisibility(
                        playbook_slot_id=slot.id,
                        catalogue_variant_id=variant.id,
                    )
                    db.add(row)
                row.is_publicly_visible = variant.id in visible_ids
                row.display_order = order

        await db.commit()


if __name__ == "__main__":
    asyncio.run(curate())
