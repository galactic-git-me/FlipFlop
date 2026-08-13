"""Structured case mount-point schema (flipflop-3d-builder-claude-prd.md §5-6).

Replaces treating Component3DAsset.anchor_manifest_json as an opaque blob for
CASE subjects — still stored as JSON (no new table), but validated against
this shape on write so a malformed manifest fails fast in the admin API
rather than silently breaking the renderer's placement logic later.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

MountCategory = Literal[
    "Motherboard", "GPU", "PSU", "CPUCooler", "CaseFan", "Storage",
]


class CaseMount(BaseModel):
    id: str
    category: MountCategory
    position_mm: tuple[float, float, float]
    rotation_deg: tuple[float, float, float] = (0, 0, 0)
    supported_formats: list[str] = Field(default_factory=list)
    max_dimensions_mm: Optional[tuple[float, float, float]] = None
    slots: Optional[int] = None
    fan_size_mm: Optional[Literal[120, 140]] = None


class CaseMountManifest(BaseModel):
    """The full manifest stored in Component3DAsset.anchor_manifest_json for
    a CASE-subject asset. case_envelope_mm is the outer case dimensions
    (depth, width, height) — mirrors CaseCatalogue's own dimension columns
    but kept here too since a manifest should be self-describing without a
    join back to the catalogue row."""

    case_envelope_mm: tuple[float, float, float]
    max_gpu_length_mm: Optional[float] = None
    max_cooler_height_mm: Optional[float] = None
    max_psu_length_mm: Optional[float] = None
    mounts: list[CaseMount] = Field(default_factory=list)


def validate_case_mount_manifest(raw: dict) -> CaseMountManifest:
    """Raises pydantic.ValidationError on malformed input — callers should
    catch and turn into an HTTP 422, not let it propagate as a 500."""
    return CaseMountManifest.model_validate(raw)
