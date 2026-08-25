"""
Multi-agent Build Wizard.

Agents run in sequence:
  1. Wizard   — turns playbook + freetext intent into a RefinedIntent struct
  2. Composer — generates 5 candidate builds grounded in real parts prices
  3. Validator — checks compatibility / completeness / feasibility (hard rules first,
                 AI double-check second); rejects failures; scores survivors
  3b. Resale Valuation — LLM-based live market pricing for finished builds (PARALLEL)
  4. Ranker   — sorts by composite score (profit × demand × inverse-risk)
  5. Planner  — produces a step-by-step purchase plan for the user's chosen build

The orchestration loop retries Composer up to 3× if fewer than 3 valid builds
survive Validator.  After 3 attempts the best available set is returned.

Resale Valuation runs in PARALLEL for all valid builds after Validator,
updating estimated_resale, estimated_profit, and profit_margin_pct before Ranker
sees them, ensuring all ranking decisions use live market data.
"""
from __future__ import annotations

import json
import re
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory
from app.services.compatibility_engine import evaluate_build_compatibility

log = structlog.get_logger(__name__)

# ─── Data structures ──────────────────────────────────────────────────────────

@dataclass
class RefinedIntent:
    playbook_name: str
    playbook_emoji: str
    budget_max: float
    target_use_case: str
    priorities: list[str]           # e.g. ["max profit", "low risk"]
    constraints: list[str]          # e.g. ["must have PSU", "ATX only"]
    user_notes: str
    owned_components: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class BuildRequirements:
    """Deterministic use-case gates applied before profitability ranking."""
    min_gpu_vram_gb: int = 0
    min_ram_gb: int = 0
    min_storage_gb: int = 0
    min_psu_watts: int = 0
    forbid_sff: bool = False
    forbid_unverified_oem_cpu_swap: bool = False
    require_expandable_base: bool = False


_USE_CASE_REQUIREMENTS: dict[str, BuildRequirements] = {
    "ai_workstation": BuildRequirements(
        min_gpu_vram_gb=16,
        min_ram_gb=64,
        min_storage_gb=1000,
        min_psu_watts=650,
        forbid_sff=True,
        forbid_unverified_oem_cpu_swap=True,
        require_expandable_base=True,
    ),
    "workstation": BuildRequirements(
        min_gpu_vram_gb=8,
        min_ram_gb=32,
        min_storage_gb=1000,
        min_psu_watts=550,
        forbid_sff=True,
        forbid_unverified_oem_cpu_swap=True,
    ),
}


def _requirements_for(use_case: str) -> BuildRequirements:
    return _USE_CASE_REQUIREMENTS.get((use_case or "").lower(), BuildRequirements())


@dataclass
class BuildUpgrade:
    role: str                       # "gpu" | "storage" | "ram" | "psu" | "os"
    item: str                       # e.g. "RTX 3060 12GB"
    cost_estimate: float
    source: str                     # "eBay used" | "Amazon" | "included"
    required: bool
    listing_url: str = ""           # specific catalogue listing URL (filled by catalogue_enrichment_agent)
    image_url: str = ""             # listing image URL


@dataclass
class ResaleValuation:
    """LLM-generated resale valuation for a finished build spec."""
    resale_low: float               # conservative (25th-percentile) market price
    resale_median: float            # expected selling price
    resale_high: float              # optimistic (75th-percentile) market price
    reasoning: str                  # why the LLM set these prices
    source: str = "llm"             # always "llm" for this agent


@dataclass
class Build:
    id: str
    name: str
    base_spec: str                  # what listing to look for ("Dell OptiPlex i7-8700…")
    base_cost: float                # expected purchase price
    upgrades: list[BuildUpgrade]
    total_cost: float
    estimated_resale: float
    estimated_profit: float
    profit_margin_pct: float
    risk: Literal["low", "medium", "high"]
    demand_fit: Literal["excellent", "good", "moderate", "poor"]
    why: str                        # one-line rationale
    sell_platform: str
    sell_price_target: float
    # Validation fields — filled by ValidatorAgent
    valid: bool = True
    validation_score: float = 0.0   # 0–100
    rejection_reason: str = ""
    compatibility_confidence: float = 0.0
    compatibility_warnings: list[str] = field(default_factory=list)
    rank: int = 0
    owned_components_applied: list[str] = field(default_factory=list)
    owned_value_offset: float = 0.0
    # Resale valuation — filled by ResaleValuationAgent (optional, LLM-based)
    resale_source: str = "rule-based"  # "rule-based" or "llm"
    resale_low: float = 0.0         # conservative estimate
    resale_high: float = 0.0        # optimistic estimate
    resale_reasoning: str = ""      # why the valuation agent set these prices
    # Visualization metadata
    risk_score: float = 5.0         # 0–10 (0=safest, 10=riskiest) for scatter graph
    demand_score: float = 5.0       # 0–10 (demand signal)
    # Catalogue enrichment — filled by catalogue_enrichment_agent
    base_listing_url: str = ""      # specific eBay listing URL for the base PC
    base_image_url: str = ""        # image of the base PC listing


@dataclass
class PurchasePlan:
    build: Build
    steps: list[dict]               # ordered action items
    total_budget: float
    contingency_buffer: float       # 10% of total_cost
    expected_net_profit: float
    expected_roi_pct: float
    timeline_days: int
    tips: list[str]


# ─── Market context (injected into prompts) ───────────────────────────────────

_MARKET_CONTEXT = """
Current UK used-parts market (June 2026):
GPU: GTX 1060 6GB ~£75 | RX 580 8GB ~£65 | RTX 3060 ~£170 | RTX 3070 ~£230 | RX 6600 ~£145
Storage: 256GB SSD ~£18 | 480GB SSD ~£28 | 1TB SSD ~£55 | 1TB HDD ~£20
RAM: 8GB DDR4 ~£12 | 16GB DDR4 ~£22 | 32GB DDR4 ~£40
OS: Windows 11 Home key ~£6 (OEM)
eBay fees: ~12.7% | Postage: £15 avg tower
Typical resale ranges:
  Budget gaming PC (i5+GTX1060): £220–280
  Mid gaming PC (i7+RTX3060): £380–450
  Office workstation clean: £100–180
  AI workstation (Xeon+A4000): £800–1200
"""


# ─── Agent 1: Wizard ──────────────────────────────────────────────────────────

async def wizard_agent(
    playbook: dict,
    budget: float,
    user_notes: str,
    priorities: list[str],
    constraints: list[str],
    owned_components: list[dict] | None = None,
) -> RefinedIntent:
    """Turns raw user input + playbook into a clean RefinedIntent."""
    return RefinedIntent(
        playbook_name=playbook.get("name", "Unknown"),
        playbook_emoji=playbook.get("emoji", "🔧"),
        budget_max=budget,
        target_use_case=playbook.get("target_use_case", "general"),
        priorities=priorities or ["max profit", "low risk"],
        constraints=constraints or [],
        user_notes=user_notes or "",
        owned_components=list(owned_components or []),
    )


async def _fetch_available_components(budget_remaining: float, requirements: BuildRequirements) -> dict[str, list[dict]]:
    """
    Query the Parts library for available CPUs, motherboards, GPUs, RAM, SSDs, PSUs within budget.
    Returns dict: category → list of available parts with prices.
    """
    async with AsyncSessionLocal() as db:
        components = {
            "cpu": [],
            "motherboard": [],
            "gpu": [],
            "ram": [],
            "ssd": [],
            "psu": [],
            "case": [],
        }

        categories = [PartCategory.cpu, PartCategory.motherboard, PartCategory.gpu,
                     PartCategory.ram, PartCategory.ssd, PartCategory.psu, PartCategory.case]

        for category in categories:
            query = select(Part).where(
                Part.category == category,
                Part.is_active == True,
                Part.price <= budget_remaining
            ).order_by(Part.price.asc()).limit(40)

            result = await db.execute(query)
            parts = result.scalars().all()

            def meets_requirements(part: Part) -> bool:
                text = f"{part.name or ''} {part.model or ''} {json.dumps(part.specs or {})}".lower()
                if category == PartCategory.gpu and requirements.min_gpu_vram_gb:
                    return _largest_gb([text]) >= requirements.min_gpu_vram_gb
                if category == PartCategory.ram and requirements.min_ram_gb:
                    return _largest_gb([text]) >= requirements.min_ram_gb
                if category == PartCategory.ssd and requirements.min_storage_gb:
                    return _largest_storage_gb([text]) >= requirements.min_storage_gb
                if category == PartCategory.psu and requirements.min_psu_watts:
                    return _largest_watts([text]) >= requirements.min_psu_watts
                return True

            parts = [part for part in parts if meets_requirements(part)][:8]

            components[category.value] = [
                {
                    "id": p.id,
                    "name": p.name,
                    "brand": p.brand,
                    "model": p.model,
                    "specs": p.specs,
                    "price": p.price,
                    "source": p.source_site,
                    "url": p.source_url,
                }
                for p in parts
            ]

        return components


def _apply_owned_components(builds: list[Build], owned_components: list[dict]) -> None:
    """
    If user already owns components, do not count those upgrade costs again.
    """
    if not owned_components:
        return
    owned_names = [str(c.get("name", "")).strip().lower() for c in owned_components if str(c.get("name", "")).strip()]
    if not owned_names:
        return

    for b in builds:
        offset = 0.0
        applied: list[str] = []
        for u in b.upgrades:
            item = (u.item or "").lower()
            role = (u.role or "").lower()
            match_name = next((n for n in owned_names if n in item or n in role), None)
            if match_name:
                offset += float(u.cost_estimate or 0.0)
                applied.append(u.item)
        if offset > 0:
            b.total_cost = max(0.0, b.total_cost - offset)
            b.estimated_profit = b.estimated_resale - b.total_cost
            b.profit_margin_pct = (b.estimated_profit / b.total_cost * 100.0) if b.total_cost > 0 else 0.0
            b.owned_components_applied = applied
            b.owned_value_offset = round(offset, 2)
            b.why = f"{b.why} · owned-offset £{offset:.0f}"


# ─── Agent 2: Composer ────────────────────────────────────────────────────────

async def composer_agent(intent: RefinedIntent, playbook: dict, attempt: int = 1) -> list[Build]:
    """
    Generates 5 candidate builds.
    Uses AI to ground builds in real parts prices from the components library.
    Considers both base listings + real available upgrades from the parts database.
    """
    from app.services.ai_service import chat as ai_chat

    upgrade_strategy = playbook.get("upgrade_strategy", {})
    profit_strategy  = playbook.get("profit_strategy", {})
    requirements = _requirements_for(intent.target_use_case)

    # Fetch real available components from Parts library
    available_components = await _fetch_available_components(intent.budget_max * 0.6, requirements)  # Reserve 40% for base unit

    # Format components for the prompt
    components_context = "AVAILABLE COMPONENTS FROM LIBRARY (real market prices):\n"
    for category, parts in available_components.items():
        if parts:
            components_context += f"\n{category.upper()} options:\n"
            for p in parts[:3]:  # Show top 3 in each category
                components_context += f"  - {p['name']} ({p['brand']} {p['model']}) - £{p['price']} from {p['source']}\n"

    prompt = f"""You are the Composer agent in a PC-flipping build wizard.

PLAYBOOK: {intent.playbook_name} {intent.playbook_emoji}
Use case: {intent.target_use_case}
Budget: £{intent.budget_max}
User priorities: {', '.join(intent.priorities)}
Constraints: {', '.join(intent.constraints) if intent.constraints else 'none'}
User notes: {intent.user_notes or 'none'}

Playbook upgrade requirements: {json.dumps(upgrade_strategy)}
Playbook profit strategy: {json.dumps(profit_strategy)}
HARD USE-CASE REQUIREMENTS (every candidate must meet all of these): {json.dumps(asdict(requirements))}

{components_context}

{_MARKET_CONTEXT}

Generate EXACTLY 5 distinct PC-flip builds that fit this playbook and budget.

CRITICAL RULES FOR base_spec:
- base_spec MUST be a COMPLETE PC SYSTEM (desktop, tower, mini PC, workstation)
- Examples of VALID base_spec: "Dell OptiPlex 7060 i7-8700 16GB no GPU", "HP EliteDesk 800 G4 SFF no graphics card", "Lenovo ThinkCentre M720 i5-8500", "Custom ATX tower i7-9700 no GPU"
- NEVER use individual components as base_spec — RAM sticks, SSDs, GPUs, CPUs, PSUs are UPGRADES, not base systems
- If a component from the library looks like RAM/DDR/SSD/GPU/CPU, it belongs in "upgrades", NOT in "base_spec"
- The base PC must be a whole machine you can buy on eBay as a complete unit
- Do not propose a CPU replacement in an OEM Dell/HP/Lenovo base unless the exact motherboard and BIOS support are established in the base specification
- Include every mandatory component explicitly. Never assume missing RAM, storage, PSU wattage, GPU VRAM, motherboard support, or chassis clearance
- For AI workstations, GPU VRAM capacity is a hard requirement, not a general gaming-performance proxy

COMPONENTS FROM THE LIBRARY are UPGRADE PARTS ONLY — use them in the "upgrades" array, never as the base system.

Each build must be a real, practical flip — not theoretical.
Make them DIFFERENT from each other: vary the base PC model, GPU tier, risk level.
Include risk_score (0=safest, 10=riskiest) and demand_score (0=low, 10=excellent).

{"This is attempt " + str(attempt) + " of 3 — make builds more conservative and achievable." if attempt > 1 else ""}

Respond with ONLY valid JSON. No explanation outside the JSON.

{{
  "builds": [
    {{
      "id": "build_1",
      "name": "Short punchy name",
      "base_spec": "Exact eBay search target e.g. Dell OptiPlex 7060 i7-8700 16GB no GPU",
      "base_cost": 85,
      "upgrades": [
        {{"role": "gpu", "item": "RTX 4070 Ti Super 16GB", "cost_estimate": 650, "source": "Parts library", "required": true}},
        {{"role": "ram", "item": "64GB DDR5 RAM", "cost_estimate": 140, "source": "Parts library", "required": true}},
        {{"role": "storage", "item": "1TB NVMe SSD", "cost_estimate": 55, "source": "Parts library", "required": true}},
        {{"role": "psu", "item": "750W ATX PSU", "cost_estimate": 80, "source": "Parts library", "required": true}}
      ],
      "total_cost": 280,
      "estimated_resale": 420,
      "estimated_profit": 140,
      "profit_margin_pct": 33,
      "risk": "low",
      "risk_score": 3,
      "demand_fit": "excellent",
      "demand_score": 9,
      "why": "One sentence on why this is a good flip",
      "sell_platform": "eBay",
      "sell_price_target": 420
    }}
  ]
}}"""

    try:
        response, model = await ai_chat(prompt, [], None)
        log.info("composer.ai_response", model=model, attempt=attempt)
        builds = _parse_builds_json(response)
        log.info("composer.builds_parsed", count=len(builds))
        return builds
    except Exception as exc:
        log.error("composer.failed", error=str(exc))
        return []


def _parse_builds_json(response: str) -> list[Build]:
    """Extract and parse the builds JSON from an AI response."""
    # Strip markdown fences
    clean = re.sub(r"```(?:json)?", "", response).strip()
    # Find the outermost JSON object
    m = re.search(r'\{[\s\S]*\}', clean)
    if not m:
        raise ValueError("No JSON object found in response")
    data = json.loads(m.group())
    builds = []
    for i, b in enumerate(data.get("builds", []), 1):
        upgrades = [
            BuildUpgrade(
                role=u.get("role", ""),
                item=u.get("item", ""),
                cost_estimate=float(u.get("cost_estimate", 0)),
                source=u.get("source", "eBay"),
                required=bool(u.get("required", True)),
            )
            for u in b.get("upgrades", [])
        ]
        builds.append(Build(
            id=b.get("id", f"build_{i}"),
            name=b.get("name", f"Build {i}"),
            base_spec=b.get("base_spec", ""),
            base_cost=float(b.get("base_cost", 0)),
            upgrades=upgrades,
            total_cost=float(b.get("total_cost", 0)),
            estimated_resale=float(b.get("estimated_resale", 0)),
            estimated_profit=float(b.get("estimated_profit", 0)),
            profit_margin_pct=float(b.get("profit_margin_pct", 0)),
            risk=b.get("risk", "medium"),
            risk_score=float(b.get("risk_score", 5.0)),
            demand_fit=b.get("demand_fit", "good"),
            demand_score=float(b.get("demand_score", 5.0)),
            why=b.get("why", ""),
            sell_platform=b.get("sell_platform", "eBay"),
            sell_price_target=float(b.get("sell_price_target", 0)),
        ))
    return builds


# ─── Agent 3: Validator ───────────────────────────────────────────────────────

_DEMAND_SCORE = {"excellent": 4, "good": 3, "moderate": 2, "poor": 1}
_RISK_SCORE   = {"low": 1, "medium": 2, "high": 3}


_COMPONENT_KEYWORDS = {
    # RAM
    "ddr3", "ddr4", "ddr5", "dimm", "sodimm", "rdimm", "lpddr", "ecc ram", "server ram",
    "memory module", "memory stick", "ram stick", "2x8gb", "2x16gb", "4x8gb",
    "pc4-", "pc3-", "m393", "m391", "kt/s",
    # Storage
    "nvme", "m.2 ssd", "sata ssd", "2.5\" ssd", "3.5\" hdd", "solid state drive",
    "hard drive only", "hdd only", "ssd only",
    # GPU
    "rtx 30", "rtx 40", "rtx 20", "gtx 10", "gtx 16", "rx 6", "rx 7", "radeon rx",
    "graphics card", "gpu only", "video card",
    # CPU
    "core i7-", "core i5-", "core i9-", "ryzen 5 ", "ryzen 7 ", "ryzen 9 ",
    "xeon e5-", "xeon e3-", "threadripper", "cpu only", "processor only",
    # PSU
    "power supply", "psu", "atx psu", "modular psu",
    # Other components
    "motherboard only", "mainboard",
}

def _base_spec_is_component(base_spec: str) -> bool:
    """Return True if base_spec looks like an individual component rather than a complete PC."""
    lower = base_spec.lower()
    # CPU/GPU names legitimately appear in complete-system descriptions. A
    # clear system noun wins unless the title explicitly says it is a part.
    if any(noun in lower for noun in [" desktop", " tower", "workstation", "gaming pc", "complete pc", "base pc"]):
        if not any(marker in lower for marker in ["cpu only", "processor only", "motherboard only", "parts only"]):
            return False
    return any(kw in lower for kw in _COMPONENT_KEYWORDS)


def _role_items(build: Build, *roles: str) -> list[str]:
    wanted = {role.lower() for role in roles}
    return [u.item.lower() for u in build.upgrades if (u.role or "").lower() in wanted]


def _largest_gb(texts: list[str]) -> int:
    values: list[int] = []
    for text in texts:
        values.extend(int(value) for value in re.findall(r"(?<!\d)(\d{1,3})\s*gb\b", text.lower()))
    return max(values, default=0)


def _largest_storage_gb(texts: list[str]) -> int:
    values: list[int] = []
    for text in texts:
        lower = text.lower()
        values.extend(int(value) * 1000 for value in re.findall(r"(?<!\d)(\d{1,2})\s*tb\b", lower))
        values.extend(int(value) for value in re.findall(r"(?<!\d)(\d{3,4})\s*gb\b", lower))
    return max(values, default=0)


def _largest_watts(texts: list[str]) -> int:
    values: list[int] = []
    for text in texts:
        values.extend(int(value) for value in re.findall(r"(?<!\d)(\d{3,4})\s*w(?:att)?s?\b", text.lower()))
    return max(values, default=0)


def _validate_use_case_requirements(build: Build, intent: RefinedIntent) -> str | None:
    requirements = _requirements_for(intent.target_use_case)
    base = build.base_spec.lower()

    if requirements.forbid_sff and any(token in base for token in [" sff", "small form factor", "mini pc", "micro pc"]):
        return f"{intent.target_use_case} requires GPU expansion; SFF/mini base is unsuitable"

    if requirements.require_expandable_base and any(
        token in base for token in ["optiplex", "prodesk", "elitedesk", "thinkcentre"]
    ):
        return "AI workstation requires an expandable workstation/custom ATX base, not an office OEM platform"

    cpu_upgrades = _role_items(build, "cpu", "processor")
    if requirements.forbid_unverified_oem_cpu_swap and cpu_upgrades and any(
        token in base for token in ["dell", "hp", "lenovo", "optiplex", "prodesk", "elitedesk", "thinkcentre"]
    ):
        return "Unverified CPU replacement in an OEM base (motherboard/BIOS/cooling support not established)"

    gpu_vram = _largest_gb(_role_items(build, "gpu", "graphics", "graphics card"))
    if gpu_vram < requirements.min_gpu_vram_gb:
        return f"GPU VRAM {gpu_vram or 'unknown'}GB is below the {requirements.min_gpu_vram_gb}GB {intent.target_use_case} minimum"

    ram_gb = max(_largest_gb(_role_items(build, "ram", "memory")), _largest_gb([base]))
    if ram_gb < requirements.min_ram_gb:
        return f"RAM {ram_gb or 'unknown'}GB is below the {requirements.min_ram_gb}GB {intent.target_use_case} minimum"

    storage_gb = max(_largest_storage_gb(_role_items(build, "storage", "ssd", "nvme")), _largest_storage_gb([base]))
    if storage_gb < requirements.min_storage_gb:
        return f"Storage {storage_gb or 'unknown'}GB is below the {requirements.min_storage_gb}GB {intent.target_use_case} minimum"

    psu_watts = max(_largest_watts(_role_items(build, "psu", "power supply")), _largest_watts([base]))
    if psu_watts < requirements.min_psu_watts:
        return f"PSU {psu_watts or 'unknown'}W is below the {requirements.min_psu_watts}W {intent.target_use_case} minimum"

    return None


def _hard_validate(build: Build, intent: RefinedIntent) -> tuple[bool, str]:
    """
    Hard rule checks — no AI needed.
    Returns (passed, rejection_reason).
    """
    # Reject builds where base_spec is a component, not a whole PC
    if _base_spec_is_component(build.base_spec):
        return False, f"base_spec '{build.base_spec[:60]}' appears to be an individual component, not a complete PC system"

    # Budget check
    if build.total_cost > intent.budget_max * 1.05:   # 5% tolerance
        return False, f"Total cost £{build.total_cost:.0f} exceeds budget £{intent.budget_max:.0f}"

    # Never trust an AI-supplied total when the component arithmetic disagrees.
    calculated_cost = round(build.base_cost + sum(max(0.0, u.cost_estimate) for u in build.upgrades), 2)
    build.total_cost = calculated_cost
    build.estimated_profit = round(build.estimated_resale - calculated_cost, 2)
    build.profit_margin_pct = round((build.estimated_profit / calculated_cost * 100) if calculated_cost else 0, 1)
    if calculated_cost > intent.budget_max * 1.05:
        return False, f"Calculated component cost £{calculated_cost:.0f} exceeds budget £{intent.budget_max:.0f}"

    requirement_failure = _validate_use_case_requirements(build, intent)
    if requirement_failure:
        return False, requirement_failure

    # Must be profitable
    if build.estimated_profit <= 0:
        return False, f"Negative or zero profit (£{build.estimated_profit:.0f})"

    # Sanity: resale > total_cost
    if build.estimated_resale <= build.total_cost:
        return False, "Estimated resale does not cover total cost"

    # Minimum profit margin
    if build.profit_margin_pct < 10:
        return False, f"Profit margin {build.profit_margin_pct:.0f}% is below 10% minimum"

    # Base cost must be positive
    if build.base_cost <= 0:
        return False, "Base cost is zero — build is not grounded"

    # Structured compatibility checks
    compat = evaluate_build_compatibility(
        base_spec=build.base_spec,
        upgrades=[asdict(u) for u in build.upgrades],
        constraints=intent.constraints,
    )
    build.compatibility_confidence = compat.confidence
    build.compatibility_warnings = compat.warnings
    if not compat.compatible:
        return False, "; ".join(compat.hard_fail_reasons)

    return True, ""


def _score_build(build: Build) -> float:
    """
    Composite score 0–100 used for ranking.
    Weights: profit 50%, demand 30%, risk 20%.
    """
    profit_score  = min(100, (build.estimated_profit / 300) * 100) * 0.45
    demand_score  = (_DEMAND_SCORE.get(build.demand_fit, 2) / 4) * 100 * 0.30
    risk_score    = ((4 - _RISK_SCORE.get(build.risk, 2)) / 3) * 100 * 0.20
    compat_score  = (build.compatibility_confidence * 100) * 0.05
    return round(profit_score + demand_score + risk_score + compat_score, 1)


async def validator_agent(builds: list[Build], intent: RefinedIntent) -> list[Build]:
    """
    Validates each build.  Hard rules first, then scores survivors.
    Returns only valid builds, scored and sorted.
    """
    valid_builds: list[Build] = []

    for build in builds:
        passed, reason = _hard_validate(build, intent)
        if not passed:
            build.valid = False
            build.rejection_reason = reason
            log.info("validator.rejected", build=build.name, reason=reason)
            continue

        build.valid = True
        build.validation_score = _score_build(build)
        valid_builds.append(build)
        log.info("validator.passed", build=build.name, score=build.validation_score)

    return valid_builds


# ─── Agent 3b: Resale Valuation ──────────────────────────────────────────────
# LLM-based live market pricing for each valid build's finished spec.
# Runs in PARALLEL for all valid builds.

async def _valuate_single_build(build: Build) -> ResaleValuation:
    """
    Ask the LLM: Given this finished PC spec, what is it worth on the market today?
    Returns conservative/median/optimistic resale estimates.
    """
    from app.services.ai_service import chat as ai_chat

    # Describe the finished build spec
    upgrade_desc = "\n".join([f"  - {u.item} (£{u.cost_estimate:.0f})" for u in build.upgrades])

    prompt = f"""You are a PC-flipping market expert evaluating finished PC build specifications.
Given this PC specification, estimate what it would sell for on eBay UK TODAY (June 2026).

BASE SYSTEM: {build.base_spec}
UPGRADES ADDED:
{upgrade_desc}

FINISHED BUILD SPECIFICS:
- Total invested: £{build.total_cost:.0f}
- Themed case: Yes (presentation premium)
- Condition: Clean, tested, working
- Platform: eBay UK

Estimate the MARKET PRICE this finished build would fetch if listed now.
Consider current demand, condition, specs, and competitive listings.
Return THREE price points:
  - Resale Low: conservative (if it sells slowly, needs a few bidders)
  - Resale Median: expected (typical sale at competitive price)
  - Resale High: optimistic (good demand, multiple bidders, clean presentation)

Respond with ONLY valid JSON:
{{
  "resale_low": <number>,
  "resale_median": <number>,
  "resale_high": <number>,
  "reasoning": "<short explanation of the market context and why you set these prices>"
}}"""

    try:
        response, _ = await ai_chat(prompt, [], None)
        clean = re.sub(r"```(?:json)?", "", response).strip()
        m = re.search(r'\{[\s\S]*\}', clean)
        if not m:
            raise ValueError("No JSON found in response")

        data = json.loads(m.group())
        return ResaleValuation(
            resale_low=float(data.get("resale_low", build.estimated_resale * 0.85)),
            resale_median=float(data.get("resale_median", build.estimated_resale)),
            resale_high=float(data.get("resale_high", build.estimated_resale * 1.15)),
            reasoning=str(data.get("reasoning", "")),
            source="llm",
        )
    except Exception as exc:
        log.warning("resale_valuation.failed", build=build.name, error=str(exc))
        # Fall back to rule-based estimates
        return ResaleValuation(
            resale_low=round(build.estimated_resale * 0.85, 2),
            resale_median=build.estimated_resale,
            resale_high=round(build.estimated_resale * 1.15, 2),
            reasoning="Rule-based fallback (LLM call failed)",
            source="rule-based",
        )


async def resale_valuation_agent(builds: list[Build]) -> list[Build]:
    """
    LLM-based resale valuation for ALL valid builds in PARALLEL.
    Updates estimated_resale, estimated_profit, and profit_margin_pct.
    """
    if not builds:
        return builds

    log.info("resale_valuation.starting", count=len(builds))

    # Fire parallel LLM calls for all builds
    valuations = await asyncio.gather(
        *[_valuate_single_build(b) for b in builds],
        return_exceptions=True
    )

    # Update each build with LLM valuation
    for i, build in enumerate(builds):
        valuation = valuations[i]

        # Handle exceptions (shouldn't happen due to return_exceptions, but be safe)
        if isinstance(valuation, Exception):
            log.error("resale_valuation.exception", build=build.name, error=str(valuation))
            continue

        # Use median estimate as the new resale target
        old_resale = build.estimated_resale
        build.estimated_resale = round(valuation.resale_median, 2)
        build.resale_low = valuation.resale_low
        build.resale_high = valuation.resale_high
        build.resale_source = valuation.source
        build.resale_reasoning = valuation.reasoning

        # Recalculate profit (cost stays the same, resale changed)
        build.estimated_profit = round(build.estimated_resale - build.total_cost, 2)
        build.profit_margin_pct = round(
            (build.estimated_profit / build.total_cost * 100.0) if build.total_cost > 0 else 0.0,
            1
        )

        log.info(
            "resale_valuation.updated",
            build=build.name,
            old_resale=old_resale,
            new_resale=build.estimated_resale,
            profit=build.estimated_profit,
        )

    log.info("resale_valuation.complete", count=len(builds))
    return builds


# ─── Agent 4: Ranker ─────────────────────────────────────────────────────────

def ranker_agent(builds: list[Build]) -> list[Build]:
    """Sorts valid builds by validation_score descending, assigns rank."""
    ranked = sorted(builds, key=lambda b: b.validation_score, reverse=True)
    for i, b in enumerate(ranked, 1):
        b.rank = i
    return ranked


# ─── Catalogue enrichment ────────────────────────────────────────────────────

def _extract_model_terms(spec: str, is_whole_pc: bool = False) -> list[str]:
    """Extract key searchable model tokens from a spec/item string."""
    s = spec.lower()
    # GPU pattern — most specific, match first
    gpu_m = re.search(r"(rtx|gtx|rx)\s*(\d{3,4})(\s*(ti|xt|super))?", s)
    if gpu_m:
        return [gpu_m.group(0).strip()]
    # CPU pattern
    cpu_m = re.search(r"(i[3579]-\d{4,5}[a-z]*|ryzen\s+[3579]\s+\d{4}[a-z]*|xeon\s+[\w-]+)", s)
    if cpu_m:
        terms = [cpu_m.group(0).strip()]
        if is_whole_pc:
            brand_m = re.search(r"\b(dell|hp|lenovo|asus|acer|fujitsu|nec|optiplex|elitedesk|thinkcentre)\b", s)
            if brand_m:
                terms.insert(0, brand_m.group(0).strip())
        return terms
    # Storage pattern
    stor_m = re.search(r"(\d+\s*(?:gb|tb))\s*(?:nvme|ssd|hdd|m\.2)", s)
    if stor_m:
        return [stor_m.group(0).strip()]
    # RAM pattern
    ram_m = re.search(r"(\d+\s*gb)\s*(?:ddr[345]?|ram)", s)
    if ram_m:
        return [ram_m.group(0).strip()]
    # Fallback: meaningful words
    stop = {"with", "and", "the", "for", "used", "no", "card", "only", "free", "inc"}
    tokens = [t for t in spec.split() if len(t) > 2 and t.lower() not in stop]
    return tokens[:3]


async def _find_catalogue_listing(
    search_terms: list[str],
    target_price: float,
    is_whole_pc: bool = True,
) -> dict | None:
    """
    Search the catalogue for a specific matching listing near the target price.
    Returns {url, image_url, title, price} or None if no match found.
    """
    from sqlalchemy import and_
    from app.models.listing import Listing, ListingStatus
    from app.models.part import Part

    if not search_terms:
        return None

    price_low  = max(1.0, target_price * 0.65)
    price_high = target_price * 1.45

    try:
        async with AsyncSessionLocal() as db:
            if is_whole_pc:
                filters: list = [
                    Listing.price.between(price_low, price_high),
                    Listing.status == ListingStatus.active,
                ]
                for term in search_terms[:3]:
                    filters.append(Listing.title.ilike(f"%{term}%"))
                result = await db.execute(
                    select(Listing)
                    .where(and_(*filters))
                    .order_by(Listing.gem_score.desc().nullslast(), Listing.price.asc())
                    .limit(1)
                )
                listing = result.scalar_one_or_none()
                if listing:
                    image = (listing.image_urls or [None])[0] if listing.image_urls else None
                    return {"url": listing.url, "image_url": image, "title": listing.title, "price": listing.price}
            else:
                # Components: check Parts table first
                part_filters: list = [Part.is_active == True]
                if target_price > 0:
                    part_filters.append(Part.price.between(price_low, price_high))
                for term in search_terms[:2]:
                    part_filters.append(Part.name.ilike(f"%{term}%"))
                result = await db.execute(
                    select(Part).where(and_(*part_filters)).order_by(Part.price.asc()).limit(1)
                )
                part = result.scalar_one_or_none()
                if part:
                    return {"url": part.source_url, "image_url": part.image_url, "title": part.name, "price": part.price}
    except Exception as exc:
        log.warning("catalogue_enrichment.search_error", terms=search_terms, error=str(exc))

    return None


async def catalogue_enrichment_agent(plan: "PurchasePlan") -> "PurchasePlan":
    """
    For each component in the plan, find a specific matching listing from the catalogue.
    Attaches listing_url and image_url to the base PC and each upgrade.
    Runs in parallel for all components.
    """
    build = plan.build

    async def _enrich_base():
        terms = _extract_model_terms(build.base_spec, is_whole_pc=True)
        match = await _find_catalogue_listing(terms, build.base_cost, is_whole_pc=True)
        if match:
            build.base_listing_url = match.get("url") or ""
            build.base_image_url   = match.get("image_url") or ""
            log.info("catalogue_enrichment.base_matched", spec=build.base_spec[:40], url=build.base_listing_url[:60])
        else:
            log.info("catalogue_enrichment.base_no_match", spec=build.base_spec[:40])

    async def _enrich_upgrade(u: BuildUpgrade):
        terms = _extract_model_terms(u.item, is_whole_pc=False)
        match = await _find_catalogue_listing(terms, u.cost_estimate, is_whole_pc=False)
        if match:
            u.listing_url = match.get("url") or ""
            u.image_url   = match.get("image_url") or ""

    await asyncio.gather(_enrich_base(), *[_enrich_upgrade(u) for u in build.upgrades])
    return plan


# ─── Agent 5: Planner ────────────────────────────────────────────────────────

async def planner_agent(build: Build, intent: RefinedIntent) -> PurchasePlan:
    """Generates a step-by-step purchase plan for the selected build."""
    from app.services.ai_service import chat as ai_chat

    upgrade_list = "\n".join(
        f"  - {u.item} ({u.role}): ~£{u.cost_estimate:.0f} via {u.source}"
        for u in build.upgrades
    )

    prompt = f"""You are the Planner agent in a PC-flipping build wizard.

The user has selected this build:
Name: {build.name}
Base PC to source: {build.base_spec}
Base cost target: £{build.base_cost:.0f}
Upgrades needed:
{upgrade_list}
Total cost: £{build.total_cost:.0f}
Target sell price: £{build.sell_price_target:.0f} on {build.sell_platform}
Estimated profit: £{build.estimated_profit:.0f}

{_MARKET_CONTEXT}

Generate a practical, step-by-step purchase and flip plan.
Do NOT include any geographic location in the tips or steps (no city names like Birmingham, London etc.).
All sourcing is done through eBay UK — no Facebook Marketplace or Gumtree.

Respond with ONLY valid JSON:
{{
  "steps": [
    {{"step": 1, "action": "Source base PC on eBay", "detail": "Search eBay UK for: {build.base_spec}", "estimated_time": "1-2 days"}},
    {{"step": 2, "action": "Inspect and test", "detail": "Check POST, RAM slots, PCIe slot", "estimated_time": "1 hour"}},
    ...
  ],
  "tips": [
    "Buy on a Sunday evening — more auctions end, less competition",
    "Check the PSU rating — 300W won't run an RTX 3060"
  ],
  "timeline_days": 14
}}"""

    contingency = round(build.total_cost * 0.10, 2)
    steps = [
        {"step": 1, "action": "Source base PC on eBay", "detail": f"Search eBay UK for: {build.base_spec}", "estimated_time": "1-3 days"},
        {"step": 2, "action": "Test on arrival", "detail": "POST test, check all slots, run memtest", "estimated_time": "1 hour"},
    ]
    for i, u in enumerate(build.upgrades, 3):
        steps.append({"step": i, "action": f"Source {u.item}", "detail": f"Source via {u.source} for ~£{u.cost_estimate:.0f}", "estimated_time": "1-2 days"})
    steps.append({"step": len(steps) + 1, "action": "Build and test", "detail": "Install upgrades, run benchmarks, clean thoroughly", "estimated_time": "2-3 hours"})
    steps.append({"step": len(steps) + 1, "action": f"List on {build.sell_platform}", "detail": f"Target price £{build.sell_price_target:.0f} — use keyword-rich title", "estimated_time": "30 minutes"})
    tips = [
        "Buy base unit on Sunday evenings — more auctions end, fewer bidders",
        f"Keep a £{contingency:.0f} contingency buffer (10%) for unexpected costs",
        f"Price at £{build.sell_price_target:.0f} — don't undercut, demand is there",
    ]
    timeline_days = 14

    try:
        response, _ = await ai_chat(prompt, [], None)
        m = re.search(r'\{[\s\S]*\}', re.sub(r"```(?:json)?", "", response).strip())
        if m:
            data = json.loads(m.group())
            steps = data.get("steps", steps)
            tips = data.get("tips", tips)
            timeline_days = data.get("timeline_days", timeline_days)
    except Exception as exc:
        log.warning("planner.ai_failed_using_template", error=str(exc))

    return PurchasePlan(
        build=build,
        steps=steps,
        total_budget=build.total_cost + contingency,
        contingency_buffer=contingency,
        expected_net_profit=build.estimated_profit,
        expected_roi_pct=round((build.estimated_profit / build.total_cost) * 100, 1),
        timeline_days=timeline_days,
        tips=tips,
    )


# ─── Orchestrator ─────────────────────────────────────────────────────────────

async def run_build_wizard(
    playbook: dict,
    budget: float,
    user_notes: str,
    priorities: list[str],
    constraints: list[str],
    owned_components: list[dict] | None = None,
) -> dict:
    """
    Main entry point.  Runs the full Wizard → Composer → Validator loop.
    Returns a dict ready for JSON serialisation.
    """
    # Phase 1: Wizard
    intent = await wizard_agent(playbook, budget, user_notes, priorities, constraints, owned_components)
    log.info("wizard.intent", playbook=intent.playbook_name, budget=intent.budget_max)

    # Phase 2+3: Composer → Validator loop (max 3 attempts)
    all_valid: list[Build] = []
    all_rejected: list[Build] = []

    for attempt in range(1, 4):
        log.info("composer.attempt", n=attempt)
        candidates = await composer_agent(intent, playbook, attempt)
        _apply_owned_components(candidates, intent.owned_components)

        valid = await validator_agent(candidates, intent)
        rejected = [b for b in candidates if not b.valid]
        all_valid.extend(valid)
        all_rejected.extend(rejected)

        # Deduplicate by name
        seen_names: set[str] = set()
        unique_valid: list[Build] = []
        for b in all_valid:
            if b.name not in seen_names:
                seen_names.add(b.name)
                unique_valid.append(b)
        all_valid = unique_valid

        log.info("validator.result", valid=len(all_valid), rejected=len(rejected), attempt=attempt)
        if len(all_valid) >= 3:
            break

        if attempt < 3:
            log.info("composer.regenerating", reason=f"only {len(all_valid)} valid builds")
            await asyncio.sleep(0.5)

    # Phase 3b: LLM Resale Valuation (parallel, for all valid builds)
    if all_valid:
        all_valid = await resale_valuation_agent(all_valid)
        log.info("resale_valuation.complete", builds=len(all_valid))

    # Phase 4: Rank
    ranked = ranker_agent(all_valid[:5])  # cap at 5
    log.info("ranker.done", builds=len(ranked))

    return {
        "intent": asdict(intent),
        "builds": [_build_to_dict(b) for b in ranked],
        "rejected_count": len(all_rejected),
        "attempts": attempt,
    }


async def run_planner(build_data: dict, intent_data: dict) -> dict:
    """Entry point for the Planner phase after user selects a build."""
    build = _dict_to_build(build_data)
    intent = RefinedIntent(**intent_data)
    plan = await planner_agent(build, intent)
    plan = await catalogue_enrichment_agent(plan)
    return {
        "build": _build_to_dict(plan.build),
        "steps": plan.steps,
        "total_budget": plan.total_budget,
        "contingency_buffer": plan.contingency_buffer,
        "expected_net_profit": plan.expected_net_profit,
        "expected_roi_pct": plan.expected_roi_pct,
        "timeline_days": plan.timeline_days,
        "tips": plan.tips,
    }


# ─── Serialisation helpers ────────────────────────────────────────────────────

def _build_to_dict(b: Build) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "base_spec": b.base_spec,
        "base_cost": b.base_cost,
        "base_listing_url": b.base_listing_url,
        "base_image_url": b.base_image_url,
        "upgrades": [
            {
                "role": u.role,
                "item": u.item,
                "cost_estimate": u.cost_estimate,
                "source": u.source,
                "required": u.required,
                "listing_url": u.listing_url,
                "image_url": u.image_url,
            }
            for u in b.upgrades
        ],
        "total_cost": b.total_cost,
        "estimated_resale": b.estimated_resale,
        "estimated_profit": b.estimated_profit,
        "profit_margin_pct": b.profit_margin_pct,
        "risk": b.risk,
        "demand_fit": b.demand_fit,
        "why": b.why,
        "sell_platform": b.sell_platform,
        "sell_price_target": b.sell_price_target,
        "valid": b.valid,
        "validation_score": b.validation_score,
        "rejection_reason": b.rejection_reason,
        "compatibility_confidence": b.compatibility_confidence,
        "compatibility_warnings": b.compatibility_warnings,
        "rank": b.rank,
        "owned_components_applied": b.owned_components_applied,
        "owned_value_offset": b.owned_value_offset,
        "resale_source": b.resale_source,
        "resale_low": b.resale_low,
        "resale_high": b.resale_high,
        "resale_reasoning": b.resale_reasoning,
    }


def _dict_to_build(d: dict) -> Build:
    upgrades = [
        BuildUpgrade(
            role=u.get("role", ""),
            item=u.get("item", ""),
            cost_estimate=float(u.get("cost_estimate", 0)),
            source=u.get("source", ""),
            required=bool(u.get("required", True)),
            listing_url=u.get("listing_url", ""),
            image_url=u.get("image_url", ""),
        )
        for u in d.get("upgrades", [])
    ]
    return Build(
        id=d["id"], name=d["name"], base_spec=d["base_spec"],
        base_cost=d["base_cost"], upgrades=upgrades,
        total_cost=d["total_cost"], estimated_resale=d["estimated_resale"],
        estimated_profit=d["estimated_profit"], profit_margin_pct=d["profit_margin_pct"],
        risk=d["risk"], demand_fit=d["demand_fit"], why=d["why"],
        sell_platform=d["sell_platform"], sell_price_target=d["sell_price_target"],
        valid=d.get("valid", True), validation_score=d.get("validation_score", 0),
        rejection_reason=d.get("rejection_reason", ""),
        compatibility_confidence=d.get("compatibility_confidence", 0.0),
        compatibility_warnings=d.get("compatibility_warnings", []),
        rank=d.get("rank", 0),
        resale_source=d.get("resale_source", "rule-based"),
        resale_low=d.get("resale_low", 0.0),
        resale_high=d.get("resale_high", 0.0),
        resale_reasoning=d.get("resale_reasoning", ""),
        base_listing_url=d.get("base_listing_url", ""),
        base_image_url=d.get("base_image_url", ""),
    )
