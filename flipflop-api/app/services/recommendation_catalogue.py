"""Fail-closed catalogue matching for customer recommendation sessions.

Catalogue BOMs are unpriced discovery candidates. They are returned only when
the public catalogue has fresh, active entries with reviewed compatibility
specifications. Ready-to-Ship matches must be listed, prebuilt units whose
stored component evidence meets every measurable hard minimum.
"""
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.build import Build
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing, ListingStatus
from app.models.manual_build import ManualBuild
from app.models.playbook import Playbook, PlaybookStatus
from app.models.product import Product, ProductStatus, ProductType
from app.services.configurator_compatibility import evaluate_configuration
from app.services.procurement_optimizer import ApprovedPart, find_compatible_catalogue_bom
from app.services.commerce_pricing import ConditionPolicy


_SEGMENT_NAMES = {
    "Great-value Gaming": "Great-value Gaming",
    "High-performance Gaming": "High-performance Gaming",
    "Student Hybrid": "Student Hybrid",
    "Business & Office": "Business & Office",
    "Content Creation": "Content Creation",
    "AI Workstation": "AI Workstation",
    "Software Development": "Software Development",
    "Family & Home": "Family & Home",
}
_ROLE_ALIASES = {"ssd": "storage", "cooler": "cooling"}
_FRESHNESS = timedelta(hours=24)
_MAX_BOM_CANDIDATES = 100_000


def _recent(value: str | None, now: datetime) -> bool:
    if not value:
        return False
    try:
        seen = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    age = now - seen.astimezone(timezone.utc)
    return timedelta(0) <= age <= _FRESHNESS


def _condition_allowed(raw: str | None, policy: ConditionPolicy) -> bool:
    condition = (raw or "").strip().lower().replace("_", " ")
    if condition in {"new", "new other", "brand new"}:
        return True
    if "refurb" in condition:
        return policy in {ConditionPolicy.NEW_OR_REFURBISHED, ConditionPolicy.USED_ALLOWED}
    if condition in {"used", "pre owned", "pre-owned", "used excellent", "used good", "used acceptable"}:
        return policy == ConditionPolicy.USED_ALLOWED
    return False


def _integer(spec: dict, *keys: str) -> int | None:
    for key in keys:
        value = spec.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return None


def _strings(spec: dict, *keys: str) -> tuple[str, ...]:
    for key in keys:
        value = spec.get(key)
        if isinstance(value, str) and value.strip():
            return (value.strip().lower(),)
        if isinstance(value, list):
            values = tuple(item.strip().lower() for item in value if isinstance(item, str) and item.strip())
            if values:
                return values
    return ()


def _approved_part(variant: CatalogueVariant, slot: PlaybookSlot, listing: Listing) -> ApprovedPart | None:
    raw = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
    spec = raw.get("configurator")
    if not isinstance(spec, dict) or spec.get("reviewed") is not True:
        return None
    role = _ROLE_ALIASES.get(slot.slot_type.lower(), slot.slot_type.lower())
    common = {
        "sku": f"catalogue:{variant.id}",
        "role": role,
        "offer": None,
        "approved": variant.status == "active" and listing.status == ListingStatus.active,
        "catalogue_variant_id": variant.id,
        "slot_id": slot.id,
        "title": listing.title,
    }
    if role == "cpu":
        return ApprovedPart(**common, cpu_cores=_integer(spec, "cpu_cores", "cores"),
                            cpu_socket=(spec.get("socket") or "").lower() or None,
                            cpu_tdp_w=_integer(spec, "power_w", "tdp_w"))
    if role == "gpu":
        return ApprovedPart(**common, gpu_vram_gb=_integer(spec, "gpu_vram_gb", "vram_gb"),
                            gpu_length_mm=_integer(spec, "length_mm", "gpu_length_mm"),
                            gpu_power_w=_integer(spec, "power_w", "gpu_power_w"))
    if role == "ram":
        return ApprovedPart(**common, ram_gb=_integer(spec, "ram_gb") or listing.ram_gb,
                            ram_generation=(spec.get("ram_type") or listing.ram_type or "").lower() or None)
    if role == "storage":
        return ApprovedPart(**common, storage_gb=_integer(spec, "storage_gb") or listing.storage_gb)
    if role == "motherboard":
        return ApprovedPart(**common, motherboard_socket=(spec.get("socket") or "").lower() or None,
                            motherboard_ram_generation=(spec.get("ram_type") or "").lower() or None,
                            motherboard_form_factor=(spec.get("form_factor") or "").lower() or None)
    if role == "psu":
        return ApprovedPart(**common, psu_wattage=_integer(spec, "wattage", "psu_wattage") or listing.psu_wattage)
    if role == "cooling":
        return ApprovedPart(**common, cooler_sockets=_strings(spec, "supported_sockets"),
                            cooler_tdp_w=_integer(spec, "cooling_capacity_w", "tdp_w"),
                            cooler_height_mm=_integer(spec, "height_mm", "cooler_height_mm"))
    if role == "case":
        return ApprovedPart(**common, case_form_factors=_strings(spec, "supported_form_factors"),
                            case_max_gpu_length_mm=_integer(spec, "max_gpu_length_mm"),
                            case_max_cooler_height_mm=_integer(spec, "max_cooler_height_mm"))
    return None


async def find_catalogue_bom_candidates(
    db: AsyncSession,
    envelope: dict,
    performance_options: list[dict],
    condition_policy: str,
) -> list[dict]:
    policy = ConditionPolicy(condition_policy)
    playbook = (
        await db.execute(
            select(Playbook).where(
                Playbook.name == _SEGMENT_NAMES.get(envelope["segment"], ""),
                Playbook.status == PlaybookStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if not playbook:
        return [{"option_id": option["id"], "status": "suppressed", "reason_code": "no_active_playbook"} for option in performance_options]

    slots = list((await db.execute(select(PlaybookSlot).where(
        PlaybookSlot.playbook_id == playbook.id,
        PlaybookSlot.is_customer_visible == True,  # noqa: E712
    ))).scalars().all())
    slot_by_id = {slot.id: slot for slot in slots}
    if not slots:
        return [{"option_id": option["id"], "status": "suppressed", "reason_code": "no_public_slots"} for option in performance_options]

    visibility = list((await db.execute(select(ConfiguratorCatalogueVisibility).where(
        ConfiguratorCatalogueVisibility.playbook_slot_id.in_(slot_by_id)
    ))).scalars().all())
    visibility_by_slot: dict[int, list[ConfiguratorCatalogueVisibility]] = {}
    for row in visibility:
        visibility_by_slot.setdefault(row.playbook_slot_id, []).append(row)

    rows = (await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(
            CatalogueVariant.slot_id.in_(slot_by_id),
            CatalogueVariant.status == "active",
            Listing.status == ListingStatus.active,
        )
    )).all()
    now = datetime.now(timezone.utc)
    candidates: list[ApprovedPart] = []
    for variant, listing in rows:
        slot_visibility = visibility_by_slot.get(variant.slot_id, [])
        if slot_visibility and not any(
            row.catalogue_variant_id == variant.id and row.is_publicly_visible
            for row in slot_visibility
        ):
            continue
        if not _recent(variant.last_seen_at, now) or not _condition_allowed(listing.condition, policy):
            continue
        candidate = _approved_part(variant, slot_by_id[variant.slot_id], listing)
        if candidate:
            candidates.append(candidate)

    required_roles = {"cpu", "motherboard", "ram", "storage", "psu", "cooling", "case"}
    if envelope["hard_minimums"].get("gpu_required"):
        required_roles.add("gpu")
    published_roles = {_ROLE_ALIASES.get(slot.slot_type.lower(), slot.slot_type.lower()) for slot in slots}
    if not required_roles.issubset(published_roles):
        reason = "required_component_slots_missing"
        return [{"option_id": option["id"], "status": "suppressed", "reason_code": reason} for option in performance_options]

    output = []
    tier_for_option = {"save": "budget", "recommended": "mid", "stretch": "high"}
    for option in performance_options:
        option_minimums = dict(envelope["hard_minimums"])
        for key, value in option.get("targets", {}).items():
            if isinstance(value, int) and isinstance(option_minimums.get(key), int):
                option_minimums[key] = max(option_minimums[key], value)
        tier = tier_for_option.get(option["id"], "budget")
        tier_slots = {slot.id for slot in slots}
        tier_variant_ids = {variant.id for variant, _ in rows if variant.slot_id in tier_slots and variant.tier == tier}
        tier_candidates = [part for part in candidates if part.catalogue_variant_id in tier_variant_ids]
        try:
            possible = find_compatible_catalogue_bom(option_minimums, tier_candidates, limit=10)
        except ValueError:
            output.append({"option_id": option["id"], "status": "suppressed", "reason_code": "candidate_search_limit"})
            continue
        selected = None
        for bom in possible:
            selections = {part["slot_id"]: part["catalogue_variant_id"] for part in bom["parts"]}
            compatibility = await evaluate_configuration(db, playbook.id, selections)
            verdict_by_slot = {item["slot_id"]: item for item in compatibility.get("slots", [])}
            known_and_compatible = True
            for part in bom["parts"]:
                verdict = verdict_by_slot.get(part["slot_id"])
                selected_verdict = next((row for row in (verdict or {}).get("variants", []) if row["variant_id"] == part["catalogue_variant_id"]), None)
                if not selected_verdict or not selected_verdict["is_compatible"]:
                    known_and_compatible = False
                    break
            if known_and_compatible:
                selected = bom
                break
        output.append({
            "option_id": option["id"],
            "status": "candidate" if selected else "suppressed",
            "reason_code": None if selected else "no_fully_evidenced_compatible_bom",
            "bom": selected,
            "availability": "not_checked",
            "price": "not_checked",
        })
    return output


def _component_capabilities(components: list, performance_card: dict) -> dict[str, int | None]:
    """Read only explicit values; model-name guesses are not used for matching."""
    capabilities: dict[str, int | None] = {
        "cpu_cores": None, "ram_gb": None, "storage_gb": None, "gpu_vram_gb": None,
    }
    aliases = {
        "cpu_cores": ("cpu_cores", "cores", "core_count"),
        "ram_gb": ("ram_gb", "capacity_gb"),
        "storage_gb": ("storage_gb", "capacity_gb"),
        "gpu_vram_gb": ("gpu_vram_gb", "vram_gb"),
    }
    nested_names = {
        "cpu_cores": ("cpu",),
        "ram_gb": ("ram", "memory"),
        "storage_gb": ("storage",),
        "gpu_vram_gb": ("gpu", "graphics"),
    }
    sources = [performance_card, performance_card.get("capabilities", {})]
    for category in nested_names["cpu_cores"] + nested_names["ram_gb"] + nested_names["storage_gb"] + nested_names["gpu_vram_gb"]:
        nested = performance_card.get(category)
        if isinstance(nested, dict):
            sources.append(nested)
    for key, keys in aliases.items():
        for source in sources:
            if not isinstance(source, dict):
                continue
            for name in keys:
                value = source.get(name)
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    capabilities[key] = value
                    break
            if capabilities[key] is not None:
                break
    for item in components if isinstance(components, list) else []:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "").lower()
        name = str(item.get("name") or "")
        if capabilities["cpu_cores"] is None and ("cpu" in slot or "processor" in slot):
            match = re.search(r"\b(\d{1,2})\s*[- ]?cores?\b", name, re.IGNORECASE)
            if match:
                capabilities["cpu_cores"] = int(match.group(1))
        if capabilities["ram_gb"] is None and ("ram" in slot or "memory" in slot):
            match = re.search(r"\b(\d{1,3})\s*gb\b", name, re.IGNORECASE)
            if match:
                capabilities["ram_gb"] = int(match.group(1))
        if capabilities["gpu_vram_gb"] is None and ("gpu" in slot or "graphics" in slot):
            match = re.search(r"\b(\d{1,2})\s*gb\b", name, re.IGNORECASE)
            if match:
                capabilities["gpu_vram_gb"] = int(match.group(1))
        if capabilities["storage_gb"] is None and any(word in slot for word in ("ssd", "storage", "drive")):
            match = re.search(r"\b(\d+(?:\.\d+)?)\s*(tb|gb)\b", name, re.IGNORECASE)
            if match:
                amount = float(match.group(1))
                capabilities["storage_gb"] = int(amount * (1000 if match.group(2).lower() == "tb" else 1))
    return capabilities


def _condition_matches_policy(raw: str | None, policy: ConditionPolicy) -> bool:
    value = (raw or "").strip().upper().replace(" ", "_")
    if value in {"NEW", "NEW_OTHER"}:
        return True
    if value in {"REFURBISHED", "CERTIFIED_REFURBISHED"}:
        return policy in {ConditionPolicy.NEW_OR_REFURBISHED, ConditionPolicy.USED_ALLOWED}
    if value.startswith("USED") or value in {"PRE_OWNED", "LIKE_NEW"}:
        return policy == ConditionPolicy.USED_ALLOWED
    return False


async def find_ready_to_ship_matches(db: AsyncSession, envelope: dict, condition_policy: str) -> list[dict]:
    policy = ConditionPolicy(condition_policy)
    products = list((await db.execute(
        select(Product)
        .options(selectinload(Product.build))
        .where(Product.product_type == ProductType.PREBUILT, Product.status == ProductStatus.LISTED)
        .order_by(Product.created_at.desc())
    )).scalars().all())
    manual_ids = {product.build.manual_build_id for product in products if product.build and product.build.manual_build_id}
    manual_builds = {}
    if manual_ids:
        manual_builds = {build.id: build for build in (await db.execute(
            select(ManualBuild).where(ManualBuild.id.in_(manual_ids))
        )).scalars().all()}

    minimums = envelope["hard_minimums"]
    matches = []
    for product in products:
        build = product.build
        manual = manual_builds.get(build.manual_build_id) if build and build.manual_build_id else None
        if not build or not manual or not _condition_matches_policy(manual.ebay_condition, policy):
            continue
        evidence = manual.evidence_data if isinstance(manual.evidence_data, dict) else {}
        performance_card = evidence.get("performance_card")
        if not isinstance(performance_card, dict):
            continue
        capabilities = _component_capabilities(build.spec_json or [], performance_card)
        required = ["cpu_cores", "ram_gb", "storage_gb"]
        if minimums.get("gpu_required"):
            required.append("gpu_vram_gb")
        if any(capabilities[key] is None for key in required):
            continue
        if capabilities["cpu_cores"] < minimums["cpu_cores"] or capabilities["ram_gb"] < minimums["ram_gb"] or capabilities["storage_gb"] < minimums["storage_gb"]:
            continue
        if minimums.get("gpu_required") and capabilities["gpu_vram_gb"] < minimums["gpu_vram_gb"]:
            continue
        matches.append({
            "product_id": product.id,
            "title": product.title,
            "hero_photo_url": product.hero_photo_url,
            "href": f"/ready-to-ship/{product.id}",
            "capabilities": capabilities,
            "status": "listed_prebuilt_match",
        })
        if len(matches) >= 3:
            break
    return matches
