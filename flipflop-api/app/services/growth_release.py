"""Versioned Growth Engine release configuration. Every UI control and job checks this."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.growth import (
    MVP_CAPABILITIES,
    ROADMAP_CAPABILITIES,
    GrowthReleaseConfiguration,
)

FEATURE_NOT_ENABLED = "FEATURE_NOT_ENABLED"

DEFAULT_CHANNELS = ["facebook", "instagram", "x"]


class FeatureNotEnabled(Exception):
    def __init__(self, capability: str):
        self.capability = capability
        self.code = FEATURE_NOT_ENABLED
        super().__init__(capability)


async def get_active_release(db: AsyncSession) -> GrowthReleaseConfiguration:
    row = (
        await db.execute(
            select(GrowthReleaseConfiguration)
            .where(GrowthReleaseConfiguration.is_active.is_(True))
            .order_by(GrowthReleaseConfiguration.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row:
        return row
    row = GrowthReleaseConfiguration(
        release_name="marketing_mvp",
        version="1.2",
        enabled_capabilities=list(MVP_CAPABILITIES),
        enabled_channels=list(DEFAULT_CHANNELS),
        enabled_agents=[],
        effective_at=datetime.utcnow(),
        approved_by="owner",
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


def capability_enabled(release: GrowthReleaseConfiguration, capability: str) -> bool:
    return capability in (release.enabled_capabilities or [])


def require_capability(release: GrowthReleaseConfiguration, capability: str) -> None:
    if not capability_enabled(release, capability):
        raise FeatureNotEnabled(capability)


def serialize_release(release: GrowthReleaseConfiguration) -> dict:
    enabled = set(release.enabled_capabilities or [])
    return {
        "release_name": release.release_name,
        "version": release.version,
        "enabled_capabilities": list(release.enabled_capabilities or []),
        "enabled_channels": list(release.enabled_channels or []),
        "enabled_agents": list(release.enabled_agents or []),
        "approval_policy_version": release.approval_policy_version,
        "financial_policy_version": release.financial_policy_version,
        "consent_policy_version": release.consent_policy_version,
        "single_user_mode": release.single_user_mode,
        "separation_of_duties": release.separation_of_duties,
        "approval_validity_hours": release.approval_validity_hours,
        "effective_at": release.effective_at.isoformat() if release.effective_at else None,
        "approved_by": release.approved_by,
        "roadmap": [
            {
                "capability": name,
                "enabled": name in enabled,
                "status": "enabled" if name in enabled else "roadmap",
            }
            for name in (*MVP_CAPABILITIES, *ROADMAP_CAPABILITIES)
        ],
    }
