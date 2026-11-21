# F2.2 Implementation Plan — Listing Proliferator

**Status**: Ready for implementation  
**Target Tests**: ~55 (13+14+14+14 across 4 AC)  
**Feature Flags**: LISTING_PUBLISH_ENABLED, LISTING_PUBLISH_DRY_RUN_ONLY, LISTING_INVENTORY_RESERVATION  
**Build Order**: DB → Models → Services → Tests → API  

---

## Overview

F2.2 enables multi-channel listing with dry-run validation and inventory reservation. All features gated by feature flags (all OFF by default).

### 4 Acceptance Criteria

| AC | Description | Tests | Files |
|----|-------------|-------|-------|
| F2.2.1 | Multi-channel listing (eBay + Storefront) | 13 | Migration + Model + Service |
| F2.2.2 | Dry-run mode (preview without commit) | 14 | Service + Tests |
| F2.2.3 | Live publishing (gated by flag) | 14 | Service + API + Tests |
| F2.2.4 | Inventory reservation (prevent oversell) | 14 | Service + Tests |

---

## Database Schema (F2.2.1)

### Migration: `20260823_0006_listing_proliferator.py`

```sql
-- Channel listing records
CREATE TABLE channel_listings (
  id INTEGER PRIMARY KEY,
  manual_build_id INTEGER NOT NULL REFERENCES manual_builds(id),
  channel VARCHAR(30) NOT NULL,  -- 'ebay' | 'storefront'
  status VARCHAR(30) DEFAULT 'draft',  -- draft | scheduled | published | withdrawn
  external_listing_id VARCHAR(100),  -- eBay item ID or storefront SKU
  published_at DATETIME,
  withdrawn_at DATETIME,
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW()
);
CREATE INDEX ix_channel_listings_manual_build_id ON channel_listings(manual_build_id);
CREATE INDEX ix_channel_listings_channel ON channel_listings(channel);

-- Inventory reservations (prevent overselling across channels)
CREATE TABLE inventory_reservations (
  id INTEGER PRIMARY KEY,
  manual_build_id INTEGER NOT NULL REFERENCES manual_builds(id),
  channel VARCHAR(30) NOT NULL,  -- which channel reserved this
  quantity_reserved INTEGER DEFAULT 1,
  reserved_at DATETIME DEFAULT NOW(),
  released_at DATETIME,
  created_at DATETIME DEFAULT NOW()
);
CREATE INDEX ix_inventory_reservations_manual_build_id ON inventory_reservations(manual_build_id);

-- Publishing audit trail
CREATE TABLE listing_publish_events (
  id INTEGER PRIMARY KEY,
  channel_listing_id INTEGER NOT NULL REFERENCES channel_listings(id),
  event_type VARCHAR(50) NOT NULL,  -- 'published' | 'withdrawn' | 'dry_run' | 'validation_failed'
  message TEXT,
  metadata JSON,
  created_at DATETIME DEFAULT NOW()
);
CREATE INDEX ix_listing_publish_events_channel_listing_id ON listing_publish_events(channel_listing_id);
```

### Models: `app/models/channel_listing.py` + `inventory_reservation.py`

```python
# channel_listing.py
@dataclass
class ChannelListing(Base):
    __tablename__ = "channel_listings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"))
    channel: Mapped[str] = mapped_column(String(30))  # ebay | storefront
    status: Mapped[str] = mapped_column(String(30), default="draft")
    external_listing_id: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, onupdate=func.now())

# inventory_reservation.py
@dataclass
class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"))
    channel: Mapped[str] = mapped_column(String(30))
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=1)
    reserved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
```

---

## Services

### F2.2.1: Multi-Channel Publisher

**File**: `app/services/multi_channel_publisher.py` (~200 LOC)

```python
class MultiChannelPublisher:
    @staticmethod
    async def prepare_for_channels(
        db: AsyncSession,
        build_id: int,
        channels: list[str],  # ['ebay', 'storefront']
    ) -> bool:
        """Create channel_listing records for each channel (draft status)."""
        
    @staticmethod
    async def sync_inventory_across_channels(
        db: AsyncSession,
        build_id: int,
    ) -> dict:
        """Check inventory consistency across all channel listings."""
        
    @staticmethod
    async def list_active_channel_listings(
        db: AsyncSession,
        build_id: int,
    ) -> list[ChannelListing]:
        """Get all listings for a build across channels."""
```

**Tests**: `test_multi_channel_publisher.py` (13 tests)
- Create listings for multiple channels
- Update channel status
- List active listings by build
- Handle duplicate channels
- Cross-channel sync verification
- Feature flag gating
- Money type in pricing (if applicable)

---

### F2.2.2: Dry-Run Validator

**File**: `app/services/dry_run_validator.py` (~180 LOC)

```python
class DryRunValidator:
    @staticmethod
    async def validate_listing(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> DryRunResult:
        """Validate without publishing. Returns what would happen."""
        # Check pricing rules
        # Check inventory availability
        # Check build readiness
        # Return validation report
        
    @staticmethod
    async def preview_publication(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> PublicationPreview:
        """Show what the listing would look like."""
        
    @staticmethod
    async def simulate_inventory_change(
        db: AsyncSession,
        build_id: int,
        channels: list[str],
    ) -> InventoryChange:
        """Show inventory impact across channels."""
```

**Tests**: `test_dry_run_validator.py` (14 tests)
- Validate without publishing
- Pricing validation
- Inventory availability check
- Preview generation
- Multi-channel simulation
- Error detection
- Flag gating (DRY_RUN_ONLY)
- No actual state changes

---

### F2.2.3: Live Publisher

**File**: `app/services/live_publisher.py` (~220 LOC)

```python
class LivePublisher:
    @staticmethod
    async def publish_to_channel(
        db: AsyncSession,
        build_id: int,
        channel: str,
        options: PublishOptions,
    ) -> PublishResult:
        """Publish listing to a channel (gated by flag)."""
        # Validate first
        # Reserve inventory if enabled
        # Call channel API (eBay, Storefront)
        # Update channel_listing status to 'published'
        # Log event
        
    @staticmethod
    async def publish_to_all_channels(
        db: AsyncSession,
        build_id: int,
        options: PublishOptions,
    ) -> dict[str, PublishResult]:
        """Publish to all configured channels."""
        
    @staticmethod
    async def withdraw_from_channel(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> bool:
        """Withdraw listing from channel."""
```

**Tests**: `test_live_publisher.py` (14 tests)
- Publish to eBay channel
- Publish to Storefront channel
- Publish to multiple channels
- Update external listing ID
- Handle API failures gracefully
- Feature flag enforcement
- Audit trail logging
- Idempotent operations
- Withdraw listings

---

### F2.2.4: Inventory Reservation Manager

**File**: `app/services/inventory_reservation.py` (~180 LOC)

```python
class InventoryReservationManager:
    @staticmethod
    async def reserve_inventory(
        db: AsyncSession,
        build_id: int,
        channel: str,
        quantity: int = 1,
    ) -> InventoryReservation | None:
        """Reserve stock for a channel."""
        
    @staticmethod
    async def get_reserved_count(
        db: AsyncSession,
        build_id: int,
    ) -> int:
        """Get total reserved across all channels."""
        
    @staticmethod
    async def check_availability(
        db: AsyncSession,
        build_id: int,
        quantity_needed: int,
    ) -> bool:
        """Check if enough stock available (accounting for reservations)."""
        
    @staticmethod
    async def release_reservation(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> bool:
        """Release reservation when listing withdrawn."""
        
    @staticmethod
    async def is_oversold(
        db: AsyncSession,
        build_id: int,
    ) -> bool:
        """Check if reserved > available (inventory bug)."""
```

**Tests**: `test_inventory_reservation.py` (14 tests)
- Reserve inventory
- Get reserved count
- Check availability
- Prevent overselling
- Release on withdrawal
- Multi-channel conflicts
- Feature flag gating
- Edge cases (zero inventory, negative reservations)
- Concurrent reservations
- Audit trail

---

## API Endpoints

### POST `/api/manual-builds/{id}/list-on-channels`

```json
{
  "channels": ["ebay", "storefront"],
  "dry_run": false,
  "options": {
    "pricing": {...},
    "shipping": {...}
  }
}
```

Response:
```json
{
  "success": true,
  "listings": [
    {
      "channel": "ebay",
      "status": "published",
      "external_id": "123456789",
      "published_at": "2026-08-23T10:30:00Z"
    },
    {
      "channel": "storefront",
      "status": "published",
      "external_id": "STORE-12345",
      "published_at": "2026-08-23T10:30:05Z"
    }
  ]
}
```

### POST `/api/manual-builds/{id}/dry-run`

Response:
```json
{
  "valid": true,
  "channels": ["ebay", "storefront"],
  "inventory": {
    "available": 1,
    "would_be_reserved": 2,  // 1 per channel
    "would_be_available_after": -1  // oversold!
  },
  "warnings": ["Would oversell inventory"]
}
```

---

## Test Coverage Estimate

| Suite | Count | Coverage |
|-------|-------|----------|
| Multi-Channel Listings (F2.2.1) | 13 | 85% |
| Dry-Run Validator (F2.2.2) | 14 | 85% |
| Live Publisher (F2.2.3) | 14 | 85% |
| Inventory Reservation (F2.2.4) | 14 | 85% |
| **F2.2 Total** | **55** | **85%** |

---

## Feature Flags (Safe by Default)

```bash
# Phase 2a: All OFF (safe)
FEATURE_LISTING_PUBLISH_ENABLED=false
FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY=true       # Only dry-run mode works
FEATURE_LISTING_INVENTORY_RESERVATION=false

# Phase 2b: Enable dry-run validation
FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY=true       # Dry-run works
FEATURE_LISTING_INVENTORY_RESERVATION=false

# Phase 2c: Enable live publishing (with caution)
FEATURE_LISTING_PUBLISH_ENABLED=true
FEATURE_LISTING_INVENTORY_RESERVATION=false

# Phase 2d: Full rollout (with inventory protection)
FEATURE_LISTING_PUBLISH_ENABLED=true
FEATURE_LISTING_INVENTORY_RESERVATION=true
```

---

## Build Order

1. **Migration** → Create channel_listings, inventory_reservations, listing_publish_events tables
2. **Models** → ChannelListing, InventoryReservation, ListingPublishEvent
3. **Services**:
   - MultiChannelPublisher (F2.2.1)
   - DryRunValidator (F2.2.2)
   - LivePublisher (F2.2.3)
   - InventoryReservationManager (F2.2.4)
4. **Tests** → 55 tests (13+14+14+14)
5. **API** → Endpoints for listing/dry-run/withdraw
6. **Docs** → Integration guide

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Oversell across channels | Inventory reservation system + validation |
| API call failures | Feature flag allows disable; audit trail shows what failed |
| Duplicate listings | Idempotency check + external_listing_id prevents dupes |
| Race conditions | Row-level locking on manual_builds (existing pattern) |
| Missing rollback | Feature flag kill-switch; don't publish if flag OFF |

---

## Phased Rollout

**Week 1**: Deploy with all flags OFF  
**Week 2**: Enable dry-run validation (test preview mode)  
**Week 3**: Enable live publishing to eBay (monitor for issues)  
**Week 4**: Enable inventory reservation (full launch)

Each phase can be rolled back by changing environment variable (no code deploy).

---

## Success Criteria

- ✅ All 55 tests passing
- ✅ Can list to multiple channels simultaneously
- ✅ Dry-run mode accurately predicts outcomes
- ✅ Inventory reservation prevents overselling
- ✅ All publishes audited and rollbackable
- ✅ Feature flags enable safe phased rollout
