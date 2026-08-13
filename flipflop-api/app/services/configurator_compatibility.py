"""Configurator live-compatibility evaluation (Commerce PRD Ch.12.4).

Given a partial selection map ({slot_id: variant_id}) plus an optional case,
returns per-slot, per-variant verdicts {is_compatible, reason, confidence}.

Two evaluation layers, combined:
  1. Data-driven `compatibility_rules` rows (structured constraint_json).
  2. Text-inference heuristics reused from `compatibility_engine`
     (socket era, DDR generation, GPU TDP, PSU wattage) — these fill the gap
     while catalogue variants carry no structured spec fields.

Unknown = compatible with a warning, never a hard block: the configurator
must not grey out parts on missing data (honesty principle: only block on a
positive signal of conflict).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import CatalogueVariant, PlaybookSlot, CaseCatalogue
from app.models.configurator import CompatibilityRule, CompatibilityRuleType
from app.models.listing import Listing
from app.models.motherboard_spec import MotherboardSpec
from app.services.compatibility_engine import (
    _extract_ram_type,
    _gpu_tdp_from_text,
    _extract_psu_watts,
    _infer_cpu_socket,
    _extract_ram_capacity_gb,
)
from app.services.motherboard_matching import match_motherboard_spec

# Four-tier verdict model (PC_BUILDER_DISCOVERY_AND_IMPLEMENTATION_PLAN.md §10).
# HARD_INCOMPATIBLE blocks purchase; NOT_RECOMMENDED and RECOMMENDED are both
# still purchasable (never hard-block on a soft signal) but change how the
# customer-facing UI badges the option. RECOMMENDED is currently unpopulated
# by any heuristic below — it's reserved for admin-curated pairings via a
# future CompatibilityRuleType, not something this text-inference layer
# should claim with any confidence.
HARD_INCOMPATIBLE = "hard_incompatible"
NOT_RECOMMENDED = "not_recommended"
COMPATIBLE = "compatible"
RECOMMENDED = "recommended"

# GPU keywords whose *typical* card length runs long enough that a compact
# case becomes a real clearance risk. This is a soft, best-effort signal, not
# a real length comparison — no structured GPU dimension field exists yet
# (see plan doc §13/§19 — component-level physical dimensions are still a gap).
_LIKELY_LONG_GPU_KEYWORDS = (
    "4090", "4080", "3090", "3080 ti", "7900 xtx", "7900 xt", "6900 xt",
)
# Below this, treat the case as "compact" for the clearance warning. Real ATX
# mid-towers with excellent clearance don't publish max_gpu_length_mm below
# this threshold in practice; ITX/SFF cases commonly do.
_COMPACT_CASE_GPU_CLEARANCE_MM = 330

# Sockets that only ever paired with one DDR generation. Mixed-support
# sockets (lga1700 supports DDR4 and DDR5) are deliberately absent.
_SOCKET_RAM_GENERATION = {
    "am4": "ddr4",
    "am5": "ddr5",
    "lga1151": "ddr4",
    "lga1200": "ddr4",
}


# Stable rule codes (flipflop-3d-builder-claude-prd.md §9: "Rules return a
# stable code, severity, customer message, developer detail and affected part
# IDs"). Codes are contracts — never rename an existing one; add a new code
# instead if a check's meaning changes, since frontend/e2e tests may assert
# against these strings.
RULE_RAM_TYPE_MISMATCH = "RAM_TYPE_MISMATCH"
RULE_RAM_CAPACITY_LOW = "RAM_CAPACITY_LOW"
RULE_RAM_CAPACITY_EXCEEDS_BOARD = "RAM_CAPACITY_EXCEEDS_BOARD"
RULE_CPU_SOCKET_MISMATCH = "CPU_SOCKET_MISMATCH"
RULE_COOLER_SOCKET_MISMATCH = "COOLER_SOCKET_MISMATCH"
RULE_PSU_INSUFFICIENT = "PSU_INSUFFICIENT"
RULE_GPU_CLEARANCE = "GPU_CLEARANCE"
RULE_DB_RULE = "CUSTOM_RULE"  # from a CompatibilityRule DB row — see rule.id for specifics


@dataclass
class VariantVerdict:
    variant_id: int
    is_compatible: bool = True
    reason: str | None = None
    rule_code: str | None = None
    warnings: list[str] = field(default_factory=list)
    # Additive field — is_compatible stays the source of truth for existing
    # API consumers (frontend VariantVerdict type in lib/asset-api.ts); verdict
    # carries the finer-grained tier on top without changing that contract.
    verdict: str = COMPATIBLE

    def fail(self, reason: str, code: str | None = None) -> "VariantVerdict":
        self.is_compatible = False
        self.verdict = HARD_INCOMPATIBLE
        self.reason = reason
        self.rule_code = code
        return self

    def flag_not_recommended(self, warning: str, code: str | None = None) -> "VariantVerdict":
        # Stays purchasable — is_compatible untouched — but the UI can badge
        # it differently once verdict is surfaced through the API response.
        if self.verdict == COMPATIBLE:
            self.verdict = NOT_RECOMMENDED
            self.rule_code = code
        self.warnings.append(warning)
        return self


def _selected_text(selected: dict[str, str]) -> str:
    return " | ".join(selected.values())


def _judge_variant(
    slot_type: str,
    candidate_title: str,
    selected: dict[str, str],
    case: CaseCatalogue | None,
    mobo_specs: list[MotherboardSpec] | None = None,
) -> VariantVerdict:
    """Heuristic cross-slot checks for one candidate variant against the
    currently selected titles in *other* slots."""
    verdict = VariantVerdict(variant_id=0)
    mobo_specs = mobo_specs or []

    cpu_text = selected.get("cpu", "")
    cpu_socket = _infer_cpu_socket(cpu_text) if cpu_text else None

    mobo_text = selected.get("motherboard", "")
    selected_mobo_spec = match_motherboard_spec(mobo_text, mobo_specs) if mobo_text else None

    def _socket_conflict(a_socket: str, b_socket: str, spec: MotherboardSpec, message: str) -> bool:
        """Shared reviewed-gating: an unreviewed AI-extracted spec can only
        ever produce a soft warning, per MotherboardSpec's docstring — only a
        human-reviewed row is trusted enough to hard-block a purchase."""
        if a_socket == b_socket:
            return False
        if spec.reviewed:
            verdict.fail(message, RULE_CPU_SOCKET_MISMATCH)
        else:
            verdict.flag_not_recommended(f"{message} (unverified match — please double-check)", RULE_CPU_SOCKET_MISMATCH)
        return True

    if slot_type == "ram":
        ram_type = _extract_ram_type(candidate_title)

        if selected_mobo_spec and selected_mobo_spec.ram_type and ram_type:
            # Precise check when we recognise the exact board — takes priority
            # over the CPU-socket-based guess below.
            if ram_type != selected_mobo_spec.ram_type:
                msg = (
                    f"{ram_type.upper()} doesn't fit the selected "
                    f"{selected_mobo_spec.canonical_model} ({selected_mobo_spec.ram_type.upper()} only)"
                )
                if selected_mobo_spec.reviewed:
                    return verdict.fail(msg, RULE_RAM_TYPE_MISMATCH)
                verdict.flag_not_recommended(f"{msg} (unverified match — please double-check)", RULE_RAM_TYPE_MISMATCH)
        elif ram_type and cpu_socket:
            required = _SOCKET_RAM_GENERATION.get(cpu_socket)
            if required and ram_type != required:
                return verdict.fail(
                    f"{ram_type.upper()} is incompatible with the selected CPU platform "
                    f"({cpu_socket.upper()} uses {required.upper()})",
                    RULE_RAM_TYPE_MISMATCH,
                )

        # Capacity signal, independent of platform match — 4-8GB is a real,
        # generation-independent limitation for a build sold today, not a
        # compatibility conflict, so this is a soft NOT_RECOMMENDED, never a fail.
        capacity_gb = _extract_ram_capacity_gb(candidate_title)
        if capacity_gb is not None and capacity_gb <= 8:
            verdict.flag_not_recommended(
                f"{capacity_gb}GB is on the low side for a modern build — "
                "16GB+ is recommended for most workloads",
                RULE_RAM_CAPACITY_LOW,
            )
        # Precise capacity-vs-board check when the exact board is known.
        if capacity_gb is not None and selected_mobo_spec and selected_mobo_spec.max_ram_gb:
            if capacity_gb > selected_mobo_spec.max_ram_gb:
                verdict.flag_not_recommended(
                    f"{capacity_gb}GB exceeds the {selected_mobo_spec.canonical_model}'s "
                    f"{selected_mobo_spec.max_ram_gb}GB maximum",
                    RULE_RAM_CAPACITY_EXCEEDS_BOARD,
                )

    if slot_type == "cpu":
        candidate_socket = _infer_cpu_socket(candidate_title)

        # New check that didn't exist before motherboard became a real slot:
        # candidate CPU vs the selected motherboard's actual socket.
        if candidate_socket and selected_mobo_spec and selected_mobo_spec.socket:
            if _socket_conflict(
                candidate_socket, selected_mobo_spec.socket, selected_mobo_spec,
                f"This CPU is {candidate_socket.upper()} but the selected "
                f"{selected_mobo_spec.canonical_model} is {selected_mobo_spec.socket.upper()}",
            ):
                return verdict

        # Reverse of the RAM check: candidate CPU vs already-selected RAM.
        ram_text = selected.get("ram", "")
        ram_type = _extract_ram_type(ram_text) if ram_text else None
        if candidate_socket and ram_type:
            required = _SOCKET_RAM_GENERATION.get(candidate_socket)
            if required and ram_type != required:
                return verdict.fail(
                    f"This CPU's platform ({candidate_socket.upper()}) requires "
                    f"{required.upper()} — you have {ram_type.upper()} RAM selected",
                    RULE_RAM_TYPE_MISMATCH,
                )

    if slot_type == "motherboard":
        # Reverse direction of the cpu-slot check above: candidate motherboard
        # vs the already-selected CPU's socket.
        candidate_spec = match_motherboard_spec(candidate_title, mobo_specs)
        if candidate_spec and candidate_spec.socket and cpu_socket:
            if _socket_conflict(
                cpu_socket, candidate_spec.socket, candidate_spec,
                f"This board is {candidate_spec.socket.upper()} but the selected "
                f"CPU is {cpu_socket.upper()}",
            ):
                return verdict
        if candidate_spec is None:
            verdict.warnings.append(
                "Board not yet in our reference database — socket/RAM checks against it are approximate"
            )

    if slot_type == "cooling":
        # Socket-specific coolers are rare in listings text; only flag an
        # explicit mismatch, otherwise stay silent.
        candidate_socket = _infer_cpu_socket(candidate_title)
        if candidate_socket and cpu_socket and candidate_socket != cpu_socket:
            return verdict.fail(
                f"Cooler mount is {candidate_socket.upper()} but the selected CPU "
                f"is {cpu_socket.upper()}",
                RULE_COOLER_SOCKET_MISMATCH,
            )

    if slot_type == "gpu":
        tdp = _gpu_tdp_from_text(candidate_title)
        psu_w = _extract_psu_watts(_selected_text(selected))
        if tdp and psu_w and psu_w < tdp + 220:
            return verdict.fail(
                f"Selected PSU ({psu_w}W) is below the ~{tdp + 220}W this GPU needs "
                f"under load",
                RULE_PSU_INSUFFICIENT,
            )
        if tdp and not psu_w:
            verdict.warnings.append("PSU wattage unknown — stability not guaranteed")

        # Soft clearance signal — see _LIKELY_LONG_GPU_KEYWORDS docstring above
        # for why this is a warning, never a hard block: we don't have a real
        # GPU length field to compare against case.max_gpu_length_mm yet.
        if case is not None and case.max_gpu_length_mm is not None:
            if case.max_gpu_length_mm < _COMPACT_CASE_GPU_CLEARANCE_MM:
                candidate_lower = candidate_title.lower()
                if any(kw in candidate_lower for kw in _LIKELY_LONG_GPU_KEYWORDS):
                    verdict.flag_not_recommended(
                        f"This case's known GPU clearance ({int(case.max_gpu_length_mm)}mm) "
                        "is tight for a card this size — check the exact card length before ordering",
                        RULE_GPU_CLEARANCE,
                    )

    return verdict


def _apply_db_rule(
    rule: CompatibilityRule,
    candidate_title: str,
    selected: dict[str, str],
    case: CaseCatalogue | None,
) -> tuple[str, str] | None:
    """Evaluate one structured rule against a candidate. Returns
    (human-readable failure reason, stable rule code), or None if the rule
    passes / can't judge. Code is RULE_DB_RULE:<rule_type>:<rule.id> — the
    rule.id suffix lets two DB rules of the same type stay distinguishable in
    logs/tests without needing a separate code per admin-authored rule."""
    c = rule.constraint_json or {}
    code = f"{RULE_DB_RULE}:{rule.rule_type.value}:{rule.id}"

    if rule.rule_type == CompatibilityRuleType.SOCKET_MATCH:
        required = (c.get("requires_socket") or "").lower()
        found = _infer_cpu_socket(candidate_title)
        if required and found and found != required:
            return f"Requires {required.upper()} socket — this part is {found.upper()}", code

    elif rule.rule_type == CompatibilityRuleType.RAM_TYPE_MATCH:
        required = (c.get("requires_ram_type") or "").lower()
        found = _extract_ram_type(candidate_title)
        if required and found and found != required:
            return f"Requires {required.upper()} — this is {found.upper()}", code

    elif rule.rule_type == CompatibilityRuleType.PSU_WATTAGE_MIN:
        minimum = c.get("min_watts")
        found = _extract_psu_watts(candidate_title)
        if minimum and found and found < int(minimum):
            return f"Needs at least {minimum}W — this PSU is {found}W", code

    elif rule.rule_type == CompatibilityRuleType.FORM_FACTOR_FIT:
        allowed = [f.lower() for f in c.get("allowed_form_factors", [])]
        if case and allowed and case.form_factor.lower() not in allowed:
            return f"Doesn't fit a {case.form_factor.upper()} case", code

    elif rule.rule_type == CompatibilityRuleType.CLEARANCE_MAX:
        # Requires structured dimensions we don't have on variants yet;
        # judged only when constraint_json carries an explicit text hint.
        blocked = [b.lower() for b in c.get("blocked_keywords", [])]
        t = candidate_title.lower()
        for kw in blocked:
            if kw in t:
                return c.get("reason") or f"Exceeds case clearance ({kw})", code

    # CUSTOM rules: keyword conflict lists.
    elif rule.rule_type == CompatibilityRuleType.CUSTOM:
        conflicts = c.get("conflicts_with_keywords", [])
        haystack = _selected_text(selected).lower()
        t = candidate_title.lower()
        trigger = (c.get("candidate_keyword") or "").lower()
        if trigger and trigger in t:
            for kw in conflicts:
                if kw.lower() in haystack:
                    return c.get("reason") or f"Conflicts with selected {kw}", code

    return None


async def evaluate_configuration(
    db: AsyncSession,
    playbook_id: int,
    selections: dict[int, int],  # {slot_id: variant_id}
    case_id: int | None = None,
) -> dict:
    """Per-slot, per-variant compatibility verdicts for a playbook's
    customer-visible slots, given the current partial selection."""
    slots_result = await db.execute(
        select(PlaybookSlot).where(
            PlaybookSlot.playbook_id == playbook_id,
            PlaybookSlot.is_customer_visible == True,  # noqa: E712
        )
    )
    slots = slots_result.scalars().all()
    slot_ids = [s.id for s in slots]
    slot_type_by_id = {s.id: s.slot_type for s in slots}
    if not slot_ids:
        return {"slots": []}

    rows_result = await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(
            CatalogueVariant.slot_id.in_(slot_ids),
            CatalogueVariant.status == "active",
        )
    )
    rows = rows_result.all()
    title_by_variant = {v.id: (l.title or "") for v, l in rows}

    # Titles of the currently selected variants, keyed by slot_type.
    selected_titles: dict[str, str] = {}
    for slot_id, variant_id in selections.items():
        slot_type = slot_type_by_id.get(int(slot_id))
        title = title_by_variant.get(int(variant_id))
        if slot_type and title:
            selected_titles[slot_type] = title

    case = None
    if case_id is not None:
        case = (
            await db.execute(select(CaseCatalogue).where(CaseCatalogue.id == case_id))
        ).scalar_one_or_none()

    # Fetched once per evaluation call (not per-candidate) — see
    # match_motherboard_spec's docstring for why this is passed as an
    # in-memory list rather than re-queried inside the judging loop.
    mobo_specs = list((await db.execute(select(MotherboardSpec))).scalars().all())

    rules_result = await db.execute(
        select(CompatibilityRule).where(
            CompatibilityRule.active == True,  # noqa: E712
            CompatibilityRule.subject_slot_id.in_(slot_ids),
        )
    )
    rules_by_slot: dict[int, list[CompatibilityRule]] = {}
    for rule in rules_result.scalars().all():
        rules_by_slot.setdefault(rule.subject_slot_id, []).append(rule)

    out_slots = []
    variants_by_slot: dict[int, list] = {}
    for v, l in rows:
        variants_by_slot.setdefault(v.slot_id, []).append((v, l))

    for slot in slots:
        verdicts = []
        for v, l in variants_by_slot.get(slot.id, []):
            title = l.title or ""

            # Skip judging the variant currently selected in this very slot
            # against itself — it's always "compatible with itself".
            other_selected = {
                st: t for st, t in selected_titles.items() if st != slot.slot_type
            }

            verdict = _judge_variant(slot.slot_type, title, other_selected, case, mobo_specs)
            verdict.variant_id = v.id

            if verdict.is_compatible:
                for rule in rules_by_slot.get(slot.id, []):
                    result = _apply_db_rule(rule, title, other_selected, case)
                    if result:
                        reason, code = result
                        verdict.fail(reason, code)
                        break

            verdicts.append(
                {
                    "variant_id": verdict.variant_id,
                    "is_compatible": verdict.is_compatible,
                    "reason": verdict.reason,
                    "rule_code": verdict.rule_code,
                    "warnings": verdict.warnings,
                    "verdict": verdict.verdict,
                }
            )

        out_slots.append(
            {
                "slot_id": slot.id,
                "slot_type": slot.slot_type,
                "variants": verdicts,
            }
        )

    return {"slots": out_slots}
