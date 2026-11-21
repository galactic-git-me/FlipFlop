from types import SimpleNamespace

from app.services.component_manual_library import matching_manuals


def _manual(component_key: str, manual_id: int = 1):
    return SimpleNamespace(
        id=manual_id,
        is_active=True,
        component_key=component_key,
        component_name=f"Manual for {component_key}",
        source_url="https://manufacturer.example/support/manual.pdf",
        filename="manual.pdf",
        sha256="a" * 64,
        size_bytes=100,
    )


def test_manual_match_requires_exact_normalized_component_identity():
    components = [{
        "slot": "Motherboard",
        "name": "MSI B850 GAMING PLUS WIFI",
        "sku": "B850-GAMING-PLUS-WIFI",
    }]

    matches = matching_manuals(components, [
        _manual("MSI B850"),
        _manual("MSI B850 Gaming Plus WiFi", manual_id=2),
    ])

    assert len(matches) == 1
    assert matches[0]["manual_id"] == 2
    assert matches[0]["component_index"] == 0


def test_manual_match_does_not_search_unrelated_component_metadata():
    components = [{
        "slot": "GPU",
        "name": "GeForce RTX 4070 SUPER",
        "description": "Compatible with the NVIDIA RTX 40 Series",
    }]

    assert matching_manuals(components, [_manual("NVIDIA RTX 40 Series")]) == []


def test_inactive_manual_is_not_matched_even_with_exact_identity():
    inactive = _manual("AMD Ryzen 7 7800X3D")
    inactive.is_active = False

    assert matching_manuals(["AMD Ryzen 7 7800X3D"], [inactive]) == []


def test_string_component_requires_full_normalized_name_match():
    assert matching_manuals(
        ["AMD Ryzen 7 7800X3D"],
        [_manual("Ryzen 7 7800X3D"), _manual("AMD Ryzen 7 7800X3D", manual_id=2)],
    ) == [{
        "manual_id": 2,
        "component_index": 0,
        "component_key": "AMD Ryzen 7 7800X3D",
        "component_name": "Manual for AMD Ryzen 7 7800X3D",
        "source_url": "https://manufacturer.example/support/manual.pdf",
        "filename": "manual.pdf",
        "sha256": "a" * 64,
        "size_bytes": 100,
    }]
