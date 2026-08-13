"""
Hermes AI service.
Primary: Ollama (local gemma4:e4b) → OpenRouter free models → Anthropic Claude last resort.
"""
import httpx
import urllib.parse
from app.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """You are Hermes, an AI assistant embedded in a PC flipping intelligence platform.

Your personality: sarcastic, dry British humour, but genuinely helpful. You know your stuff about PC hardware, resale markets, and flipping strategy. You speak like someone who's seen too many overpriced "gaming PCs" on Facebook Marketplace.

Your capabilities:
- Evaluate PC listings (buy / skip / conditional)
- Suggest upgrade paths with estimated costs and ROI
- Estimate resale values and profit margins
- Flag gem signals (no GPU, no storage, poor title, collection only, etc.)
- Analyse builds for compatibility
- Suggest selling prices and platform strategy
- Recommend which flips to prioritise based on score and market timing

Current market context:
- GTX 1060 6GB: ~£75 used
- RX 580 8GB: ~£65 used
- RX 570 4GB: ~£45 used
- 480GB SSD: ~£28 used / £35 new
- 1TB SSD: ~£55 used / £65 new
- 16GB DDR4: ~£22 used
- 8GB DDR4: ~£12 used
- eBay fees: ~12.7%
- Facebook/Gumtree fees: 0–2%
- Sweet spot: i5/i7 6th–9th gen, 16GB DDR4, no storage, no GPU, < £150
- Sci-fi themed cases add £30–80 to resale value if done well

When evaluating listings, always give: verdict, reasoning, upgrade path if applicable, estimated profit range.
Keep responses concise but complete. Use markdown for structure."""

# OpenRouter free models to try in order — primary first
OPENROUTER_FREE_MODELS = [
    "google/gemma-4-31b-it:free",       # primary
    "google/gemma-3-4b-it:free",        # fallback 1
    "mistralai/mistral-7b-instruct:free",  # fallback 2
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "meta-llama/llama-3.2-3b-instruct:free",
]


async def chat(
    message: str,
    history: list[dict],
    listing_context: dict | None = None,
) -> tuple[str, str]:
    """Returns (response_text, model_used)."""
    messages = _build_messages(message, history, listing_context)

    # Re-read settings so in-process changes (via /settings PUT) take effect without restart
    _s = get_settings()

    # 1. Try Ollama (local gemma4:e4b) — primary
    if _s.ollama_base_url:
        try:
            response = await _ollama_chat(messages, _s)
            if response:
                return response, _s.ollama_model
        except Exception as e:
            print(f"[hermes] Ollama failed: {e}")

    # 2. Try OpenRouter free models as fallback
    if _s.openrouter_api_key:
        primary = _s.openrouter_primary_model or OPENROUTER_FREE_MODELS[0]
        try:
            result = await _openrouter_chat(messages, primary, _s.openrouter_api_key)
            if result:
                content, label = result
                return content, f"openrouter/{label}"
        except Exception as e:
            print(f"[hermes] OpenRouter primary ({primary}) failed: {e}")

        for model in OPENROUTER_FREE_MODELS:
            if model == primary:
                continue
            try:
                result = await _openrouter_chat(messages, model, _s.openrouter_api_key)
                if result:
                    content, label = result
                    return content, f"openrouter/{label}"
            except Exception as e:
                print(f"[hermes] OpenRouter {model} failed: {e}")

    # 3. Try Claude as last resort
    if _s.anthropic_api_key:
        try:
            response = await _claude_chat(messages)
            if response:
                return response, "claude-haiku-4-5"
        except Exception as e:
            print(f"[hermes] Claude failed: {e}")

    return (
        "All AI backends offline. Ensure Ollama is running (`ollama serve`) or add an OpenRouter API key in Settings.",
        "none",
    )


async def generate_listing_content(
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    storage_type: str | None,
    gpu: str | None,
    location: str | None,
    case_theme: str | None = None,
) -> tuple[list[str], str]:
    """Generate 3 eBay titles and a full description. Returns (titles, description)."""
    theme_line = f"\nCase theme: {case_theme} (sci-fi themed build)" if case_theme else ""
    spec_summary = f"CPU: {cpu or 'Unknown'}, RAM: {ram_gb or '?'}GB {ram_type or ''}, Storage: {storage_gb or 'None'} {storage_type or ''}, GPU: {gpu or 'None'}, Location: {location or 'UK'}{theme_line}"

    prompt = f"""Generate eBay listing content for this PC:
{spec_summary}

Title rules (Algorithm Playbook row 4 — title keyword match is Cassini's
strongest ranking signal, so follow this exactly):
- Structure: Item type + Brand/Model or key specs (CPU, GPU, RAM, storage) + Condition.
- Front-load the item and key specs FIRST; put anything else (case theme, extras) LAST.
- Use as much of the ~80-character budget as the real specs justify — don't pad, but don't
  leave it mostly empty either.
- No keyword-stuffing, no subjective filler ("Amazing", "Bargain", "L@@K", "Must See") —
  Cassini doesn't reward it and it wastes characters that could carry another real spec.

Respond with EXACTLY this JSON format (no extra text):
{{
  "titles": [
    "Title option 1 (spec-first structure above, max 80 chars)",
    "Title option 2 (different real angle — e.g. lead with GPU instead of CPU — same rules)",
    "Title option 3 (different real angle — e.g. lead with use-case, still spec-first, same rules)"
  ],
  "description": "Full eBay description with specs, condition, use cases, and call to action"
}}"""

    try:
        response, _ = await chat(prompt, [], None)
        import json, re
        # Extract JSON from response
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            data = json.loads(match.group())
            return data.get("titles", []), data.get("description", "")
    except Exception as e:
        print(f"[hermes] listing gen failed: {e}")

    # Fallback: template-based
    titles = _template_titles(cpu, ram_gb, storage_gb, gpu, case_theme)
    description = _template_description(cpu, ram_gb, ram_type, storage_gb, storage_type, gpu, location, case_theme)
    return titles, description


async def generate_product_images(
    cpu: str | None,
    gpu: str | None,
    case_theme: str | None,
    provider: str = "pollinations",
    listing_images: list[str] | None = None,
) -> list[str]:
    """
    Generate AI product/marketing photos for a flipped PC.
    Returns list of image URLs (Pollinations.ai by default — free, no key needed).

    Shot list (6 angles):
      1. Studio front — white bg, commercial product shot
      2. Dark hero — RGB glow, gamer aesthetic
      3. Gamer's desk — lifestyle, room context, ambient light
      4. 45° beauty — angled, bokeh background
      5. Internals close-up — cable management, components
      6. Extreme zoom — logo detail / cable weave
    """
    theme_desc = f"{case_theme}-themed" if case_theme else "custom-built"
    cpu_desc   = cpu or "Intel Core i7"
    gpu_desc   = f", {gpu}" if gpu else ", integrated graphics"
    build_desc = f"{cpu_desc}{gpu_desc}"

    base_neg = "blurry, low quality, cartoon, illustration, watermark, text, logo, hands, person"

    shots = [
        # 1 — clean product shot
        (
            f"Professional commercial product photography of a {theme_desc} gaming PC tower, "
            f"{build_desc}, clean white studio background, soft box lighting, sharp focus, "
            f"4K ultra realistic, front view, eBay listing quality, no reflections",
            800, 600,
        ),
        # 2 — dark RGB hero
        (
            f"Dark background dramatic hero shot of a {theme_desc} gaming PC, {build_desc}, "
            f"colourful RGB lighting, neon glow, studio setup, side angle, ultra realistic 4K, "
            f"commercial photography, sharp details",
            800, 600,
        ),
        # 3 — lifestyle gamer's desk
        (
            f"Lifestyle photography of a {theme_desc} gaming PC tower on a modern gamer's desk, "
            f"dual monitors, RGB keyboard and mouse, dark room, ambient purple and blue lighting, "
            f"cable management visible, ultra realistic 4K, cinematic, {build_desc}",
            900, 600,
        ),
        # 4 — 45° beauty shot
        (
            f"45-degree beauty shot of a {theme_desc} PC tower, {build_desc}, "
            f"dark bokeh background, shallow depth of field, professional product photography, "
            f"RGB reflections, ultra realistic 4K",
            800, 600,
        ),
        # 5 — internals / side panel open
        (
            f"Side panel open view of a {theme_desc} gaming PC showing internals, "
            f"{cpu_desc} CPU, {gpu_desc.strip(', ')}, neat cable management, RGB RAM and fans, "
            f"professional photography, dark background, ultra realistic 4K",
            800, 600,
        ),
        # 6 — extreme close-up detail
        (
            f"Macro close-up photography of {theme_desc} PC case front panel detail, "
            f"RGB fan mesh, premium build quality, dark moody background, "
            f"ultra realistic 4K, bokeh, product photography",
            600, 600,
        ),
    ]

    if provider == "pollinations":
        images = []
        for i, (prompt, w, h) in enumerate(shots):
            encoded = urllib.parse.quote(prompt)
            seed = abs(hash(f"{cpu}{gpu}{case_theme}{i}") % 99999)
            url = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?width={w}&height={h}&seed={seed}&nologo=true&negative={urllib.parse.quote(base_neg)}"
            )
            images.append(url)
        return images

    return []


def _build_messages(message: str, history: list[dict], listing_context: dict | None) -> list[dict]:
    messages = []
    if listing_context:
        context_str = (
            f"\n\n[Listing context: {listing_context.get('title', '')} — "
            f"£{listing_context.get('price', '')} — "
            f"{listing_context.get('specs', '')}]"
        )
        message = message + context_str
    for h in history[-8:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})
    return messages


async def _ollama_chat(messages: list[dict], cfg=None) -> str | None:
    cfg = cfg or settings
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{cfg.ollama_base_url}/api/chat",
            json={
                "model": cfg.ollama_model,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                "stream": False,
            },
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content")


async def _openrouter_chat(messages: list[dict], model: str, api_key: str | None = None) -> tuple[str, str] | None:
    """Returns (content, actual_model_used) or None on failure."""
    key = api_key or settings.openrouter_api_key
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "PC Flipper Hermes",
            },
            json={
                "model": model,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                "max_tokens": 1024,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        # Use the model OpenRouter actually routed to (may differ from requested)
        actual_model = data.get("model", model)
        # Shorten to just the model name portion for display
        label = actual_model.split("/")[-1].replace(":free", "") if "/" in actual_model else actual_model
        return content, label


async def _claude_chat(messages: list[dict]) -> str | None:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return resp.content[0].text if resp.content else None


def _template_titles(cpu, ram_gb, storage_gb, gpu, case_theme) -> list[str]:
    # Row 4: item + key specs first, filler (theme, condition words) last.
    storage = f"{storage_gb}GB SSD" if storage_gb else "No Storage"
    gpu_str = gpu or "No GPU"
    theme_suffix = f" {case_theme} Theme" if case_theme else ""
    return [
        f"Gaming PC {cpu} {gpu_str} {ram_gb}GB {storage} Desktop Computer{theme_suffix}",
        f"Desktop PC {cpu} {ram_gb}GB RAM {gpu_str}{theme_suffix} Windows 11",
        f"Custom PC Tower {cpu} {gpu_str} {ram_gb}GB {storage}{theme_suffix}",
    ]


def _template_description(cpu, ram_gb, ram_type, storage_gb, storage_type, gpu, location, case_theme) -> str:
    theme_line = f"\nSci-fi themed case: {case_theme} — perfect conversation piece and gaming centrepiece.\n" if case_theme else ""
    storage_str = f"{storage_gb}GB {storage_type}" if storage_gb else "No storage included (easy upgrade)"
    gpu_str = gpu if gpu else "Integrated graphics (upgrade-ready)"
    return f"""For sale: Custom built desktop PC in excellent condition.
{theme_line}
Specifications:
• CPU: {cpu or 'See listing'}
• RAM: {ram_gb or '?'}GB {ram_type or 'DDR4'}
• Storage: {storage_str}
• GPU: {gpu_str}

Tested and working. Windows 11 ready.
{f'Collection from {location} or can post at buyer''s expense.' if location else 'Collection preferred or can arrange postage.'}

Any questions welcome!"""
