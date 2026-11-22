"""Shared deterministic compatibility gate for every proposed desktop build.

The underlying rule engine is the reviewed, deterministic ``studio_fit``
implementation. LLM compatibility reviews remain advisory and never affect
this verdict. Missing facts are represented as unknown, not as a pass.
"""
from __future__ import annotations

from typing import Any
import re

from app.services.studio_fit import evaluate_fit


def _gpu_interface_severity(actual: Any, supported: Any) -> str:
    if not actual or not isinstance(supported, list) or not supported:
        return "unknown"
    actual_text = str(actual).casefold()
    if "pcie" not in actual_text and "pci express" not in actual_text:
        return "error"
    match = re.search(r"x\s*(\d+)", actual_text)
    required_lanes = int(match.group(1)) if match else None
    board_texts = [str(value).casefold() for value in supported]
    if not any("pcie" in value or "pci express" in value for value in board_texts):
        return "error"
    if required_lanes is None:
        return "pass" if any(actual_text == value for value in board_texts) else "unknown"
    board_lanes = [int(found.group(1)) for value in board_texts
                   if (found := re.search(r"x\s*(\d+)", value))]
    if not board_lanes:
        return "unknown"
    # PCI Express generations are backward-compatible; the motherboard slot
    # must offer at least the GPU's lane width, generation need not be equal.
    return "pass" if max(board_lanes) >= required_lanes else "error"


def evaluate_playbook_build_compatibility(
    parts: dict[str, dict[str, Any]], case: dict[str, Any] | None,
    *, gpu_required: bool = True,
) -> dict[str, Any]:
    """Apply the shared full-fit rules and attach curated publication stages."""
    return evaluate_build_compatibility(parts, case, gpu_required=gpu_required, curated_policy=True)


def evaluate_build_compatibility(
    parts: dict[str, dict[str, Any]],
    case: dict[str, Any] | None,
    *,
    gpu_required: bool = True,
    curated_policy: bool = False,
    required_socket: str | None = None,
) -> dict[str, Any]:
    """Evaluate a complete selected BOM using the shared deterministic rules.

    All profiles receive the full physical-fit checks. Curated checks carry
    publication/workshop stage labels for traceability, but unknown facts are
    still blocking in all build pathways; an LLM cannot turn them into a pass.
    """
    checks = evaluate_fit(parts, case or {}, gpu_required=gpu_required)
    if curated_policy:
        publication_codes = {"CPU_SOCKET", "RAM_TYPE", "BOARD_FIT", "INTEGRATED_GRAPHICS", "GPU_INTERFACE"}
        for item in checks:
            item["stage"] = "publication" if item.get("code") in publication_codes else "workshop"
    if required_socket:
        for role in ("cpu", "motherboard"):
            component = parts.get(role) or {}
            actual_socket = component.get("socket") if component.get("reviewed") is True else None
            severity = ("unknown" if not actual_socket else
                        "pass" if str(actual_socket).casefold() == required_socket.casefold() else "error")
            checks.append({"code": "PLATFORM_SOCKET", "severity": severity,
                "message": f"{role.title()} platform socket: " +
                    (f"{actual_socket} matches {required_socket.upper()}." if severity == "pass" else
                     f"{actual_socket} does not match {required_socket.upper()}." if severity == "error" else
                     f"reviewed {required_socket.upper()} socket evidence needed."),
                "affected": [role]})
    if gpu_required or "gpu" in parts:
        gpu = parts.get("gpu") or {}
        board = parts.get("motherboard") or {}
        actual = gpu.get("gpu_interface") if gpu.get("reviewed") is True else None
        supported = board.get("gpu_interfaces") if board.get("reviewed") is True else None
        severity = _gpu_interface_severity(actual, supported)
        check = next((item for item in checks if item.get("code") == "GPU_INTERFACE"), None)
        if check is None:
            check = {"code": "GPU_INTERFACE", "affected": ["gpu", "motherboard"],
                     **({"stage": "publication"} if curated_policy else {})}
            checks.append(check)
        check.update(severity=severity,
            message="GPU and motherboard expansion interface: " +
                ("compatible." if severity == "pass" else "incompatible." if severity == "error" else "source specifications needed."))
    blocking = [
        item for item in checks
        if item.get("severity") in {"error", "unknown"}
    ]
    unknown = [item for item in checks if item.get("severity") == "unknown"]
    if any(item.get("severity") == "error" for item in checks):
        status = "incompatible"
    elif unknown:
        status = "unverified"
    elif any(item.get("severity") == "warning" for item in checks):
        status = "compatible_with_warnings"
    else:
        status = "compatible"
    return {
        "status": status,
        "checks": checks,
        "can_proceed": not blocking,
        "ruleset": "flipflop-pc-compatibility-v1",
        "authority": "deterministic_reviewed_specs",
    }
