"""AI-generated tradeoff analysis for a multi-build comparison.

Reuses the same AsyncAnthropic client pattern as _claude_chat
(app/services/ai_service.py) rather than the sync `Anthropic` client used in
gem_service.py — this runs inside an async FastAPI endpoint, where a
blocking sync HTTP call would stall the event loop. Uses a stronger model
than ai_service.py's haiku-tier chat: comparison analysis is a lower-
frequency, higher-stakes-per-call feature (helping a customer choose between
two builds they might spend real money on) than casual chat.
"""

import structlog
from app.config import get_settings
from app.schemas.build_comparison import ComparedBuildOut

log = structlog.get_logger(__name__)

FALLBACK_MESSAGE = (
    "AI analysis is unavailable right now (ANTHROPIC_API_KEY not configured). "
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
    settings = get_settings()
    if not settings.anthropic_api_key:
        return FALLBACK_MESSAGE

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model="claude-sonnet-5",
            max_tokens=600,
            messages=[{"role": "user", "content": _build_prompt(builds)}],
        )
        text = resp.content[0].text if resp.content else None
        return text.strip() if text else FALLBACK_MESSAGE
    except Exception as e:
        log.warning("comparison_analysis.claude_call_failed", error=str(e))
        return FALLBACK_MESSAGE
