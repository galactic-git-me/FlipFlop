"""
Selling Toolkit — generates eBay/Facebook listing titles and descriptions.
Uses AI when available; falls back to template generation.
"""
from pathlib import Path
from app.services.ai_service import chat

TITLE_PROMPT = """Generate 3 optimised eBay listing titles for this PC.

Rules:
- Max 80 characters each
- Lead with CPU model and key specs
- Include GPU if present
- Use search-friendly terms
- No ALL CAPS
- No special characters except slashes

PC specs:
{specs}

Return exactly 3 titles, one per line, no numbering or bullets."""

DESCRIPTION_PROMPT = """Write an eBay listing description for this PC.

Format:
- Brief intro sentence
- Specs list (use actual values)
- What it's good for (3 bullet points)
- Condition notes
- "Tested and working" if applicable
- Collection / postage note

Keep it under 200 words. Plain text only, no markdown.

PC specs:
{specs}
Asking price: £{price}
Location: {location}"""


def _specs_string(
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    storage_type: str | None,
    gpu: str | None,
    location: str | None,
) -> str:
    parts = []
    if cpu:
        parts.append(f"CPU: {cpu}")
    if ram_gb:
        parts.append(f"RAM: {ram_gb}GB {ram_type or 'DDR4'}")
    if storage_gb:
        parts.append(f"Storage: {storage_gb}GB {storage_type or 'SSD'}")
    else:
        parts.append("Storage: None")
    if gpu:
        parts.append(f"GPU: {gpu}")
    else:
        parts.append("GPU: Integrated only")
    if location:
        parts.append(f"Location: {location}")
    return "\n".join(parts)


async def generate_titles(
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    storage_type: str | None,
    gpu: str | None,
    location: str | None,
) -> list[str]:
    specs = _specs_string(cpu, ram_gb, ram_type, storage_gb, storage_type, gpu, location)
    prompt = TITLE_PROMPT.format(specs=specs)
    response, _ = await chat(prompt, [])
    titles = [t.strip() for t in response.strip().split("\n") if t.strip()][:3]
    if not titles:
        titles = _template_titles(cpu, ram_gb, ram_type, gpu)
    return titles


async def generate_description(
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    storage_type: str | None,
    gpu: str | None,
    price: float,
    location: str | None,
) -> str:
    specs = _specs_string(cpu, ram_gb, ram_type, storage_gb, storage_type, gpu, location)
    prompt = DESCRIPTION_PROMPT.format(specs=specs, price=price, location=location or "UK")
    response, _ = await chat(prompt, [])
    base_desc = response.strip() if response else _template_description(cpu, ram_gb, gpu, price)

    about_content = _load_about_flipflop()
    formatted_about = _format_about_flipflop(about_content)

    if formatted_about:
        return f"{base_desc}\n\n{formatted_about}"
    return base_desc


def _template_titles(
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    gpu: str | None,
) -> list[str]:
    cpu_s = cpu or "Desktop PC"
    ram_s = f"{ram_gb}GB {ram_type or 'DDR4'}" if ram_gb else ""
    gpu_s = gpu or ""
    base = f"{cpu_s} {ram_s}".strip()
    return [
        f"Gaming Desktop PC {base} {gpu_s} Windows 11".strip()[:80],
        f"Desktop Computer {base} Fast SSD Ready To Use".strip()[:80],
        f"PC Tower {cpu_s} {ram_s} Budget Desktop".strip()[:80],
    ]


def _load_about_flipflop() -> str:
    """Load the About FlipFlop content to append to listings."""
    about_path = Path(__file__).resolve().parent.parent.parent / "config" / "about_flipflop.md"
    if about_path.exists():
        return about_path.read_text(encoding="utf-8")
    return ""


def _format_about_flipflop(content: str) -> str:
    """Convert markdown About FlipFlop to plain text for eBay listing."""
    if not content:
        return ""
    lines = content.split("\n")
    formatted = []
    for line in lines:
        if line.startswith("# "):
            formatted.append("\n" + line.replace("# ", "").upper())
        elif line.startswith("## "):
            formatted.append("\n" + line.replace("## ", ""))
        elif line.startswith("- "):
            formatted.append("• " + line[2:])
        elif line.strip():
            formatted.append(line)
    return "\n".join(formatted)


def _template_description(
    cpu: str | None,
    ram_gb: int | None,
    gpu: str | None,
    price: float,
) -> str:
    base_desc = (
        f"Desktop PC for sale. {cpu or 'Good processor'}, "
        f"{ram_gb or 8}GB RAM"
        f"{', ' + gpu if gpu else ''}. "
        f"Tested and working. Asking £{price:.0f}. "
        "Collection preferred. Message with any questions."
    )

    about_content = _load_about_flipflop()
    formatted_about = _format_about_flipflop(about_content)

    if formatted_about:
        return f"{base_desc}\n\n{formatted_about}"
    return base_desc
