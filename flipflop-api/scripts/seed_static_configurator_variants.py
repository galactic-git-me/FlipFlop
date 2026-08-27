"""Seed stable configurator choices that do not come from marketplace scans."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update

from app.database import AsyncSessionLocal
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing, ListingStatus
from app.models.playbook import Playbook


TIERS = ("budget", "mid", "high")

# Stable sellable specifications. Marketplace scans may later resolve these to
# procurement offers, but must never redefine what each curated tier means.
COMMON = {
    "ram": [
        ("budget", "16 GB DDR4 memory", 45.0),
        ("mid", "32 GB DDR4 memory", 75.0),
        ("high", "32 GB DDR5 memory", 115.0),
    ],
    "storage": [
        ("budget", "1 TB NVMe SSD", 65.0),
        ("mid", "2 TB NVMe SSD", 115.0),
        ("high", "2 TB high-performance NVMe SSD", 165.0),
    ],
    "cooling": [
        ("budget", "Quiet tower CPU cooler", 35.0),
        ("mid", "Premium dual-tower CPU cooler", 65.0),
        ("high", "240 mm liquid CPU cooler", 105.0),
    ],
    "fan": [
        ("budget", "2 × 120 mm PWM case fans", 18.0),
        ("mid", "3 × 120 mm PWM case fans", 30.0),
        ("high", "4 × 120 mm PWM ARGB case fans", 55.0),
    ],
    "os": [
        ("budget", "No operating system", 0.0),
        ("mid", "Windows 11 Home", 109.0),
        ("high", "Windows 11 Pro", 159.0),
    ],
}

PURPOSE_CHOICES = {
    "Great-value Gaming": {
        "cpu": [("budget", "AMD Ryzen 5 5600", 105.0), ("mid", "AMD Ryzen 5 7600", 185.0), ("high", "AMD Ryzen 7 7700", 265.0)],
        "gpu": [("budget", "GeForce RTX 4060 8 GB", 285.0), ("mid", "Radeon RX 7800 XT 16 GB", 475.0), ("high", "GeForce RTX 4070 Super 12 GB", 565.0)],
        "motherboard": [("budget", "B550 ATX motherboard", 90.0), ("mid", "B650 ATX motherboard", 145.0), ("high", "Premium B650 Wi-Fi ATX motherboard", 195.0)],
        "psu": [("budget", "650 W 80 Plus Bronze PSU", 65.0), ("mid", "750 W 80 Plus Gold PSU", 95.0), ("high", "850 W 80 Plus Gold modular PSU", 125.0)],
    },
    "High-performance Gaming": {
        "cpu": [("budget", "AMD Ryzen 7 7700", 265.0), ("mid", "AMD Ryzen 7 7800X3D", 355.0), ("high", "AMD Ryzen 9 9950X3D", 665.0)],
        "gpu": [("budget", "GeForce RTX 4070 Super 12 GB", 565.0), ("mid", "GeForce RTX 5080 16 GB", 1099.0), ("high", "GeForce RTX 5090 32 GB", 2099.0)],
        "motherboard": [("budget", "B650 Wi-Fi ATX motherboard", 165.0), ("mid", "X870 Wi-Fi ATX motherboard", 285.0), ("high", "Premium X870E ATX motherboard", 425.0)],
        "psu": [("budget", "850 W 80 Plus Gold modular PSU", 125.0), ("mid", "1000 W 80 Plus Gold ATX 3 PSU", 175.0), ("high", "1200 W 80 Plus Platinum ATX 3 PSU", 255.0)],
    },
    "Student Hybrid": {
        "cpu": [("budget", "AMD Ryzen 5 5600G", 115.0), ("mid", "AMD Ryzen 5 7600", 185.0), ("high", "AMD Ryzen 7 7700", 265.0)],
        "gpu": [("budget", "Integrated Radeon graphics", 0.0), ("mid", "GeForce RTX 4060 8 GB", 285.0), ("high", "GeForce RTX 4070 12 GB", 495.0)],
        "motherboard": [("budget", "B550 micro-ATX motherboard", 80.0), ("mid", "B650 micro-ATX Wi-Fi motherboard", 135.0), ("high", "B650 ATX Wi-Fi motherboard", 175.0)],
        "psu": [("budget", "550 W 80 Plus Bronze PSU", 55.0), ("mid", "650 W 80 Plus Gold PSU", 80.0), ("high", "750 W 80 Plus Gold modular PSU", 105.0)],
    },
    "Business & Office": {
        "cpu": [("budget", "Intel Core i3-14100", 115.0), ("mid", "Intel Core i5-14500", 225.0), ("high", "Intel Core i7-14700", 355.0)],
        "gpu": [("budget", "Integrated Intel graphics", 0.0), ("mid", "Integrated Intel graphics", 0.0), ("high", "NVIDIA RTX A1000 8 GB", 385.0)],
        "motherboard": [("budget", "H610 micro-ATX motherboard", 75.0), ("mid", "B760 micro-ATX Wi-Fi motherboard", 135.0), ("high", "B760 ATX Wi-Fi motherboard", 175.0)],
        "psu": [("budget", "450 W 80 Plus Bronze PSU", 48.0), ("mid", "550 W 80 Plus Gold PSU", 70.0), ("high", "650 W 80 Plus Gold modular PSU", 90.0)],
    },
    "Content Creation": {
        "cpu": [("budget", "AMD Ryzen 7 7700", 265.0), ("mid", "AMD Ryzen 9 7900X", 365.0), ("high", "AMD Ryzen 9 9950X", 585.0)],
        "gpu": [("budget", "GeForce RTX 4060 Ti 16 GB", 445.0), ("mid", "GeForce RTX 5070 Ti 16 GB", 795.0), ("high", "GeForce RTX 5090 32 GB", 2099.0)],
        "motherboard": [("budget", "B650 ATX motherboard", 145.0), ("mid", "X870 Wi-Fi ATX motherboard", 285.0), ("high", "Creator X870E 10 GbE motherboard", 525.0)],
        "psu": [("budget", "750 W 80 Plus Gold PSU", 95.0), ("mid", "1000 W 80 Plus Gold ATX 3 PSU", 175.0), ("high", "1200 W 80 Plus Platinum ATX 3 PSU", 255.0)],
    },
    "AI Workstation": {
        "cpu": [("budget", "AMD Ryzen 9 7900X", 365.0), ("mid", "AMD Ryzen 9 9950X", 585.0), ("high", "AMD Threadripper 7970X", 2350.0)],
        "gpu": [("budget", "GeForce RTX 3090 24 GB refurbished", 725.0), ("mid", "GeForce RTX 5090 32 GB", 2099.0), ("high", "NVIDIA RTX PRO 6000 Blackwell 96 GB", 8299.0)],
        "motherboard": [("budget", "X670E ATX motherboard", 285.0), ("mid", "Premium X870E ATX motherboard", 425.0), ("high", "TRX50 workstation motherboard", 795.0)],
        "psu": [("budget", "1000 W 80 Plus Gold ATX 3 PSU", 175.0), ("mid", "1200 W 80 Plus Platinum ATX 3 PSU", 255.0), ("high", "1600 W 80 Plus Titanium PSU", 475.0)],
    },
    "Software Development": {
        "cpu": [("budget", "AMD Ryzen 7 7700", 265.0), ("mid", "AMD Ryzen 9 7900X", 365.0), ("high", "AMD Ryzen 9 9950X", 585.0)],
        "gpu": [("budget", "Integrated Radeon graphics", 0.0), ("mid", "GeForce RTX 4060 8 GB", 285.0), ("high", "GeForce RTX 5070 12 GB", 595.0)],
        "motherboard": [("budget", "B650 micro-ATX Wi-Fi motherboard", 135.0), ("mid", "B650 ATX Wi-Fi motherboard", 175.0), ("high", "X870E ATX motherboard", 355.0)],
        "psu": [("budget", "550 W 80 Plus Gold PSU", 70.0), ("mid", "650 W 80 Plus Gold modular PSU", 90.0), ("high", "850 W 80 Plus Gold modular PSU", 125.0)],
    },
    "Family & Home": {
        "cpu": [("budget", "AMD Ryzen 5 5600G", 115.0), ("mid", "AMD Ryzen 5 7600", 185.0), ("high", "AMD Ryzen 7 7700", 265.0)],
        "gpu": [("budget", "Integrated Radeon graphics", 0.0), ("mid", "GeForce RTX 4060 8 GB", 285.0), ("high", "GeForce RTX 4070 12 GB", 495.0)],
        "motherboard": [("budget", "B550 micro-ATX motherboard", 80.0), ("mid", "B650 micro-ATX Wi-Fi motherboard", 135.0), ("high", "B650 ATX Wi-Fi motherboard", 175.0)],
        "psu": [("budget", "500 W 80 Plus Bronze PSU", 52.0), ("mid", "650 W 80 Plus Gold PSU", 80.0), ("high", "750 W 80 Plus Gold modular PSU", 105.0)],
    },
}


def choices_for(playbook_name: str, slot_type: str):
    return PURPOSE_CHOICES.get(playbook_name, {}).get(slot_type) or COMMON.get(slot_type)


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
                choices = choices_for(playbook.name, slot.slot_type)
                if not choices:
                    continue
                # Once a slot is curated, only explicit fixed choices remain
                # public. Marketplace candidates stay in the admin catalogue.
                await db.execute(
                    update(ConfiguratorCatalogueVisibility)
                    .where(ConfiguratorCatalogueVisibility.playbook_slot_id == slot.id)
                    .values(is_publicly_visible=False)
                )
                for order, (tier, title, price) in enumerate(choices):
                    external_id = f"configurator:{playbook.name}:{slot.slot_type}:{tier}"
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
                            url="https://theflipflop.shop/builds",
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
                        listing.title = title
                        listing.price = price
                        listing.status = ListingStatus.active
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
