# Phase 3 F3.1 Implementation Plan — Demand Intelligence

**Status**: Ready for implementation  
**Target Tests**: ~45 (12+11+11+11 across 4 AC)  
**Feature Flags**: DEMAND_INTEL_ENABLED, DEMAND_INTEL_EXPORTS  
**Build Order**: DB → Models → Services → Tests → API  

---

## Overview

Phase 3 F3.1 provides **demand metrics dashboard** with **CSV export**, **trend analysis**, and **predictive alerts**. Enables users to understand build demand and make pricing/inventory decisions.

### 4 Acceptance Criteria

| AC | Description | Tests | Files |
|----|-------------|-------|-------|
| F3.1.1 | View demand metrics dashboard | 12 | Migration + Model + Service |
| F3.1.2 | Export metrics to CSV | 11 | Service + API + Tests |
| F3.1.3 | Historical trends & moving avg | 11 | Service + Tests |
| F3.1.4 | Predictive demand alerts | 11 | Service + Tests + API |

---

## Database Schema (F3.1.1)

### Migration: `20260823_0007_demand_intelligence.py`

```sql
-- Demand metrics snapshot (denormalized for fast dashboard)
CREATE TABLE demand_metrics_snapshots (
  id INTEGER PRIMARY KEY,
  manual_build_id INTEGER NOT NULL REFERENCES manual_builds(id),
  
  -- Raw demand signals
  view_count INTEGER DEFAULT 0,
  impression_count INTEGER DEFAULT 0,
  conversion_count INTEGER DEFAULT 0,
  
  -- Calculated rates
  view_to_conversion_rate FLOAT,  -- conversions / views (0.0-1.0)
  sell_through_rate FLOAT,         -- conversions / (views + non-converters)
  
  -- Velocity metrics
  views_per_day FLOAT,
  conversions_per_day FLOAT,
  
  -- Trends
  demand_trend VARCHAR(20),        -- rising, stable, declining, unknown
  trend_confidence FLOAT,          -- 0.0-1.0, higher = more certain
  
  -- Volatility
  volatility_score FLOAT,          -- 0.0-1.0, higher = more volatile
  
  recorded_at DATETIME DEFAULT NOW(),
  created_at DATETIME DEFAULT NOW()
);
CREATE INDEX ix_demand_metrics_manual_build_id ON demand_metrics_snapshots(manual_build_id);
CREATE INDEX ix_demand_metrics_recorded_at ON demand_metrics_snapshots(recorded_at);

-- Demand alerts (thresholds for alerting)
CREATE TABLE demand_alerts (
  id INTEGER PRIMARY KEY,
  manual_build_id INTEGER NOT NULL REFERENCES manual_builds(id),
  
  alert_type VARCHAR(30) NOT NULL,  -- high_demand, low_demand, risk_flag
  severity VARCHAR(20),              -- info, warning, critical
  message TEXT,
  
  -- Alert criteria
  metric_name VARCHAR(50),           -- view_count, conversion_rate, etc.
  threshold_value FLOAT,
  actual_value FLOAT,
  
  acknowledged_at DATETIME,
  created_at DATETIME DEFAULT NOW()
);
Create INDEX ix_demand_alerts_manual_build_id ON demand_alerts(manual_build_id);
Create INDEX ix_demand_alerts_alert_type ON demand_alerts(alert_type);

-- Export history (audit trail of CSV exports)
CREATE TABLE demand_export_audits (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,                  -- NULL if API, else admin user
  
  export_type VARCHAR(30),          -- all_builds, single_build, filtered
  filter_params JSON,               -- date range, status filters, etc.
  
  row_count INTEGER,                -- rows in exported CSV
  exported_at DATETIME DEFAULT NOW()
);
Create INDEX ix_demand_export_audits_exported_at ON demand_export_audits(exported_at);
```

### Models: `app/models/demand_metrics_snapshot.py` + `demand_alert.py` + `demand_export_audit.py`

```python
# demand_metrics_snapshot.py
@dataclass
class DemandMetricsSnapshot(Base):
    __tablename__ = "demand_metrics_snapshots"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"))
    
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    impression_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_count: Mapped[int] = mapped_column(Integer, default=0)
    
    view_to_conversion_rate: Mapped[float | None] = mapped_column(Float)
    sell_through_rate: Mapped[float | None] = mapped_column(Float)
    
    views_per_day: Mapped[float | None] = mapped_column(Float)
    conversions_per_day: Mapped[float | None] = mapped_column(Float)
    
    demand_trend: Mapped[str] = mapped_column(String(20), default="unknown")
    trend_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    volatility_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    recorded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

# demand_alert.py
@dataclass
class DemandAlert(Base):
    __tablename__ = "demand_alerts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"))
    
    alert_type: Mapped[str] = mapped_column(String(30))  # high_demand, low_demand, risk_flag
    severity: Mapped[str] = mapped_column(String(20))    # info, warning, critical
    message: Mapped[str] = mapped_column(String(500))
    
    metric_name: Mapped[str] = mapped_column(String(50))
    threshold_value: Mapped[float] = mapped_column(Float)
    actual_value: Mapped[float] = mapped_column(Float)
    
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

# demand_export_audit.py
@dataclass
class DemandExportAudit(Base):
    __tablename__ = "demand_export_audits"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer)
    
    export_type: Mapped[str] = mapped_column(String(30))
    filter_params: Mapped[dict] = mapped_column(JSON, default=dict)
    
    row_count: Mapped[int] = mapped_column(Integer)
    exported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

---

## Services

### F3.1.1: Demand Metrics Calculator

**File**: `app/services/demand_metrics_calculator.py` (~200 LOC)

```python
class DemandMetricsCalculator:
    @staticmethod
    async def calculate_metrics(
        db: AsyncSession,
        build_id: int,
        lookback_days: int = 30,
    ) -> DemandMetricsSnapshot:
        """Calculate demand metrics for build from gem_radar_listing_demand_history."""
        # Query demand history for build
        # Calculate view_count, impression_count, conversion_count from gem_radar
        # Calculate rates (view_to_conversion, sell_through)
        # Calculate velocity (views_per_day, conversions_per_day)
        # Create snapshot
        
    @staticmethod
    async def get_current_metrics(
        db: AsyncSession,
        build_id: int,
    ) -> DemandMetricsSnapshot | None:
        """Get latest metrics for build."""
        
    @staticmethod
    async def get_metrics_history(
        db: AsyncSession,
        build_id: int,
        days: int = 30,
    ) -> list[DemandMetricsSnapshot]:
        """Get historical metrics over time period."""
```

**Tests**: `test_demand_metrics_calculator.py` (12 tests)
- Calculate from gem_radar data
- Conversion rate calculation
- Sell-through rate calculation
- Velocity metrics
- Handle missing data gracefully
- Feature flag gating
- Money type precision (if applicable)

---

### F3.1.2: CSV Export Service

**File**: `app/services/demand_export_service.py` (~180 LOC)

```python
class DemandExportService:
    @staticmethod
    async def export_builds_to_csv(
        db: AsyncSession,
        build_ids: list[int],
        include_metrics: bool = True,
        include_trends: bool = True,
    ) -> str:  # CSV content as string
        """Export demand metrics to CSV."""
        # Columns: build, price, views, impressions, conversions, rates, trend
        # Query metrics for builds
        # Format as CSV
        # Log to demand_export_audits
        
    @staticmethod
    async def export_all_builds_csv(
        db: AsyncSession,
        status_filter: str | None = None,  # in_progress, listed, sold, archived
    ) -> str:
        """Export metrics for all builds (or filtered)."""
        
    @staticmethod
    async def get_export_history(
        db: AsyncSession,
        limit: int = 100,
    ) -> list[DemandExportAudit]:
        """Get audit trail of exports."""
```

**Tests**: `test_demand_export_service.py` (11 tests)
- Export single build to CSV
- Export multiple builds
- Export all builds with filters
- CSV format validation
- Column headers correct
- Feature flag enforcement (DEMAND_INTEL_EXPORTS)
- Audit trail logging
- Handle empty results
- Money type in prices

---

### F3.1.3: Trend Analysis Service

**File**: `app/services/demand_trend_analyzer.py` (~200 LOC)

```python
class DemandTrendAnalyzer:
    @staticmethod
    async def calculate_trend(
        db: AsyncSession,
        build_id: int,
        window_days: int = 7,
    ) -> dict:
        """Calculate demand trend over window."""
        # Get metrics history
        # Calculate moving average
        # Compare to prior period
        # Determine: rising, stable, declining, unknown
        # Calculate confidence (0.0-1.0)
        
    @staticmethod
    async def get_moving_average(
        db: AsyncSession,
        build_id: int,
        metric: str,  # view_count, conversion_count, etc.
        window_days: int = 7,
    ) -> float:
        """Get N-day moving average for metric."""
        
    @staticmethod
    async def detect_volatility(
        db: AsyncSession,
        build_id: int,
        lookback_days: int = 30,
    ) -> float:
        """Calculate demand volatility (0.0-1.0)."""
        # High std dev in conversion rate = high volatility
        
    @staticmethod
    async def estimate_sell_through(
        db: AsyncSession,
        build_id: int,
        days_listed: int,
    ) -> dict:
        """Estimate when build will sell based on trend."""
        # Returns: days_to_sell, confidence
```

**Tests**: `test_demand_trend_analyzer.py` (11 tests)
- Calculate trend (rising/stable/declining)
- 7-day moving average
- 30-day moving average
- Volatility detection
- Sell-through estimation
- Handle insufficient data
- Money type precision
- Edge cases (no history, single data point)

---

### F3.1.4: Demand Alert Service

**File**: `app/services/demand_alert_service.py` (~220 LOC)

```python
class DemandAlertService:
    @staticmethod
    async def check_demand_alerts(
        db: AsyncSession,
        build_id: int,
    ) -> list[DemandAlert]:
        """Check if build triggers any demand alerts."""
        # Get current metrics
        # Check thresholds:
        #   - High demand: conversions > 10 AND conversion_rate > 0.5 → HIGH_DEMAND (info)
        #   - Low demand: views > 100 AND conversion_rate < 0.1 → LOW_DEMAND (warning)
        #   - Risk flag: listed > 60 days AND conversions < 1 → RISK_FLAG (critical)
        # Create alerts if threshold met
        
    @staticmethod
    async def get_active_alerts(
        db: AsyncSession,
        build_id: int,
    ) -> list[DemandAlert]:
        """Get unacknowledged alerts for build."""
        
    @staticmethod
    async def acknowledge_alert(
        db: AsyncSession,
        alert_id: int,
    ) -> bool:
        """Mark alert as acknowledged."""
        
    @staticmethod
    async def get_alert_stats(
        db: AsyncSession,
    ) -> dict:
        """Get statistics on all active alerts."""
        # Returns: total_alerts, by_severity, by_type
        
    @staticmethod
    async def send_alert_notifications(
        db: AsyncSession,
        alert: DemandAlert,
        user_email: str,
    ) -> bool:
        """Send email for critical alerts (optional)."""
        # Gated by EMAIL_DISPATCH_ENABLED + severity=critical
```

**Tests**: `test_demand_alert_service.py` (11 tests)
- High demand alert triggers
- Low demand alert triggers
- Risk flag alert triggers
- No false positives
- Acknowledge alert
- Get active alerts
- Alert statistics
- Email notifications (when enabled)
- Feature flag gating
- Edge cases (new builds, no history)

---

## API Endpoints

### GET `/api/demand/metrics/{build_id}`

Response:
```json
{
  "build_id": 123,
  "view_count": 450,
  "impression_count": 320,
  "conversion_count": 15,
  "view_to_conversion_rate": 0.033,
  "sell_through_rate": 0.045,
  "views_per_day": 21.4,
  "conversions_per_day": 0.71,
  "demand_trend": "rising",
  "trend_confidence": 0.87,
  "volatility_score": 0.34,
  "recorded_at": "2026-08-23T10:30:00Z"
}
```

### POST `/api/demand/export`

Body:
```json
{
  "build_ids": [123, 124, 125],
  "include_trends": true,
  "include_metrics": true
}
```

Response:
```json
{
  "csv_url": "/files/export-20260823-103000.csv",
  "row_count": 3,
  "generated_at": "2026-08-23T10:30:00Z"
}
```

### GET `/api/demand/alerts/{build_id}`

Response:
```json
{
  "build_id": 123,
  "alerts": [
    {
      "id": 1,
      "alert_type": "high_demand",
      "severity": "info",
      "message": "Build showing strong demand signal",
      "metric_name": "conversion_rate",
      "threshold_value": 0.5,
      "actual_value": 0.58,
      "created_at": "2026-08-23T10:00:00Z"
    }
  ]
}
```

---

## Test Coverage Estimate

| Suite | Count | Coverage |
|-------|-------|----------|
| Demand Metrics Calc (F3.1.1) | 12 | 85% |
| CSV Export (F3.1.2) | 11 | 85% |
| Trend Analysis (F3.1.3) | 11 | 85% |
| Demand Alerts (F3.1.4) | 11 | 85% |
| **F3.1 Total** | **45** | **85%** |

---

## Feature Flags (Safe by Default)

```bash
# Phase 3a: All OFF (safe)
FEATURE_DEMAND_INTEL_ENABLED=false
FEATURE_DEMAND_INTEL_EXPORTS=false

# Phase 3b: Enable metrics viewing
FEATURE_DEMAND_INTEL_ENABLED=true
FEATURE_DEMAND_INTEL_EXPORTS=false

# Phase 3c: Full rollout (with exports)
FEATURE_DEMAND_INTEL_ENABLED=true
FEATURE_DEMAND_INTEL_EXPORTS=true
```

---

## Build Order

1. **Migration** → Create demand_metrics_snapshots, demand_alerts, demand_export_audits tables
2. **Models** → DemandMetricsSnapshot, DemandAlert, DemandExportAudit
3. **Services** (in parallel):
   - DemandMetricsCalculator (F3.1.1)
   - DemandExportService (F3.1.2)
   - DemandTrendAnalyzer (F3.1.3)
   - DemandAlertService (F3.1.4)
4. **Tests** → 45 tests
5. **API** → 4 endpoints
6. **Docs** → Integration guide

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Missing gem_radar data | Default to 0 for unknown metrics; log warnings |
| Performance (large metric queries) | Denormalized snapshots table; indexes on build_id + time |
| Alert spam | Deduplication; don't re-alert same condition within 24h |
| Export audit bloat | Retention policy; archive audits >90 days old |
| Division by zero | Always check denominator; default to 0.0 if zero views |

---

## Phased Rollout

**Week 1**: Deploy with all flags OFF  
**Week 2**: Enable metrics dashboard (test view)  
**Week 3**: Enable CSV export (test export)  
**Week 4**: Enable alerts (full launch)

Each phase can be rolled back by changing environment variable (no code deploy).

---

## Success Criteria

- ✅ All 45 tests passing
- ✅ Can view demand metrics for build
- ✅ Can export to CSV with proper formatting
- ✅ Trends accurate (moving averages)
- ✅ Alerts fire correctly (no false positives)
- ✅ All operations audited
- ✅ Feature flags enable safe phased rollout
