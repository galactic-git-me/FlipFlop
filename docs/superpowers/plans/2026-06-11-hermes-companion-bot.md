# Hermes Companion Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent floating chat companion ("Hermes") to every page of the FlipFlop app, powered by local Ollama `gemma4:e4b`, with live catalogue search and context injection.

**Architecture:** A `"use client"` React context holds chat state (persists across navigation); a floating component mounts in `layout.tsx`; a new FastAPI SSE endpoint streams responses from Ollama, executing a `search_listings` tool call when the model asks for it. Context (top gems, counts, last scan) is injected fresh on every request.

**Tech Stack:** Next.js 14 (TypeScript, Tailwind), FastAPI (Python 3.12), Ollama `/api/chat` with tools, SQLAlchemy async, SSE via `StreamingResponse`.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pc-flipper/public/pics/hermes.gif` | Create (copy) | Bot avatar GIF |
| `pc-flipper-backend/app/services/companion_service.py` | Create | Ollama call, tool dispatch, context snapshot, search |
| `pc-flipper-backend/app/api/companion.py` | Create | SSE endpoint `/api/companion/stream` |
| `pc-flipper-backend/app/main.py` | Modify | Register companion router |
| `pc-flipper/lib/api.ts` | Modify | `streamCompanion()` fetch helper |
| `pc-flipper/components/hermes-context.tsx` | Create | React context — open state + message history |
| `pc-flipper/components/hermes-companion.tsx` | Create | Floating GIF button + chat panel UI |
| `pc-flipper/app/layout.tsx` | Modify | Mount `<HermesProvider>` and `<HermesCompanion>` |

---

## Task 1: Copy GIF asset

**Files:**
- Create: `pc-flipper/public/pics/hermes.gif`

- [ ] **Step 1: Copy the GIF**

```bash
cp /home/mac/CODING/on-the.trading/mac_client/public/images/AI_1.gif \
   /home/mac/CODING/FlipFlop/pc-flipper/public/pics/hermes.gif
```

- [ ] **Step 2: Verify it's there**

```bash
ls -lh /home/mac/CODING/FlipFlop/pc-flipper/public/pics/hermes.gif
```
Expected: file present, size ~1–4 MB.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/public/pics/hermes.gif
git commit -m "feat: add Hermes companion bot avatar GIF"
```

---

## Task 2: Backend — companion_service.py

**Files:**
- Create: `pc-flipper-backend/app/services/companion_service.py`

- [ ] **Step 1: Write tests**

Create `pc-flipper-backend/tests/test_companion_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.companion_service import (
    build_system_prompt,
    parse_search_args,
    format_listing_result,
)


def test_build_system_prompt_contains_snapshot():
    snapshot = "Total: 100 | Gems: 12 | Last scan: 5m ago"
    prompt = build_system_prompt(snapshot, "listings")
    assert "100" in prompt
    assert "12" in prompt
    assert "listings" in prompt.lower()


def test_parse_search_args_extracts_query():
    args = {"query": "rtx 3060", "max_price": 200}
    result = parse_search_args(args)
    assert result["query"] == "rtx 3060"
    assert result["max_price"] == 200.0


def test_parse_search_args_defaults():
    result = parse_search_args({"query": "gaming pc"})
    assert result["max_price"] is None
    assert result["classification"] is None


def test_format_listing_result():
    listing = MagicMock()
    listing.id = 1
    listing.title = "Gaming PC i7 RTX 3060"
    listing.price = 149.0
    listing.classification = MagicMock(value="gem")
    listing.gem_score = 81.0
    listing.source_name = "eBay"
    listing.url = "https://ebay.com/itm/123"
    result = format_listing_result(listing)
    assert result["title"] == "Gaming PC i7 RTX 3060"
    assert result["price"] == 149.0
    assert result["classification"] == "gem"
    assert result["score"] == 81.0
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-backend
python -m pytest tests/test_companion_service.py -v 2>&1 | head -30
```
Expected: `ImportError` or `ModuleNotFoundError` — file doesn't exist yet.

- [ ] **Step 3: Create companion_service.py**

Create `/home/mac/CODING/FlipFlop/pc-flipper-backend/app/services/companion_service.py`:

```python
"""
Hermes companion service — Ollama streaming + search_listings tool dispatch.
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
    return {
        "query": str(args.get("query", "")),
        "max_price": float(args["max_price"]) if args.get("max_price") is not None else None,
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


async def do_search_listings(db: AsyncSession, query: str, max_price: float | None, classification: str | None, limit: int = 6) -> list[dict]:
    from sqlalchemy import or_
    words = query.lower().split()
    conditions = [Listing.title.ilike(f"%{w}%") for w in words if len(w) > 2]
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

    # First call: non-streaming so we can detect tool calls cleanly
    try:
        async with httpx.AsyncClient(timeout=60) as client:
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
        yield f"data: {json.dumps({'type': 'token', 'content': 'I'm having trouble connecting to my brain right now. Try again in a moment.'})}\n\n"
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

        # Second call: give Ollama the results, get commentary
        messages.append(assistant_msg)
        messages.append({
            "role": "tool",
            "content": json.dumps(results),
            "name": "search_listings",
        })
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp2 = await client.post(ollama_url, json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                })
                resp2.raise_for_status()
                final_text = resp2.json().get("message", {}).get("content", "")
        except Exception as exc:
            log.warning("companion.ollama_followup_error", error=str(exc))
            final_text = ""
    else:
        final_text = assistant_msg.get("content", "")

    # Stream text in small chunks for typewriter effect
    chunk_size = 5
    for i in range(0, len(final_text), chunk_size):
        yield f"data: {json.dumps({'type': 'token', 'content': final_text[i:i+chunk_size]})}\n\n"
        await asyncio.sleep(0.01)

    yield f"data: {json.dumps({'type': 'done', 'model_used': f'ollama/{model}'})}\n\n"
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-backend
python -m pytest tests/test_companion_service.py -v
```
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-backend/app/services/companion_service.py \
        pc-flipper-backend/tests/test_companion_service.py
git commit -m "feat: add Hermes companion service with Ollama streaming and search tool"
```

---

## Task 3: Backend — companion.py endpoint

**Files:**
- Create: `pc-flipper-backend/app/api/companion.py`

- [ ] **Step 1: Create the endpoint**

Create `/home/mac/CODING/FlipFlop/pc-flipper-backend/app/api/companion.py`:

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.companion_service import stream_companion

router = APIRouter(prefix="/companion", tags=["companion"])


class CompanionMessage(BaseModel):
    role: str
    content: str


class CompanionRequest(BaseModel):
    message: str
    history: list[CompanionMessage] = []
    page_context: str = "general"


@router.post("/stream")
async def companion_stream(body: CompanionRequest, db: AsyncSession = Depends(get_db)):
    history = [{"role": m.role, "content": m.content} for m in body.history]
    return StreamingResponse(
        stream_companion(body.message, history, body.page_context, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: Register the router in main.py**

In `/home/mac/CODING/FlipFlop/pc-flipper-backend/app/main.py`, add to the imports:

```python
from app.api.companion import router as companion_router
```

And add after the existing `app.include_router(chat.router, prefix="/api")` line:

```python
app.include_router(companion_router, prefix="/api")
```

- [ ] **Step 3: Smoke test the endpoint**

```bash
cd /home/mac/CODING/FlipFlop
docker compose restart backend
sleep 8
curl -s -N -X POST http://localhost:4311/api/companion/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "history": [], "page_context": "listings"}' | head -5
```
Expected: SSE lines starting with `data: {"type": "token", ...}` or an error message token.

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-backend/app/api/companion.py pc-flipper-backend/app/main.py
git commit -m "feat: add /api/companion/stream SSE endpoint"
```

---

## Task 4: Frontend — HermesContext

**Files:**
- Create: `pc-flipper/components/hermes-context.tsx`

- [ ] **Step 1: Create the context**

Create `/home/mac/CODING/FlipFlop/pc-flipper/components/hermes-context.tsx`:

```tsx
"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export interface HermesMessage {
  role: "user" | "assistant";
  content: string;
  searchResults?: SearchResult[];
  isStreaming?: boolean;
}

export interface SearchResult {
  id: number;
  title: string;
  price: number;
  classification: string;
  score: number;
  source: string;
  url: string;
  gpu: string | null;
  cpu: string | null;
  ram_gb: number | null;
}

interface HermesContextValue {
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  messages: HermesMessage[];
  addUserMessage: (content: string) => void;
  appendToken: (token: string) => void;
  appendSearchResults: (results: SearchResult[]) => void;
  finaliseAssistantMessage: () => void;
  startAssistantMessage: () => void;
}

const HermesContext = createContext<HermesContextValue | null>(null);

export function HermesProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const [messages, setMessages] = useState<HermesMessage[]>([
    {
      role: "assistant",
      content: "Hey! I'm Hermes. I can search your catalogue, evaluate listings, or just chat. What do you need?",
    },
  ]);

  const addUserMessage = useCallback((content: string) => {
    setMessages(prev => [...prev, { role: "user", content }]);
  }, []);

  const startAssistantMessage = useCallback(() => {
    setMessages(prev => [...prev, { role: "assistant", content: "", isStreaming: true }]);
  }, []);

  const appendToken = useCallback((token: string) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && last.isStreaming) {
        return [...prev.slice(0, -1), { ...last, content: last.content + token }];
      }
      return prev;
    });
  }, []);

  const appendSearchResults = useCallback((results: SearchResult[]) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && last.isStreaming) {
        return [...prev.slice(0, -1), { ...last, searchResults: results }];
      }
      return prev;
    });
  }, []);

  const finaliseAssistantMessage = useCallback(() => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant") {
        return [...prev.slice(0, -1), { ...last, isStreaming: false }];
      }
      return prev;
    });
  }, []);

  return (
    <HermesContext.Provider value={{
      isOpen, setOpen, messages,
      addUserMessage, startAssistantMessage,
      appendToken, appendSearchResults, finaliseAssistantMessage,
    }}>
      {children}
    </HermesContext.Provider>
  );
}

export function useHermes() {
  const ctx = useContext(HermesContext);
  if (!ctx) throw new Error("useHermes must be used inside HermesProvider");
  return ctx;
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/components/hermes-context.tsx
git commit -m "feat: add HermesContext for persistent companion chat state"
```

---

## Task 5: Frontend — API streaming helper

**Files:**
- Modify: `pc-flipper/lib/api.ts`

- [ ] **Step 1: Add streamCompanion to api.ts**

Open `/home/mac/CODING/FlipFlop/pc-flipper/lib/api.ts` and append at the end of the file:

```typescript
// ── Hermes Companion ──────────────────────────────────────────────────────────

export interface CompanionMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CompanionSSEEvent {
  type: "token" | "search_results" | "done";
  content?: string;
  results?: import("@/components/hermes-context").SearchResult[];
  model_used?: string;
}

export async function streamCompanion(
  message: string,
  history: CompanionMessage[],
  pageContext: string,
  onEvent: (event: CompanionSSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(apiUrl("/companion/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, page_context: pageContext }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Companion stream failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event: CompanionSSEEvent = JSON.parse(line.slice(6));
          onEvent(event);
        } catch {
          // malformed line, skip
        }
      }
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/lib/api.ts
git commit -m "feat: add streamCompanion SSE helper to api.ts"
```

---

## Task 6: Frontend — HermesCompanion component

**Files:**
- Create: `pc-flipper/components/hermes-companion.tsx`

- [ ] **Step 1: Create the component**

Create `/home/mac/CODING/FlipFlop/pc-flipper/components/hermes-companion.tsx`:

```tsx
"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { X, Send, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useHermes, SearchResult } from "@/components/hermes-context";
import { streamCompanion } from "@/lib/api";

function classificationColour(cls: string) {
  switch (cls) {
    case "gem": return "text-emerald-400 bg-emerald-400/10 border-emerald-400/30";
    case "watch": return "text-yellow-400 bg-yellow-400/10 border-yellow-400/30";
    case "overpriced": return "text-red-400 bg-red-400/10 border-red-400/30";
    default: return "text-slate-400 bg-slate-400/10 border-slate-400/30";
  }
}

function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <a
      href={result.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-[#0d0f1a] border border-[#2a2d3e] rounded-lg p-2.5 hover:border-[#7c85ff]/50 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs text-slate-200 leading-snug line-clamp-2">{result.title}</span>
        <span className="text-sm font-bold text-emerald-400 whitespace-nowrap">£{result.price.toFixed(0)}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
        <span className={cn("text-[10px] px-1.5 py-0.5 rounded border font-medium uppercase", classificationColour(result.classification))}>
          {result.classification}
        </span>
        <span className="text-[10px] text-slate-500">{result.source}</span>
        {result.score > 0 && (
          <span className="text-[10px] text-amber-400">score {result.score.toFixed(0)}</span>
        )}
      </div>
    </a>
  );
}

function MessageBubble({ msg }: { msg: ReturnType<typeof useHermes>["messages"][number] }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex flex-col gap-1.5", isUser && "items-end")}>
      {msg.searchResults && msg.searchResults.length > 0 && (
        <div className="flex flex-col gap-1.5 w-full">
          {msg.searchResults.map(r => <SearchResultCard key={r.id} result={r} />)}
        </div>
      )}
      {(msg.content || msg.isStreaming) && (
        <div className={cn(
          "max-w-[90%] rounded-2xl px-3 py-2 text-xs leading-relaxed",
          isUser
            ? "bg-[#7c85ff]/20 border border-[#7c85ff]/30 text-slate-200 rounded-tr-sm"
            : "bg-[#1a1d2e] text-slate-200 rounded-tl-sm"
        )}>
          {msg.content}
          {msg.isStreaming && !msg.content && (
            <span className="inline-flex gap-0.5 ml-1">
              <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function HermesCompanion() {
  const { isOpen, setOpen, messages, addUserMessage, startAssistantMessage, appendToken, appendSearchResults, finaliseAssistantMessage } = useHermes();
  const pathname = usePathname();
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const pageContext = pathname?.split("/")[1] || "general";

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput("");
    setIsSending(true);

    addUserMessage(text);
    startAssistantMessage();

    const history = messages
      .filter(m => !m.isStreaming)
      .map(m => ({ role: m.role as "user" | "assistant", content: m.content }));

    abortRef.current = new AbortController();
    try {
      await streamCompanion(text, history, pageContext, (event) => {
        if (event.type === "token" && event.content) appendToken(event.content);
        if (event.type === "search_results" && event.results) appendSearchResults(event.results);
        if (event.type === "done") finaliseAssistantMessage();
      }, abortRef.current.signal);
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        appendToken("Something went wrong. Try again.");
        finaliseAssistantMessage();
      }
    } finally {
      setIsSending(false);
    }
  }, [input, isSending, messages, pageContext, addUserMessage, startAssistantMessage, appendToken, appendSearchResults, finaliseAssistantMessage]);

  return (
    <>
      {/* Chat panel */}
      {isOpen && (
        <div className="fixed bottom-24 right-5 z-50 w-[340px] flex flex-col bg-[#12151f] border border-[#2a2d3e] rounded-2xl shadow-2xl shadow-black/60 overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#1a1d2e] border-b border-[#2a2d3e]">
            <div className="relative w-8 h-8 rounded-full overflow-hidden border border-[#7c85ff]/40 flex-shrink-0">
              <Image src="/pics/hermes.gif" alt="Hermes" fill className="object-cover" unoptimized />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-100">Hermes</p>
              <p className="text-[10px] text-emerald-400">● online · gemma4:e4b</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="ml-auto text-slate-500 hover:text-slate-300 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex flex-col gap-3 p-3 overflow-y-auto max-h-[400px] min-h-[200px]">
            {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="flex items-center gap-2 p-2.5 border-t border-[#2a2d3e]">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }}
              placeholder="Ask anything..."
              disabled={isSending}
              className="flex-1 bg-[#1a1d2e] border border-[#2a2d3e] rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-[#7c85ff]/50 disabled:opacity-50"
            />
            <button
              onClick={() => void send()}
              disabled={isSending || !input.trim()}
              className="flex-shrink-0 w-8 h-8 bg-[#7c85ff] hover:bg-[#9099ff] disabled:opacity-40 disabled:cursor-not-allowed rounded-lg flex items-center justify-center transition-colors"
            >
              {isSending
                ? <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
                : <Send className="w-3.5 h-3.5 text-white" />}
            </button>
          </div>
        </div>
      )}

      {/* Floating GIF button */}
      <button
        onClick={() => setOpen(!isOpen)}
        className={cn(
          "fixed bottom-5 right-5 z-50 w-14 h-14 rounded-full overflow-hidden",
          "border-2 shadow-lg shadow-[#7c85ff]/20 transition-all duration-200",
          "hover:scale-110 hover:shadow-[#7c85ff]/40",
          isOpen ? "border-[#7c85ff] scale-105" : "border-[#7c85ff]/50"
        )}
        title="Chat with Hermes"
      >
        <Image src="/pics/hermes.gif" alt="Hermes" fill className="object-cover" unoptimized />
      </button>
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/components/hermes-companion.tsx
git commit -m "feat: add HermesCompanion floating chat widget component"
```

---

## Task 7: Mount in layout.tsx

**Files:**
- Modify: `pc-flipper/app/layout.tsx`

- [ ] **Step 1: Update layout.tsx**

Replace the contents of `/home/mac/CODING/FlipFlop/pc-flipper/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Rajdhani, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { BackendStatus } from "@/components/backend-status";
import { TraeBg } from "@/components/trae-bg";
import { TopCommandBar } from "@/components/top-command-bar";
import { FaviconAnimator } from "@/components/favicon-animator";
import { HermesProvider } from "@/components/hermes-context";
import { HermesCompanion } from "@/components/hermes-companion";

const rajdhani = Rajdhani({
  variable: "--font-rajdhani",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "FlipFlop",
  description: "AI-powered PC flipping intelligence platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${rajdhani.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="h-full node-body" suppressHydrationWarning>
        <FaviconAnimator />
        <TraeBg />
        <Sidebar />

        <div className="node-main-wrap">
          <TopCommandBar />
          <main className="node-content">
            <HermesProvider>
              {children}
              <HermesCompanion />
            </HermesProvider>
          </main>
        </div>

        <BackendStatus />
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Build the frontend to check for TypeScript errors**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
npm run build 2>&1 | tail -20
```
Expected: build completes without TypeScript errors. Fix any type errors before proceeding.

- [ ] **Step 3: Rebuild and restart frontend container**

```bash
cd /home/mac/CODING/FlipFlop
docker compose build --no-cache frontend 2>&1 | tail -5
docker compose up -d --no-build frontend
sleep 5
docker compose logs --tail=10 frontend
```
Expected: container starts, no crash.

- [ ] **Step 4: Manual smoke test**
  - Open `http://localhost:4310` in browser
  - Verify the Hermes GIF button appears bottom-right on every page
  - Click it — chat panel should open with the greeting message
  - Navigate to a different page — panel should stay open and messages should persist
  - Type "hello" and send — should get a response from Hermes
  - Type "find me RTX 3060 PCs under £200" — should show listing result cards

- [ ] **Step 5: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/app/layout.tsx
git commit -m "feat: mount HermesCompanion on all pages via root layout"
```

---

## Self-Review Checklist

- [x] **GIF asset** — Task 1 copies it to `public/pics/hermes.gif`, used in both button and panel header
- [x] **Backend service** — Task 2 covers `companion_service.py` with snapshot, search, and Ollama streaming
- [x] **SSE endpoint** — Task 3 covers `companion.py` + router registration in `main.py`
- [x] **React context** — Task 4 covers state persistence across navigation
- [x] **API helper** — Task 5 covers `streamCompanion()` in `api.ts`
- [x] **UI component** — Task 6 covers floating button + panel + search result cards
- [x] **Layout mount** — Task 7 wraps layout in `HermesProvider` and renders `HermesCompanion`
- [x] **No TBDs or placeholders** — all code blocks are complete
- [x] **Type consistency** — `SearchResult`, `HermesMessage`, `CompanionSSEEvent` defined in Task 4 and imported in Tasks 5 and 6
- [x] **Ollama model** — `get_settings().ollama_model` used (currently `gemma4:e4b` from config)
