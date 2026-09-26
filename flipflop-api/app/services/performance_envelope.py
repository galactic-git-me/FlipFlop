"""Deterministic, SKU-free starting envelopes for the guided PC journey.

These profiles describe requirements. They are not quotes or stock promises.
"""
from copy import deepcopy

from pydantic import BaseModel, Field


class CustomerRequirements(BaseModel):
    primary_use: str
    secondary_uses: list[str] = Field(default_factory=list)
    budget_gbp: int = Field(ge=300, le=20000)
    budget_policy: str = "firm"  # firm, small_stretch, best_value
    resolution: str | None = None
    docker_or_vms: bool = False
    local_ai: bool = False
    quiet: bool = False
    storage_gb: int | None = Field(default=None, ge=0)
    condition_policy: str = "NEW_ONLY"


PROFILES = {
    "gaming": {"segment": "Great-value Gaming", "cpu_cores": 6, "ram_gb": 16, "storage_gb": 1000, "gpu_vram_gb": 8, "gpu_required": True},
    "high_performance_gaming": {"segment": "High-performance Gaming", "cpu_cores": 8, "ram_gb": 32, "storage_gb": 1000, "gpu_vram_gb": 12, "gpu_required": True},
    "study": {"segment": "Student Hybrid", "cpu_cores": 4, "ram_gb": 16, "storage_gb": 500, "gpu_vram_gb": 0, "gpu_required": False},
    "business": {"segment": "Business & Office", "cpu_cores": 4, "ram_gb": 16, "storage_gb": 500, "gpu_vram_gb": 0, "gpu_required": False},
    "content_creation": {"segment": "Content Creation", "cpu_cores": 8, "ram_gb": 32, "storage_gb": 1000, "gpu_vram_gb": 8, "gpu_required": True},
    "ai": {"segment": "AI Workstation", "cpu_cores": 8, "ram_gb": 32, "storage_gb": 1000, "gpu_vram_gb": 12, "gpu_required": True},
    "software_development": {"segment": "Software Development", "cpu_cores": 6, "ram_gb": 16, "storage_gb": 1000, "gpu_vram_gb": 0, "gpu_required": False},
    "family": {"segment": "Family & Home", "cpu_cores": 4, "ram_gb": 16, "storage_gb": 500, "gpu_vram_gb": 0, "gpu_required": False},
}

ALIASES = {"office": "business", "family_home": "family", "student": "study", "development": "software_development", "local_ai": "ai"}


def build_envelope(requirements: CustomerRequirements) -> dict:
    use = requirements.primary_use.strip().lower().replace(" ", "_").replace("-", "_")
    use = ALIASES.get(use, use)
    if use not in PROFILES:
        raise ValueError("Unsupported primary use")
    if requirements.budget_policy not in {"firm", "small_stretch", "best_value"}:
        raise ValueError("Unsupported budget policy")
    if requirements.condition_policy not in {"NEW_ONLY", "NEW_OR_REFURBISHED", "USED_ALLOWED"}:
        raise ValueError("Unsupported condition policy")

    minimums = deepcopy(PROFILES[use])
    segment = minimums.pop("segment")
    reasons = []
    if requirements.docker_or_vms or "software_development" in requirements.secondary_uses:
        minimums["ram_gb"] = max(minimums["ram_gb"], 32)
        minimums["cpu_cores"] = max(minimums["cpu_cores"], 8)
        reasons.append("Docker or virtual machines benefit from more memory and processor headroom.")
    if requirements.local_ai or "ai" in requirements.secondary_uses:
        minimums["ram_gb"] = max(minimums["ram_gb"], 32)
        minimums["gpu_vram_gb"] = max(minimums["gpu_vram_gb"], 12)
        minimums["gpu_required"] = True
        reasons.append("Local AI work needs dedicated graphics memory; we prioritise that before cosmetic upgrades.")
    if use in {"gaming", "high_performance_gaming"} and requirements.resolution == "1440p":
        minimums["gpu_vram_gb"] = max(minimums["gpu_vram_gb"], 12)
        reasons.append("At 1440p, graphics capability matters more than paying for a premium processor tier.")
    if requirements.storage_gb:
        minimums["storage_gb"] = max(minimums["storage_gb"], requirements.storage_gb)
    if requirements.quiet:
        reasons.append("We will check cooling and case acoustics before selecting compatible parts.")
    if not reasons:
        reasons.append("This profile covers the stated use without assuming that a more expensive component is worthwhile.")

    return {
        "envelope_version": "1.0",
        "segment": segment,
        "budget_gbp": requirements.budget_gbp,
        "budget_policy": requirements.budget_policy,
        "condition_policy": requirements.condition_policy,
        "hard_minimums": minimums,
        "preferred_targets": {"ram_gb": max(32, minimums["ram_gb"]), "storage_gb": max(1000, minimums["storage_gb"])},
        "budget_strategy": reasons,
        "status": "requirements_only",
        "next_step": "Check approved SKUs, compatibility, live supplier offers, true cost and market evidence before presenting a price or delivery option.",
    }
