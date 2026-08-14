"""
Listing Generator Service - Generate professional eBay listings with AI.

Handles:
- AI-generated product titles (multiple options)
- AI-generated descriptions with FlipFlop branding
- Performance stats and warranty messaging
- eBay-optimized HTML formatting
"""

import structlog
from typing import Optional, List
from app.models.flip import Flip
from app.services.ai_service import chat as _ai_chat

log = structlog.get_logger(__name__)


async def ai_chat(prompt: str, context: List, model_hint=None) -> tuple[str, str]:
    return await _ai_chat(prompt, context)


async def generate_listing_title_options(
    flip: Flip,
    num_options: int = 3,
) -> List[str]:
    """
    Generate multiple title options for a flip listing.

    Args:
        flip: Flip object with build details
        num_options: Number of title variations to generate

    Returns:
        List of suggested titles (max length 80 chars for eBay)
    """
    # Build context from flip specs
    specs_summary = _build_specs_summary(flip)

    prompt = f"""Generate {num_options} compelling eBay product titles for a high-performance gaming/workstation PC.

Build Specifications:
{specs_summary}

Requirements:
1. Each title MUST be under 80 characters (eBay limit)
2. Include key specs that drive sales (GPU, CPU, RAM, etc.)
3. Lead with the most valuable component or performance positioning
4. Make it appeal to the target buyer (gamer, content creator, professional)
5. Each title should have a slightly different angle/positioning
6. Include condition if notable (e.g., "Like New Gaming PC" or "Tested & Ready to Ship")

Return ONLY the titles, one per line, no numbering or explanation."""

    try:
        response, model = await ai_chat(prompt, [], None)
        titles = [t.strip() for t in response.strip().split("\n") if t.strip() and len(t.strip()) < 100]
        log.info("listing_generator.titles_generated", count=len(titles), model=model)
        return titles[:num_options]
    except Exception as e:
        log.error("listing_generator.title_generation_failed", error=str(e))
        # Fallback to simple title
        return [f"Gaming PC Build - {specs_summary.split()[0]}"]


async def generate_listing_description(
    flip: Flip,
    brand_name: str = "FlipFlop",
    image_urls: Optional[List[str]] = None,
) -> str:
    """
    Generate a professional, structured eBay listing description with FlipFlop branding.

    Args:
        flip: Flip object with build details
        brand_name: Brand name to include in messaging
        image_urls: List of image URLs to embed in the description

    Returns:
        eBay-formatted HTML description with professional styling
    """
    specs_summary = _build_specs_summary(flip)

    # Build image HTML if URLs are provided
    image_html = ""
    if image_urls:
        image_html = "\n".join([
            f'<p style="margin: 20px 0; text-align: center;"><img src="{url}" style="max-width: 100%; height: auto; border-radius: 8px;" alt="Product Image" /></p>'
            for url in image_urls[:3]  # Limit to 3 images for performance
        ])

    prompt = f"""Generate a PROFESSIONAL, PREMIUM eBay listing description for a high-end gaming/workstation PC.

Build Specifications:
{specs_summary}

Brand: {brand_name} - Premium PC Specialist

CRITICAL REQUIREMENTS:
1. Use proper HTML structure with semantic tags
2. Organize into clear, professional sections with visual hierarchy
3. Use <strong> tags for key specs, NOT asterisks or markdown
4. Include line breaks for readability between sections
5. Write in professional business tone - no emojis, no casual language
6. Every specification should be highlighted and easy to scan
7. Include compelling benefits for each component category
8. Professional warranty and support messaging
9. Shipping and returns section with clear policy
10. Strong call-to-action that conveys premium quality

SECTION STRUCTURE:
- Opening: Compelling hook about the build's quality and performance
- Key Highlights: 3-4 bullet points of major selling points
- Detailed Specifications: CPU, GPU, RAM, Storage, Motherboard, Power Supply, Cooling
- Condition & Testing: Professional statement about testing and readiness
- {brand_name} Quality Promise: Trust and support messaging
- Shipping & Logistics: Clear shipping timeline and details
- Warranty & Returns: Professional policy statement
- Why Choose This Build: Compelling positioning for buyer type
- Call to Action: Encouraging purchase message

Return ONLY clean HTML formatted as <p> tags and <strong> tags.
NO markdown syntax, NO asterisks, NO emojis, NO casual language.
Make it look like a premium product listing."""

    try:
        response, model = await ai_chat(prompt, [], None)
        description = response.strip()

        # Post-process to ensure proper HTML formatting
        if not description.startswith("<"):
            description = f"<p>{description}</p>"

        # Inject images after opening section if available
        if image_html:
            # Insert images after first paragraph
            parts = description.split("</p>", 1)
            if len(parts) == 2:
                description = parts[0] + "</p>" + image_html + parts[1]

        log.info("listing_generator.description_generated", length=len(description), model=model)
        return description

    except Exception as e:
        log.error("listing_generator.description_generation_failed", error=str(e))
        # Fallback description with professional formatting
        return f"""<p><strong>Premium Gaming/Workstation PC - Professionally Built & Tested</strong></p>
<p>This high-performance system is configured for demanding users who expect reliability and power. Every component has been carefully selected, tested, and optimized for peak performance.</p>
<p><strong>Key Specifications:</strong></p>
<p>{specs_summary}</p>
<p><strong>Condition:</strong> Excellent. Fully tested and verified to be in perfect working order. Ships immediately ready to use.</p>
<p><strong>{brand_name} Quality Promise:</strong> We stand behind every build with expert support and quality assurance. Your satisfaction is our priority.</p>
<p><strong>Shipping:</strong> Ships within 1-2 business days via tracked courier service.</p>
<p>Don't miss this opportunity to own a premium-built gaming or workstation PC. Bid with confidence!</p>"""


def _build_specs_summary(flip: Flip) -> str:
    """
    Build a human-readable specs summary from flip data.

    Args:
        flip: Flip object

    Returns:
        Specs summary string
    """
    specs = []

    if flip.listing and flip.listing.cpu:
        specs.append(f"CPU: {flip.listing.cpu}")
    if flip.listing and flip.listing.gpu:
        specs.append(f"GPU: {flip.listing.gpu}")
    if flip.listing and flip.listing.ram_gb:
        specs.append(f"RAM: {flip.listing.ram_gb}GB {flip.listing.ram_type or ''}")
    if flip.listing and flip.listing.storage_gb:
        specs.append(f"Storage: {flip.listing.storage_gb}GB {flip.listing.storage_type or ''}")
    if flip.listing and flip.listing.has_psu:
        specs.append("PSU: Included")

    # Add any upgrade components
    if flip.selected_upgrade_ids:
        specs.append(f"\nUpgrades: {len(flip.selected_upgrade_ids)} components added")

    return "\n".join(specs) if specs else "Performance PC Build"


def format_description_html(description: str, include_specifications: bool = True) -> str:
    """
    Format a description as proper eBay HTML.

    Args:
        description: Raw description text
        include_specifications: Whether to add specs section

    Returns:
        eBay-ready HTML description
    """
    # Ensure proper HTML structure
    if not description.startswith("<"):
        # Wrap plain text in paragraphs
        paragraphs = description.split("\n\n")
        description = "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())

    # Remove dangerous tags
    for bad_tag in ["<script>", "<iframe>", "<object>"]:
        description = description.replace(bad_tag, "").replace(bad_tag.replace(">", "</"), "")

    return description


async def generate_full_listing(
    flip: Flip,
    num_title_options: int = 3,
) -> dict:
    """
    Generate complete listing package (titles, description, specs).

    Args:
        flip: Flip object
        num_title_options: Number of title variations

    Returns:
        Dict with title_options and description
    """
    try:
        # Generate titles and description in parallel
        title_options = await generate_listing_title_options(flip, num_title_options)
        description = await generate_listing_description(flip)

        log.info("listing_generator.full_listing_generated", flip_id=flip.id)

        return {
            "flip_id": flip.id,
            "title_options": title_options,
            "description": description,
            "recommended_title": title_options[0] if title_options else "Gaming PC Build",
            "specs": _build_specs_summary(flip),
        }

    except Exception as e:
        log.error("listing_generator.full_listing_failed", flip_id=flip.id, error=str(e))
        raise
