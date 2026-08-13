"""
Seed PlaybookSlots and CatalogueVariants for the configurator.

This script:
1. Creates standard slots (CPU, GPU, RAM, Storage, Cooling, OS) for each playbook
2. Pulls recent listings from the database and groups them by tier
3. Creates CatalogueVariants (component options)
4. Links them via ConfiguratorCatalogueVisibility
"""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.playbook import Playbook
from app.models.catalogue import PlaybookSlot, CatalogueVariant
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing
from app.database import Base

settings = get_settings()

# Map slot types to tier configuration
SLOT_CONFIG = {
    "cpu": {
        "tier_names": {"budget": "Budget CPU", "mid": "Mid-Range CPU", "high": "High-End CPU"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
    "motherboard": {
        "tier_names": {"budget": "Budget Motherboard", "mid": "Mid-Range Motherboard", "high": "High-End Motherboard"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
    "gpu": {
        "tier_names": {"budget": "Budget GPU", "mid": "Mid-Range GPU", "high": "High-End GPU"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
    "ram": {
        "tier_names": {"budget": "Budget RAM", "mid": "Mid-Range RAM", "high": "High-End RAM"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
    "storage": {
        "tier_names": {"budget": "Budget Storage", "mid": "Standard Storage", "high": "Premium Storage"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
    "cooling": {
        "tier_names": {"budget": "Standard Cooling", "mid": "Mid-Range Cooling", "high": "Premium Cooling"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
    "os": {
        "tier_names": {"budget": "OS Included", "mid": "OS Included", "high": "OS Included"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
    "psu": {
        "tier_names": {"budget": "Budget PSU", "mid": "Mid-Range PSU", "high": "High-End PSU"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
    "fan": {
        "tier_names": {"budget": "Standard Fans", "mid": "Mid-Range Fans", "high": "Premium Fans"},
        "score_band_budget": [40, 60],
        "score_band_mid": [60, 80],
        "score_band_high": [80, 100],
    },
}

SLOT_TYPES = list(SLOT_CONFIG.keys())

_PSU_TITLE_KEYWORDS = (
    "psu", "power supply", "80+", "80 plus", "fully modular", "semi modular",
)
_FAN_TITLE_KEYWORDS = (
    "case fan", "pc fan", "argb fan", "rgb fan", "120mm fan", "140mm fan",
    "fan pack", "cooling fan",
)


_MOTHERBOARD_TITLE_KEYWORDS = (
    "motherboard", "mobo", "mainboard",
    # Common chipset codenames — a reasonable proxy for "this listing is a
    # bare motherboard" when the word "motherboard" itself isn't in the title.
    "b650", "b550", "b450", "x670", "x570", "x470", "a620",
    "z790", "z690", "z590", "z490", "b760", "b660", "b560", "h610",
)


async def get_listings_by_category(db: AsyncSession, category: str, limit: int = 30):
    """Get recent listings for a category, sorted by price."""
    # Map slot types to listing fields
    field_map = {
        "cpu": Listing.cpu,
        "gpu": Listing.gpu,
        "ram": Listing.ram_gb,
        "storage": Listing.storage_gb,
    }

    field = field_map.get(category)
    if field is not None:
        result = await db.execute(
            select(Listing)
            .where(field.isnot(None))
            .where(Listing.status.in_(["active", "sold"]))
            .order_by(Listing.price.asc())
            .limit(limit)
        )
        return result.scalars().all()

    title_keywords_by_category = {
        "motherboard": _MOTHERBOARD_TITLE_KEYWORDS,
        "psu": _PSU_TITLE_KEYWORDS,
        "fan": _FAN_TITLE_KEYWORDS,
    }
    keywords = title_keywords_by_category.get(category)
    if keywords:
        # No structured Listing column exists for these categories yet (see
        # PC_BUILDER_DISCOVERY_AND_IMPLEMENTATION_PLAN.md) — title-keyword
        # search is the honest best-effort option until one is added.
        from sqlalchemy import or_
        conditions = [Listing.title.ilike(f"%{kw}%") for kw in keywords]
        result = await db.execute(
            select(Listing)
            .where(or_(*conditions))
            .where(Listing.status.in_(["active", "sold"]))
            .order_by(Listing.price.asc())
            .limit(limit)
        )
        return result.scalars().all()

    # cooling/os and any other slot type without a structured field or
    # dedicated branch — no automated candidate source yet, matches
    # pre-existing behaviour for those two slot types.
    return []


def categorize_by_tier(listings: list, category: str) -> dict:
    """Group listings into budget/mid/high tiers based on price."""
    if not listings:
        return {"budget": [], "mid": [], "high": []}

    prices = [l.price for l in listings if l.price]
    if not prices:
        return {"budget": [], "mid": [], "high": []}

    prices.sort()
    low_third = prices[len(prices) // 3]
    high_two_thirds = prices[(2 * len(prices)) // 3]

    tiers = {"budget": [], "mid": [], "high": []}
    for listing in listings:
        if listing.price <= low_third:
            tiers["budget"].append(listing)
        elif listing.price <= high_two_thirds:
            tiers["mid"].append(listing)
        else:
            tiers["high"].append(listing)

    return tiers


async def seed_configurator(db: AsyncSession):
    """Main seeding function."""
    print("🌱 Seeding configurator slots and variants...")

    # Get all playbooks
    result = await db.execute(select(Playbook).where(Playbook.status == "active"))
    playbooks = result.scalars().all()

    if not playbooks:
        print("❌ No active playbooks found. Run seeding after creating playbooks.")
        return

    print(f"Found {len(playbooks)} playbooks")

    for playbook in playbooks:
        print(f"\n📚 Processing: {playbook.name}")

        # Slot creation is idempotent (skip any (playbook, slot_type) pair
        # that already exists — needed so this script can be safely re-run
        # after adding a new slot_type to SLOT_CONFIG without erroring on the
        # existing rows' unique constraint). Variant backfilling is a SEPARATE
        # decision from slot creation: a slot existing does not mean it has
        # any variants — found 2026-08-12 that a naive "skip if slot exists"
        # guard was silently leaving cpu/gpu/ram/storage/cooling/os with zero
        # variants forever on every re-run, since those slots already existed
        # from an earlier seeding pass but were never actually populated.
        existing_slots_result = await db.execute(
            select(PlaybookSlot).where(PlaybookSlot.playbook_id == playbook.id)
        )
        existing_slots_by_type = {s.slot_type: s for s in existing_slots_result.scalars().all()}

        for slot_type in SLOT_TYPES:
            config = SLOT_CONFIG[slot_type]
            slot = existing_slots_by_type.get(slot_type)

            if slot is None:
                slot = PlaybookSlot(
                    playbook_id=playbook.id,
                    slot_type=slot_type,
                    is_customer_visible=True,
                    tier_names=config["tier_names"],
                    score_band_budget=config["score_band_budget"],
                    score_band_mid=config["score_band_mid"],
                    score_band_high=config["score_band_high"],
                )
                db.add(slot)
                await db.flush()  # Get the slot ID
            else:
                existing_variant_count = (
                    await db.execute(
                        select(func.count()).select_from(CatalogueVariant).where(CatalogueVariant.slot_id == slot.id)
                    )
                ).scalar()
                if existing_variant_count > 0:
                    print(f"  ⏭️  {slot_type}: already has {existing_variant_count} variants, skipping")
                    continue
                print(f"  🔄 {slot_type}: slot exists but has zero variants, backfilling")

            # Get listings for this category
            listings = await get_listings_by_category(db, slot_type, limit=30)
            if not listings:
                print(f"  ⚠️  No listings found for {slot_type}")
                continue

            # Categorize by tier
            tiers = categorize_by_tier(listings, slot_type)

            # Create variants for each tier
            for tier, tier_listings in tiers.items():
                # Take top 3 per tier to avoid bloating
                for listing in tier_listings[:3]:
                    variant = CatalogueVariant(
                        listing_id=listing.id,
                        slot_id=slot.id,
                        status="active",
                        display_price=listing.price,
                        tier=tier,
                    )
                    db.add(variant)
                    await db.flush()

                    # Link visibility
                    visibility = ConfiguratorCatalogueVisibility(
                        playbook_slot_id=slot.id,
                        catalogue_variant_id=variant.id,
                        is_publicly_visible=True,
                        display_order=0,
                    )
                    db.add(visibility)

            print(f"  ✅ {slot_type}: created slots and variants")

    await db.commit()
    print("\n✅ Seeding complete!")


async def main():
    """Initialize database and run seeding."""
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        # Create tables if needed
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        await seed_configurator(db)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
