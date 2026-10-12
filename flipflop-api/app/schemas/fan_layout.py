"""Validated per-asset procedural RGB fan layout."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProceduralFan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40)
    # Normalized coordinates on the selected case face.
    x: float = Field(ge=-1, le=1)
    y: float = Field(ge=-1, le=1)
    diameter_mm: float = Field(ge=60, le=200)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_image_index: int | None = Field(default=None, ge=0, le=3)
    source_image_url: str | None = Field(default=None, max_length=2000)


class FanLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    face: Literal["+z", "-z", "+x", "-x"] = "+z"
    mode: Literal["rainbow", "static", "breathing", "color-cycle", "off"] = "rainbow"
    color: str = Field(default="#ff4fb3", pattern=r"^#[0-9a-fA-F]{6}$")
    speed: float = Field(default=1, ge=0.1, le=3)
    fans: list[ProceduralFan] = Field(default_factory=list, max_length=24)
