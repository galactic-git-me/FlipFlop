# Manual Build Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/flips` inventory screen with a named, auto-saving PC build composer that lets users assemble components (from catalogue or manually), track cost paid, and request an LLM high/mid/low resale valuation with enhancement suggestions.

**Architecture:** New `manual_builds` DB table + FastAPI CRUD/evaluate endpoints in the backend; new Next.js page at `app/flips/page.tsx` with three sub-components (BuildRow, EntryModal, EvalPanel); auto-save via debounced PATCH calls; sidebar nav label updated.

**Tech Stack:** FastAPI + SQLAlchemy async (SQLite/Postgres), Pydantic v2, Next.js 14 App Router, React hooks, Tailwind CSS + existing FlipFlop CSS classes, existing `ai_service.chat()` for LLM calls.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pc-flipper-backend/app/models/manual_build.py` | Create | SQLAlchemy model for `manual_builds` table |
| `pc-flipper-backend/app/schemas/manual_build.py` | Create | Pydantic request/response schemas |
| `pc-flipper-backend/app/api/manual_builds.py` | Create | CRUD + evaluate endpoints |
| `pc-flipper-backend/app/models/__init__.py` | Modify | Register ManualBuild model |
| `pc-flipper-backend/app/main.py` | Modify | Mount manual_builds router |
| `pc-flipper/lib/api.ts` | Modify | Add ManualBuild types + API client methods |
| `pc-flipper/components/manual-build/BuildRow.tsx` | Create | Single filled/empty component slot row |
| `pc-flipper/components/manual-build/EntryModal.tsx` | Create | Two-tab modal (Catalogue / Manual) |
| `pc-flipper/components/manual-build/EvalPanel.tsx` | Create | Expandable evaluation results panel |
| `pc-flipper/app/flips/page.tsx` | Replace | Full Manual Build screen |
| `pc-flipper/components/sidebar.tsx` | Modify | Rename nav label "Inventory" → "Manual Build" |

---

## Task 1: Backend model

**Files:**
- Create: `pc-flipper-backend/app/models/manual_build.py`
- Modify: `pc-flipper-backend/app/models/__init__.py`

- [ ] **Step 1: Create the model file**

```python
# pc-flipper-backend/app/models/manual_build.py
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ManualBuild(Base):
    __tablename__ = "manual_builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), default="Untitled Build")
    components: Mapped[list] = mapped_column(JSON, default=list)
    total_cost: Mapped[float | None] = mapped_column(Float)
    last_evaluation: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ManualBuild {self.id} {self.name!r}>"
```

- [ ] **Step 2: Register model in `__init__.py`**

Add to `pc-flipper-backend/app/models/__init__.py`:

```python
from app.models.manual_build import ManualBuild
```

Add `"ManualBuild"` to the `__all__` list.

- [ ] **Step 3: Verify table is created**

Run the backend and check the DB creates the table:
```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-backend
docker compose restart backend 2>/dev/null || python -c "
import asyncio
from app.database import engine, Base
from app.models.manual_build import ManualBuild
async def go():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(go())
print('Table created OK')
"
```
Expected output: `Table created OK`

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-backend/app/models/manual_build.py pc-flipper-backend/app/models/__init__.py
git commit -m "feat: add ManualBuild SQLAlchemy model"
```

---

## Task 2: Backend schemas

**Files:**
- Create: `pc-flipper-backend/app/schemas/manual_build.py`

- [ ] **Step 1: Create schema file**

```python
# pc-flipper-backend/app/schemas/manual_build.py
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class BuildComponent(BaseModel):
    slot: str                        # "GPU", "CPU", "Base PC", etc.
    name: str
    price_paid: float
    source: str = "manual"           # "catalogue" | "manual"
    part_id: Optional[int] = None   # set when source == "catalogue"
    listing_url: Optional[str] = None
    image_url: Optional[str] = None


class ManualBuildCreate(BaseModel):
    name: str = "Untitled Build"


class ManualBuildPatch(BaseModel):
    name: Optional[str] = None
    components: Optional[list[BuildComponent]] = None


class EvaluationSuggestion(BaseModel):
    text: str
    uplift: float


class EvaluationResult(BaseModel):
    low: float
    mid: float
    high: float
    narrative: str
    suggestions: list[EvaluationSuggestion]


class ManualBuildOut(BaseModel):
    id: int
    name: str
    components: list[BuildComponent]
    total_cost: Optional[float]
    last_evaluation: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ManualBuildSummary(BaseModel):
    id: int
    name: str
    total_cost: Optional[float]
    component_count: int
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-backend/app/schemas/manual_build.py
git commit -m "feat: add ManualBuild Pydantic schemas"
```

---

## Task 3: Backend CRUD endpoints

**Files:**
- Create: `pc-flipper-backend/app/api/manual_builds.py`

- [ ] **Step 1: Create the router**

```python
# pc-flipper-backend/app/api/manual_builds.py
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.manual_build import ManualBuild
from app.schemas.manual_build import (
    ManualBuildCreate, ManualBuildPatch, ManualBuildOut, ManualBuildSummary
)

router = APIRouter(prefix="/manual-builds", tags=["manual-builds"])


@router.post("/", response_model=ManualBuildOut, status_code=201)
async def create_build(body: ManualBuildCreate, db: AsyncSession = Depends(get_db)):
    build = ManualBuild(name=body.name, components=[], total_cost=None)
    db.add(build)
    await db.flush()
    await db.refresh(build)
    return build


@router.get("/", response_model=list[ManualBuildSummary])
async def list_builds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManualBuild).order_by(ManualBuild.updated_at.desc())
    )
    builds = result.scalars().all()
    return [
        ManualBuildSummary(
            id=b.id,
            name=b.name,
            total_cost=b.total_cost,
            component_count=len(b.components or []),
            updated_at=b.updated_at,
        )
        for b in builds
    ]


@router.get("/{build_id}", response_model=ManualBuildOut)
async def get_build(build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    return build


@router.patch("/{build_id}", response_model=ManualBuildOut)
async def patch_build(build_id: int, body: ManualBuildPatch, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if body.name is not None:
        build.name = body.name
    if body.components is not None:
        build.components = [c.model_dump() for c in body.components]
        build.total_cost = sum(c.price_paid for c in body.components)
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.delete("/{build_id}", status_code=204)
async def delete_build(build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    await db.delete(build)
```

- [ ] **Step 2: Mount the router in `main.py`**

In `pc-flipper-backend/app/main.py`, add the import near the other API imports:
```python
from app.api.manual_builds import router as manual_builds_router
```

Then in the section where routers are registered (look for `app.include_router`):
```python
app.include_router(manual_builds_router)
```

- [ ] **Step 3: Smoke-test the endpoints**

Start the backend (or restart it), then:
```bash
# Create a build
curl -s -X POST http://localhost:8000/manual-builds/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Build"}' | python3 -m json.tool

# List builds
curl -s http://localhost:8000/manual-builds/ | python3 -m json.tool

# Patch it (use the id from the create response)
curl -s -X PATCH http://localhost:8000/manual-builds/1 \
  -H "Content-Type: application/json" \
  -d '{"components":[{"slot":"GPU","name":"RTX 3060","price_paid":170}]}' | python3 -m json.tool
```
Expected: valid JSON responses, no 422/500 errors.

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-backend/app/api/manual_builds.py pc-flipper-backend/app/main.py
git commit -m "feat: add manual builds CRUD API endpoints"
```

---

## Task 4: Backend evaluate endpoint

**Files:**
- Modify: `pc-flipper-backend/app/api/manual_builds.py`

- [ ] **Step 1: Add the evaluate endpoint**

Append to `pc-flipper-backend/app/api/manual_builds.py`:

```python
import re
from app.schemas.manual_build import EvaluationResult, EvaluationSuggestion
from app.services import ai_service


@router.post("/{build_id}/evaluate", response_model=EvaluationResult)
async def evaluate_build(build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.components:
        raise HTTPException(400, "Build has no components to evaluate")

    # Format component list for the prompt
    lines = []
    for c in build.components:
        name = c["name"] if isinstance(c, dict) else c.name
        slot = c["slot"] if isinstance(c, dict) else c.slot
        price = c["price_paid"] if isinstance(c, dict) else c.price_paid
        lines.append(f"  - {slot}: {name} (paid £{price:.0f})")
    component_text = "\n".join(lines)
    total = build.total_cost or sum(
        (c["price_paid"] if isinstance(c, dict) else c.price_paid)
        for c in build.components
    )

    prompt = f"""I have assembled a PC build for resale in the UK secondhand market. Here are the components and what I paid:

{component_text}

Total cost: £{total:.0f}

Please assess this build and respond with ONLY valid JSON (no markdown, no code fences) in this exact format:
{{
  "low": <number>,
  "mid": <number>,
  "high": <number>,
  "narrative": "<2-3 sentence assessment>",
  "suggestions": [
    {{"text": "<actionable suggestion>", "uplift": <number>}},
    {{"text": "<actionable suggestion>", "uplift": <number>}},
    {{"text": "<actionable suggestion>", "uplift": <number>}}
  ]
}}

low/mid/high = estimated resale prices in GBP. uplift = estimated price increase in GBP from that suggestion. Max 3 suggestions. Be realistic about UK eBay/Gumtree prices."""

    response_text, _model = await ai_service.chat(prompt, history=[])

    # Parse JSON from response — strip any accidental markdown fences
    raw = response_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON object from response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise HTTPException(502, f"LLM returned unparseable response: {raw[:200]}")
        data = json.loads(match.group())

    result = EvaluationResult(
        low=float(data.get("low", 0)),
        mid=float(data.get("mid", 0)),
        high=float(data.get("high", 0)),
        narrative=data.get("narrative", ""),
        suggestions=[
            EvaluationSuggestion(text=s["text"], uplift=float(s.get("uplift", 0)))
            for s in data.get("suggestions", [])[:3]
        ],
    )

    # Persist evaluation result back to the build
    build.last_evaluation = result.model_dump()
    build.updated_at = datetime.utcnow()
    await db.flush()

    return result
```

Also add `import json` and `import re` to the top of the file (they're used in the evaluate endpoint). The `ai_service` and schema imports are also needed — add them to the top of the file alongside the existing imports:

```python
import json
import re
from app.schemas.manual_build import (
    ManualBuildCreate, ManualBuildPatch, ManualBuildOut, ManualBuildSummary,
    EvaluationResult, EvaluationSuggestion,
)
from app.services import ai_service
```

- [ ] **Step 2: Test the evaluate endpoint**

First ensure you have an OpenRouter API key configured in Settings, then:
```bash
# Create a build with components
curl -s -X POST http://localhost:8000/manual-builds/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Eval Build"}' | python3 -m json.tool

# Patch with components (replace 1 with actual id)
curl -s -X PATCH http://localhost:8000/manual-builds/1 \
  -H "Content-Type: application/json" \
  -d '{"components":[{"slot":"Base PC","name":"Dell OptiPlex i7-8700","price_paid":85},{"slot":"GPU","name":"RTX 3060 12GB","price_paid":170}]}' | python3 -m json.tool

# Evaluate
curl -s -X POST http://localhost:8000/manual-builds/1/evaluate | python3 -m json.tool
```
Expected: JSON with `low`, `mid`, `high`, `narrative`, `suggestions`.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-backend/app/api/manual_builds.py
git commit -m "feat: add manual build LLM evaluation endpoint"
```

---

## Task 5: Frontend API types + client

**Files:**
- Modify: `pc-flipper/lib/api.ts`

- [ ] **Step 1: Add ManualBuild types**

In `pc-flipper/lib/api.ts`, add these interfaces alongside the other type definitions:

```typescript
export interface BuildComponent {
  slot: string;
  name: string;
  price_paid: number;
  source: "catalogue" | "manual";
  part_id?: number;
  listing_url?: string;
  image_url?: string;
}

export interface ManualBuild {
  id: number;
  name: string;
  components: BuildComponent[];
  total_cost: number | null;
  last_evaluation: ManualBuildEvaluation | null;
  created_at: string;
  updated_at: string;
}

export interface ManualBuildSummary {
  id: number;
  name: string;
  total_cost: number | null;
  component_count: number;
  updated_at: string;
}

export interface EvaluationSuggestion {
  text: string;
  uplift: number;
}

export interface ManualBuildEvaluation {
  low: number;
  mid: number;
  high: number;
  narrative: string;
  suggestions: EvaluationSuggestion[];
}
```

- [ ] **Step 2: Add API client methods**

In the `api` object in `pc-flipper/lib/api.ts`, add a `manualBuilds` section alongside the other sections (e.g. after `parts`):

```typescript
manualBuilds: {
  list: () => request<ManualBuildSummary[]>("/manual-builds/"),
  get: (id: number) => request<ManualBuild>(`/manual-builds/${id}`),
  create: (name: string) =>
    request<ManualBuild>("/manual-builds/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  patch: (id: number, data: { name?: string; components?: BuildComponent[] }) =>
    request<ManualBuild>(`/manual-builds/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  delete: (id: number) =>
    fetch(`${apiUrl}/manual-builds/${id}`, { method: "DELETE" }),
  evaluate: (id: number) =>
    request<ManualBuildEvaluation>(`/manual-builds/${id}/evaluate`, {
      method: "POST",
    }),
},
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/lib/api.ts
git commit -m "feat: add ManualBuild types and API client methods"
```

---

## Task 6: BuildRow component

**Files:**
- Create: `pc-flipper/components/manual-build/BuildRow.tsx`

- [ ] **Step 1: Create component directory and file**

```bash
mkdir -p /home/mac/CODING/FlipFlop/pc-flipper/components/manual-build
```

```tsx
// pc-flipper/components/manual-build/BuildRow.tsx
"use client";

import { X } from "lucide-react";
import { BuildComponent } from "@/lib/api";

const SLOT_COLOURS: Record<string, string> = {
  "Base PC": "#a855f7",
  CPU:       "#3b82f6",
  GPU:       "#22d3ee",
  RAM:       "#f59e0b",
  Storage:   "#10b981",
  PSU:       "#ef4444",
  Case:      "#6366f1",
  Motherboard: "#14b8a6",
  Cooling:   "#38bdf8",
};

function slotColour(slot: string): string {
  return SLOT_COLOURS[slot] ?? "#94a3b8";
}

interface FilledRowProps {
  component: BuildComponent;
  onPriceChange: (price: number) => void;
  onRemove: () => void;
}

function FilledRow({ component, onPriceChange, onRemove }: FilledRowProps) {
  const colour = slotColour(component.slot);
  return (
    <div
      className="flex items-center gap-3 rounded-md px-3 py-2 border"
      style={{ borderColor: colour + "55", background: "#0d1a2a" }}
    >
      <span
        className="text-xs font-mono uppercase min-w-[80px] font-semibold"
        style={{ color: colour }}
      >
        {component.slot}
      </span>
      <span className="flex-1 text-sm text-slate-200 truncate">{component.name}</span>
      {component.image_url && (
        <img
          src={component.image_url}
          alt=""
          className="w-8 h-8 rounded object-cover opacity-80"
        />
      )}
      <span className="text-xs text-slate-400 mr-1">£</span>
      <input
        type="number"
        value={component.price_paid}
        onChange={(e) => onPriceChange(parseFloat(e.target.value) || 0)}
        className="w-20 text-sm text-right bg-transparent border-b border-slate-600 focus:border-[#00dc82] outline-none text-[#00dc82] font-mono"
        min={0}
        step={0.01}
      />
      {component.listing_url && (
        <a
          href={component.listing_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] text-cyan-500 hover:text-cyan-300 ml-1"
        >
          ↗
        </a>
      )}
      <button
        onClick={onRemove}
        className="text-slate-500 hover:text-red-400 transition-colors ml-1"
        title="Remove"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

interface EmptyRowProps {
  slot: string;
  onClick: () => void;
}

function EmptyRow({ slot, onClick }: EmptyRowProps) {
  const colour = slotColour(slot);
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 rounded-md px-3 py-2 border border-dashed opacity-40 hover:opacity-70 transition-opacity text-left"
      style={{ borderColor: "#374151" }}
    >
      <span
        className="text-xs font-mono uppercase min-w-[80px] font-semibold"
        style={{ color: colour }}
      >
        {slot}
      </span>
      <span className="flex-1 text-xs text-slate-500">Click to add…</span>
    </button>
  );
}

export interface BuildRowProps {
  slot: string;
  component: BuildComponent | null;
  onAdd: (slot: string) => void;
  onPriceChange: (slot: string, price: number) => void;
  onRemove: (slot: string) => void;
}

export function BuildRow({ slot, component, onAdd, onPriceChange, onRemove }: BuildRowProps) {
  if (component) {
    return (
      <FilledRow
        component={component}
        onPriceChange={(price) => onPriceChange(slot, price)}
        onRemove={() => onRemove(slot)}
      />
    );
  }
  return <EmptyRow slot={slot} onClick={() => onAdd(slot)} />;
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/components/manual-build/BuildRow.tsx
git commit -m "feat: add BuildRow component for manual build slots"
```

---

## Task 7: EntryModal component

**Files:**
- Create: `pc-flipper/components/manual-build/EntryModal.tsx`

- [ ] **Step 1: Create the modal**

```tsx
// pc-flipper/components/manual-build/EntryModal.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Search } from "lucide-react";
import { BuildComponent } from "@/lib/api";

interface CatalogueResult {
  id: number;
  name: string;
  category: string;
  price: number | null;
  image_url: string | null;
  source_url: string | null;
  source_site: string | null;
}

interface EntryModalProps {
  slot: string;
  onConfirm: (component: BuildComponent) => void;
  onClose: () => void;
}

export function EntryModal({ slot, onConfirm, onClose }: EntryModalProps) {
  const [tab, setTab] = useState<"catalogue" | "manual">("catalogue");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CatalogueResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<CatalogueResult | null>(null);
  const [pricePaid, setPricePaid] = useState("");

  // Manual tab state
  const [manualName, setManualName] = useState("");
  const [manualPrice, setManualPrice] = useState("");

  const search = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); return; }
    setSearching(true);
    try {
      const res = await fetch(
        `/api/proxy?path=${encodeURIComponent(`/parts?search_name=${encodeURIComponent(q)}&limit=20`)}`
      ).catch(() => null);
      // Fall back to direct backend call
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/parts/?limit=50`;
      const r = await fetch(url);
      const all: CatalogueResult[] = await r.json();
      const lower = q.toLowerCase();
      setResults(all.filter(p => p.name.toLowerCase().includes(lower)).slice(0, 12));
    } catch {
      setResults([]);
    }
    setSearching(false);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => search(query), 300);
    return () => clearTimeout(t);
  }, [query, search]);

  function handleCatalogueConfirm() {
    if (!selected) return;
    onConfirm({
      slot,
      name: selected.name,
      price_paid: parseFloat(pricePaid) || selected.price || 0,
      source: "catalogue",
      part_id: selected.id,
      listing_url: selected.source_url ?? undefined,
      image_url: selected.image_url ?? undefined,
    });
  }

  function handleManualConfirm() {
    if (!manualName.trim()) return;
    onConfirm({
      slot,
      name: manualName.trim(),
      price_paid: parseFloat(manualPrice) || 0,
      source: "manual",
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="relative w-full max-w-md rounded-xl border border-slate-700 bg-[#0b1220] shadow-2xl p-0 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-slate-800">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wide">
            Add {slot}
          </h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-800">
          {(["catalogue", "manual"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-xs font-mono uppercase transition-colors ${
                tab === t
                  ? "text-[#00dc82] border-b-2 border-[#00dc82]"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {t === "catalogue" ? "From Catalogue" : "Enter Manually"}
            </button>
          ))}
        </div>

        <div className="p-4">
          {tab === "catalogue" ? (
            <div className="space-y-3">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-slate-500" />
                <input
                  autoFocus
                  type="text"
                  placeholder="Search parts catalogue…"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSelected(null); }}
                  className="w-full pl-8 pr-3 py-2 text-sm bg-[#0d1a2a] border border-slate-700 rounded-md text-slate-200 placeholder-slate-500 focus:border-[#00dc82] focus:outline-none"
                />
              </div>

              {searching && (
                <p className="text-xs text-slate-500 text-center py-2">Searching…</p>
              )}

              {!searching && results.length === 0 && query.length > 1 && (
                <p className="text-xs text-slate-500 text-center py-2">
                  No catalogue matches —{" "}
                  <button onClick={() => setTab("manual")} className="text-cyan-400 hover:underline">
                    enter manually instead
                  </button>
                </p>
              )}

              <div className="space-y-1 max-h-48 overflow-y-auto">
                {results.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => { setSelected(r); setPricePaid(String(r.price ?? "")); }}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors ${
                      selected?.id === r.id
                        ? "bg-[#00dc82]/10 border border-[#00dc82]/30"
                        : "hover:bg-slate-800 border border-transparent"
                    }`}
                  >
                    {r.image_url ? (
                      <img src={r.image_url} alt="" className="w-8 h-8 rounded object-cover" />
                    ) : (
                      <div className="w-8 h-8 rounded bg-slate-700" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-slate-200 truncate">{r.name}</p>
                      <p className="text-[10px] text-slate-500">{r.source_site} · {r.category}</p>
                    </div>
                    {r.price != null && (
                      <span className="text-xs text-[#00dc82] font-mono">£{r.price}</span>
                    )}
                  </button>
                ))}
              </div>

              {selected && (
                <div className="flex items-center gap-2 pt-2 border-t border-slate-800">
                  <span className="text-xs text-slate-400">Price paid £</span>
                  <input
                    type="number"
                    value={pricePaid}
                    onChange={(e) => setPricePaid(e.target.value)}
                    className="flex-1 px-2 py-1 text-sm bg-[#0d1a2a] border border-slate-700 rounded text-slate-200 focus:border-[#00dc82] focus:outline-none"
                    min={0}
                    step={0.01}
                    autoFocus
                  />
                  <button
                    onClick={handleCatalogueConfirm}
                    className="px-3 py-1 text-xs font-semibold bg-[#00dc82] text-[#04120d] rounded hover:bg-[#00b86d] transition-colors"
                  >
                    Add
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Component name</label>
                <input
                  autoFocus
                  type="text"
                  placeholder={`e.g. RTX 3060 12GB`}
                  value={manualName}
                  onChange={(e) => setManualName(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-[#0d1a2a] border border-slate-700 rounded-md text-slate-200 placeholder-slate-500 focus:border-[#00dc82] focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Price paid (£)</label>
                <input
                  type="number"
                  placeholder="0.00"
                  value={manualPrice}
                  onChange={(e) => setManualPrice(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-[#0d1a2a] border border-slate-700 rounded-md text-slate-200 placeholder-slate-500 focus:border-[#00dc82] focus:outline-none"
                  min={0}
                  step={0.01}
                />
              </div>
              <button
                onClick={handleManualConfirm}
                disabled={!manualName.trim()}
                className="w-full py-2 text-xs font-semibold bg-[#00dc82] text-[#04120d] rounded hover:bg-[#00b86d] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Add Component
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/components/manual-build/EntryModal.tsx
git commit -m "feat: add EntryModal component (catalogue + manual tabs)"
```

---

## Task 8: EvalPanel component

**Files:**
- Create: `pc-flipper/components/manual-build/EvalPanel.tsx`

- [ ] **Step 1: Create the panel**

```tsx
// pc-flipper/components/manual-build/EvalPanel.tsx
"use client";

import { ManualBuildEvaluation } from "@/lib/api";
import { Lightbulb, TrendingUp } from "lucide-react";

interface EvalPanelProps {
  evaluation: ManualBuildEvaluation;
  totalCost: number;
}

export function EvalPanel({ evaluation, totalCost }: EvalPanelProps) {
  const tiers: { label: string; price: number; colour: string }[] = [
    { label: "LOW",  price: evaluation.low,  colour: "#86efac" },
    { label: "MID",  price: evaluation.mid,  colour: "#00dc82" },
    { label: "HIGH", price: evaluation.high, colour: "#34d399" },
  ];

  return (
    <div className="border border-[#00dc82]/30 rounded-lg bg-[#021b12] p-4 space-y-4">
      {/* Price tiers */}
      <div>
        <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2 font-mono">
          🤖 AI Resale Assessment
        </p>
        <div className="grid grid-cols-3 gap-2">
          {tiers.map((t) => {
            const profit = t.price - totalCost;
            return (
              <div
                key={t.label}
                className="rounded-md bg-[#0a2010] border border-[#1a3a20] p-3 text-center"
              >
                <p className="text-[10px] font-mono uppercase text-slate-400 mb-1">{t.label}</p>
                <p className="text-xl font-bold font-mono" style={{ color: t.colour }}>
                  £{Math.round(t.price)}
                </p>
                <p
                  className="text-[10px] font-mono mt-0.5"
                  style={{ color: profit >= 0 ? "#4ade80" : "#f87171" }}
                >
                  {profit >= 0 ? "+" : ""}£{Math.round(profit)} profit
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Narrative */}
      {evaluation.narrative && (
        <p className="text-xs text-slate-400 leading-relaxed border-t border-slate-800 pt-3">
          {evaluation.narrative}
        </p>
      )}

      {/* Suggestions */}
      {evaluation.suggestions.length > 0 && (
        <div className="border-t border-slate-800 pt-3 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-slate-500 font-mono flex items-center gap-1">
            <Lightbulb className="w-3 h-3" /> Enhancement suggestions
          </p>
          {evaluation.suggestions.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
              <TrendingUp className="w-3 h-3 text-[#00dc82] mt-0.5 flex-shrink-0" />
              <span>{s.text}</span>
              {s.uplift > 0 && (
                <span className="ml-auto text-[#00dc82] font-mono text-[10px] whitespace-nowrap">
                  +£{s.uplift}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/components/manual-build/EvalPanel.tsx
git commit -m "feat: add EvalPanel component for LLM valuation results"
```

---

## Task 9: Manual Build main page

**Files:**
- Replace: `pc-flipper/app/flips/page.tsx`

- [ ] **Step 1: Replace the page**

```tsx
// pc-flipper/app/flips/page.tsx
"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Plus, ChevronDown, RotateCcw, Loader2 } from "lucide-react";
import { api, BuildComponent, ManualBuild, ManualBuildEvaluation } from "@/lib/api";
import { BuildRow } from "@/components/manual-build/BuildRow";
import { EntryModal } from "@/components/manual-build/EntryModal";
import { EvalPanel } from "@/components/manual-build/EvalPanel";

const DEFAULT_SLOTS = [
  "Base PC",
  "CPU",
  "GPU",
  "RAM",
  "Storage",
  "PSU",
  "Case",
  "Motherboard",
  "Cooling",
];

export default function ManualBuildPage() {
  // Build state
  const [build, setBuild] = useState<ManualBuild | null>(null);
  const [savedBuilds, setSavedBuilds] = useState<{ id: number; name: string; updated_at: string }[]>([]);
  const [customSlots, setCustomSlots] = useState<string[]>([]);
  const [loadingBuilds, setLoadingBuilds] = useState(true);
  const [showLoadDropdown, setShowLoadDropdown] = useState(false);

  // Save indicator
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Modal
  const [activeSlot, setActiveSlot] = useState<string | null>(null);

  // Evaluation
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState<ManualBuildEvaluation | null>(null);

  // Load saved builds list on mount
  useEffect(() => {
    api.manualBuilds.list().then((list) => {
      setSavedBuilds(list);
      setLoadingBuilds(false);
    }).catch(() => setLoadingBuilds(false));
  }, []);

  // Auto-save: debounced PATCH whenever build changes
  const autoSave = useCallback((updated: ManualBuild) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaveStatus("saving");
    saveTimer.current = setTimeout(async () => {
      try {
        await api.manualBuilds.patch(updated.id, {
          name: updated.name,
          components: updated.components,
        });
        setSaveStatus("saved");
        setTimeout(() => setSaveStatus("idle"), 1500);
      } catch {
        setSaveStatus("idle");
      }
    }, 400);
  }, []);

  async function createNewBuild() {
    const b = await api.manualBuilds.create("Untitled Build");
    setBuild(b);
    setEvalResult(null);
    setCustomSlots([]);
    setSavedBuilds((prev) => [
      { id: b.id, name: b.name, updated_at: b.updated_at },
      ...prev,
    ]);
  }

  async function loadBuild(id: number) {
    const b = await api.manualBuilds.get(id);
    setBuild(b);
    setEvalResult(b.last_evaluation ?? null);
    // Restore any custom slots from the loaded build
    const knownSlots = new Set(DEFAULT_SLOTS);
    const extras = b.components
      .map((c) => c.slot)
      .filter((s) => !knownSlots.has(s));
    setCustomSlots([...new Set(extras)]);
    setShowLoadDropdown(false);
  }

  function updateBuild(patch: Partial<ManualBuild>) {
    if (!build) return;
    const updated = { ...build, ...patch };
    setBuild(updated);
    autoSave(updated);
  }

  function handleNameChange(name: string) {
    updateBuild({ name });
  }

  function handleAddComponent(slot: string) {
    setActiveSlot(slot);
  }

  function handleComponentConfirmed(component: BuildComponent) {
    if (!build) return;
    const existing = build.components.filter((c) => c.slot !== component.slot);
    const newComponents = [...existing, component];
    updateBuild({ components: newComponents });
    setActiveSlot(null);
  }

  function handleRemoveComponent(slot: string) {
    if (!build) return;
    updateBuild({ components: build.components.filter((c) => c.slot !== slot) });
  }

  function handlePriceChange(slot: string, price: number) {
    if (!build) return;
    updateBuild({
      components: build.components.map((c) =>
        c.slot === slot ? { ...c, price_paid: price } : c
      ),
    });
  }

  function addCustomSlot() {
    const name = prompt("Custom slot name (e.g. Capture Card):");
    if (name?.trim()) setCustomSlots((prev) => [...prev, name.trim()]);
  }

  async function handleEvaluate() {
    if (!build) return;
    setEvaluating(true);
    try {
      const result = await api.manualBuilds.evaluate(build.id);
      setEvalResult(result);
    } catch (e) {
      alert("Evaluation failed — check AI backend is configured in Settings.");
    }
    setEvaluating(false);
  }

  const allSlots = [...DEFAULT_SLOTS, ...customSlots];
  const componentBySlot = Object.fromEntries(
    (build?.components ?? []).map((c) => [c.slot, c])
  );
  const totalCost = build?.components.reduce((s, c) => s + c.price_paid, 0) ?? 0;

  return (
    <div className="flex flex-col h-full min-h-0 p-6 gap-4 max-w-2xl mx-auto w-full">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={build?.name ?? ""}
          onChange={(e) => handleNameChange(e.target.value)}
          placeholder="Build name…"
          disabled={!build}
          className="flex-1 text-lg font-semibold bg-transparent border-b border-slate-700 focus:border-[#00dc82] outline-none text-slate-100 placeholder-slate-600 pb-0.5 disabled:opacity-30"
        />

        {saveStatus === "saving" && (
          <span className="text-[10px] text-slate-500 font-mono">saving…</span>
        )}
        {saveStatus === "saved" && (
          <span className="text-[10px] text-[#00dc82] font-mono">Saved ✓</span>
        )}

        {/* Load dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowLoadDropdown((v) => !v)}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs border border-slate-700 rounded-md text-slate-400 hover:border-slate-500 hover:text-slate-200 transition-colors"
          >
            Load <ChevronDown className="w-3 h-3" />
          </button>
          {showLoadDropdown && (
            <div className="absolute right-0 top-full mt-1 w-64 bg-[#0b1220] border border-slate-700 rounded-lg shadow-xl z-20 overflow-hidden">
              {savedBuilds.length === 0 ? (
                <p className="px-3 py-2 text-xs text-slate-500">No saved builds</p>
              ) : (
                savedBuilds.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => loadBuild(b.id)}
                    className="w-full px-3 py-2 text-left text-xs hover:bg-slate-800 transition-colors"
                  >
                    <span className="text-slate-200">{b.name}</span>
                    <span className="text-slate-500 ml-2">
                      {new Date(b.updated_at).toLocaleDateString()}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <button
          onClick={createNewBuild}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-[#00dc82] text-[#04120d] rounded-md font-semibold hover:bg-[#00b86d] transition-colors"
        >
          <Plus className="w-3 h-3" /> New Build
        </button>
      </div>

      {/* ── Empty state ── */}
      {!build && (
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-4 opacity-50">
          <p className="text-slate-400 text-sm">No build loaded. Create a new build or load an existing one.</p>
        </div>
      )}

      {/* ── Component list ── */}
      {build && (
        <div className="flex-1 flex flex-col gap-2 overflow-y-auto">
          {allSlots.map((slot) => (
            <BuildRow
              key={slot}
              slot={slot}
              component={componentBySlot[slot] ?? null}
              onAdd={handleAddComponent}
              onPriceChange={handlePriceChange}
              onRemove={handleRemoveComponent}
            />
          ))}

          {/* Add custom slot */}
          <button
            onClick={addCustomSlot}
            className="text-xs text-slate-600 hover:text-slate-400 text-left pl-1 pt-1 transition-colors"
          >
            + Add custom slot
          </button>
        </div>
      )}

      {/* ── Eval panel (shown after evaluation) ── */}
      {evalResult && build && (
        <EvalPanel evaluation={evalResult} totalCost={totalCost} />
      )}

      {/* ── Pinned footer ── */}
      {build && (
        <div className="flex items-center gap-4 border-t border-slate-800 pt-3">
          <span className="text-sm font-mono text-slate-400">
            Total paid:{" "}
            <span className="text-slate-100 font-semibold">£{totalCost.toFixed(0)}</span>
          </span>
          <div className="flex-1" />
          {evalResult && (
            <button
              onClick={handleEvaluate}
              disabled={evaluating || build.components.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-[#00dc82]/40 text-[#00dc82] rounded-md hover:bg-[#00dc82]/10 transition-colors disabled:opacity-40"
            >
              <RotateCcw className="w-3 h-3" /> Re-evaluate
            </button>
          )}
          {!evalResult && (
            <button
              onClick={handleEvaluate}
              disabled={evaluating || build.components.length === 0}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-semibold bg-[#00dc82] text-[#04120d] rounded-md hover:bg-[#00b86d] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {evaluating ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Evaluating…</>
              ) : (
                <>🤖 Evaluate Build →</>
              )}
            </button>
          )}
        </div>
      )}

      {/* ── Entry modal ── */}
      {activeSlot && (
        <EntryModal
          slot={activeSlot}
          onConfirm={handleComponentConfirmed}
          onClose={() => setActiveSlot(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

- [ ] **Step 3: Check the page renders**

Start the frontend dev server if not running:
```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
npm run dev &
```
Open http://localhost:3000/flips — should show the Manual Build screen with an empty state and "New Build" button.

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/app/flips/page.tsx
git commit -m "feat: replace inventory page with Manual Build screen"
```

---

## Task 10: Sidebar rename + final wire-up

**Files:**
- Modify: `pc-flipper/components/sidebar.tsx`

- [ ] **Step 1: Rename nav label**

In `pc-flipper/components/sidebar.tsx`, find the PRIMARY_NAV array entry for `/flips`:

```typescript
{ href: "/flips", icon: Boxes, label: "Inventory" },
```

Change it to:

```typescript
{ href: "/flips", icon: Boxes, label: "Manual Build" },
```

- [ ] **Step 2: Fix the catalogue search in EntryModal**

The `EntryModal` currently makes a direct fetch to `/parts/`. Update it to use the `api` client instead for consistency. In `pc-flipper/components/manual-build/EntryModal.tsx`, replace the `search` function:

```typescript
const search = useCallback(async (q: string) => {
  if (!q.trim()) { setResults([]); return; }
  setSearching(true);
  try {
    const all = await api.parts.list() as CatalogueResult[];
    const lower = q.toLowerCase();
    setResults(all.filter((p) => p.name.toLowerCase().includes(lower)).slice(0, 12));
  } catch {
    setResults([]);
  }
  setSearching(false);
}, []);
```

Also add `import { api } from "@/lib/api";` to the imports in `EntryModal.tsx` (it already imports types from `@/lib/api` — just add `api` to that import).

- [ ] **Step 3: Final TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

- [ ] **Step 4: End-to-end smoke test**

1. Open http://localhost:3000 — sidebar shows "Manual Build" instead of "Inventory"
2. Click "Manual Build" in nav → lands on `/flips`
3. Click "New Build" → build is created, name field appears
4. Click an empty slot (e.g. GPU) → entry modal opens with Catalogue tab
5. Type "RTX" in search → catalogue results appear
6. Select a result, set price paid, click Add → row fills in
7. Switch to Manual tab, add another component manually → row fills in
8. Edit price paid in-place → "saving…" / "Saved ✓" flash appears
9. With ≥1 component, click "Evaluate Build →" → evaluating spinner → EvalPanel appears with low/mid/high
10. Refresh page → load the build from dropdown → same components restored

- [ ] **Step 5: Final commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper/components/sidebar.tsx pc-flipper/components/manual-build/EntryModal.tsx
git commit -m "feat: rename nav to Manual Build; fix catalogue search in EntryModal"
```
