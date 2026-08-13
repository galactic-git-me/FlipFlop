"""Seed the PRD reference build's components as real catalogue rows
(flipflop-3d-builder-claude-prd.md §3) — attached to the "High-end Gamer"
playbook's existing slots so they flow through the real compatibility/pricing
pipeline like any other component, rather than inventing a parallel structure.

Every component also gets a Component3DAsset row recording its ACTUAL
provenance status per the PRD's own model-source register (§12) — nothing
here is marked commercial_use_approved/redistribution_approved unless the PRD
itself already reached that conclusion (only the case, and only as an
original recreation from published dimensions — see seed_o11_vision_compact.py).
Everything else stays MISSING/metadata-only until a human actually reviews a
real licence, exactly as the PRD instructs. Safe to re-run.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.playbook import Playbook
from app.models.catalogue import PlaybookSlot, CatalogueVariant
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing
from app.models.component_3d_asset import Component3DAsset, AssetSubjectType, Component3DAssetStatus

PLAYBOOK_NAME = "High-end Gamer"

# (slot_type, external_id, title, price_gbp, provenance dict)
COMPONENTS = [
    (
        "cpu", "prd-ref-cpu-i7-270k",
        "Intel Core Ultra 7 270K Plus", 299.99,
        {
            "provenance_status": "metadata-only",
            "source_name": "Concealed inside case — exterior geometry adds little customer value (PRD §12)",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
    (
        "motherboard", "prd-ref-mobo-asus-tuf-z890",
        "Asus TUF GAMING Z890-PLUS WIFI DDR5 ATX", 221.99,
        {
            "provenance_status": "metadata-only",
            "source_name": "No suitable exact public model found — needs ASUS CAD/media permission or an original 305x244mm ATX recreation (PRD §12)",
            "source_url": "https://www.asus.com/motherboards-components/motherboards/tuf-gaming/tuf-gaming-z890-plus-wifi/",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
    (
        "gpu", "prd-ref-gpu-pny-rtx5070",
        "PNY GeForce RTX 5070 12GB GDDR7 ARGB EPIC-X RGB Overclocked Triple Fan", 599.99,
        {
            "provenance_status": "metadata-only",
            "source_name": "No suitable exact licensed model found — needs PNY CAD/media permission or an original silhouette-faithful recreation (~299.7x120.1mm, 2.4-slot) (PRD §12)",
            "source_url": "https://www.pny.com/geforce-rtx-5070-models",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
    (
        "ram", "prd-ref-ram-corsair-vengeance-ddr5",
        "Corsair Vengeance RGB 32GB (2x16GB) DDR5 6000 CL30 Black", 449.99,
        {
            "provenance_status": "metadata-only",
            "source_name": "Candidate: Sketchfab low-poly by PolyDavid (UID 5352b17857ea4036ab61980c4c57f265) — licence NOT yet verified, do not import without review (PRD §12)",
            "source_url": "https://sketchfab.com/3d-models/corsair-vengeance-rgb-ddr5-ram-low-poly-5352b17857ea4036ab61980c4c57f265",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
    (
        "cooling", "prd-ref-cooler-lianli-hydroshift-360",
        "Lian Li HydroShift II LCD-S 360 CL Black", 150.98,
        {
            "provenance_status": "metadata-only",
            "source_name": "No public reusable model found — needs Lian Li CAD/marketing permission or an original proxy on standard 360 radiator/fan spacing (PRD §12)",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
    (
        "storage", "prd-ref-storage-kingston-nv3-1tb",
        "Kingston NV3 PCIe 4.0 NVMe SSD 2280 1TB", 129.99,
        {
            "provenance_status": "metadata-only",
            "source_name": "Concealed M.2 board — exterior geometry adds little customer value (PRD §12)",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
    (
        "psu", "prd-ref-psu-corsair-rm1000e-2025",
        "Corsair RM1000e (2025) Black ATX 1000W Fully Modular", 138.99,
        {
            "provenance_status": "metadata-only",
            "source_name": "Mostly concealed in the case's PSU chamber — simplified generic geometry is enough until an exploded/product view is built (PRD §12)",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
    (
        "fan", "prd-ref-fan-asiahorse-amici5gt-reverse-x3",
        "AsiaHorse AMICI-5GT RGB PC Fans, Infinity Mirror ARGB Fans 120mm Black Reverse Blade Pack of 3", 45.00,
        {
            "provenance_status": "metadata-only",
            "source_name": "No suitable exact downloadable model found — product imagery is enough to build an original parametric 120mm fan (reverse-blade variant) (PRD §12)",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
    (
        "fan", "prd-ref-fan-asiahorse-amici5gt-standard-x1",
        "AsiaHorse AMICI-5GT 120mm Black ARGB", 15.00,
        {
            "provenance_status": "metadata-only",
            "source_name": "Same base model as the reverse-blade pack, standard blade orientation — one original parametric fan model, two blade-direction variants (PRD §12)",
            "commercial_use_approved": False,
            "redistribution_approved": False,
        },
    ),
]


async def _get_or_create_listing(db, external_id: str, title: str, price: float) -> Listing:
    existing = (
        await db.execute(select(Listing).where(Listing.external_id == external_id))
    ).scalar_one_or_none()
    if existing:
        existing.title = title
        existing.price = price
        return existing

    listing = Listing(
        external_id=external_id,
        source_id=0,
        source_name="flipflop-reference-build",
        title=title,
        price=price,
        url="https://theflipflop.shop/reference-build",
        status="active",
    )
    db.add(listing)
    await db.flush()
    return listing


async def main():
    async with AsyncSessionLocal() as db:
        playbook = (
            await db.execute(select(Playbook).where(Playbook.name == PLAYBOOK_NAME))
        ).scalar_one_or_none()
        if not playbook:
            print(f"Playbook '{PLAYBOOK_NAME}' not found — run scripts/seed_configurator_slots.py first.")
            return

        slots_by_type = {
            s.slot_type: s
            for s in (
                await db.execute(
                    select(PlaybookSlot).where(PlaybookSlot.playbook_id == playbook.id)
                )
            ).scalars().all()
        }

        for slot_type, external_id, title, price, provenance in COMPONENTS:
            slot = slots_by_type.get(slot_type)
            if not slot:
                print(f"  SKIP {title}: no '{slot_type}' slot on {PLAYBOOK_NAME}")
                continue

            listing = await _get_or_create_listing(db, external_id, title, price)

            variant = (
                await db.execute(
                    select(CatalogueVariant).where(CatalogueVariant.listing_id == listing.id)
                )
            ).scalar_one_or_none()
            if not variant:
                variant = CatalogueVariant(
                    listing_id=listing.id,
                    slot_id=slot.id,
                    status="active",
                    display_price=price,
                    tier="high",
                )
                db.add(variant)
                await db.flush()
                print(f"  + {title} -> {slot_type} slot (variant {variant.id})")
            else:
                variant.display_price = price
                print(f"  = {title} already linked (variant {variant.id})")

            # Explicit visibility row — required once any curation rows exist
            # for a slot (see app/api/public_catalogue.py's gate), which they
            # do here since scripts/seed_configurator_slots.py already created
            # rows for this slot's other variants. Missing this silently hid
            # every component seeded by this script until diagnosed 2026-08-12.
            visibility = (
                await db.execute(
                    select(ConfiguratorCatalogueVisibility).where(
                        ConfiguratorCatalogueVisibility.catalogue_variant_id == variant.id
                    )
                )
            ).scalar_one_or_none()
            if not visibility:
                db.add(
                    ConfiguratorCatalogueVisibility(
                        playbook_slot_id=slot.id,
                        catalogue_variant_id=variant.id,
                        is_publicly_visible=True,
                        display_order=0,
                    )
                )

            asset = (
                await db.execute(
                    select(Component3DAsset).where(
                        Component3DAsset.subject_type == AssetSubjectType.VARIANT,
                        Component3DAsset.subject_id == variant.id,
                    )
                )
            ).scalar_one_or_none()
            if not asset:
                asset = Component3DAsset(
                    subject_type=AssetSubjectType.VARIANT,
                    subject_id=variant.id,
                    status=Component3DAssetStatus.MISSING,
                )
                db.add(asset)

            for field, value in provenance.items():
                setattr(asset, field, value)

        await db.commit()
        print("\nDone. All 8 catalogue-eligible reference components linked "
              "(CPU/motherboard/GPU/RAM/cooler/storage/PSU/fan). "
              "Case handled separately by scripts/seed_o11_vision_compact.py.")


if __name__ == "__main__":
    asyncio.run(main())
