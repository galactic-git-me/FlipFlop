"""
Generates buyer-facing performance summaries and listing text from benchmark data.
No network calls — pure data transformation.
"""
from __future__ import annotations
import math
from typing import Optional

_CPU_TIERS = [(50000, "Flagship"), (25000, "High-End"), (10000, "Mid-Range"), (0, "Entry")]
_GPU_TIERS = [(25000, "Flagship"), (12000, "High-End"), (6000, "Mid-Range"), (0, "Entry")]


def classify_tier(component_type: str, score: float) -> str:
    thresholds = _CPU_TIERS if component_type == "cpu" else _GPU_TIERS
    for threshold, label in thresholds:
        if score >= threshold:
            return label
    return "Entry"


def generate_build_performance_summary(
    cpu_model: str,
    cpu_score: float,
    gpu_model: str,
    gpu_score: float,
    vram_gb: float,
    ram_gb: float,
    ram_speed_mts: float,
    storage_gb: float,
    storage_interface: str,
) -> dict:
    cpu_tier = classify_tier("cpu", cpu_score)
    gpu_tier = classify_tier("gpu", gpu_score)

    cpu_strengths = []
    if cpu_score >= 30000:
        cpu_strengths.append("Excellent multi-core performance")
    if "3D" in cpu_model or "x3d" in cpu_model.lower():
        cpu_strengths.append("3D V-Cache gaming optimised")
    if cpu_score >= 15000:
        cpu_strengths.append("Strong for streaming and encoding")

    gpu_strengths = []
    if vram_gb >= 16:
        gpu_strengths.append(f"{vram_gb:.0f}GB VRAM — AI/4K capable")
    elif vram_gb >= 12:
        gpu_strengths.append(f"{vram_gb:.0f}GB VRAM — excellent 1440p")
    elif vram_gb >= 8:
        gpu_strengths.append(f"{vram_gb:.0f}GB VRAM — solid 1080p/1440p")
    if gpu_score >= 15000:
        gpu_strengths.append("High-FPS 1440p gaming")

    overall_gaming = round((cpu_score * 0.3 + gpu_score * 0.7) / 500, 1)
    overall_workstation = round((cpu_score * 0.6 + gpu_score * 0.4) / 500, 1)
    overall_ai = round((gpu_score * 0.6 + vram_gb * 500 + cpu_score * 0.1) / 500, 1)
    overall_value = round((overall_gaming + overall_workstation) / 2, 1)

    return {
        "cpu": {
            "model": cpu_model,
            "benchmark_score": cpu_score,
            "tier": cpu_tier,
            "strengths": cpu_strengths,
        },
        "gpu": {
            "model": gpu_model,
            "benchmark_score": gpu_score,
            "tier": gpu_tier,
            "vram_gb": vram_gb,
            "strengths": gpu_strengths,
        },
        "ram": {
            "capacity_gb": ram_gb,
            "speed_mts": ram_speed_mts,
            "score": round(ram_gb * (ram_speed_mts / 3200) * 10, 0),
        },
        "storage": {
            "capacity_gb": storage_gb,
            "interface": storage_interface,
            "score": _storage_interface_score(storage_interface),
        },
        "overall": {
            "gaming_score": min(100.0, overall_gaming),
            "workstation_score": min(100.0, overall_workstation),
            "ai_score": min(100.0, overall_ai),
            "value_score": min(100.0, overall_value),
        },
    }


def _storage_interface_score(interface: str) -> float:
    i = (interface or "").lower()
    if "pcie 5" in i or "gen5" in i:
        return 100.0
    if "pcie 4" in i or "gen4" in i:
        return 85.0
    if "pcie 3" in i or "gen3" in i or "nvme" in i:
        return 70.0
    if "sata ssd" in i or "sata" in i:
        return 45.0
    if "hdd" in i:
        return 15.0
    return 50.0


_USE_CASE_TEMPLATES = {
    "gaming": (
        "Built for high-FPS 1080p / 1440p gaming\n"
        "{cpu_model} gaming CPU ({cpu_tier})\n"
        "{gpu_model} graphics ({gpu_tier})\n"
        "{ram_gb}GB RAM\n"
        "{storage_gb}GB {storage_interface}"
    ),
    "workstation": (
        "Built for coding, Docker and multitasking\n"
        "{cpu_model} ({cpu_tier} — multi-core powerhouse)\n"
        "{ram_gb}GB RAM\n"
        "{storage_gb}GB {storage_interface}\n"
        "Ideal for development workloads"
    ),
    "ai": (
        "Designed for local AI experimentation\n"
        "{gpu_model} GPU ({gpu_tier})\n"
        "{ram_gb}GB RAM\n"
        "{storage_gb}GB {storage_interface}\n"
        "Ready for Ollama / Stable Diffusion workloads"
    ),
    "creator": (
        "Built for content creation and streaming\n"
        "{cpu_model} ({cpu_tier})\n"
        "{gpu_model} graphics\n"
        "{ram_gb}GB RAM · {storage_gb}GB {storage_interface}"
    ),
}


def generate_listing_performance_text(
    use_case: str,
    cpu_model: str,
    cpu_tier: str,
    gpu_model: str,
    gpu_tier: str,
    ram_gb: float,
    storage_interface: str,
    storage_gb: float = 1000,
    vram_gb: Optional[float] = None,
) -> str:
    template = _USE_CASE_TEMPLATES.get(use_case, _USE_CASE_TEMPLATES["gaming"])
    return template.format(
        cpu_model=cpu_model,
        cpu_tier=cpu_tier,
        gpu_model=gpu_model,
        gpu_tier=gpu_tier,
        ram_gb=int(ram_gb),
        storage_gb=int(storage_gb),
        storage_interface=storage_interface,
        vram_gb=int(vram_gb) if vram_gb else "?",
    )
