"""Resolve the software recommendation attached to a Ready-to-Ship product."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.models.build import Build
from app.models.manual_build import ManualBuild
from app.models.playbook import Playbook
from app.models.product import Product
from app.models.curated_build_segment import CuratedBuildSegment
from app.services.software_catalogue import (
    effective_software_profile_for_playbook,
    normalize_software_profile,
    software_profile_for_curated_cell,
)

PLAYBOOK_BUDGET_TIERS = {
    "budget": "Budget",
    "mid-range": "Mid-range",
    "high-end": "High-end",
}


async def software_profile_for_playbook_cell_from_db(
    db: AsyncSession,
    playbook_name: str,
    budget_tier: str,
    base_profile: dict | None = None,
) -> dict:
    """Resolve a customer-declared use-case × budget cell profile."""
    normalized_tier = " ".join(str(budget_tier or "").strip().casefold().replace("_", "-").split())
    canonical_tier = PLAYBOOK_BUDGET_TIERS.get(normalized_tier)
    if canonical_tier is None:
        raise ValueError("Choose Budget, Mid-range, or High-end for the Made-by-you Playbook")

    profile = effective_software_profile_for_playbook(playbook_name, base_profile)
    row = (await db.execute(
        select(CuratedBuildSegment).where(
            func.lower(func.trim(CuratedBuildSegment.customer_type)) == str(playbook_name or "").strip().casefold(),
            func.lower(func.replace(func.trim(CuratedBuildSegment.budget_level), "_", "-")) == normalized_tier,
        )
    )).scalar_one_or_none()
    if row and row.software_profile is not None:
        authored = normalize_software_profile(row.software_profile) or {}
        profile.update(authored)
        profile["profile_source"] = "admin_reviewed_playbook_cell"
    else:
        profile["profile_source"] = str(profile.get("profile_source") or "reviewed_default_v1")
    profile["budget_tier"] = canonical_tier
    profile["playbook_cell"] = f"{playbook_name} / {canonical_tier}"
    return profile


async def software_profile_for_curated_cell_from_db(
    db: AsyncSession,
    build_id: str,
    playbook_name: str,
    base_profile: dict | None = None,
    *,
    lock_profile: bool = False,
) -> dict:
    """Prefer a reviewed DB-authored customer-type × budget-cell profile."""
    from app.services.curated_build_policy import definitions

    cell = next((item for item in definitions().get("builds", []) if item.get("id") == build_id), None)
    if cell is None:
        raise ValueError(f"Unknown curated Playbook cell: {build_id}")
    if str(cell.get("segment", "")).strip().casefold() != str(playbook_name or "").strip().casefold():
        raise ValueError("Curated Playbook cell does not match the selected customer type")

    profile = software_profile_for_curated_cell(build_id, playbook_name, base_profile)
    tier = " ".join(str(cell.get("tier") or "").strip().casefold().replace("-", " ").split())
    segment_query = select(CuratedBuildSegment).where(
        func.lower(func.trim(CuratedBuildSegment.customer_type)) == str(cell["segment"]).strip().casefold(),
        func.lower(func.replace(func.trim(CuratedBuildSegment.budget_level), "-", " ")) == tier,
    )
    if lock_profile:
        segment_query = segment_query.with_for_update()
    row = (await db.execute(segment_query)).scalar_one_or_none()
    if row and row.software_profile is not None:
        from app.services.software_catalogue import normalize_software_profile
        authored = normalize_software_profile(row.software_profile) or {}
        profile.update(authored)
        profile["profile_source"] = "admin_reviewed_curated_cell"
        profile["curated_build_id"] = build_id
        profile["budget_tier"] = cell["tier"]
    return profile


async def software_profile_for_product(db: AsyncSession, product: Product) -> dict:
    """Prefer the pre-sale cell snapshot, then the Playbook profile/default."""
    assignment = {}
    if product.build_id:
        build = await db.get(Build, product.build_id)
        manual_build = await db.get(ManualBuild, build.manual_build_id) if build and build.manual_build_id else None
        assignment = ((manual_build.evidence_data or {}).get("playbook_assignment") or {}) if manual_build else {}

    saved_profile = assignment.get("software_profile")
    playbook_id = assignment.get("playbook_id") or product.playbook_id
    playbook = await db.get(Playbook, playbook_id) if playbook_id else None
    if assignment.get("curated_build_id"):
        # Recover cell context even when an older assignment did not snapshot
        # its software profile at creation time.
        return await software_profile_for_curated_cell_from_db(
            db,
            assignment["curated_build_id"],
            playbook.name if playbook else str(assignment.get("customer_type") or ""),
            saved_profile or (playbook.software_profile if playbook else None),
        )
    if saved_profile:
        profile = normalize_software_profile(saved_profile) or {}
        return profile

    if playbook:
        return effective_software_profile_for_playbook(playbook.name, playbook.software_profile)
    return effective_software_profile_for_playbook("", None)
