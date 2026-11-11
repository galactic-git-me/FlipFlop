"""FlipFlop's deterministic PC part compatibility rules.

The upstream PCPartsCompatibilityProgram is a 2019 Expo prototype with a
SQLite CPU-spec table and generation scrapers; it does not contain a usable
compatibility engine. This service reuses FlipFlop's reviewed engineering
facts and fit checks, then applies the product's explicit hard-fail/warning
policy. Missing evidence stays unknown.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.studio_fit import evaluate_fit


WARNING_RULES = {
    "POWER", "BIOS", "M2_SLOT_COUNT", "SATA_PORT_COUNT", "SATA_BAY_COUNT",
    "RAM_CLEARANCE",
}


def _version(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, (str, int, float)):
        return None
    values = tuple(int(part) for part in re.findall(r"\d+", str(value)))
    return values or None


def _bios_check(parts: dict[str, dict[str, Any]], checks: list[dict[str, Any]]) -> None:
    cpu = parts.get("cpu") or {}
    board = parts.get("motherboard") or {}
    if cpu.get("reviewed") is not True or board.get("reviewed") is not True:
        return
    cpu_id = str(cpu.get("cpu_id") or "")
    required = cpu.get("required_bios_version") or cpu.get("bios_required_version")
    version_map = board.get("cpu_bios_versions") or board.get("bios_versions")
    if isinstance(version_map, dict) and cpu_id:
        required = required or version_map.get(cpu_id)
    installed = board.get("installed_bios_version") or board.get("bios_version")
    current = _version(installed)
    minimum = _version(required)
    if current and minimum:
        bios = next((item for item in checks if item.get("code") == "BIOS"), None)
        if bios:
            bios["severity"] = "warning" if current < minimum else "pass"
            bios["message"] = (
                f"BIOS {installed} is older than the CPU's required version {required}; update the motherboard BIOS before installing this CPU."
                if current < minimum else
                f"BIOS {installed} meets the CPU's required version {required}."
            )


def evaluate_pc_parts_compatibility(
    parts: dict[str, dict[str, Any]],
    case: dict[str, Any] | None = None,
    *,
    gpu_required: bool = True,
) -> dict[str, Any]:
    """Evaluate known engineering facts and classify warnings conservatively.

    Hard failures block the build. Warnings describe known risks that do not
    prove a physical incompatibility. Unknown measurements remain unknown and
    are never silently treated as a pass.
    """
    checks = evaluate_fit(parts, case or {}, gpu_required=gpu_required)
    for check in checks:
        if check.get("code") in WARNING_RULES and check.get("severity") == "error":
            check["severity"] = "warning"
    _bios_check(parts, checks)

    if any(item["severity"] == "error" for item in checks):
        status = "incompatible"
    elif any(item["severity"] == "unknown" for item in checks):
        status = "needs_specifications"
    elif any(item["severity"] == "warning" for item in checks):
        status = "compatible_with_warnings"
    else:
        status = "compatible"

    return {
        "status": status,
        "checks": checks,
        "ruleset": "flipflop-pc-compatibility-v1",
        "reference": "https://github.com/sr0409/PCPartsCompatibilityProgram",
        "physically_tested": False,
    }
