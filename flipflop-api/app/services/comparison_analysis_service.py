"""AI-generated tradeoff analysis for multi-build comparisons."""

import structlog
from app.services.model_selection_service import model_selection_service
from app.schemas.build_comparison import ComparedBuildOut

log = structlog.get_logger(__name__)

FALLBACK_MESSAGE = (
    "AI analysis is unavailable right now (configured model tiers are unavailable). "
    "The comparison table above is still accurate."
)


def _build_prompt(builds: list[ComparedBuildOut]) -> str:
    lines = ["Compare these FlipFlop PC builds for a customer deciding between them:\n"]
    for b in builds:
        lines.append(f"## {b.label} ({b.playbook_name})")
        for slot in b.slots:
            lines.append(f"- {slot.slot_type}: {slot.title} (£{slot.price:.2f})")
        if b.case_name:
            lines.append(f"- Case: {b.case_name} (£{b.case_price:.2f})")
        lines.append(f"Total: £{b.total:.2f}\n")

    lines.append(
        "Write a short, honest comparison (150-250 words) covering: the concrete "
        "spec differences that actually matter (not every line item), which build "
        "suits which use case, and a clear recommendation if one build is simply "
        "better value at a similar price. Plain text, no markdown headers, no "
        "bullet points — a few short paragraphs a customer would actually read."
    )
    return "\n".join(lines)


async def generate_comparison_analysis(builds: list[ComparedBuildOut]) -> str:
    try:
        result = await model_selection_service.complete(
            task="Build comparison analysis",
            messages=[{"role": "user", "content": _build_prompt(builds)}], max_tokens=600,
        )
        return result.text.strip() if result.text else FALLBACK_MESSAGE
    except Exception as e:
        log.warning("comparison_analysis.claude_call_failed", error=str(e))
        return FALLBACK_MESSAGE
