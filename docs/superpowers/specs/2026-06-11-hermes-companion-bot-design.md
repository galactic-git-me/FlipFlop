# Hermes Companion Bot — Design Spec
**Date:** 2026-06-11  
**Status:** Approved

## Overview

A persistent floating chat companion ("Hermes") visible on every page of the FlipFlop app. Powered by local Ollama `gemma4:e4b`. The bot can answer general questions, search the live listings catalogue, and is always aware of the current app state via context injection.

---

## UI / Frontend

### Floating Widget (all pages)
- Mounted in `pc-flipper/app/layout.tsx` so it persists across all page navigations
- **Collapsed state**: a 56×56px circular button at bottom-right showing `AI_1.gif` (copied from `on-the.trading` project to `public/pics/hermes.gif`). A small "Need help?" tooltip appears on hover.
- **Expanded state**: a 340px wide chat panel slides up from bottom-right, overlaying page content (does not push layout). The panel header shows `AI_1.gif` as avatar, name "Hermes", and model indicator ("gemma4:e4b · online").
- Panel has: scrollable message history, inline listing result cards, text input, send button.
- State (open/closed, message history) lives in a React context so it survives page navigation.

### Inline Search Result Cards
When Hermes returns search results, they render as compact listing cards inside the message bubble:
- Title, price, classification badge (GEM / WATCH / OK), source, score
- Clicking a card navigates to that listing's detail view

### Avatar GIF
Source: `/home/mac/CODING/on-the.trading/mac_client/public/images/AI_1.gif`  
Copy to: `pc-flipper/public/pics/hermes.gif`  
Used in: the circular button and panel header.

---

## Backend

### New endpoint: `POST /api/chat/companion`
Replaces the existing `/api/chat/` for companion use. Supports streaming via Server-Sent Events (SSE).

**Request body:**
```json
{
  "message": "string",
  "history": [{"role": "user|assistant", "content": "string"}],
  "page_context": "listings|flips|parts|settings|..."
}
```

**Response:** SSE stream with event types:
- `token` — streamed text chunk from Ollama
- `search_results` — JSON array of listing results when a search tool call fires
- `done` — end of response with `model_used`

### Context Injection (system prompt)
On each request the backend builds a context snapshot injected as a hidden system message prefix:

```
You are Hermes, companion AI for the FlipFlop PC flipping platform.
Current catalogue snapshot (as of <timestamp>):
- Total listings: N | Gems: N | Watching: N
- Top gems: [title £price, ...]
- Last scan: <time ago>
- Active flips: N | Total profit tracked: £N

You have access to a search_listings tool. When the user asks to find, search, or show listings, call it.
```

Context is fetched fresh on each request (single DB query, < 5ms).

### `search_listings` Tool
The bot can trigger a catalogue search mid-conversation. The backend detects intent from the model's output (keyword pattern match or structured tool call JSON), runs the query, and injects results back into the stream.

**Parameters:** `query` (free text), `max_price` (optional), `min_score` (optional), `gpu` (optional), `classification` (optional: gem/watch/ok)

**Implementation:** Since Ollama's `gemma4:e4b` supports tool/function calling via the Ollama API `tools` field, the backend passes the tool schema to Ollama. When the model emits a tool call, the backend executes `search_listings()` against the DB and sends results back as a `search_results` SSE event, then resumes generation with the results appended.

---

## Data Flow

```
User types message
  → Frontend sends POST /api/chat/companion (with page_context)
  → Backend builds context snapshot + appends to system prompt
  → Sends to Ollama gemma4:e4b with search_listings tool schema
  → Ollama streams tokens  →  frontend renders incrementally
  → If Ollama emits tool_call(search_listings, args):
      → Backend queries DB
      → Sends search_results SSE event  →  frontend renders cards
      → Backend sends results back to Ollama  →  Ollama continues
  → done event sent
```

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `pc-flipper/public/pics/hermes.gif` | Copy AI_1.gif here |
| `pc-flipper/components/hermes-companion.tsx` | Floating widget + chat panel component |
| `pc-flipper/components/hermes-context.tsx` | React context for chat state (persists across navigation) |
| `pc-flipper/app/layout.tsx` | Mount `<HermesCompanion />` |
| `pc-flipper/lib/api.ts` | Add `companionChat()` streaming API call |
| `pc-flipper-backend/app/api/companion.py` | New SSE endpoint |
| `pc-flipper-backend/app/services/companion_service.py` | Ollama streaming + tool dispatch |
| `pc-flipper-backend/app/main.py` | Register companion router |

---

## Context Refresh Strategy

Context is re-fetched on every message (cheap snapshot query). No separate event listener needed — the bot always has fresh data on each turn.

---

## Error Handling

- If Ollama is down: respond with "I'm having trouble connecting to my brain right now. Try again in a moment." — no fallback to OpenRouter (keep it simple for the companion).
- If search returns 0 results: Hermes says so naturally ("Nothing in the catalogue matches that right now").
- Network errors: shown inline in the chat panel, non-blocking.
