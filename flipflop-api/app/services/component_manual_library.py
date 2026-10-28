"""Exact model-key matching for the admin-curated component manual cache."""
from __future__ import annotations

import re
from typing import Any, Iterable


def normalize_manual_key(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


_COMPONENT_IDENTITY_FIELDS = (
    "component_key",
    "component_name",
    "model",
    "model_number",
    "mpn",
    "manufacturer_part_number",
    "part_number",
    "sku",
    "name",
    "title",
)


def _component_identity_keys(component: Any) -> set[str]:
    if isinstance(component, dict):
        values = [component.get(field) for field in _COMPONENT_IDENTITY_FIELDS]
        values = [value for value in values if isinstance(value, (str, int))]
    else:
        values = [component] if isinstance(component, (str, int)) else []
    return {normalized for value in values if (normalized := normalize_manual_key(str(value)))}


def matching_manuals(components: Iterable[Any], manuals: Iterable[Any]) -> list[dict[str, Any]]:
    """Return cached PDFs only when the manual key equals a build identity field.

    Substring matches are unsafe: a family or shorter model name must not select
    a manual for a different board, GPU revision, or component variant.
    """
    component_values = list(components or [])
    active_manuals = sorted(
        (manual for manual in manuals if manual.is_active),
        key=lambda manual: (len(normalize_manual_key(manual.component_key)), manual.id),
        reverse=True,
    )
    matches: list[dict[str, Any]] = []
    used_ids: set[int] = set()
    for index, component in enumerate(component_values):
        identity_keys = _component_identity_keys(component)
        for manual in active_manuals:
            key = normalize_manual_key(manual.component_key)
            if manual.id not in used_ids and len(key) >= 8 and key in identity_keys:
                matches.append({
                    "manual_id": manual.id,
                    "component_index": index,
                    "component_key": manual.component_key,
                    "component_name": manual.component_name,
                    "source_url": manual.source_url,
                    "filename": manual.filename,
                    "sha256": manual.sha256,
                    "size_bytes": manual.size_bytes,
                })
                used_ids.add(manual.id)
                break
    return matches
