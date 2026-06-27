# Inventory Allocation & Profit Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the inventory system to link inventory items to flips (builds) and calculate per-flip profit down to the penny.

**Architecture:** 
- Split InventoryItem's `actual_cost` into separate `base_price`, `shipping_cost`, and `discount_amount` fields for transparency
- Create a new `InventoryAllocation` model that links quantities of inventory items to specific flips
- Add profit calculation that sums landed costs of allocated inventory and compares against actual sale price minus platform fees
- Frontend shows which inventory is assigned to which flip and displays profit per flip

**Tech Stack:** SQLAlchemy ORM, FastAPI, React/TypeScript, Tailwind CSS

---

## File Structure

**Backend files to create:**
- `app/models/inventory_allocation.py` — Links InventoryItem quantities to Flip
- `app/schemas/inventory_allocation.py` — Pydantic schemas for allocation requests/responses
- `tests/test_inventory_allocation.py` — Tests for allocation and profit calculation logic

**Backend files to modify:**
- `app/models/inventory.py` — Add base_price, shipping_cost, discount_amount fields (actual_cost becomes calculated)
- `app/schemas/inventory.py` — Update schemas for new fields, add allocation info
- `app/api/inventory.py` — Add allocation CRUD endpoints, profit calculation endpoint
- `app/main.py` — Register new routes if needed

**Frontend files to modify:**
- `app/inventory/page.tsx` — Add flip assignment dropdown, show profit per flip, allocation table
- `lib/api.ts` — Add inventory allocation API methods

---

## Task Breakdown

### Task 1: Update InventoryItem Model — Split Costs

**Files:**
- Modify: `app/models/inventory.py`
- Modify: `alembic/versions/` (we'll generate migration after)

**Rationale:** Currently `actual_cost` lumps everything together. We need granularity: base price, shipping, discount. The total landed cost (actual_cost) becomes calculated.

- [ ] **Step 1: Update the InventoryItem model**

Open `app/models/inventory.py` and update the model:

```python
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_name: Mapped[str] = mapped_column(String(300))
    component_type: Mapped[str] = mapped_column(String(50))  # gpu, cpu, ram, ssd, psu, motherboard, cooler
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    
    # Cost breakdown — allows tracking shipping, discounts separately
    base_price: Mapped[float] = mapped_column(Float)  # Price before shipping/discount
    shipping_cost: Mapped[float] = mapped_column(Float, default=0.0)  # Shipping per unit
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Discount per unit (positive = discount applied)
    
    purchase_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str | None] = mapped_column(String(100))  # eBay, Amazon, local, auction, etc.
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def actual_cost(self) -> float:
        """Calculated landed cost per unit: base + shipping - discount"""
        return self.base_price + self.shipping_cost - self.discount_amount
    
    @property
    def total_landed_cost(self) -> float:
        """Total cost for all units: actual_cost * quantity"""
        return self.actual_cost * self.quantity

    def __repr__(self):
        return f"<InventoryItem {self.component_name} x{self.quantity} £{self.actual_cost:.2f}>"
```

- [ ] **Step 2: Create database migration**

Run alembic to auto-generate the migration:

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-backend
source .venv/bin/activate
alembic revision --autogenerate -m "refactor: split inventory actual_cost into base_price, shipping_cost, discount_amount"
```

Expected: New file created in `alembic/versions/` with migration logic.

- [ ] **Step 3: Review migration**

The migration file should add three columns and make them non-nullable. Edit it to handle the data migration — we'll map existing `actual_cost` to `base_price` and set shipping/discount to 0:

Open the generated file and find the `upgrade()` function. It should look something like:

```python
def upgrade() -> None:
    op.add_column('inventory', sa.Column('base_price', sa.Float(), nullable=False, server_default='0'))
    op.add_column('inventory', sa.Column('shipping_cost', sa.Float(), nullable=False, server_default='0'))
    op.add_column('inventory', sa.Column('discount_amount', sa.Float(), nullable=False, server_default='0'))
    
    # Migrate existing data: actual_cost → base_price, others to 0
    op.execute("UPDATE inventory SET base_price = actual_cost, shipping_cost = 0, discount_amount = 0")
```

- [ ] **Step 4: Run migration**

```bash
alembic upgrade head
```

Expected: Migration applies successfully. Verify with:

```bash
docker exec flipflop-db psql -U flipper -d pcflipper -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='inventory' ORDER BY ordinal_position;"
```

Should show: id, component_name, component_type, quantity, base_price, shipping_cost, discount_amount, purchase_date, source, notes, created_at, updated_at.

- [ ] **Step 5: Commit**

```bash
git add app/models/inventory.py alembic/versions/
git commit -m "refactor: split inventory actual_cost into base_price, shipping_cost, discount_amount for cost transparency"
```

---

### Task 2: Update InventoryItem Schemas

**Files:**
- Modify: `app/schemas/inventory.py`

- [ ] **Step 1: Update schemas to reflect new fields**

Open `app/schemas/inventory.py` and replace with:

```python
from datetime import datetime
from pydantic import BaseModel


class InventoryItemIn(BaseModel):
    """Request schema for creating/updating inventory items"""
    component_name: str
    component_type: str
    quantity: int = 1
    base_price: float
    shipping_cost: float = 0.0
    discount_amount: float = 0.0
    purchase_date: str  # ISO format "2026-06-20"
    source: str | None = None
    notes: str | None = None


class InventoryItemOut(BaseModel):
    """Response schema for inventory items"""
    id: int
    component_name: str
    component_type: str
    quantity: int
    base_price: float
    shipping_cost: float
    discount_amount: float
    actual_cost: float  # Calculated: base + shipping - discount
    total_landed_cost: float  # Calculated: actual_cost * quantity
    purchase_date: datetime
    source: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Verify schema tests (if they exist)**

Check if there are existing schema tests:

```bash
find /home/mac/CODING/FlipFlop/pc-flipper-backend/tests -name "*inventory*" -type f
```

If tests exist, update them to use the new field names. If none exist, we'll add tests in a later task.

- [ ] **Step 3: Commit**

```bash
git add app/schemas/inventory.py
git commit -m "refactor: update inventory schemas to include base_price, shipping_cost, discount_amount"
```

---

### Task 3: Create InventoryAllocation Model

**Files:**
- Create: `app/models/inventory_allocation.py`

**Rationale:** Links quantities of inventory items to flips. Allows tracking which inventory was used to build which PC and calculate profit.

- [ ] **Step 1: Create the InventoryAllocation model**

Create file `/app/models/inventory_allocation.py`:

```python
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class InventoryAllocation(Base):
    __tablename__ = "inventory_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Foreign keys
    inventory_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventory.id"), index=True)
    flip_id: Mapped[int] = mapped_column(Integer, ForeignKey("flips.id"), index=True)
    
    # How many units of this inventory item are allocated to this flip
    quantity_allocated: Mapped[int] = mapped_column(Integer, default=1)
    
    # Snapshot of cost at time of allocation (in case prices change later)
    cost_per_unit_at_allocation: Mapped[float] = mapped_column(Float)  # actual_cost at allocation time
    
    # Metadata
    notes: Mapped[str | None] = mapped_column(String(500))  # e.g., "Primary graphics card"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    inventory_item = relationship("InventoryItem")
    flip = relationship("Flip")

    @property
    def total_allocated_cost(self) -> float:
        """Total cost for this allocation: cost_per_unit * quantity_allocated"""
        return self.cost_per_unit_at_allocation * self.quantity_allocated

    def __repr__(self):
        return f"<InventoryAllocation flip_id={self.flip_id} item_id={self.inventory_item_id} qty={self.quantity_allocated} £{self.total_allocated_cost:.2f}>"
```

- [ ] **Step 2: Register model in app/models/__init__.py**

Open `app/models/__init__.py` and verify InventoryAllocation is imported. Add if missing:

```python
from app.models.inventory_allocation import InventoryAllocation
```

(Check what's already in the file and follow the existing pattern)

- [ ] **Step 3: Create migration**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-backend
alembic revision --autogenerate -m "feat: create inventory_allocations table to link inventory to flips"
```

- [ ] **Step 4: Run migration**

```bash
alembic upgrade head
```

Verify:

```bash
docker exec flipflop-db psql -U flipper -d pcflipper -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='inventory_allocations' ORDER BY ordinal_position;"
```

- [ ] **Step 5: Commit**

```bash
git add app/models/inventory_allocation.py alembic/versions/
git commit -m "feat: add InventoryAllocation model to link inventory items to flips"
```

---

### Task 4: Create InventoryAllocation Schemas

**Files:**
- Create: `app/schemas/inventory_allocation.py`

- [ ] **Step 1: Create schemas**

Create `/app/schemas/inventory_allocation.py`:

```python
from datetime import datetime
from pydantic import BaseModel


class InventoryAllocationIn(BaseModel):
    """Request schema for creating/updating allocations"""
    inventory_item_id: int
    flip_id: int
    quantity_allocated: int
    notes: str | None = None


class InventoryAllocationOut(BaseModel):
    """Response schema for allocations"""
    id: int
    inventory_item_id: int
    flip_id: int
    quantity_allocated: int
    cost_per_unit_at_allocation: float
    total_allocated_cost: float  # Calculated
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InventoryAllocationWithDetails(InventoryAllocationOut):
    """Allocation with nested inventory and flip details"""
    inventory_item: dict  # Will populate from relationship
    flip: dict  # Will populate from relationship
```

- [ ] **Step 2: Commit**

```bash
git add app/schemas/inventory_allocation.py
git commit -m "feat: add InventoryAllocation request/response schemas"
```

---

### Task 5: Add Allocation CRUD Endpoints

**Files:**
- Create: `app/api/inventory_allocations.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create inventory_allocations API router**

Create `/app/api/inventory_allocations.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
from app.models.flip import Flip
from app.schemas.inventory_allocation import (
    InventoryAllocationIn,
    InventoryAllocationOut,
    InventoryAllocationWithDetails,
)

router = APIRouter(tags=["inventory-allocations"])


@router.post("/inventory-allocations/", response_model=InventoryAllocationOut)
async def create_allocation(
    data: InventoryAllocationIn,
    db: AsyncSession = Depends(get_db),
):
    """Create new allocation of inventory item to flip"""
    # Verify inventory item exists
    item = await db.get(InventoryItem, data.inventory_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    # Verify flip exists
    flip = await db.get(Flip, data.flip_id)
    if not flip:
        raise HTTPException(status_code=404, detail="Flip not found")
    
    # Verify quantity doesn't exceed available
    result = await db.execute(
        select(InventoryAllocation).where(
            InventoryAllocation.inventory_item_id == data.inventory_item_id,
            InventoryAllocation.flip_id == data.flip_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Allocation already exists for this item and flip")
    
    # Create allocation
    allocation = InventoryAllocation(
        inventory_item_id=data.inventory_item_id,
        flip_id=data.flip_id,
        quantity_allocated=data.quantity_allocated,
        cost_per_unit_at_allocation=item.actual_cost,
        notes=data.notes,
    )
    db.add(allocation)
    await db.commit()
    await db.refresh(allocation)
    return allocation


@router.get("/inventory-allocations/", response_model=list[InventoryAllocationOut])
async def list_allocations(flip_id: int | None = None, db: AsyncSession = Depends(get_db)):
    """List all allocations, optionally filtered by flip_id"""
    query = select(InventoryAllocation)
    if flip_id:
        query = query.where(InventoryAllocation.flip_id == flip_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/inventory-allocations/{allocation_id}", response_model=InventoryAllocationOut)
async def get_allocation(allocation_id: int, db: AsyncSession = Depends(get_db)):
    """Get single allocation by ID"""
    allocation = await db.get(InventoryAllocation, allocation_id)
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found")
    return allocation


@router.patch("/inventory-allocations/{allocation_id}", response_model=InventoryAllocationOut)
async def update_allocation(
    allocation_id: int,
    data: InventoryAllocationIn,
    db: AsyncSession = Depends(get_db),
):
    """Update allocation (quantity or notes)"""
    allocation = await db.get(InventoryAllocation, allocation_id)
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found")
    
    # Update fields
    allocation.quantity_allocated = data.quantity_allocated
    if data.notes is not None:
        allocation.notes = data.notes
    
    await db.commit()
    await db.refresh(allocation)
    return allocation


@router.delete("/inventory-allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_allocation(allocation_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an allocation (unassign inventory from flip)"""
    allocation = await db.get(InventoryAllocation, allocation_id)
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found")
    
    await db.delete(allocation)
    await db.commit()
```

- [ ] **Step 2: Register router in main.py**

Open `app/main.py`, find the imports section where other routers are imported (around line 20), and add:

```python
from app.api import inventory_allocations
```

Then find the `include_router` section (around line 420-450), and add:

```python
app.include_router(inventory_allocations.router, prefix="/api")
```

- [ ] **Step 3: Test endpoints with curl**

Rebuild backend:

```bash
docker compose up -d --build backend && sleep 10
```

Test creating an allocation:

```bash
curl -s -X POST http://localhost:4311/api/inventory-allocations/ \
  -H "Content-Type: application/json" \
  -d '{
    "inventory_item_id": 1,
    "flip_id": 1,
    "quantity_allocated": 1,
    "notes": "Primary GPU for gaming build"
  }' | jq .
```

Expected: Returns the created allocation with id, cost_per_unit_at_allocation, etc.

- [ ] **Step 4: Commit**

```bash
git add app/api/inventory_allocations.py app/main.py
git commit -m "feat: add inventory allocation CRUD endpoints"
```

---

### Task 6: Add Profit Calculation Endpoint

**Files:**
- Modify: `app/api/inventory_allocations.py`

- [ ] **Step 1: Add profit calculation to inventory_allocations.py**

Add this new endpoint at the end of the file:

```python
from sqlalchemy import func


@router.get("/flips/{flip_id}/profit-breakdown", response_model=dict)
async def get_flip_profit_breakdown(flip_id: int, db: AsyncSession = Depends(get_db)):
    """Calculate detailed profit breakdown for a flip"""
    # Get flip
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(status_code=404, detail="Flip not found")
    
    # Get all allocations for this flip
    result = await db.execute(
        select(InventoryAllocation).where(InventoryAllocation.flip_id == flip_id)
    )
    allocations = result.scalars().all()
    
    # Calculate total landed cost
    total_landed_cost = sum(a.total_allocated_cost for a in allocations)
    
    # Get sale price and fees
    sale_price = flip.actual_sale_price or 0.0
    selling_fee = flip.actual_selling_fee or 0.0
    
    # Calculate profit: (sale_price - fees) - landed_costs
    net_proceeds = sale_price - selling_fee
    profit = net_proceeds - total_landed_cost
    profit_margin_pct = (profit / sale_price * 100) if sale_price > 0 else 0.0
    
    return {
        "flip_id": flip_id,
        "sale_price": sale_price,
        "selling_fee": selling_fee,
        "net_proceeds": net_proceeds,
        "total_landed_cost": total_landed_cost,
        "profit": profit,
        "profit_margin_pct": profit_margin_pct,
        "allocations": [
            {
                "inventory_item_id": a.inventory_item_id,
                "quantity": a.quantity_allocated,
                "cost_per_unit": a.cost_per_unit_at_allocation,
                "total_cost": a.total_allocated_cost,
            }
            for a in allocations
        ],
    }
```

- [ ] **Step 2: Test profit calculation**

Create a test flip and allocation, then call the endpoint:

```bash
# Assuming flip_id=1 exists with sale price £800 and fee £100
curl -s http://localhost:4311/api/flips/1/profit-breakdown | jq .
```

Expected output (example):
```json
{
  "flip_id": 1,
  "sale_price": 800.0,
  "selling_fee": 100.0,
  "net_proceeds": 700.0,
  "total_landed_cost": 465.0,
  "profit": 235.0,
  "profit_margin_pct": 29.375,
  "allocations": [...]
}
```

- [ ] **Step 3: Commit**

```bash
git add app/api/inventory_allocations.py
git commit -m "feat: add flip profit breakdown calculation endpoint"
```

---

### Task 7: Update Inventory API to Return Allocation Info

**Files:**
- Modify: `app/api/inventory.py`

**Rationale:** When listing inventory items, we should show which flip(s) they're allocated to.

- [ ] **Step 1: Update the list endpoint**

Open `app/api/inventory.py`. Find the list endpoint (`GET /inventory/`) and update it to include allocation info. Replace the entire route with:

```python
@router.get("/inventory/", response_model=list[dict])
async def list_inventory(component_type: str | None = None, db: AsyncSession = Depends(get_db)):
    """List all inventory items with allocation info"""
    query = select(InventoryItem)
    if component_type:
        query = query.where(InventoryItem.component_type == component_type)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    response = []
    for item in items:
        # Get allocations for this item
        alloc_result = await db.execute(
            select(InventoryAllocation).where(InventoryAllocation.inventory_item_id == item.id)
        )
        allocations = alloc_result.scalars().all()
        
        # Calculate total allocated quantity
        total_allocated = sum(a.quantity_allocated for a in allocations)
        
        response.append({
            "id": item.id,
            "component_name": item.component_name,
            "component_type": item.component_type,
            "quantity": item.quantity,
            "quantity_unallocated": item.quantity - total_allocated,
            "base_price": item.base_price,
            "shipping_cost": item.shipping_cost,
            "discount_amount": item.discount_amount,
            "actual_cost": item.actual_cost,
            "total_landed_cost": item.total_landed_cost,
            "purchase_date": item.purchase_date,
            "source": item.source,
            "notes": item.notes,
            "created_at": item.created_at,
            "allocations": [
                {
                    "allocation_id": a.id,
                    "flip_id": a.flip_id,
                    "quantity_allocated": a.quantity_allocated,
                }
                for a in allocations
            ],
        })
    
    return response
```

Also add the import at the top:

```python
from app.models.inventory_allocation import InventoryAllocation
```

- [ ] **Step 2: Test updated endpoint**

```bash
curl -s http://localhost:4311/api/inventory/ | jq '.[] | {component_name, quantity, quantity_unallocated, allocations}'
```

Expected: Shows quantity_unallocated and allocations array.

- [ ] **Step 3: Commit**

```bash
git add app/api/inventory.py
git commit -m "feat: update inventory list endpoint to show allocation info"
```

---

### Task 8: Update Frontend Inventory Page — Add Flip Assignment UI

**Files:**
- Modify: `app/inventory/page.tsx`

- [ ] **Step 1: Add flip selection to the form**

Open `app/inventory/page.tsx`. Find the form section (around line 180) and add a flip selection dropdown before the submit button. Add this after the notes textarea:

```tsx
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Assign to Build (Optional)</label>
              <select
                value={selectedFlipId}
                onChange={e => setSelectedFlipId(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
              >
                <option value="">Unassigned</option>
                {flips.map(flip => (
                  <option key={flip.id} value={flip.id}>
                    Flip #{flip.id} - {flip.name || 'Untitled'}
                  </option>
                ))}
              </select>
            </div>
```

- [ ] **Step 2: Add state for flips and selected flip**

Add to the state section (after the form state):

```tsx
  const [flips, setFlips] = useState<Array<{ id: number; name?: string }>>([]);
  const [selectedFlipId, setSelectedFlipId] = useState<number | null>(null);
```

- [ ] **Step 3: Load flips on mount**

Add useEffect to load flips:

```tsx
  useEffect(() => {
    fetch("/api/flips")
      .then(r => r.json())
      .then(data => setFlips(data))
      .catch(() => setFlips([]));
  }, []);
```

- [ ] **Step 4: Update table to show allocation**

Find the table body (line ~320) and add an allocation column. Change the table header to add:

```tsx
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Assigned To</th>
```

And in the table body row, add after the Source column:

```tsx
                  <td className="px-4 py-3 text-slate-400">
                    {item.allocations && item.allocations.length > 0
                      ? `Flip #${item.allocations[0].flip_id}`
                      : <span className="text-slate-600">Unassigned</span>
                    }
                  </td>
```

- [ ] **Step 5: Rebuild frontend and test**

```bash
docker compose up -d --build frontend && sleep 10
```

Navigate to http://localhost:4310/inventory and verify:
- Form shows "Assign to Build" dropdown
- Table shows "Assigned To" column
- Can see allocations if items are assigned

- [ ] **Step 6: Commit**

```bash
git add app/inventory/page.tsx
git commit -m "feat: add flip assignment UI to inventory page"
```

---

### Task 9: Add Flip Profit Breakdown Page

**Files:**
- Create: `app/flips/[id]/profit.tsx`

**Rationale:** Show detailed profit breakdown for a specific flip including all allocated inventory.

- [ ] **Step 1: Create profit breakdown page**

Create `/app/flips/[id]/profit.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { TrendingUp, Package, DollarSign } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

interface ProfitBreakdown {
  flip_id: number;
  sale_price: number;
  selling_fee: number;
  net_proceeds: number;
  total_landed_cost: number;
  profit: number;
  profit_margin_pct: number;
  allocations: Array<{
    inventory_item_id: number;
    quantity: number;
    cost_per_unit: number;
    total_cost: number;
  }>;
}

export default function FlipProfitPage({ params }: { params: { id: string } }) {
  const [breakdown, setBreakdown] = useState<ProfitBreakdown | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/flips/${params.id}/profit-breakdown`)
      .then(r => r.json())
      .then(setBreakdown)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) return <div className="p-6">Loading...</div>;
  if (!breakdown) return <div className="p-6">Profit breakdown not found</div>;

  const profitColor = breakdown.profit >= 0 ? "text-green-400" : "text-red-400";

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
          <TrendingUp className="w-5 h-5" /> Flip #{breakdown.flip_id} Profit Breakdown
        </h1>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-4">
          <div className="text-slate-600 text-sm">Sale Price</div>
          <div className="text-2xl font-bold text-slate-200 mt-1">{formatCurrency(breakdown.sale_price)}</div>
        </div>
        <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-4">
          <div className="text-slate-600 text-sm">Selling Fee</div>
          <div className="text-2xl font-bold text-red-400 mt-1">{formatCurrency(breakdown.selling_fee)}</div>
        </div>
        <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-4">
          <div className="text-slate-600 text-sm">Total Inventory Cost</div>
          <div className="text-2xl font-bold text-amber-400 mt-1">{formatCurrency(breakdown.total_landed_cost)}</div>
        </div>
        <div className={`bg-[#0a1119] border border-[#1e2d45] rounded-lg p-4 ${profitColor}`}>
          <div className="text-slate-600 text-sm">Net Profit</div>
          <div className={`text-2xl font-bold mt-1 ${profitColor}`}>{formatCurrency(breakdown.profit)}</div>
          <div className="text-xs mt-1 opacity-75">{breakdown.profit_margin_pct.toFixed(1)}% margin</div>
        </div>
      </div>

      {/* Calculation breakdown */}
      <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <Package className="w-4 h-4" /> Cost Breakdown
        </h2>
        <div className="space-y-3 font-mono text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Sale Price</span>
            <span className="text-slate-200">{formatCurrency(breakdown.sale_price)}</span>
          </div>
          <div className="flex justify-between text-red-400">
            <span>− Selling Fee</span>
            <span>{formatCurrency(breakdown.selling_fee)}</span>
          </div>
          <div className="border-t border-[#1e2d45] pt-3 flex justify-between text-blue-400">
            <span>= Net Proceeds</span>
            <span>{formatCurrency(breakdown.net_proceeds)}</span>
          </div>
          <div className="border-t border-[#1e2d45] pt-3 flex justify-between text-amber-400">
            <span>− Inventory Costs</span>
            <span>{formatCurrency(breakdown.total_landed_cost)}</span>
          </div>
          <div className={`border-t border-[#1e2d45] pt-3 flex justify-between text-lg font-bold ${profitColor}`}>
            <span>= Profit</span>
            <span>{formatCurrency(breakdown.profit)}</span>
          </div>
        </div>
      </div>

      {/* Allocated inventory */}
      {breakdown.allocations.length > 0 && (
        <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <DollarSign className="w-4 h-4" /> Allocated Inventory
          </h2>
          <div className="space-y-3">
            {breakdown.allocations.map((alloc, i) => (
              <div key={i} className="flex justify-between items-center px-4 py-3 bg-[#0d1320] rounded border border-[#1e2d45]">
                <div>
                  <div className="text-slate-200 font-medium">Item #{alloc.inventory_item_id}</div>
                  <div className="text-xs text-slate-500">Qty: {alloc.quantity}</div>
                </div>
                <div className="text-right">
                  <div className="text-amber-400 font-mono">{formatCurrency(alloc.cost_per_unit)}/ea</div>
                  <div className="text-sm text-slate-400 font-mono">{formatCurrency(alloc.total_cost)} total</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Update flips list page to link to profit page**

Open `app/flips/page.tsx` (or wherever flips are listed). Add a link to the profit breakdown:

Add this somewhere in the flip card/row:

```tsx
<Link href={`/flips/${flip.id}/profit`} className="text-xs text-[#00dc82] hover:underline">
  View Profit
</Link>
```

- [ ] **Step 3: Rebuild and test**

```bash
docker compose up -d --build frontend && sleep 10
```

Navigate to http://localhost:4310/flips and click "View Profit" on a flip to see the breakdown.

- [ ] **Step 4: Commit**

```bash
git add app/flips/[id]/profit.tsx
git commit -m "feat: add flip profit breakdown detail page"
```

---

### Task 10: Update API Client Library

**Files:**
- Modify: `lib/api.ts`

- [ ] **Step 1: Add inventory allocation methods**

Open `lib/api.ts`, find the `api` object (around line 263), and add this new section:

```typescript
  inventoryAllocations: {
    list: (flipId?: number) => 
      request<unknown[]>(`/inventory-allocations${flipId ? `?flip_id=${flipId}` : ""}`),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/inventory-allocations", { method: "POST", body: JSON.stringify(data) }),
    get: (id: number) => request<unknown>(`/inventory-allocations/${id}`),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/inventory-allocations/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: number) => request<void>(`/inventory-allocations/${id}`, { method: "DELETE" }),
  },

  flipProfitBreakdown: {
    get: (flipId: number) => 
      request<{
        flip_id: number;
        sale_price: number;
        selling_fee: number;
        net_proceeds: number;
        total_landed_cost: number;
        profit: number;
        profit_margin_pct: number;
        allocations: Array<{
          inventory_item_id: number;
          quantity: number;
          cost_per_unit: number;
          total_cost: number;
        }>;
      }>(`/flips/${flipId}/profit-breakdown`),
  },
```

- [ ] **Step 2: Commit**

```bash
git add lib/api.ts
git commit -m "feat: add inventory allocation and profit breakdown API methods"
```

---

## Spec Coverage Checklist

- ✅ **Requirement 1:** Every inventory item needs base_price, shipping, discount (separate) — Task 1-2
- ✅ **Requirement 2:** Inventory items can be allocated to flips — Task 3-5
- ✅ **Requirement 3:** Profit calculation: (sale_price - fees) - landed_costs — Task 6
- ✅ **Requirement 4:** Frontend shows allocation and profit per flip — Task 8-9
- ✅ **Requirement 5:** Unallocated inventory shown as "Unassigned" — Task 8
