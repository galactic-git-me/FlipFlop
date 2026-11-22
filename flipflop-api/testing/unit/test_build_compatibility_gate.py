from app.services.build_compatibility_gate import evaluate_build_compatibility


BASE_PARTS = {
    "cpu": {"reviewed": True, "socket": "am4", "power_w": 65, "cpu_id": "CPU-1", "integrated_graphics": True},
    "motherboard": {"reviewed": True, "socket": "am4", "ram_type": "ddr4", "ram_slots": 4,
                    "form_factor": "matx", "gpu_interfaces": ["pcie x16"], "bios_cpu_ids": ["CPU-1"],
                    "storage_interfaces": ["nvme"], "m2_lengths": [2280], "m2_slots": 1, "sata_ports": 4},
    "ram": {"reviewed": True, "ram_type": "ddr4", "ram_modules": 2, "ram_height_mm": 35},
    "gpu": {"reviewed": True, "gpu_interface": "pcie x16", "length_mm": 250, "power_w": 150,
            "gpu_power_connectors": {"8pin": 1}, "recommended_psu_w": 500},
    "cooling": {"reviewed": True, "supported_sockets": ["am4"], "cooler_type": "air", "height_mm": 150,
                "ram_clearance_mm": 42},
    "psu": {"reviewed": True, "form_factor": "atx", "length_mm": 140, "wattage": 650,
            "psu_connectors": {"8pin": 2}},
    "storage": {"reviewed": True, "storage_interface": "nvme", "m2_length": 2280},
}

CASE = {
    "form_factor": "matx", "max_gpu_length_mm": 300, "max_cooler_height_mm": 160,
    "radiator_support": {}, "engineering": {"psu_form_factors": ["atx"], "max_psu_length_mm": 160,
    "sata_bays": 2}, "supported_form_factors": ["atx", "matx", "itx"],
}


def test_complete_reviewed_build_passes_shared_gate():
    result = evaluate_build_compatibility(BASE_PARTS, CASE)
    assert result["status"] == "compatible_with_warnings"
    assert result["can_proceed"] is True
    assert result["authority"] == "deterministic_reviewed_specs"


def test_socket_mismatch_is_incompatible_and_blocked():
    parts = {**BASE_PARTS, "cpu": {**BASE_PARTS["cpu"], "socket": "am5"}}
    result = evaluate_build_compatibility(parts, CASE)
    assert result["status"] == "incompatible"
    assert result["can_proceed"] is False
    assert any(item["code"] == "CPU_SOCKET" and item["severity"] == "error" for item in result["checks"])


def test_missing_reviewed_specs_are_unverified_and_blocked():
    parts = {**BASE_PARTS, "ram": {"reviewed": False, "ram_type": "ddr4"}}
    result = evaluate_build_compatibility(parts, CASE)
    assert result["status"] == "unverified"
    assert result["can_proceed"] is False
    assert any(item["severity"] == "unknown" for item in result["checks"])


def test_curated_policy_still_blocks_unknown_publication_facts():
    parts = {**BASE_PARTS, "motherboard": {**BASE_PARTS["motherboard"], "reviewed": False}}
    result = evaluate_build_compatibility(parts, CASE, curated_policy=True)
    assert result["can_proceed"] is False
    assert any(item.get("stage") == "publication" and item["severity"] == "unknown" for item in result["checks"])
