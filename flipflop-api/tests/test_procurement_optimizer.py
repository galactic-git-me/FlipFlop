from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D

from app.services.commerce_pricing import Condition, ConditionPolicy, FulfilmentMode, SupplierOffer
from app.services.procurement_optimizer import ApprovedPart, optimise_bom


def offer(price: str, *, stock: bool = True, condition: Condition = Condition.NEW) -> SupplierOffer:
    return SupplierOffer(
        "Amazon", "retail", condition, D(price), D("0"), D("0"), D("0"),
        datetime.now(timezone.utc).isoformat(), stock, True, 1,
    )


def parts() -> list[ApprovedPart]:
    return [
        ApprovedPart("cpu-a", "cpu", offer("180"), True, cpu_cores=6, cpu_socket="AM5", cpu_tdp_w=65),
        ApprovedPart("board-a", "motherboard", offer("130"), True, motherboard_socket="AM5", motherboard_ram_generation="DDR5", motherboard_form_factor="ATX"),
        ApprovedPart("ram-a", "ram", offer("90"), True, ram_gb=16, ram_generation="DDR5"),
        ApprovedPart("ssd-a", "storage", offer("70"), True, storage_gb=1000),
        ApprovedPart("psu-a", "psu", offer("100"), True, psu_wattage=650),
        ApprovedPart("cooler-a", "cooling", offer("40"), True, cooler_sockets=("AM5",), cooler_tdp_w=120, cooler_height_mm=155),
        ApprovedPart("case-a", "case", offer("80"), True, case_form_factors=("ATX",), case_max_gpu_length_mm=350, case_max_cooler_height_mm=165),
        ApprovedPart("gpu-a", "gpu", offer("300"), True, gpu_vram_gb=12, gpu_length_mm=300, gpu_power_w=220),
        ApprovedPart("gpu-b", "gpu", offer("330"), True, gpu_vram_gb=12, gpu_length_mm=300, gpu_power_w=220),
    ]


def test_stock_change_selects_another_compliant_bom():
    minimums = {"cpu_cores": 6, "ram_gb": 16, "storage_gb": 1000, "gpu_vram_gb": 12, "gpu_required": True}
    candidates = parts()
    first = optimise_bom(minimums, candidates, FulfilmentMode.STANDARD, ConditionPolicy.NEW_ONLY, False)
    assert first["parts"]["gpu"] == "gpu-a"
    changed = [replace(part, offer=replace(part.offer, stock_confirmed=False)) if part.sku == "gpu-a" else part for part in candidates]
    second = optimise_bom(minimums, changed, FulfilmentMode.STANDARD, ConditionPolicy.NEW_ONLY, False)
    assert second["parts"]["gpu"] == "gpu-b"


def test_incompatible_or_nonnew_parts_cannot_enter_new_only_plan():
    minimums = {"cpu_cores": 6, "ram_gb": 16, "storage_gb": 1000, "gpu_vram_gb": 12, "gpu_required": True}
    candidates = parts()
    candidates = [replace(part, offer=replace(part.offer, condition=Condition.USED)) if part.role == "gpu" else part for part in candidates]
    assert optimise_bom(minimums, candidates, FulfilmentMode.STANDARD, ConditionPolicy.NEW_ONLY, False) is None
    candidates = parts()
    candidates = [replace(part, motherboard_socket="LGA1700") if part.role == "motherboard" else part for part in candidates]
    assert optimise_bom(minimums, candidates, FulfilmentMode.STANDARD, ConditionPolicy.NEW_ONLY, False) is None
