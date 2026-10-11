"""Canonical normalization and provenance for the customer Getting Started guide."""
from __future__ import annotations

from hashlib import sha256


def normalize_guide_text(value: str | None) -> str | None:
    """Return the exact UTF-8 text form used by uploads and package creation."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return f"{normalized}\n" if normalized else None


def guide_snapshot(
    *,
    configured_guide: str | None,
    request_guide: str | None,
    generated_intro: str | None = None,
) -> tuple[str | None, dict[str, str | None]]:
    """Choose the highest-priority guide and bind its normalized content hash."""
    candidates = (
        ("admin_settings_upload", configured_guide),
        ("generation_request", request_guide),
        ("generated_manifest_intro", generated_intro),
    )
    for source, value in candidates:
        normalized = normalize_guide_text(value)
        if normalized is not None:
            return normalized, {
                "source": source,
                "sha256": sha256(normalized.encode("utf-8")).hexdigest(),
            }
    return None, {"source": "none", "sha256": None}
