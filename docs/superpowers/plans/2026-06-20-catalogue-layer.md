# Catalogue Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a catalogue layer to FlipFlop that curates gem listings into a structured, customer-facing product catalogue — with playbook-aligned slots, auto-publish pipeline, admin review UI, and public API endpoints for the future customer website.

**Architecture:** Three new DB tables (`playbook_slots`, `catalogue_variants`, `case_catalogue`) extend the existing Listing/Playbook models. The existing hourly gem detection feeds an auto-publish service that creates variants for admin review. A new Catalogue section in the admin sidebar (4 sub-pages) + two new API routers (admin + public) complete the feature.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 async (backend), Next.js 14 / TypeScript (admin frontend), PostgreSQL.

**Spec:** `docs/superpowers/specs/2026-06-20-catalogue-layer-design.md`

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `pc-flipper-backend/app/models/catalogue.py` | PlaybookSlot, CatalogueVariant, CaseCatalogue ORM models |
| `pc-flipper-backend/app/schemas/catalogue.py` | Pydantic schemas for all three models |
| `pc-flipper-backend/app/services/catalogue_service.py` | Auto-publish, freshness, price-update, review-digest logic |
| `pc-flipper-backend/app/api/catalogue.py` | Admin API router (`/api/catalogue/…`) |
| `pc-flipper-backend/app/api/public_catalogue.py` | Public API router (`/api/public/…`, no auth) |
| `pc-flipper-backend/scripts/seed_catalogue_slots.py` | One-off script: seeds default PlaybookSlot rows from spec |
| `pc-flipper/app/catalogue/page.tsx` | Admin UI — Review Queue (sidebar landing page) |
| `pc-flipper/app/catalogue/variants/page.tsx` | Admin UI — Component Variants list |
| `pc-flipper/app/catalogue/cases/page.tsx` | Admin UI — Case Catalogue management |
| `pc-flipper/app/catalogue/slots/page.tsx` | Admin UI — Slot Configuration |
| `pc-flipper-backend/tests/test_catalogue_models.py` | Model schema smoke tests |
| `pc-flipper-backend/tests/test_catalogue_service.py` | Service unit tests (pure logic, no DB) |
| `pc-flipper-backend/tests/test_catalogue_api.py` | Admin API integration tests |
| `pc-flipper-backend/tests/test_public_catalogue_api.py` | Public API integration tests |

### Modified files
| File | Change |
|------|--------|
| `pc-flipper-backend/app/main.py` | Import + `include_router` for catalogue and public_catalogue |
| `pc-flipper-backend/app/workers/scheduler.py` | Add daily review digest job at 08:00 |
| `pc-flipper/components/sidebar.tsx` | Add Catalogue section with badge and 4 sub-links |

---

## Task 1: DB Models

**Files:**
- Create: `pc-flipper-backend/app/models/catalogue.py`
- Test: `pc-flipper-backend/tests/test_catalogue_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_catalogue_models.py
import pytest
from sqlalchemy import inspect
from app.models.catalogue import PlaybookSlot, CatalogueVariant, CaseCatalogue
from app.database import Base

def test_playbook_slot_tablename():
    assert PlaybookSlot.__tablename__ == "playbook_slots"

def test_catalogue_variant_tablename():
    assert CatalogueVariant.__tablename__ == "catalogue_variants"

def test_case_catalogue_tablename():
    assert CaseCatalogue.__tablename__ == "case_catalogue"

def test_playbook_slot_required_columns():
    cols = {c.key for c in inspect(PlaybookSlot).mapper.column_attrs}
    assert {"playbook_id", "slot_type", "is_customer_visible", "tier_names",
            "score_band_budget", "score_band_mid", "score_band_high"} <= cols

def test_catalogue_variant_required_columns():
    cols = {c.key for c in inspect(CatalogueVariant).mapper.column_attrs}
    assert {"listing_id", "slot_id", "status", "display_price", "tier",
            "consecutive_misses", "last_seen_at", "auto_published_at"} <= cols

def test_case_catalogue_required_columns():
    cols = {c.key for c in inspect(CaseCatalogue).mapper.column_attrs}
    assert {"name", "brand", "form_factor", "images", "rrp_gbp",
            "is_transparent_panel", "status"} <= cols
```

- [ ] **Step 2: Run test to verify it fails**

```
cd pc-flipper-backend
pytest tests/test_catalogue_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.models.catalogue'`

- [ ] **Step 3: Create the model file**

```python
# app/models/catalogue.py
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, Float, Integer, String, Text, JSON,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PlaybookSlot(Base):
    __tablename__ = "playbook_slots"
    __table_args__ = (
        UniqueConstraint("playbook_id", "slot_type", name="uq_playbook_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    playbook_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # cpu | gpu | ram | storage | cooling | os
    is_customer_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    tier_names: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"budget": "Budget", "mid": "Mid-Range", "high": "High End"}
    )
    score_band_budget: Mapped[list] = mapped_column(JSON, default=lambda: [40, 65])
    score_band_mid: Mapped[list] = mapped_column(JSON, default=lambda: [65, 80])
    score_band_high: Mapped[list] = mapped_column(JSON, default=lambda: [80, 100])
    created_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )


class CatalogueVariant(Base):
    __tablename__ = "catalogue_variants"
    __table_args__ = (
        Index("ix_catalogue_variants_slot_status", "slot_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("playbook_slots.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending_review", index=True)
    # pending_review | active | hidden | rejected
    display_price: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    # budget | mid | high
    consecutive_misses: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    auto_published_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    reviewed_at: Mapped[Optional[str]] = mapped_column(String(50))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reject_reason: Mapped[Optional[str]] = mapped_column(String(200))


class CaseCatalogue(Base):
    __tablename__ = "case_catalogue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    form_factor: Mapped[str] = mapped_column(String(10), nullable=False)
    # atx | matx | itx
    images: Mapped[list] = mapped_column(JSON, default=list)
    rrp_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    is_transparent_panel: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)
    # active | hidden
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
```

- [ ] **Step 4: Register model in `app/models/__init__.py`**

Open `pc-flipper-backend/app/models/__init__.py` and add:
```python
from app.models import catalogue as _catalogue  # noqa: F401
```
(follow the same pattern as other model imports already in that file)

- [ ] **Step 5: Run test to verify it passes**

```
pytest tests/test_catalogue_models.py -v
```
Expected: 6 PASSED

- [ ] **Step 6: Commit**

```bash
git add pc-flipper-backend/app/models/catalogue.py \
        pc-flipper-backend/app/models/__init__.py \
        pc-flipper-backend/tests/test_catalogue_models.py
git commit -m "feat(catalogue): add PlaybookSlot, CatalogueVariant, CaseCatalogue ORM models"
```

---

## Task 2: Pydantic Schemas

**Files:**
- Create: `pc-flipper-backend/app/schemas/catalogue.py`

No unit test needed — schemas are pure typing verified by the API tests in Task 4 and 5.

- [ ] **Step 1: Create schemas file**

```python
# app/schemas/catalogue.py
from typing import Optional
from pydantic import BaseModel


# ── PlaybookSlot ──────────────────────────────────────────────────────────────

class PlaybookSlotBase(BaseModel):
    slot_type: str
    is_customer_visible: bool = True
    tier_names: dict = {"budget": "Budget", "mid": "Mid-Range", "high": "High End"}
    score_band_budget: list[int] = [40, 65]
    score_band_mid: list[int] = [65, 80]
    score_band_high: list[int] = [80, 100]

class PlaybookSlotUpdate(BaseModel):
    is_customer_visible: Optional[bool] = None
    tier_names: Optional[dict] = None
    score_band_budget: Optional[list[int]] = None
    score_band_mid: Optional[list[int]] = None
    score_band_high: Optional[list[int]] = None

class PlaybookSlotOut(PlaybookSlotBase):
    id: int
    playbook_id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ── CatalogueVariant ──────────────────────────────────────────────────────────

class CatalogueVariantOut(BaseModel):
    id: int
    listing_id: int
    slot_id: int
    status: str
    display_price: float
    tier: str
    consecutive_misses: int
    last_seen_at: str
    auto_published_at: str
    reviewed_at: Optional[str]
    reviewed_by: Optional[str]
    reject_reason: Optional[str]

    class Config:
        from_attributes = True

class RejectBody(BaseModel):
    reason: str


# ── CaseCatalogue ─────────────────────────────────────────────────────────────

class CaseCatalogueCreate(BaseModel):
    name: str
    brand: str
    form_factor: str
    images: list[str] = []
    rrp_gbp: float
    is_transparent_panel: bool = True
    notes: Optional[str] = None

class CaseCatalogueUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    form_factor: Optional[str] = None
    images: Optional[list[str]] = None
    rrp_gbp: Optional[float] = None
    is_transparent_panel: Optional[bool] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class CaseCatalogueOut(BaseModel):
    id: int
    name: str
    brand: str
    form_factor: str
    images: list[str]
    rrp_gbp: float
    is_transparent_panel: bool
    status: str
    notes: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Commit**

```bash
git add pc-flipper-backend/app/schemas/catalogue.py
git commit -m "feat(catalogue): add Pydantic schemas for PlaybookSlot, CatalogueVariant, CaseCatalogue"
```

---

## Task 3: Catalogue Service

**Files:**
- Create: `pc-flipper-backend/app/services/catalogue_service.py`
- Test: `pc-flipper-backend/tests/test_catalogue_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_catalogue_service.py
import pytest
from app.services.catalogue_service import (
    compute_display_price,
    determine_tier,
    infer_slot_type,
)

# ── compute_display_price ─────────────────────────────────────────────────────

def test_display_price_rounds_up_to_five():
    # £164.35 * 1.15 = £189.00 → already on £5 boundary
    assert compute_display_price(164.35) == 190.0

def test_display_price_rounds_up_not_down():
    # £100 * 1.15 = £115 → £115
    assert compute_display_price(100.0) == 115.0

def test_display_price_partial_boundary():
    # £50 * 1.15 = £57.50 → rounds up to £60
    assert compute_display_price(50.0) == 60.0

def test_display_price_already_on_boundary():
    # £100 * 1.15 = £115.00 → stays £115
    assert compute_display_price(100.0) == 115.0

def test_display_price_small_amount():
    # £1 * 1.15 = £1.15 → rounds up to £5
    assert compute_display_price(1.0) == 5.0

# ── determine_tier ────────────────────────────────────────────────────────────

class _MockSlot:
    score_band_budget = [40, 65]
    score_band_mid = [65, 80]
    score_band_high = [80, 100]

def test_determine_tier_budget():
    assert determine_tier(45.0, _MockSlot()) == "budget"

def test_determine_tier_budget_boundary():
    assert determine_tier(40.0, _MockSlot()) == "budget"

def test_determine_tier_mid():
    assert determine_tier(65.0, _MockSlot()) == "mid"

def test_determine_tier_mid_upper():
    assert determine_tier(79.9, _MockSlot()) == "mid"

def test_determine_tier_high():
    assert determine_tier(80.0, _MockSlot()) == "high"

def test_determine_tier_perfect_score():
    assert determine_tier(100.0, _MockSlot()) == "high"

# ── infer_slot_type ───────────────────────────────────────────────────────────

def test_infer_slot_type_cpu():
    assert infer_slot_type("Intel Core i7-12700 cpu only") == "cpu"

def test_infer_slot_type_gpu():
    assert infer_slot_type("NVIDIA GeForce RTX 3060 Ti graphics card 8GB") == "gpu"

def test_infer_slot_type_ram():
    assert infer_slot_type("Corsair 32GB DDR4 RAM stick 3200MHz") == "ram"

def test_infer_slot_type_storage():
    assert infer_slot_type("Samsung 870 EVO 1TB SSD solid state drive") == "storage"

def test_infer_slot_type_unknown_returns_none():
    assert infer_slot_type("Complete Gaming PC i7 RTX 3060") is None

def test_infer_slot_type_psu_returns_none():
    # PSU is not a catalogue slot type
    assert infer_slot_type("Corsair 650W modular psu") is None
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_catalogue_service.py -v
```
Expected: `ImportError` — service file does not exist yet.

- [ ] **Step 3: Create the service file**

```python
# app/services/catalogue_service.py
"""
Catalogue layer service functions.

Called by:
  - Hourly scrape jobs (auto_publish_gems, check_freshness, update_prices)
  - Daily digest job (send_review_digest)
  - Admin API (approve_variant, reject_variant)
"""
from __future__ import annotations

import math
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import PlaybookSlot, CatalogueVariant, CaseCatalogue
from app.models.listing import Listing, Classification
from app.services.classifier import detect_component_category
from app.services.alerts import emit_alert

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# Maps classifier output to catalogue slot_type strings.
# "ssd" and "motherboard"/"psu"/"accessory" are excluded from catalogue slots.
_CATEGORY_TO_SLOT: dict[str, str] = {
    "cpu": "cpu",
    "gpu": "gpu",
    "ram": "ram",
    "ssd": "storage",
}

FRESH_WINDOW_HOURS = 2  # a listing is "seen this run" if last_seen_at is within this window


def compute_display_price(scrape_price: float) -> float:
    """Return scrape_price × 1.15 rounded up to the nearest £5."""
    return math.ceil(scrape_price * 1.15 / 5) * 5


def determine_tier(gem_score: float, slot: PlaybookSlot) -> str:
    """Return 'budget', 'mid', or 'high' based on gem_score and slot score bands."""
    if gem_score >= slot.score_band_high[0]:
        return "high"
    if gem_score >= slot.score_band_mid[0]:
        return "mid"
    return "budget"


def infer_slot_type(title: str) -> str | None:
    """
    Derive catalogue slot_type from listing title using the existing classifier.
    Returns None for complete PCs, PSUs, motherboards, accessories — anything
    that is not a catalogued component slot.
    """
    raw = detect_component_category(title)
    return _CATEGORY_TO_SLOT.get(raw) if raw else None


# ── Scrape-run steps ──────────────────────────────────────────────────────────

async def auto_publish_gems(db: AsyncSession) -> int:
    """
    Step A: For every active gem listing, create a pending_review CatalogueVariant
    for each matching PlaybookSlot if one doesn't already exist.

    Returns the number of new variants created.
    """
    gem_classifications = (Classification.gem.value, Classification.amazing_gem.value)
    result = await db.execute(
        select(Listing).where(
            Listing.classification.in_(gem_classifications),
            Listing.gem_score >= 40,
        )
    )
    gem_listings = result.scalars().all()

    slots_result = await db.execute(select(PlaybookSlot))
    all_slots = slots_result.scalars().all()

    # Build lookup: slot_type → list[PlaybookSlot]
    slots_by_type: dict[str, list[PlaybookSlot]] = {}
    for slot in all_slots:
        slots_by_type.setdefault(slot.slot_type, []).append(slot)

    # Fetch existing (listing_id, slot_id) pairs to avoid duplicates
    existing_result = await db.execute(
        select(CatalogueVariant.listing_id, CatalogueVariant.slot_id)
    )
    existing_pairs = {(r.listing_id, r.slot_id) for r in existing_result}

    created = 0
    now = datetime.utcnow().isoformat()

    for listing in gem_listings:
        slot_type = infer_slot_type(listing.title)
        if not slot_type:
            continue
        for slot in slots_by_type.get(slot_type, []):
            if (listing.id, slot.id) in existing_pairs:
                continue
            tier = determine_tier(listing.gem_score, slot)
            variant = CatalogueVariant(
                listing_id=listing.id,
                slot_id=slot.id,
                status="pending_review",
                display_price=compute_display_price(listing.price),
                tier=tier,
                consecutive_misses=0,
                last_seen_at=now,
                auto_published_at=now,
            )
            db.add(variant)
            existing_pairs.add((listing.id, slot.id))
            created += 1

    await db.commit()
    log.info("auto_publish_gems: created %d new variants", created)
    return created


async def check_freshness(db: AsyncSession) -> int:
    """
    Step B: Increment consecutive_misses for variants whose listing hasn't been
    seen recently. Hide variants that reach 2 misses. Reinstate hidden variants
    whose listing reappears within 24h.

    A listing is 'seen this run' if its last_seen_at is within the last FRESH_WINDOW_HOURS.

    Returns the number of variants hidden.
    """
    cutoff = datetime.utcnow() - timedelta(hours=FRESH_WINDOW_HOURS)
    cutoff_iso = cutoff.isoformat()
    reinstate_cutoff = datetime.utcnow() - timedelta(hours=24)
    reinstate_cutoff_iso = reinstate_cutoff.isoformat()

    # Load active and pending variants with their listings
    result = await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.status.in_(["active", "pending_review"]))
    )
    rows = result.all()

    hidden = 0
    now = datetime.utcnow().isoformat()

    for variant, listing in rows:
        last_seen = listing.last_seen_at.isoformat() if listing.last_seen_at else ""
        if last_seen >= cutoff_iso:
            # Listing was seen in this run
            variant.consecutive_misses = 0
            variant.last_seen_at = now
        else:
            variant.consecutive_misses += 1
            if variant.consecutive_misses >= 2:
                variant.status = "hidden"
                hidden += 1

    # Reinstate hidden variants whose listing reappeared within 24h
    hidden_result = await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.status == "hidden")
    )
    for variant, listing in hidden_result.all():
        last_seen = listing.last_seen_at.isoformat() if listing.last_seen_at else ""
        if last_seen >= reinstate_cutoff_iso and last_seen >= cutoff_iso:
            variant.status = "active"
            variant.consecutive_misses = 0
            variant.last_seen_at = now

    await db.commit()
    log.info("check_freshness: hid %d variants", hidden)
    return hidden


async def update_prices(db: AsyncSession) -> int:
    """
    Step C: Recalculate display_price for all active variants from current listing price.

    Returns the number of variants updated.
    """
    result = await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.status == "active")
    )
    rows = result.all()

    updated = 0
    for variant, listing in rows:
        new_price = compute_display_price(listing.price)
        if new_price != variant.display_price:
            variant.display_price = new_price
            updated += 1

    await db.commit()
    log.info("update_prices: updated %d variant prices", updated)
    return updated


async def send_review_digest(db: AsyncSession) -> None:
    """
    Step D: Emit an alert if any variants are pending review.
    Called once daily at 08:00 by the scheduler.
    """
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.status == "pending_review")
    )
    pending = result.scalars().all()
    count = len(pending)
    if count > 0:
        await emit_alert(
            code="CATALOGUE_REVIEW_PENDING",
            source="catalogue_service",
            message=f"Catalogue review: {count} new variants awaiting approval",
            severity="info",
        )
        log.info("send_review_digest: emitted alert for %d pending variants", count)


# ── Admin actions ─────────────────────────────────────────────────────────────

async def approve_variant(db: AsyncSession, variant_id: int, reviewed_by: str = "admin") -> CatalogueVariant | None:
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        return None
    variant.status = "active"
    variant.reviewed_at = datetime.utcnow().isoformat()
    variant.reviewed_by = reviewed_by
    variant.reject_reason = None
    await db.commit()
    await db.refresh(variant)
    return variant


async def reject_variant(
    db: AsyncSession, variant_id: int, reason: str, reviewed_by: str = "admin"
) -> CatalogueVariant | None:
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        return None
    variant.status = "rejected"
    variant.reviewed_at = datetime.utcnow().isoformat()
    variant.reviewed_by = reviewed_by
    variant.reject_reason = reason
    await db.commit()
    await db.refresh(variant)
    return variant


async def run_catalogue_pipeline(db: AsyncSession) -> dict:
    """Runs all four catalogue pipeline steps in sequence. Called by scheduler."""
    created = await auto_publish_gems(db)
    hidden = await check_freshness(db)
    updated = await update_prices(db)
    return {"variants_created": created, "variants_hidden": hidden, "prices_updated": updated}
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_catalogue_service.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add pc-flipper-backend/app/services/catalogue_service.py \
        pc-flipper-backend/tests/test_catalogue_service.py
git commit -m "feat(catalogue): add catalogue service — auto-publish, freshness, price-update, digest"
```

---

## Task 4: Admin API Router

**Files:**
- Create: `pc-flipper-backend/app/api/catalogue.py`
- Test: `pc-flipper-backend/tests/test_catalogue_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_catalogue_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app

client = TestClient(app)


def test_review_queue_returns_200():
    with patch("app.api.catalogue.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(all=lambda: []))
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        resp = client.get("/api/catalogue/review-queue")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_variants_returns_200():
    with patch("app.api.catalogue.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(all=lambda: []))
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        resp = client.get("/api/catalogue/variants")
    assert resp.status_code == 200


def test_cases_returns_200():
    with patch("app.api.catalogue.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        resp = client.get("/api/catalogue/cases")
    assert resp.status_code == 200


def test_approve_unknown_variant_returns_404():
    with patch("app.api.catalogue.approve_variant", new_callable=AsyncMock) as mock_approve:
        mock_approve.return_value = None
        resp = client.post("/api/catalogue/variants/99999/approve")
    assert resp.status_code == 404


def test_reject_unknown_variant_returns_404():
    with patch("app.api.catalogue.reject_variant", new_callable=AsyncMock) as mock_reject:
        mock_reject.return_value = None
        resp = client.post(
            "/api/catalogue/variants/99999/reject",
            json={"reason": "Price too high"}
        )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_catalogue_api.py -v
```
Expected: 404 (routes don't exist yet)

- [ ] **Step 3: Create the admin API router**

```python
# app/api/catalogue.py
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.schemas.catalogue import (
    CaseCatalogueCreate,
    CaseCatalogueOut,
    CaseCatalogueUpdate,
    CatalogueVariantOut,
    RejectBody,
)
from app.services.catalogue_service import approve_variant, reject_variant

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


# ── Review Queue ──────────────────────────────────────────────────────────────

@router.get("/review-queue")
async def get_review_queue(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
        .where(CatalogueVariant.status == "pending_review")
        .order_by(CatalogueVariant.auto_published_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": v.id,
            "listing_id": v.listing_id,
            "listing_title": l.title,
            "listing_price": l.price,
            "gem_score": l.gem_score,
            "slot_id": v.slot_id,
            "slot_type": s.slot_type,
            "playbook_id": s.playbook_id,
            "tier": v.tier,
            "display_price": v.display_price,
            "auto_published_at": v.auto_published_at,
        }
        for v, l, s in rows
    ]


@router.post("/variants/approve-all")
async def approve_all_variants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.status == "pending_review")
    )
    variants = result.scalars().all()
    now = datetime.utcnow().isoformat()
    for v in variants:
        v.status = "active"
        v.reviewed_at = now
        v.reviewed_by = "admin-bulk"
    await db.commit()
    return {"approved": len(variants)}


# ── Variant actions ───────────────────────────────────────────────────────────

@router.post("/variants/{variant_id}/approve")
async def approve_one(variant_id: int, db: AsyncSession = Depends(get_db)):
    variant = await approve_variant(db, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"id": variant.id, "status": variant.status}


@router.post("/variants/{variant_id}/reject")
async def reject_one(variant_id: int, body: RejectBody, db: AsyncSession = Depends(get_db)):
    variant = await reject_variant(db, variant_id, reason=body.reason)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"id": variant.id, "status": variant.status, "reject_reason": variant.reject_reason}


@router.get("/variants")
async def list_variants(
    status: Optional[str] = Query(None),
    playbook_id: Optional[int] = Query(None),
    slot_type: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
    )
    if status:
        q = q.where(CatalogueVariant.status == status)
    if playbook_id:
        q = q.where(PlaybookSlot.playbook_id == playbook_id)
    if slot_type:
        q = q.where(PlaybookSlot.slot_type == slot_type)
    if tier:
        q = q.where(CatalogueVariant.tier == tier)
    result = await db.execute(q.order_by(CatalogueVariant.auto_published_at.desc()))
    rows = result.all()
    return [
        {
            "id": v.id,
            "listing_id": v.listing_id,
            "listing_title": l.title,
            "slot_type": s.slot_type,
            "playbook_id": s.playbook_id,
            "status": v.status,
            "tier": v.tier,
            "display_price": v.display_price,
            "gem_score": l.gem_score,
            "consecutive_misses": v.consecutive_misses,
            "last_seen_at": v.last_seen_at,
            "auto_published_at": v.auto_published_at,
            "reviewed_at": v.reviewed_at,
            "reject_reason": v.reject_reason,
        }
        for v, l, s in rows
    ]


@router.patch("/variants/{variant_id}/toggle-status")
async def toggle_variant_status(variant_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    variant.status = "hidden" if variant.status == "active" else "active"
    await db.commit()
    return {"id": variant.id, "status": variant.status}


# ── Case Catalogue ────────────────────────────────────────────────────────────

@router.get("/cases", response_model=list[CaseCatalogueOut])
async def list_cases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CaseCatalogue).order_by(CaseCatalogue.brand, CaseCatalogue.name)
    )
    return result.scalars().all()


@router.post("/cases", response_model=CaseCatalogueOut, status_code=201)
async def create_case(body: CaseCatalogueCreate, db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow().isoformat()
    case = CaseCatalogue(**body.model_dump(), created_at=now, updated_at=now)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.patch("/cases/{case_id}", response_model=CaseCatalogueOut)
async def update_case(case_id: int, body: CaseCatalogueUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CaseCatalogue).where(CaseCatalogue.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    case.updated_at = datetime.utcnow().isoformat()
    await db.commit()
    await db.refresh(case)
    return case


# ── Slot Config ───────────────────────────────────────────────────────────────

@router.get("/slots")
async def list_slots(playbook_id: Optional[int] = Query(None), db: AsyncSession = Depends(get_db)):
    q = select(PlaybookSlot)
    if playbook_id:
        q = q.where(PlaybookSlot.playbook_id == playbook_id)
    result = await db.execute(q.order_by(PlaybookSlot.playbook_id, PlaybookSlot.slot_type))
    return [
        {
            "id": s.id,
            "playbook_id": s.playbook_id,
            "slot_type": s.slot_type,
            "is_customer_visible": s.is_customer_visible,
            "tier_names": s.tier_names,
            "score_band_budget": s.score_band_budget,
            "score_band_mid": s.score_band_mid,
            "score_band_high": s.score_band_high,
        }
        for s in result.scalars().all()
    ]


@router.patch("/slots/{slot_id}")
async def update_slot(slot_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlaybookSlot).where(PlaybookSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    allowed = {"is_customer_visible", "tier_names", "score_band_budget", "score_band_mid", "score_band_high"}
    for k, v in body.items():
        if k in allowed:
            setattr(slot, k, v)
    slot.updated_at = datetime.utcnow().isoformat()
    await db.commit()
    return {"id": slot.id, "slot_type": slot.slot_type, "updated": True}
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_catalogue_api.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add pc-flipper-backend/app/api/catalogue.py \
        pc-flipper-backend/tests/test_catalogue_api.py
git commit -m "feat(catalogue): admin API router — review queue, variant actions, cases, slot config"
```

---

## Task 5: Public API Router

**Files:**
- Create: `pc-flipper-backend/app/api/public_catalogue.py`
- Test: `pc-flipper-backend/tests/test_public_catalogue_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_public_catalogue_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app

client = TestClient(app)


def test_public_playbooks_returns_200():
    with patch("app.api.public_catalogue.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: []))
        )
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        resp = client.get("/api/public/playbooks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_public_cases_returns_200():
    with patch("app.api.public_catalogue.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: []))
        )
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        resp = client.get("/api/public/cases")
    assert resp.status_code == 200


def test_public_playbook_slots_unknown_returns_404():
    with patch("app.api.public_catalogue.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: None)
        )
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        resp = client.get("/api/public/playbooks/99999/slots")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_public_catalogue_api.py -v
```
Expected: 404 (routes don't exist)

- [ ] **Step 3: Create the public API router**

```python
# app/api/public_catalogue.py
"""
Public catalogue endpoints — no auth required. Rate limited by reverse proxy.
Consumed by the customer website (Subsystem 3).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.models.playbook import Playbook

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/playbooks")
async def public_list_playbooks(db: AsyncSession = Depends(get_db)):
    """Active playbooks with their slot definitions and tier_names."""
    result = await db.execute(
        select(Playbook).where(Playbook.status == "active")
    )
    playbooks = result.scalars().all()

    output = []
    for pb in playbooks:
        slots_result = await db.execute(
            select(PlaybookSlot).where(PlaybookSlot.playbook_id == pb.id)
        )
        slots = slots_result.scalars().all()
        output.append({
            "id": pb.id,
            "name": pb.name,
            "slots": [
                {
                    "id": s.id,
                    "slot_type": s.slot_type,
                    "is_customer_visible": s.is_customer_visible,
                    "tier_names": s.tier_names,
                }
                for s in slots
            ],
        })
    return output


@router.get("/playbooks/{playbook_id}/slots")
async def public_playbook_slots(playbook_id: int, db: AsyncSession = Depends(get_db)):
    """
    Customer-visible slots for a playbook, with active variants grouped by tier.
    Each variant exposes only display_price, title, and gem_score.
    """
    pb_result = await db.execute(
        select(Playbook).where(Playbook.id == playbook_id, Playbook.status == "active")
    )
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    slots_result = await db.execute(
        select(PlaybookSlot).where(
            PlaybookSlot.playbook_id == playbook_id,
            PlaybookSlot.is_customer_visible == True,  # noqa: E712
        )
    )
    slots = slots_result.scalars().all()

    output = []
    for slot in slots:
        variants_result = await db.execute(
            select(CatalogueVariant, Listing)
            .join(Listing, CatalogueVariant.listing_id == Listing.id)
            .where(
                CatalogueVariant.slot_id == slot.id,
                CatalogueVariant.status == "active",
            )
            .order_by(CatalogueVariant.display_price)
        )
        rows = variants_result.all()

        by_tier: dict[str, list] = {"budget": [], "mid": [], "high": []}
        for v, l in rows:
            by_tier[v.tier].append({
                "id": v.id,
                "title": l.title,
                "display_price": v.display_price,
                "gem_score": l.gem_score,
            })

        output.append({
            "slot_id": slot.id,
            "slot_type": slot.slot_type,
            "tier_names": slot.tier_names,
            "variants_by_tier": by_tier,
        })

    return output


@router.get("/cases")
async def public_list_cases(db: AsyncSession = Depends(get_db)):
    """Active cases only — images, form_factor, transparent panel flag."""
    result = await db.execute(
        select(CaseCatalogue)
        .where(CaseCatalogue.status == "active")
        .order_by(CaseCatalogue.brand, CaseCatalogue.name)
    )
    cases = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "brand": c.brand,
            "form_factor": c.form_factor,
            "images": c.images,
            "rrp_gbp": c.rrp_gbp,
            "is_transparent_panel": c.is_transparent_panel,
        }
        for c in cases
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_public_catalogue_api.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add pc-flipper-backend/app/api/public_catalogue.py \
        pc-flipper-backend/tests/test_public_catalogue_api.py
git commit -m "feat(catalogue): public API router — playbooks, slots+variants, cases (no auth)"
```

---

## Task 6: Wire into main.py and scheduler

**Files:**
- Modify: `pc-flipper-backend/app/main.py`
- Modify: `pc-flipper-backend/app/workers/scheduler.py`

- [ ] **Step 1: Register routers in main.py**

Open `pc-flipper-backend/app/main.py`. After the existing router imports (around line 35), add:
```python
from app.api.catalogue import router as catalogue_router
from app.api.public_catalogue import router as public_catalogue_router
```

Then after the existing `app.include_router(...)` calls (around line 435), add:
```python
app.include_router(catalogue_router, prefix="/api")
app.include_router(public_catalogue_router, prefix="/api")
```

- [ ] **Step 2: Add hourly catalogue pipeline to scheduler**

Open `pc-flipper-backend/app/workers/scheduler.py`.

Add to the imports at the top (with the other service imports):
```python
from app.services.catalogue_service import run_catalogue_pipeline, send_review_digest
```

Add to the `_job_history` dict (with the other keys):
```python
"catalogue_pipeline": deque(maxlen=50),
"catalogue_digest": deque(maxlen=50),
```

In the function that registers jobs (look for `scheduler.add_job` calls), add after the existing hourly jobs:
```python
scheduler.add_job(
    _wrap("catalogue_pipeline", _run_with_db(run_catalogue_pipeline)),
    IntervalTrigger(minutes=60),
    id="catalogue_pipeline",
    replace_existing=True,
)
scheduler.add_job(
    _wrap("catalogue_digest", _run_with_db(send_review_digest)),
    "cron",
    hour=8,
    minute=0,
    id="catalogue_digest",
    replace_existing=True,
)
```

Where `_run_with_db` is a helper that injects an AsyncSession. Check how other DB-dependent jobs are structured in `scheduler.py` and follow the same pattern. If there is no `_run_with_db` helper, add:

```python
from app.database import AsyncSessionLocal

def _run_with_db(fn):
    async def _inner(*args, **kwargs):
        async with AsyncSessionLocal() as db:
            return await fn(db, *args, **kwargs)
    return _inner
```

- [ ] **Step 3: Smoke test — start the server and check routes are registered**

```bash
cd pc-flipper-backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001 &
sleep 3
curl -s http://andromeda-ts:8001/api/catalogue/review-queue | head -c 200
curl -s http://andromeda-ts:8001/api/public/cases | head -c 200
kill %1
```
Expected: both return `[]` (empty list, no DB data yet)

- [ ] **Step 4: Commit**

```bash
git add pc-flipper-backend/app/main.py \
        pc-flipper-backend/app/workers/scheduler.py
git commit -m "feat(catalogue): wire catalogue and public routers into main.py; register pipeline + digest jobs in scheduler"
```

---

## Task 7: Seed Script

**Files:**
- Create: `pc-flipper-backend/scripts/seed_catalogue_slots.py`

- [ ] **Step 1: Create the seed script**

```python
#!/usr/bin/env python3
"""
Seed default PlaybookSlot rows for all active playbooks.

Run once after Task 6 is deployed:
    cd pc-flipper-backend
    python scripts/seed_catalogue_slots.py

Safe to re-run — uses upsert logic (insert if not exists).
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.playbook import Playbook
from app.models.catalogue import PlaybookSlot

# Slot visibility per playbook keyword.
# Matches on playbook.name (case-insensitive substring).
# Playbooks NOT matched here get the "generic" slot set.
PLAYBOOK_PROFILES = {
    "gaming": {
        "tier_names": {"budget": "Starter", "mid": "Battle-Ready", "high": "Beast Mode"},
        "visible": {"cpu", "gpu", "ram", "storage", "cooling", "os"},
    },
    "ai": {
        "tier_names": {"budget": "Foundation", "mid": "Accelerator", "high": "Powerhouse"},
        "visible": {"cpu", "gpu", "ram", "storage", "cooling", "os"},
    },
    "creative": {
        "tier_names": {"budget": "Essentials", "mid": "Professional", "high": "Elite"},
        "visible": {"cpu", "gpu", "ram", "storage", "cooling", "os"},
    },
    "build": {  # "Build Your Own"
        "tier_names": {"budget": "Budget", "mid": "Mid-Range", "high": "High End"},
        "visible": {"cpu", "gpu", "ram", "storage", "cooling", "os"},
    },
    "home": {
        "tier_names": {"budget": "Basic", "mid": "Balanced", "high": "Premium"},
        "visible": {"cpu", "ram", "storage", "os"},
    },
    "business": {
        "tier_names": {"budget": "Basic", "mid": "Balanced", "high": "Premium"},
        "visible": {"cpu", "ram", "storage", "os"},
    },
    "student": {
        "tier_names": {"budget": "Essential", "mid": "Capable", "high": "Top of Class"},
        "visible": {"cpu", "ram", "storage", "os"},
    },
}

ALL_SLOTS = ["cpu", "gpu", "ram", "storage", "cooling", "os"]

DEFAULT_SCORE_BANDS = {
    "score_band_budget": [40, 65],
    "score_band_mid": [65, 80],
    "score_band_high": [80, 100],
}


def get_profile(playbook_name: str) -> dict:
    name_lower = playbook_name.lower()
    for key, profile in PLAYBOOK_PROFILES.items():
        if key in name_lower:
            return profile
    return {
        "tier_names": {"budget": "Budget", "mid": "Mid-Range", "high": "High End"},
        "visible": {"cpu", "ram", "storage", "os"},
    }


async def seed():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Playbook).where(Playbook.status == "active"))
        playbooks = result.scalars().all()

        if not playbooks:
            print("No active playbooks found. Run the playbook seeder first.")
            return

        created = 0
        skipped = 0

        for pb in playbooks:
            profile = get_profile(pb.name)
            for slot_type in ALL_SLOTS:
                # Skip if already exists
                existing = await db.execute(
                    select(PlaybookSlot).where(
                        PlaybookSlot.playbook_id == pb.id,
                        PlaybookSlot.slot_type == slot_type,
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                slot = PlaybookSlot(
                    playbook_id=pb.id,
                    slot_type=slot_type,
                    is_customer_visible=(slot_type in profile["visible"]),
                    tier_names=profile["tier_names"],
                    **DEFAULT_SCORE_BANDS,
                )
                db.add(slot)
                created += 1
                print(f"  + {pb.name} / {slot_type} (visible={slot_type in profile['visible']})")

        await db.commit()
        print(f"\nDone. Created {created} slots, skipped {skipped} existing.")


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 2: Run the seed script against the live DB**

```bash
cd pc-flipper-backend
python scripts/seed_catalogue_slots.py
```
Expected output: lines like `+ Gaming Rig / cpu (visible=True)` for each playbook × slot combination. Final line: `Done. Created N slots, skipped 0 existing.`

- [ ] **Step 3: Verify via API**

```bash
curl -s http://andromeda-ts:8000/api/catalogue/slots | python3 -m json.tool | head -50
```
Expected: JSON array of slot objects.

- [ ] **Step 4: Commit**

```bash
git add pc-flipper-backend/scripts/seed_catalogue_slots.py
git commit -m "feat(catalogue): seed script for default PlaybookSlot rows per playbook"
```

---

## Task 8: Frontend — Review Queue Page

**Files:**
- Create: `pc-flipper/app/catalogue/page.tsx`

- [ ] **Step 1: Create the Review Queue page**

```tsx
// pc-flipper/app/catalogue/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import {
  CheckCircle, XCircle, AlertTriangle, Package, RefreshCw
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface QueueItem {
  id: number;
  listing_title: string;
  listing_price: number;
  gem_score: number;
  slot_type: string;
  playbook_id: number;
  tier: string;
  display_price: number;
  auto_published_at: string;
}

const REJECT_REASONS = [
  "Price too high",
  "Wrong category",
  "Duplicate",
  "Low quality listing",
  "Other",
];

const TIER_COLOURS: Record<string, string> = {
  budget: "text-sky-400",
  mid: "text-amber-400",
  high: "text-emerald-400",
};

export default function CatalogueReviewQueuePage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState(REJECT_REASONS[0]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.catalogue.reviewQueue();
      setItems(data as QueueItem[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const approve = async (id: number) => {
    setBusy(true);
    await api.catalogue.approve(id);
    setItems(prev => prev.filter(i => i.id !== id));
    setBusy(false);
  };

  const reject = async (id: number) => {
    setBusy(true);
    await api.catalogue.reject(id, rejectReason);
    setItems(prev => prev.filter(i => i.id !== id));
    setRejectingId(null);
    setBusy(false);
  };

  const approveAll = async () => {
    setBusy(true);
    await api.catalogue.approveAll();
    setItems([]);
    setBusy(false);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Review Queue</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {items.length} variant{items.length !== 1 ? "s" : ""} awaiting approval
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          {items.length > 0 && (
            <Button size="sm" onClick={approveAll} disabled={busy}>
              <CheckCircle className="w-3.5 h-3.5 mr-1.5" />
              Approve All ({items.length})
            </Button>
          )}
        </div>
      </div>

      {loading && (
        <div className="text-center py-12 text-muted-foreground text-sm">Loading…</div>
      )}

      {!loading && items.length === 0 && (
        <div className="text-center py-16">
          <Package className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground text-sm">No variants pending review</p>
        </div>
      )}

      <div className="space-y-2">
        {items.map(item => (
          <div
            key={item.id}
            className="border rounded-lg overflow-hidden bg-card"
          >
            <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-3 items-center px-4 py-3">
              <div>
                <p className="font-medium text-sm truncate">{item.listing_title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {item.slot_type.toUpperCase()} ·{" "}
                  <span className={TIER_COLOURS[item.tier] ?? ""}>
                    {item.tier}
                  </span>{" "}
                  · auto-published {new Date(item.auto_published_at).toLocaleDateString()}
                </p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-sm">£{item.display_price}</p>
                <p className="text-xs text-muted-foreground">display price</p>
              </div>
              <div className="text-center">
                <p className="font-bold text-emerald-400">{item.gem_score.toFixed(0)}</p>
                <p className="text-xs text-muted-foreground">gem score</p>
              </div>
              <Button
                size="sm"
                variant="destructive"
                disabled={busy}
                onClick={() => setRejectingId(rejectingId === item.id ? null : item.id)}
              >
                <XCircle className="w-3.5 h-3.5 mr-1" />
                Reject
              </Button>
              <Button
                size="sm"
                className="bg-emerald-500 hover:bg-emerald-600 text-black"
                disabled={busy}
                onClick={() => approve(item.id)}
              >
                <CheckCircle className="w-3.5 h-3.5 mr-1" />
                Approve
              </Button>
            </div>

            {rejectingId === item.id && (
              <div className="border-t px-4 py-3 bg-muted/30 flex items-center gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                <select
                  className="text-sm bg-background border rounded px-2 py-1"
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                >
                  {REJECT_REASONS.map(r => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={busy}
                  onClick={() => reject(item.id)}
                >
                  Confirm Reject
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setRejectingId(null)}
                >
                  Cancel
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add `catalogue` API methods to `pc-flipper/lib/api.ts`**

Open `pc-flipper/lib/api.ts`. After the last entry in the `api` object, add:

```typescript
  catalogue: {
    reviewQueue: () => request<unknown[]>("/catalogue/review-queue"),
    approve: (id: number) =>
      request<unknown>(`/catalogue/variants/${id}/approve`, { method: "POST" }),
    reject: (id: number, reason: string) =>
      request<unknown>(`/catalogue/variants/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    approveAll: () =>
      request<unknown>("/catalogue/variants/approve-all", { method: "POST" }),
    variants: (params?: Record<string, string>) =>
      request<unknown[]>(`/catalogue/variants${params ? "?" + new URLSearchParams(params) : ""}`),
    toggleVariantStatus: (id: number) =>
      request<unknown>(`/catalogue/variants/${id}/toggle-status`, { method: "PATCH" }),
    cases: () => request<unknown[]>("/catalogue/cases"),
    createCase: (data: Record<string, unknown>) =>
      request<unknown>("/catalogue/cases", { method: "POST", body: JSON.stringify(data) }),
    updateCase: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/catalogue/cases/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    slots: (playbookId?: number) =>
      request<unknown[]>(`/catalogue/slots${playbookId ? `?playbook_id=${playbookId}` : ""}`),
    updateSlot: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/catalogue/slots/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  },
```

- [ ] **Step 3: Commit**

```bash
git add pc-flipper/app/catalogue/page.tsx pc-flipper/lib/api.ts
git commit -m "feat(catalogue): Review Queue admin UI page + catalogue API client methods"
```

---

## Task 9: Frontend — Variants, Cases, and Slot Config Pages

**Files:**
- Create: `pc-flipper/app/catalogue/variants/page.tsx`
- Create: `pc-flipper/app/catalogue/cases/page.tsx`
- Create: `pc-flipper/app/catalogue/slots/page.tsx`

- [ ] **Step 1: Create Component Variants page**

```tsx
// pc-flipper/app/catalogue/variants/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface Variant {
  id: number;
  listing_title: string;
  slot_type: string;
  playbook_id: number;
  status: string;
  tier: string;
  display_price: number;
  gem_score: number;
  consecutive_misses: number;
  last_seen_at: string;
  reviewed_at: string | null;
  reject_reason: string | null;
}

const STATUS_COLOURS: Record<string, string> = {
  active: "text-emerald-400",
  pending_review: "text-amber-400",
  hidden: "text-muted-foreground",
  rejected: "text-red-400",
};

const ALL_STATUSES = ["", "active", "pending_review", "hidden", "rejected"];

export default function CatalogueVariantsPage() {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      const data = await api.catalogue.variants(params);
      setVariants(data as Variant[]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const toggle = async (v: Variant) => {
    setBusy(v.id);
    await api.catalogue.toggleVariantStatus(v.id);
    await load();
    setBusy(null);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Component Variants</h1>
        <div className="flex items-center gap-2">
          <select
            className="text-sm bg-background border rounded px-2 py-1.5"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            {ALL_STATUSES.map(s => (
              <option key={s} value={s}>{s || "All statuses"}</option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/30">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">Component</th>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">Slot</th>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">Status</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">Price</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">Score</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">Misses</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {variants.map(v => (
              <tr key={v.id} className="border-b last:border-0 hover:bg-muted/10">
                <td className="px-3 py-2.5 max-w-xs truncate">{v.listing_title}</td>
                <td className="px-3 py-2.5 uppercase text-xs font-mono">{v.slot_type}</td>
                <td className={`px-3 py-2.5 text-xs font-medium ${STATUS_COLOURS[v.status] ?? ""}`}>
                  {v.status}
                </td>
                <td className="px-3 py-2.5 text-right">£{v.display_price}</td>
                <td className="px-3 py-2.5 text-right text-emerald-400 font-bold">
                  {v.gem_score.toFixed(0)}
                </td>
                <td className={`px-3 py-2.5 text-right font-mono ${v.consecutive_misses >= 1 ? "text-amber-400" : ""}`}>
                  {v.consecutive_misses}
                </td>
                <td className="px-3 py-2.5 text-right">
                  {(v.status === "active" || v.status === "hidden") && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy === v.id}
                      onClick={() => toggle(v)}
                    >
                      {v.status === "active"
                        ? <EyeOff className="w-3.5 h-3.5" />
                        : <Eye className="w-3.5 h-3.5" />}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && variants.length === 0 && (
          <p className="text-center text-muted-foreground text-sm py-10">No variants found</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create Case Catalogue page**

```tsx
// pc-flipper/app/catalogue/cases/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, RefreshCw, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface CaseItem {
  id: number;
  name: string;
  brand: string;
  form_factor: string;
  images: string[];
  rrp_gbp: number;
  is_transparent_panel: boolean;
  status: string;
  notes: string | null;
}

const FORM_FACTORS = ["atx", "matx", "itx"];

export default function CaseCataloguePage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    name: "", brand: "", form_factor: "atx", rrp_gbp: 0,
    is_transparent_panel: true, notes: "", images: "",
  });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.catalogue.cases();
      setCases(data as CaseItem[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleStatus = async (c: CaseItem) => {
    await api.catalogue.updateCase(c.id, {
      status: c.status === "active" ? "hidden" : "active",
    });
    await load();
  };

  const submitAdd = async () => {
    setSaving(true);
    await api.catalogue.createCase({
      ...form,
      rrp_gbp: Number(form.rrp_gbp),
      images: form.images.split("\n").map(s => s.trim()).filter(Boolean),
    });
    setForm({ name: "", brand: "", form_factor: "atx", rrp_gbp: 0, is_transparent_panel: true, notes: "", images: "" });
    setShowAdd(false);
    await load();
    setSaving(false);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Case Catalogue</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={() => setShowAdd(!showAdd)}>
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Add Case
          </Button>
        </div>
      </div>

      {showAdd && (
        <div className="border rounded-lg p-4 mb-6 bg-card space-y-3">
          <h2 className="font-semibold text-sm">Add New Case</h2>
          <div className="grid grid-cols-2 gap-3">
            <input
              className="border rounded px-2 py-1.5 text-sm bg-background"
              placeholder="Case name (e.g. O11 Dynamic EVO)"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
            <input
              className="border rounded px-2 py-1.5 text-sm bg-background"
              placeholder="Brand (e.g. Lian Li)"
              value={form.brand}
              onChange={e => setForm(f => ({ ...f, brand: e.target.value }))}
            />
            <select
              className="border rounded px-2 py-1.5 text-sm bg-background"
              value={form.form_factor}
              onChange={e => setForm(f => ({ ...f, form_factor: e.target.value }))}
            >
              {FORM_FACTORS.map(ff => <option key={ff} value={ff}>{ff.toUpperCase()}</option>)}
            </select>
            <input
              type="number"
              className="border rounded px-2 py-1.5 text-sm bg-background"
              placeholder="RRP £"
              value={form.rrp_gbp || ""}
              onChange={e => setForm(f => ({ ...f, rrp_gbp: Number(e.target.value) }))}
            />
          </div>
          <textarea
            className="w-full border rounded px-2 py-1.5 text-sm bg-background"
            placeholder="Image URLs (one per line)"
            rows={3}
            value={form.images}
            onChange={e => setForm(f => ({ ...f, images: e.target.value }))}
          />
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_transparent_panel}
                onChange={e => setForm(f => ({ ...f, is_transparent_panel: e.target.checked }))}
              />
              Transparent panel
            </label>
            <input
              className="flex-1 border rounded px-2 py-1.5 text-sm bg-background"
              placeholder="Notes (optional)"
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={submitAdd} disabled={saving || !form.name || !form.brand}>
              {saving ? "Saving…" : "Add Case"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {cases.map(c => (
          <div key={c.id} className={`border rounded-lg p-3 bg-card ${c.status === "hidden" ? "opacity-50" : ""}`}>
            {c.images[0] && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={c.images[0]} alt={c.name} className="w-full h-32 object-contain mb-2 rounded" />
            )}
            <p className="font-semibold text-sm truncate">{c.name}</p>
            <p className="text-xs text-muted-foreground">{c.brand} · {c.form_factor.toUpperCase()}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              £{c.rrp_gbp} RRP · {c.is_transparent_panel ? "Glass panel" : "Solid panel"}
            </p>
            <Button
              size="sm"
              variant="ghost"
              className="mt-2 w-full"
              onClick={() => toggleStatus(c)}
            >
              {c.status === "active"
                ? <><EyeOff className="w-3 h-3 mr-1.5" />Hide</>
                : <><Eye className="w-3 h-3 mr-1.5" />Show</>}
            </Button>
          </div>
        ))}
      </div>

      {!loading && cases.length === 0 && (
        <p className="text-center text-muted-foreground text-sm py-12">
          No cases yet — add the first one above.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create Slot Configuration page**

```tsx
// pc-flipper/app/catalogue/slots/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface Slot {
  id: number;
  playbook_id: number;
  slot_type: string;
  is_customer_visible: boolean;
  tier_names: { budget: string; mid: string; high: string };
}

const SLOT_ORDER = ["cpu", "gpu", "ram", "storage", "cooling", "os"];

export default function SlotConfigPage() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [edits, setEdits] = useState<Record<number, Partial<Slot>>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.catalogue.slots();
      setSlots(data as Slot[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const patch = (id: number, changes: Partial<Slot>) => {
    setEdits(prev => ({ ...prev, [id]: { ...prev[id], ...changes } }));
  };

  const save = async (slot: Slot) => {
    setSaving(slot.id);
    const changes = edits[slot.id];
    if (changes) {
      await api.catalogue.updateSlot(slot.id, changes as Record<string, unknown>);
      setEdits(prev => { const next = { ...prev }; delete next[slot.id]; return next; });
      await load();
    }
    setSaving(null);
  };

  const grouped: Record<number, Slot[]> = {};
  for (const s of slots) {
    (grouped[s.playbook_id] ??= []).push(s);
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Slot Configuration</h1>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {Object.entries(grouped).map(([playbookId, pbSlots]) => {
        const ordered = SLOT_ORDER.map(st => pbSlots.find(s => s.slot_type === st)).filter(Boolean) as Slot[];
        return (
          <div key={playbookId} className="mb-6 border rounded-lg overflow-hidden">
            <div className="px-4 py-2 bg-muted/30 border-b text-sm font-semibold">
              Playbook #{playbookId}
            </div>
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr>
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">Slot</th>
                  <th className="text-center px-3 py-2 text-muted-foreground font-medium">Visible to customer</th>
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">Budget tier name</th>
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">Mid tier name</th>
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">High tier name</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {ordered.map(slot => {
                  const e = edits[slot.id] ?? {};
                  const visible = e.is_customer_visible ?? slot.is_customer_visible;
                  const names = { ...slot.tier_names, ...(e.tier_names ?? {}) };
                  const isDirty = !!edits[slot.id];
                  return (
                    <tr key={slot.id} className="border-b last:border-0 hover:bg-muted/10">
                      <td className="px-3 py-2 font-mono uppercase text-xs">{slot.slot_type}</td>
                      <td className="px-3 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={visible}
                          onChange={e => patch(slot.id, { is_customer_visible: e.target.checked })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className="border rounded px-2 py-0.5 text-xs bg-background w-full"
                          value={names.budget}
                          onChange={ev => patch(slot.id, { tier_names: { ...names, budget: ev.target.value } })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className="border rounded px-2 py-0.5 text-xs bg-background w-full"
                          value={names.mid}
                          onChange={ev => patch(slot.id, { tier_names: { ...names, mid: ev.target.value } })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className="border rounded px-2 py-0.5 text-xs bg-background w-full"
                          value={names.high}
                          onChange={ev => patch(slot.id, { tier_names: { ...names, high: ev.target.value } })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        {isDirty && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={saving === slot.id}
                            onClick={() => save(slot)}
                          >
                            <Save className="w-3 h-3" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}

      {!loading && Object.keys(grouped).length === 0 && (
        <p className="text-center text-muted-foreground text-sm py-12">
          No slots found. Run <code className="bg-muted px-1 rounded">seed_catalogue_slots.py</code> first.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add pc-flipper/app/catalogue/variants/page.tsx \
        pc-flipper/app/catalogue/cases/page.tsx \
        pc-flipper/app/catalogue/slots/page.tsx
git commit -m "feat(catalogue): Component Variants, Case Catalogue, and Slot Config admin pages"
```

---

## Task 10: Sidebar — Catalogue Section

**Files:**
- Modify: `pc-flipper/components/sidebar.tsx`

- [ ] **Step 1: Add imports to sidebar**

Open `pc-flipper/components/sidebar.tsx`. Add to the lucide-react import block:
```typescript
  Library,
```
(or whichever icon fits — `PackageCheck`, `Layers`, or `Library` all work)

- [ ] **Step 2: Add a CATALOGUE_NAV group after PRIMARY_NAV**

```typescript
const CATALOGUE_NAV = [
  { href: "/catalogue", label: "Review Queue" },
  { href: "/catalogue/variants", label: "Component Variants" },
  { href: "/catalogue/cases", label: "Cases" },
  { href: "/catalogue/slots", label: "Slot Config" },
];
```

- [ ] **Step 3: Add the Catalogue section to the sidebar JSX**

Inside the `<aside>` element, after the primary nav section, add:

```tsx
{/* Catalogue section */}
<div className="mt-4 px-3">
  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 px-1">
    Catalogue
  </p>
  {CATALOGUE_NAV.map(item => (
    <Link
      key={item.href}
      href={item.href}
      className={cn(
        "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
        pathname === item.href
          ? "bg-accent text-accent-foreground font-medium"
          : "text-muted-foreground hover:text-foreground hover:bg-muted"
      )}
    >
      {item.label}
      {item.href === "/catalogue" && pendingCount > 0 && (
        <span className="ml-auto text-xs bg-amber-400 text-black rounded-full px-1.5 py-0.5 font-bold">
          {pendingCount}
        </span>
      )}
    </Link>
  ))}
</div>
```

- [ ] **Step 4: Add pending count state to sidebar**

At the top of the `Sidebar` component function, add:
```typescript
const [pendingCount, setPendingCount] = useState(0);

useEffect(() => {
  fetch("/api/catalogue/review-queue")
    .then(r => r.json())
    .then((data: unknown[]) => setPendingCount(data.length))
    .catch(() => {});
}, []);
```

Add `useState` to the React import if not already present.

- [ ] **Step 5: Verify in browser**

Start the dev server:
```bash
cd pc-flipper
npm run dev
```
Navigate to `http://andromeda-ts:3000`. Confirm:
- "Catalogue" section appears in the sidebar with 4 links
- Clicking "Review Queue" renders the queue page
- Badge appears on Review Queue when pending variants exist

- [ ] **Step 6: Commit**

```bash
git add pc-flipper/components/sidebar.tsx
git commit -m "feat(catalogue): add Catalogue section to sidebar with pending badge"
```

---

## Self-Review Checklist

### Spec coverage
- [x] `playbook_slots` table — Task 1
- [x] `catalogue_variants` table — Task 1
- [x] `case_catalogue` table — Task 1
- [x] Auto-publish step (Step A) — Task 3
- [x] Freshness check (Step B) — Task 3
- [x] Price update (Step C) — Task 3
- [x] Review digest alert (Step D) — Task 3, Task 6
- [x] `GET /api/catalogue/review-queue` — Task 4
- [x] `POST /api/catalogue/variants/{id}/approve` — Task 4
- [x] `POST /api/catalogue/variants/{id}/reject` — Task 4
- [x] `POST /api/catalogue/variants/approve-all` — Task 4
- [x] `GET /api/catalogue/variants` (with filters) — Task 4
- [x] `GET /api/catalogue/cases` — Task 4
- [x] `POST /api/catalogue/cases` — Task 4
- [x] `PATCH /api/catalogue/cases/{id}` — Task 4
- [x] `GET /api/public/playbooks` — Task 5
- [x] `GET /api/public/playbooks/{id}/slots` — Task 5
- [x] `GET /api/public/cases` — Task 5
- [x] Hourly pipeline job in scheduler — Task 6
- [x] Daily digest job at 08:00 — Task 6
- [x] Seed script for default slot config — Task 7
- [x] Review Queue UI — Task 8
- [x] Component Variants UI — Task 9
- [x] Case Catalogue UI — Task 9
- [x] Slot Configuration UI — Task 9
- [x] Sidebar Catalogue section with badge — Task 10

### Notes for implementers
- **`app/models/__init__.py`**: confirm the existing pattern for registering new model files — some codebases use `from app.models import *`, others explicit imports
- **Scheduler `_run_with_db`**: check `scheduler.py` for whether a session-injection helper already exists before adding a new one — `run_price_refresh` and `run_benchmark_refresh` likely use the same pattern
- **Case column `is_transparent_panel`**: most modern cases have glass panels; default is `True`
- **Cooling and OS slots**: `detect_component_category` does not currently detect coolers or OS licences from listing titles. These slots will not auto-populate via the pipeline. They can be manually assigned via the admin API later, or the classifier extended. Document this limitation in a code comment in `catalogue_service.py`
- **`display_price` for £100 × 1.15 = £115**: verify test — £115 is already on a £5 boundary, so `ceil(115 / 5) * 5 = 115`. The test value in Task 3 is correct
