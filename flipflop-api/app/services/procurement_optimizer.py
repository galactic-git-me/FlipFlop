"""Conservative BOM search over explicitly approved, evidenced parts.

The caller owns stock ingestion. Missing compatibility attributes reject a
combination instead of being silently treated as compatible.
"""
from dataclasses import dataclass
from decimal import Decimal
from itertools import product
from math import prod

from app.services.commerce_pricing import (
    ConditionPolicy, FulfilmentMode, SupplierOffer, eligible_offers,
)

REQUIRED_ROLES = ("cpu", "motherboard", "ram", "storage", "psu", "cooling", "case")


@dataclass(frozen=True)
class ApprovedPart:
    sku: str
    role: str
    offer: SupplierOffer
    approved: bool
    cpu_cores: int | None = None
    cpu_socket: str | None = None
    cpu_tdp_w: int | None = None
    gpu_vram_gb: int | None = None
    gpu_length_mm: int | None = None
    gpu_power_w: int | None = None
    ram_gb: int | None = None
    ram_generation: str | None = None
    storage_gb: int | None = None
    motherboard_socket: str | None = None
    motherboard_ram_generation: str | None = None
    motherboard_form_factor: str | None = None
    psu_wattage: int | None = None
    cooler_sockets: tuple[str, ...] = ()
    cooler_tdp_w: int | None = None
    cooler_height_mm: int | None = None
    case_form_factors: tuple[str, ...] = ()
    case_max_gpu_length_mm: int | None = None
    case_max_cooler_height_mm: int | None = None


def _meets_minimum(part: ApprovedPart, minimums: dict) -> bool:
    threshold = {
        "cpu": (part.cpu_cores, minimums.get("cpu_cores", 0)),
        "gpu": (part.gpu_vram_gb, minimums.get("gpu_vram_gb", 0)),
        "ram": (part.ram_gb, minimums.get("ram_gb", 0)),
        "storage": (part.storage_gb, minimums.get("storage_gb", 0)),
    }.get(part.role)
    return threshold is None or (threshold[0] is not None and threshold[0] >= threshold[1])


def _compatible(parts: dict[str, ApprovedPart]) -> bool:
    cpu, board, ram, psu, cooler, case = (parts[role] for role in REQUIRED_ROLES if role != "storage")
    if not all((cpu.cpu_socket, cpu.cpu_tdp_w, board.motherboard_socket,
                board.motherboard_ram_generation, board.motherboard_form_factor,
                ram.ram_generation, psu.psu_wattage, cooler.cooler_sockets,
                cooler.cooler_tdp_w, cooler.cooler_height_mm, case.case_form_factors,
                case.case_max_cooler_height_mm)):
        return False
    if cpu.cpu_socket != board.motherboard_socket or ram.ram_generation != board.motherboard_ram_generation:
        return False
    if board.motherboard_form_factor not in case.case_form_factors:
        return False
    if cpu.cpu_socket not in cooler.cooler_sockets or cooler.cooler_tdp_w < cpu.cpu_tdp_w:
        return False
    if cooler.cooler_height_mm > case.case_max_cooler_height_mm:
        return False
    gpu = parts.get("gpu")
    if gpu:
        if gpu.gpu_power_w is None or gpu.gpu_length_mm is None or case.case_max_gpu_length_mm is None:
            return False
        if gpu.gpu_length_mm > case.case_max_gpu_length_mm:
            return False
    return psu.psu_wattage >= cpu.cpu_tdp_w + (gpu.gpu_power_w if gpu else 0) + 100


def optimise_bom(
    minimums: dict,
    candidates: list[ApprovedPart],
    mode: FulfilmentMode,
    policy: ConditionPolicy,
    consent: bool,
    *, priority_capacity: bool = False,
    parts_cost_ceiling_gbp: Decimal | None = None,
) -> dict | None:
    roles = REQUIRED_ROLES + (("gpu",) if minimums.get("gpu_required") else ())
    by_role: dict[str, list[ApprovedPart]] = {role: [] for role in roles}
    for part in candidates:
        if part.role not in by_role or not part.approved or not _meets_minimum(part, minimums):
            continue
        if not eligible_offers([part.offer], mode, policy, consent, priority_capacity=priority_capacity):
            continue
        by_role[part.role].append(part)
    if any(not values for values in by_role.values()):
        return None
    pools = [sorted(by_role[role], key=lambda part: part.offer.landed_gbp + part.offer.risk_gbp) for role in roles]
    if prod(len(pool) for pool in pools) > 100_000:
        raise ValueError("Candidate set exceeds safe exhaustive search size")
    best = None
    best_score = None
    for combination in product(*pools):
        chosen = dict(zip(roles, combination))
        if not _compatible(chosen):
            continue
        landed = sum((part.offer.landed_gbp for part in combination), Decimal("0"))
        if parts_cost_ceiling_gbp is not None and landed > parts_cost_ceiling_gbp:
            continue
        risk = sum((part.offer.risk_gbp for part in combination), Decimal("0"))
        delivery_penalty = sum((Decimal(part.offer.delivery_working_days or 0) for part in combination), Decimal("0"))
        score = landed + risk + delivery_penalty
        if best_score is None or score < best_score:
            best, best_score = chosen, score
    if best is None:
        return None
    return {
        "parts": {role: part.sku for role, part in best.items()},
        "supplier_offers": {role: {"supplier": part.offer.supplier, "condition": part.offer.condition.value,
                                    "landed_gbp": str(part.offer.landed_gbp), "observed_at": part.offer.observed_at}
                            for role, part in best.items()},
        "landed_parts_gbp": str(sum((part.offer.landed_gbp for part in best.values()), Decimal("0"))),
        "mode": mode.value,
    }
