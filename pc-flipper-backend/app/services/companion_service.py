"""
Hermes companion service — Ollama call + search_listings tool dispatch.
"""
from __future__ import annotations

import json
import asyncio
from typing import AsyncIterator

import httpx
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.listing import Listing, Classification

log = structlog.get_logger(__name__)

SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_listings",
        "description": (
            "Search the live PC listings catalogue. Call this whenever the user asks to find, "
            "show, or search for listings, PCs, or specific hardware."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms, e.g. 'RTX 3060 gaming PC'",
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum price in GBP (optional)",
                },
                "classification": {
                    "type": "string",
                    "enum": ["gem", "watch", "ok", "overpriced"],
                    "description": "Filter by listing classification (optional)",
                },
            },
            "required": ["query"],
        },
    },
}


def build_system_prompt(snapshot: str, page_context: str) -> str:
    return f"""You are Hermes, a sharp and helpful companion AI embedded in FlipFlop — a PC flipping intelligence platform.

Personality: dry British wit, genuinely useful, concise. You know PC hardware, resale markets, and flipping inside-out.

Current page: {page_context}

Live catalogue state:
{snapshot}

You have a search_listings tool. When the user asks to find, show, or search for listings or hardware, call it — don't make up listings.
When showing search results, briefly comment on the best option(s) after the results.
Keep replies short unless the user asks for detail. Use markdown sparingly."""


def parse_search_args(args: dict) -> dict:
    try:
        max_price = float(args["max_price"]) if args.get("max_price") is not None else None
    except (ValueError, TypeError):
        max_price = None
    return {
        "query": str(args.get("query", "")),
        "max_price": max_price,
        "classification": str(args["classification"]) if args.get("classification") else None,
    }


def format_listing_result(listing: Listing) -> dict:
    return {
        "id": listing.id,
        "title": listing.title,
        "price": listing.price,
        "classification": listing.classification.value if listing.classification else "unknown",
        "score": listing.gem_score or 0.0,
        "source": listing.source_name,
        "url": listing.url,
        "gpu": listing.gpu,
        "cpu": listing.cpu,
        "ram_gb": listing.ram_gb,
    }


async def get_catalogue_snapshot(db: AsyncSession) -> str:
    row = await db.execute(
        select(
            func.count().label("total"),
            func.sum((Listing.classification == Classification.gem).cast(int)).label("gems"),
            func.sum((Listing.classification == Classification.watching).cast(int)).label("watching"),
            func.max(Listing.seen_at).label("last_seen"),
        ).select_from(Listing)
    )
    stats = row.one()
    total = stats.total or 0
    gems = int(stats.gems or 0)
    watching = int(stats.watching or 0)

    top_gems_q = await db.execute(
        select(Listing.title, Listing.price)
        .where(Listing.classification == Classification.gem)
        .order_by(Listing.gem_score.desc())
        .limit(5)
    )
    top_gems = top_gems_q.all()
    gems_str = ", ".join(f"{t[:35]} £{p:.0f}" for t, p in top_gems) if top_gems else "none"

    return (
        f"Total listings: {total} | Gems: {gems} | Watching: {watching}\n"
        f"Top gems: {gems_str}"
    )


async def do_search_listings(
    db: AsyncSession,
    query: str,
    max_price: float | None = None,
    classification: str | None = None,
    limit: int = 6,
) -> list[dict]:
    from sqlalchemy import or_
    words = query.lower().split()
    conditions = [Listing.title.ilike(f"%{w}%") for w in words if len(w) >= 2]
    if not conditions and query.strip():
        return []
    stmt = select(Listing)
    if conditions:
        stmt = stmt.where(or_(*conditions))
    if max_price is not None:
        stmt = stmt.where(Listing.price <= max_price)
    if classification:
        try:
            cls = Classification(classification)
            stmt = stmt.where(Listing.classification == cls)
        except ValueError:
            pass
    stmt = stmt.order_by(Listing.gem_score.desc()).limit(limit)
    result = await db.execute(stmt)
    return [format_listing_result(r) for r in result.scalars().all()]


async def stream_companion(
    message: str,
    history: list[dict],
    page_context: str,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """Yields SSE-formatted strings."""
    _s = get_settings()
    ollama_url = f"{_s.ollama_base_url}/api/chat"
    model = _s.ollama_model

    snapshot = await get_catalogue_snapshot(db)
    system = build_system_prompt(snapshot, page_context)

    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": message}]

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(ollama_url, json={
                "model": model,
                "messages": messages,
                "tools": [SEARCH_TOOL_SCHEMA],
                "stream": False,
            })
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.warning("companion.ollama_error", error=str(exc))
            yield f"data: {json.dumps({'type': 'token', 'content': \"I'm having trouble connecting to my brain right now. Try again in a moment.\"})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'model_used': 'none'})}\n\n"
            return

        assistant_msg = data.get("message", {})
        tool_calls = assistant_msg.get("tool_calls") or []

        if tool_calls:
            tool_call = tool_calls[0]
            fn = tool_call.get("function", {})
            raw_args = fn.get("arguments", {})
            args = parse_search_args(raw_args if isinstance(raw_args, dict) else json.loads(raw_args))

            results = await do_search_listings(db, **args)
            yield f"data: {json.dumps({'type': 'search_results', 'results': results})}\n\n"

            messages.append(assistant_msg)
            messages.append({
                "role": "tool",
                "content": json.dumps(results),
                "name": "search_listings",
            })
            try:
                resp2 = await client.post(ollama_url, json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                })
                resp2.raise_for_status()
                final_text = resp2.json().get("message", {}).get("content", "")
            except Exception as exc:
                log.warning("companion.ollama_followup_error", error=str(exc))
                final_text = "Found those results — had a hiccup summarising them, but they're above."
        else:
            final_text = assistant_msg.get("content", "")

    chunk_size = 5
    for i in range(0, len(final_text), chunk_size):
        yield f"data: {json.dumps({'type': 'token', 'content': final_text[i:i+chunk_size]})}\n\n"
        await asyncio.sleep(0.01)

    yield f"data: {json.dumps({'type': 'done', 'model_used': f'ollama/{model}'})}\n\n"
