"""Reviewed catalogue and validation for optional paid AI setup services."""
from __future__ import annotations

from typing import Any


AI_SETUP_OFFER_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "ai_assistant_automation_pack",
        "name": "AI assistant and automation setup",
        "description": "Install and configure an approved AI assistant with a reviewed starter automation pack.",
        "included_automations": [
            {"name": "Research brief", "benefit": "Turn selected sources into a cited summary for review."},
            {"name": "Inbox triage", "benefit": "Group and summarise messages without sending replies."},
            {"name": "Meeting actions", "benefit": "Draft decisions and follow-up tasks from notes you provide."},
            {"name": "File finding", "benefit": "Help locate and summarise files in folders you explicitly approve."},
            {"name": "Idea to project plan", "benefit": "Turn an idea into draft steps, milestones and open questions."},
        ],
        "requires_vram_gb": None,
    },
    {
        "id": "personal_ai_second_brain",
        "name": "Personal AI and second brain setup",
        "description": "Prepare a personal assistant and second-brain memory workspace, with account access, storage location and data handling confirmed by the customer.",
        "included_automations": [],
        "requires_vram_gb": None,
    },
    {
        "id": "local_llm_setup",
        "name": "Local AI model setup",
        "description": "Install and configure a reviewed local language model and tools for this build. Local inference avoids per-request cloud API charges, but electricity, model licence terms and optional services still apply.",
        "included_automations": [],
        "requires_vram_gb": 12,
    },
)
_BY_ID = {item["id"]: item for item in AI_SETUP_OFFER_DEFINITIONS}


def normalise_ai_setup_offers(configured: list | None) -> list[dict[str, Any]]:
    saved = {item.get("id"): item for item in (configured or []) if isinstance(item, dict)}
    return [
        {
            **definition,
            "enabled": bool(saved.get(definition["id"], {}).get("enabled", False)),
            "price_gbp": saved.get(definition["id"], {}).get("price_gbp"),
            "commercial_scope_reviewed": bool(saved.get(definition["id"], {}).get("commercial_scope_reviewed", False)),
        }
        for definition in AI_SETUP_OFFER_DEFINITIONS
    ]


def validate_ai_setup_offers(configured: list) -> list[dict[str, Any]]:
    if len(configured) != len(AI_SETUP_OFFER_DEFINITIONS):
        raise ValueError("Provide exactly one configuration for each supported AI setup offer")
    by_id: dict[str, dict[str, Any]] = {}
    for item in configured:
        offer_id = item.get("id")
        if offer_id not in _BY_ID or offer_id in by_id:
            raise ValueError("AI setup offer IDs must be unique and supported")
        enabled = bool(item.get("enabled"))
        price = item.get("price_gbp")
        if price is not None and (isinstance(price, bool) or not isinstance(price, (int, float)) or not 0 < float(price) <= 5000):
            raise ValueError("AI setup prices must be greater than £0 and no more than £5,000")
        if enabled and price is None:
            raise ValueError("Set a price before enabling an AI setup offer")
        by_id[offer_id] = {"id": offer_id, "enabled": enabled, "price_gbp": round(float(price), 2) if price is not None else None}
    if set(by_id) != set(_BY_ID):
        raise ValueError("Provide every supported AI setup offer exactly once")
    return [by_id[definition["id"]] for definition in AI_SETUP_OFFER_DEFINITIONS]


def public_ai_setup_offers(configured: list | None, gpu_vram_gb: float | None) -> list[dict[str, Any]]:
    result = []
    for offer in normalise_ai_setup_offers(configured):
        minimum = offer["requires_vram_gb"]
        eligible = minimum is None or (gpu_vram_gb is not None and gpu_vram_gb >= minimum)
        if not offer["enabled"] or offer["price_gbp"] is None or not offer["commercial_scope_reviewed"]:
            continue
        result.append({
            **offer,
            "eligible": eligible,
            "eligibility_message": None if eligible else (
                f"This option needs a graphics card with at least {minimum} GB VRAM. "
                "The required VRAM has not been confirmed for this build."
            ),
        })
    return result
