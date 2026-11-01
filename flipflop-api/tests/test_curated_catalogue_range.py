"""Deterministic range-policy checks; no providers, database or services."""
from types import SimpleNamespace
from collections import Counter

from app.services.curated_catalogue_range import (
    _matches_requirement, range_bucket, select_curated_range,
)


def product(category, rank, title=None, asin=None):
    return SimpleNamespace(category=category, rank=rank,
        title=title or f"{category} product {rank}", asin=asin or f"{category}-{rank}")


def test_independent_top_tens_and_all_cases():
    rows = [product(role, rank) for role in ("cpu", "motherboard", "gpu", "ram", "psu", "cooler") for rank in range(1, 16)]
    rows += [product("case", rank) for rank in range(1, 151)]
    rows += [product("storage", rank, f"1TB {interface} SSD", f"{interface}-{rank}")
        for interface in ("NVMe", "SATA") for rank in range(1, 16)]
    selected, _ = select_curated_range(rows, [])
    assert Counter(range_bucket(row.category, row.title) for row in selected) == {
        "cpu": 10, "motherboard": 10, "gpu": 10, "ram": 10, "psu": 10,
        "cooling": 10, "nvme": 10, "sata": 10, "case": 150,
    }


def test_rank_turnover_replaces_without_accumulating():
    rows = [product("psu", rank) for rank in range(1, 12)]
    first, _ = select_curated_range(rows, [])
    second, _ = select_curated_range(rows[1:], [])
    assert "psu-1" in {row.asin for row in first}
    assert "psu-1" not in {row.asin for row in second}
    assert "psu-11" in {row.asin for row in second}


def test_only_needed_exception_is_added_with_reason():
    rows = [product("cpu", rank, f"AMD Ryzen 9 {9900 + rank}X Processor") for rank in range(1, 16)]
    selected, reasons = select_curated_range(rows, [{"name": "Specialist AI", "components": {"cpu": "AMD Ryzen 9 9913X"}}])
    assert len(selected) == 11
    assert reasons["cpu", "cpu-13"]["kind"] == "playbook_requirement"
    assert reasons["cpu", "cpu-13"]["cell"] == "Specialist AI"
    assert "cpu-12" not in {row.asin for row in selected}


def test_secondary_drive_requirement_has_its_own_exception():
    rows = [product("storage", rank, "2TB NVMe SSD") for rank in range(1, 11)]
    rows.append(product("storage", 23, "4TB NVMe SSD"))
    selected, reasons = select_curated_range(rows, [{"name": "Workstation", "components": {"storage": "2TB NVMe SSD + 4TB NVMe SSD"}}])
    assert len(selected) == 11
    assert reasons["storage", "storage-23"]["requirement"] == "4TB NVMe SSD"


def test_historical_identity_cannot_enter_normal_top_ten():
    old = product("psu", None, "Historical PSU", "historical")
    selected, _ = select_curated_range([old], [])
    assert selected == []


def test_ambiguous_interface_and_memory_requirements():
    assert range_bucket("storage", "M.2 SSD") is None
    assert range_bucket("storage", "M.2 SATA SSD") == "sata"
    assert not _matches_requirement("ram", "128GB DDR5 UDIMM", "128GB DDR5 ECC RDIMM")


if __name__ == "__main__":
    checks = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for check in checks:
        check()
    print(f"PASS: {len(checks)} isolated catalogue range policy checks")
