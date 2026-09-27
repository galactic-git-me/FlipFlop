"""Deterministic, SKU-free starting envelopes for the guided PC journey.

These profiles describe requirements. They are not quotes or stock promises.
"""
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, Field


class CustomerRequirements(BaseModel):
    primary_use: str
    secondary_uses: list[str] = Field(default_factory=list)
    budget_gbp: int = Field(ge=300, le=20000)
    budget_policy: str = "firm"  # firm, small_stretch, best_value
    playbook_version: str | None = None
    resolution: Literal["1080p", "1440p", "4k"] | None = None
    refresh_rate_hz: int | None = Field(default=None, ge=30, le=500)
    gaming_priority: Literal["competitive", "visuals", "balanced"] | None = None
    docker_or_vms: bool = False
    heavy_compilation: bool = False
    local_ai: bool = False
    ai_workload: Literal["experimentation", "regular", "large_models"] | None = None
    creation_workload: Literal["photo", "video", "3d", "audio", "mixed"] | None = None
    quiet: bool = False
    storage_gb: int | None = Field(default=None, ge=0)
    useful_life_years: int | None = Field(default=None, ge=1, le=10)
    condition_policy: str = "NEW_ONLY"


PROFILES_V1_0 = {
    "gaming": {"segment": "Great-value Gaming", "cpu_cores": 6, "ram_gb": 16, "storage_gb": 1000, "gpu_vram_gb": 8, "gpu_required": True},
    "high_performance_gaming": {"segment": "High-performance Gaming", "cpu_cores": 8, "ram_gb": 32, "storage_gb": 1000, "gpu_vram_gb": 12, "gpu_required": True},
    "study": {"segment": "Student Hybrid", "cpu_cores": 4, "ram_gb": 16, "storage_gb": 500, "gpu_vram_gb": 0, "gpu_required": False},
    "business": {"segment": "Business & Office", "cpu_cores": 4, "ram_gb": 16, "storage_gb": 500, "gpu_vram_gb": 0, "gpu_required": False},
    "content_creation": {"segment": "Content Creation", "cpu_cores": 8, "ram_gb": 32, "storage_gb": 1000, "gpu_vram_gb": 8, "gpu_required": True},
    "ai": {"segment": "AI Workstation", "cpu_cores": 8, "ram_gb": 32, "storage_gb": 1000, "gpu_vram_gb": 12, "gpu_required": True},
    "software_development": {"segment": "Software Development", "cpu_cores": 6, "ram_gb": 16, "storage_gb": 1000, "gpu_vram_gb": 0, "gpu_required": False},
    "family": {"segment": "Family & Home", "cpu_cores": 4, "ram_gb": 16, "storage_gb": 500, "gpu_vram_gb": 0, "gpu_required": False},
}

# Keep released rule sets immutable so a saved session can be replayed later.
PROFILES_V1_1 = deepcopy(PROFILES_V1_0)
PLAYBOOKS = {"1.0": PROFILES_V1_0, "1.1": PROFILES_V1_1}
ACTIVE_PLAYBOOK_VERSION = "1.1"

ALIASES = {"office": "business", "family_home": "family", "student": "study", "development": "software_development", "local_ai": "ai"}


def build_envelope(requirements: CustomerRequirements) -> dict:
    use = requirements.primary_use.strip().lower().replace(" ", "_").replace("-", "_")
    use = ALIASES.get(use, use)
    if requirements.budget_policy not in {"firm", "small_stretch", "best_value"}:
        raise ValueError("Unsupported budget policy")
    if requirements.condition_policy not in {"NEW_ONLY", "NEW_OR_REFURBISHED", "USED_ALLOWED"}:
        raise ValueError("Unsupported condition policy")

    playbook_version = requirements.playbook_version or ACTIVE_PLAYBOOK_VERSION
    profiles = PLAYBOOKS.get(playbook_version)
    if profiles is None:
        raise ValueError("Unsupported Playbook version")
    if use not in profiles:
        raise ValueError("Unsupported primary use")

    minimums = deepcopy(profiles[use])
    segment = minimums.pop("segment")
    reasons = []
    gaming_relevant = use in {"gaming", "high_performance_gaming"} or "gaming" in requirements.secondary_uses
    if requirements.docker_or_vms or "software_development" in requirements.secondary_uses:
        minimums["ram_gb"] = max(minimums["ram_gb"], 32)
        minimums["cpu_cores"] = max(minimums["cpu_cores"], 8)
        reasons.append("Docker or virtual machines benefit from more memory and processor headroom.")
    if requirements.local_ai or "ai" in requirements.secondary_uses:
        minimums["ram_gb"] = max(minimums["ram_gb"], 32)
        minimums["gpu_vram_gb"] = max(minimums["gpu_vram_gb"], 12)
        minimums["gpu_required"] = True
        reasons.append("Local AI work needs dedicated graphics memory; we prioritise that before cosmetic upgrades.")
    if gaming_relevant and requirements.resolution == "1440p":
        minimums["gpu_vram_gb"] = max(minimums["gpu_vram_gb"], 12)
        reasons.append("At 1440p, graphics capability matters more than paying for a premium processor tier.")
    elif playbook_version == "1.1" and gaming_relevant and requirements.resolution == "4k":
        minimums["gpu_vram_gb"] = max(minimums["gpu_vram_gb"], 16)
        reasons.append("4K gaming needs more graphics headroom; we will check real game performance before choosing parts.")
    if playbook_version == "1.1":
        if gaming_relevant and (requirements.refresh_rate_hz or 0) >= 144:
            reasons.append("Your high refresh rate makes smooth frame delivery a priority; we will balance processor and graphics performance for it.")
        if gaming_relevant and requirements.gaming_priority == "competitive":
            reasons.append("We will favour consistent high frame rates and low input delay over visual effects that do not help competitive play.")
        elif gaming_relevant and requirements.gaming_priority == "visuals":
            reasons.append("We will prioritise image quality where it improves the games and resolution you chose.")
        if requirements.heavy_compilation:
            minimums["cpu_cores"] = max(minimums["cpu_cores"], 8)
            minimums["ram_gb"] = max(minimums["ram_gb"], 32)
            reasons.append("Large software builds benefit from more processor and memory headroom.")
        if requirements.ai_workload == "large_models":
            minimums["ram_gb"] = max(minimums["ram_gb"], 64)
            minimums["gpu_vram_gb"] = max(minimums["gpu_vram_gb"], 16)
            minimums["gpu_required"] = True
            reasons.append("Larger local AI models can need substantially more system memory and graphics memory; we will verify model fit before recommending parts.")
        elif requirements.ai_workload == "regular":
            minimums["ram_gb"] = max(minimums["ram_gb"], 32)
            minimums["gpu_vram_gb"] = max(minimums["gpu_vram_gb"], 12)
            minimums["gpu_required"] = True
            reasons.append("Regular local AI use benefits from dedicated graphics memory and 32GB of system memory.")
        if requirements.creation_workload in {"video", "3d", "mixed"}:
            minimums["ram_gb"] = max(minimums["ram_gb"], 32)
            reasons.append("Video and 3D workloads benefit from extra memory; the right graphics choice depends on your specific software.")
    if requirements.storage_gb:
        minimums["storage_gb"] = max(minimums["storage_gb"], requirements.storage_gb)
    if requirements.quiet:
        reasons.append("We will check cooling and case acoustics before selecting compatible parts.")
    if playbook_version == "1.1" and requirements.useful_life_years and requirements.useful_life_years >= 5:
        reasons.append("You want to keep this PC for several years, so we will favour useful headroom over upgrades with little practical benefit.")
    if not reasons:
        reasons.append("This profile covers the stated use without assuming that a more expensive component is worthwhile.")

    preferred = {"ram_gb": max(32, minimums["ram_gb"]), "storage_gb": max(1000, minimums["storage_gb"])}
    options = [{
        "id": "save",
        "label": "Save",
        "summary": "Meet every stated minimum while keeping optional upgrades out.",
        "hard_minimums": deepcopy(minimums),
        "targets": {},
        "stretch_allowed": False,
    }]
    recommended_targets = {key: value for key, value in preferred.items() if value > minimums[key]}
    if recommended_targets:
        options.append({
            "id": "recommended",
            "label": "Recommended",
            "summary": "Add useful memory or storage headroom where it fits the workload.",
            "hard_minimums": deepcopy(minimums),
            "targets": recommended_targets,
            "stretch_allowed": False,
        })
    stretch_targets = {}
    if playbook_version == "1.1" and requirements.budget_policy != "firm":
        if requirements.ai_workload in {"regular", "large_models"}:
            stretch_targets["gpu_vram_gb"] = max(16, minimums["gpu_vram_gb"])
        elif requirements.creation_workload in {"video", "3d", "mixed"} or requirements.heavy_compilation:
            stretch_targets["ram_gb"] = max(64, minimums["ram_gb"])
        elif gaming_relevant and requirements.resolution in {"1440p", "4k"}:
            stretch_targets["gpu_vram_gb"] = max(16, minimums["gpu_vram_gb"])
    stretch_targets = {key: value for key, value in stretch_targets.items() if value > minimums.get(key, 0)}
    if stretch_targets:
        options.append({
            "id": "stretch",
            "label": "Stretch",
            "summary": "Consider extra headroom only if live compatibility and pricing checks show a worthwhile benefit.",
            "hard_minimums": deepcopy(minimums),
            "targets": stretch_targets,
            "stretch_allowed": True,
        })

    return {
        "envelope_version": "2.0",
        "playbook_version": playbook_version,
        "segment": segment,
        "budget_gbp": requirements.budget_gbp,
        "budget_policy": requirements.budget_policy,
        "condition_policy": requirements.condition_policy,
        "hard_minimums": minimums,
        "preferred_targets": preferred,
        "performance_options": options,
        "budget_strategy": reasons,
        "status": "requirements_only",
        "next_step": "Check approved SKUs, compatibility, live supplier offers, true cost and market evidence before presenting a price or delivery option.",
    }
