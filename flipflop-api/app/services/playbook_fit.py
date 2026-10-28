"""Customer-safe Playbook assignment context for finished build listings."""
from collections.abc import Mapping


def public_playbook_fit(assignment: object) -> dict | None:
    if not isinstance(assignment, Mapping):
        return None
    segment = assignment.get("customer_type")
    tier = assignment.get("budget_tier")
    if not isinstance(segment, str) or not segment.strip() or not isinstance(tier, str) or not tier.strip():
        return None

    segment = segment.strip()
    tier = tier.strip()
    cell_name = f"{segment} · {tier}"

    intended_use = None
    curated_id = assignment.get("curated_build_id")
    if isinstance(curated_id, str) and curated_id.strip():
        from app.services.curated_build_policy import definitions

        definition = next(
            (row for row in definitions().get("builds", []) if row.get("id") == curated_id),
            None,
        )
        if definition:
            use = definition.get("use")
            intended_use = use.strip() if isinstance(use, str) and use.strip() else None

    return {
        "cell_name": cell_name,
        "customer_type": segment,
        "budget_tier": tier,
        "intended_use": intended_use,
        "explanation": (
            "This build was assigned to this Playbook cell during preparation. "
            "Use the exact specification and measured results below to decide how well it fits your own needs."
        ),
    }
