"""
CPK Versioning Service

Manages soft supersession of PC builds via CPU-Motherboard-RAM triplet versioning.
Enables "Rebuild with newer X" flows without duplicating component data.

CPK version = semantic tag for CPU-Mobo-RAM triplet
- Same triplet = same version
- Example: "Ryzen7-7800X3D_B850_DDR5-48GB"

Soft supersession = marking older builds as obsolete while keeping rows intact
- storefront shows "Newer version available: X" link
- "Rebuild with X" fetches the superseding version's pricing and photos
- Reuses original component selections (CPU-Mobo-RAM lock)

Use cases:
1. New CPU in same socket (RTX 4070 Ti stays same, CPU upgrades)
2. Price drop on current config
3. Better availability of newer revision

Never hard-deletes ManualBuild rows (breaks eBay linkage).
"""

import hashlib
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models import ManualBuild
import structlog

log = structlog.get_logger(__name__)


class CPKVersioner:
    """Manages CPU-Mobo-RAM versioning and soft supersession."""

    @staticmethod
    def generate_cpk_version(build: ManualBuild) -> str:
        """
        Generate semantic CPK version tag from build's CPU, motherboard, RAM.

        Args:
            build: ManualBuild instance with components populated

        Returns:
            Semantic version tag, e.g., "Ryzen7-7800X3D_B850_DDR5-48GB"

        Note:
            Returns hash-based fallback if components are unparseable.
        """
        components = build.components or []
        if not components:
            return _hashify_build(build.id)

        cpu_name = None
        mobo_name = None
        ram_spec = None

        for comp in components:
            if isinstance(comp, dict):
                category = comp.get("category", "").lower()
                name = comp.get("name", "").strip()

                if category == "cpu" and name:
                    cpu_name = _sanitize_component_name(name)
                elif category == "motherboard" and name:
                    mobo_name = _sanitize_component_name(name)
                elif category == "ram" and name:
                    ram_spec = _sanitize_component_name(name)

        if not all([cpu_name, mobo_name, ram_spec]):
            return _hashify_build(build.id)

        return f"{cpu_name}_{mobo_name}_{ram_spec}"

    @staticmethod
    async def mark_superseded(
        db: AsyncSession,
        old_build_id: int,
        new_build_id: int,
        reason: str,
    ) -> bool:
        """
        Mark an older build as superseded by a newer one.

        Args:
            db: AsyncSession for DB operations
            old_build_id: ID of older build to mark as superseded
            new_build_id: ID of newer build to supersede the old one
            reason: Human-readable reason for supersession

        Returns:
            True if update successful, False otherwise
        """
        try:
            old_build = await db.get(ManualBuild, old_build_id)
            new_build = await db.get(ManualBuild, new_build_id)

            if not old_build or not new_build:
                log.warning(
                    "mark_superseded failed: build not found",
                    old_build_id=old_build_id,
                    new_build_id=new_build_id,
                )
                return False

            # Verify same CPK family (both have same CPU-Mobo-RAM)
            old_cpk = old_build.cpk_version or CPKVersioner.generate_cpk_version(old_build)
            new_cpk = new_build.cpk_version or CPKVersioner.generate_cpk_version(new_build)

            if old_cpk != new_cpk:
                log.warning(
                    "mark_superseded rejected: different CPK versions",
                    old_cpk=old_cpk,
                    new_cpk=new_cpk,
                    reason="CPK families must match for soft supersession",
                )
                return False

            # Mark old build as superseded
            old_build.superseded_by_cpk_version = new_cpk
            old_build.compatibility_reason = reason
            old_build.cpk_version = old_cpk

            # Ensure new build has its CPK version set
            if not new_build.cpk_version:
                new_build.cpk_version = new_cpk

            await db.commit()
            log.info(
                "build superseded",
                old_build_id=old_build_id,
                new_build_id=new_build_id,
                cpk_version=new_cpk,
                reason=reason,
            )
            return True

        except Exception as e:
            log.error(
                "mark_superseded exception",
                old_build_id=old_build_id,
                new_build_id=new_build_id,
                error=str(e),
            )
            await db.rollback()
            return False

    @staticmethod
    async def find_latest_by_cpk(
        db: AsyncSession,
        cpk_version: str,
    ) -> Optional[ManualBuild]:
        """
        Find latest unsuperseded build for a CPK version.

        Args:
            db: AsyncSession
            cpk_version: CPK version tag to search

        Returns:
            Latest unsuperseded ManualBuild, or None if not found
        """
        stmt = select(ManualBuild).where(
            and_(
                ManualBuild.cpk_version == cpk_version,
                ManualBuild.superseded_by_cpk_version.is_(None),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_supersession_chain(
        db: AsyncSession,
        cpk_version: str,
    ) -> list[ManualBuild]:
        """
        Get all builds in a CPK version chain (oldest to newest).

        Useful for understanding the build evolution and "Rebuild with X" workflows.

        Args:
            db: AsyncSession
            cpk_version: CPK version tag

        Returns:
            List of ManualBuilds for this CPK version, ordered by created_at
        """
        stmt = select(ManualBuild).where(
            ManualBuild.cpk_version == cpk_version
        ).order_by(ManualBuild.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().all()


def _sanitize_component_name(name: str) -> str:
    """
    Sanitize component name for use in CPK version tag.

    Examples:
        "AMD Ryzen 7 7800X3D" → "7800X3D"
        "ASUS ProArt B850-CREATOR" → "B850"
        "Corsair Vengeance 48GB DDR5-6000" → "DDR5-48GB"
    """
    import re

    if not name:
        return "unknown"

    # Remove common prefixes
    for prefix in ["AMD ", "Intel ", "NVIDIA ", "ASUS ", "Gigabyte ", "MSI ", "Corsair "]:
        if name.startswith(prefix):
            name = name[len(prefix):]

    # Extract key parts
    parts = []

    # For CPU: keep model number (7800X3D, 14900K, etc.)
    if any(x in name for x in ["Ryzen", "Core i", "Core Ultra", "Xeon"]):
        # Match patterns like "7800X3D", "14900K", "9950X", "285K"
        match = re.search(r"\d+[A-Z]+\d*", name)
        if match:
            parts.append(match.group(0))

    # For motherboard: keep socket/chipset (B850, X870, Z790, etc.)
    match = re.search(r"[BZX]\d{3,4}", name)
    if match:
        parts.append(match.group(0))

    # For RAM: keep capacity and speed (DDR5-48GB, DDR4-32GB, etc.)
    if "DDR" in name:
        speed_match = re.search(r"DDR\d", name)
        capacity_match = re.search(r"(\d+)(GB|MB)", name)
        if speed_match and capacity_match:
            speed = speed_match.group(0)
            capacity = capacity_match.group(0)
            parts.append(f"{speed}-{capacity}")

    if parts:
        return "_".join(parts)

    # Fallback: replace spaces with dashes, remove special chars
    return re.sub(r"[^A-Za-z0-9-]", "", name.replace(" ", "-"))[:50]


def _hashify_build(build_id: int) -> str:
    """
    Generate hash-based CPK version when components are unparseable.

    Ensures stable versioning even if component data is malformed.
    """
    hash_obj = hashlib.sha256(str(build_id).encode())
    return f"build_{hash_obj.hexdigest()[:16]}"
