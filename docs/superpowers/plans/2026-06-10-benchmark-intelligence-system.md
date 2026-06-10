# Benchmark Intelligence System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a benchmark data retrieval, storage, refresh and scoring subsystem that identifies which PC components are underpriced relative to their performance — making PC Flipper smarter than a human manually comparing listings.

**Architecture:** Backend-only Python services added to `pc-flipper-backend/app/`. New SQLAlchemy models (`hardware_benchmarks`, `component_performance_metrics`, `benchmark_refresh_runs`) in `app/models/`. New services (`benchmark_normaliser`, `benchmark_fetcher`, `benchmark_scorer`) in `app/services/`. A scheduled job registered in `app/workers/scheduler.py`. A new FastAPI router `app/api/benchmarks.py` for admin/debug UI. Frontend admin page added to `pc-flipper/app/benchmarks/page.tsx`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, httpx, BeautifulSoup4, APScheduler (already in requirements), Next.js 14 / TypeScript for the admin page. No new pip dependencies required — all existing.

---

## File Map

### New files — Backend
- `app/models/benchmark.py` — three ORM models: `HardwareBenchmark`, `ComponentPerformanceMetric`, `BenchmarkRefreshRun`
- `app/services/benchmark_normaliser.py` — model name normalisation (CPU/GPU/storage/RAM)
- `app/services/benchmark_fetcher.py` — HTTP scraping of PassMark CPU/GPU/disk rankings
- `app/services/benchmark_scorer.py` — RAM derived scoring + performance/£ calculations + opportunity scoring + gem flag logic
- `app/services/benchmark_refresh_job.py` — orchestrator: load active models → check staleness → fetch → save → recalculate
- `app/api/benchmarks.py` — REST endpoints for admin UI

### Modified files — Backend
- `app/models/__init__.py` — import new models so `Base.metadata.create_all` sees them
- `app/main.py` — add `_migrate_add_columns` entries for new tables; include benchmark router
- `app/workers/scheduler.py` — register `benchmark_refresh_daily` and `benchmark_refresh_weekly` jobs
- `app/services/classifier.py` — call `benchmark_scorer.get_opportunity_score()` and add `performance_per_pound` to signals
- `app/services/listing_generator.py` — use benchmark data to enrich listing copy and performance summaries

### New files — Frontend
- `pc-flipper/app/benchmarks/page.tsx` — admin/debug UI for benchmark coverage, refresh status, top gems

---

## Task 1: Database models

**Files:**
- Create: `pc-flipper-backend/app/models/benchmark.py`
- Modify: `pc-flipper-backend/app/models/__init__.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_benchmark_models.py
import pytest
from sqlalchemy import inspect
from app.models.benchmark import HardwareBenchmark, ComponentPerformanceMetric, BenchmarkRefreshRun
from app.database import Base

def test_hardware_benchmark_tablename():
    assert HardwareBenchmark.__tablename__ == "hardware_benchmarks"

def test_component_performance_metric_tablename():
    assert ComponentPerformanceMetric.__tablename__ == "component_performance_metrics"

def test_benchmark_refresh_run_tablename():
    assert BenchmarkRefreshRun.__tablename__ == "benchmark_refresh_runs"

def test_hardware_benchmark_required_columns():
    cols = {c.key for c in inspect(HardwareBenchmark).mapper.column_attrs}
    assert {"component_type", "model", "normalized_model", "benchmark_source", "overall_score"} <= cols
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_models.py -v
```
Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create the model file**

```python
# app/models/benchmark.py
from datetime import datetime
from typing import Optional
from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class HardwareBenchmark(Base):
    __tablename__ = "hardware_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_type: Mapped[str] = mapped_column(String(20), index=True)   # cpu | gpu | storage | ram
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(300))
    normalized_model: Mapped[str] = mapped_column(String(300), index=True)
    benchmark_source: Mapped[str] = mapped_column(String(100))
    overall_score: Mapped[Optional[float]] = mapped_column(Float)
    gaming_score: Mapped[Optional[float]] = mapped_column(Float)
    workstation_score: Mapped[Optional[float]] = mapped_column(Float)
    single_thread_score: Mapped[Optional[float]] = mapped_column(Float)
    multi_thread_score: Mapped[Optional[float]] = mapped_column(Float)
    memory_score: Mapped[Optional[float]] = mapped_column(Float)
    storage_score: Mapped[Optional[float]] = mapped_column(Float)
    vram_gb: Mapped[Optional[float]] = mapped_column(Float)
    ram_capacity_gb: Mapped[Optional[float]] = mapped_column(Float)
    ram_speed_mts: Mapped[Optional[float]] = mapped_column(Float)
    ram_latency_cl: Mapped[Optional[float]] = mapped_column(Float)
    storage_capacity_gb: Mapped[Optional[float]] = mapped_column(Float)
    storage_interface: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_refreshed_at: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.utcnow().isoformat())
    updated_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.utcnow().isoformat())


class ComponentPerformanceMetric(Base):
    __tablename__ = "component_performance_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_listing_id: Mapped[Optional[str]] = mapped_column(String(100))
    component_type: Mapped[str] = mapped_column(String(20), index=True)
    normalized_model: Mapped[str] = mapped_column(String(300), index=True)
    acquisition_price: Mapped[Optional[float]] = mapped_column(Float)
    benchmark_score: Mapped[Optional[float]] = mapped_column(Float)
    gaming_score: Mapped[Optional[float]] = mapped_column(Float)
    workstation_score: Mapped[Optional[float]] = mapped_column(Float)
    performance_per_pound: Mapped[Optional[float]] = mapped_column(Float)
    gaming_per_pound: Mapped[Optional[float]] = mapped_column(Float)
    workstation_per_pound: Mapped[Optional[float]] = mapped_column(Float)
    marketability_score: Mapped[Optional[float]] = mapped_column(Float)
    demand_score: Mapped[Optional[float]] = mapped_column(Float)
    liquidity_score: Mapped[Optional[float]] = mapped_column(Float)
    opportunity_score: Mapped[Optional[float]] = mapped_column(Float)
    calculated_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.utcnow().isoformat())


class BenchmarkRefreshRun(Base):
    __tablename__ = "benchmark_refresh_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[Optional[str]] = mapped_column(String(20))   # daily | weekly | manual
    started_at: Mapped[Optional[str]] = mapped_column(String(50))
    completed_at: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[Optional[str]] = mapped_column(String(100))
    components_checked: Mapped[int] = mapped_column(Integer, default=0)
    components_updated: Mapped[int] = mapped_column(Integer, default=0)
    components_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[Optional[str]] = mapped_column(String(20))     # running | completed | failed
    error_log: Mapped[Optional[str]] = mapped_column(Text)
```

- [ ] **Step 4: Register models in `__init__.py`**

Open `app/models/__init__.py`. Add this line alongside the other model imports:

```python
from app.models import benchmark as _benchmark  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_models.py -v
```
Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
cd pc-flipper-backend && git add app/models/benchmark.py app/models/__init__.py tests/test_benchmark_models.py
git commit -m "feat: add hardware_benchmarks, component_performance_metrics, benchmark_refresh_runs models"
```

---

## Task 2: Model name normaliser

**Files:**
- Create: `pc-flipper-backend/app/services/benchmark_normaliser.py`
- Create: `pc-flipper-backend/tests/test_benchmark_normaliser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_benchmark_normaliser.py
from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu, normalise_storage, detect_component_type

def test_normalise_cpu_variants():
    assert normalise_cpu("AMD Ryzen 7 7800X3D") == "amd_ryzen_7_7800x3d"
    assert normalise_cpu("Ryzen 7 7800X3D") == "amd_ryzen_7_7800x3d"
    assert normalise_cpu("R7 7800X3D") == "amd_ryzen_7_7800x3d"
    assert normalise_cpu("7800 X3D") == "amd_ryzen_7_7800x3d"
    assert normalise_cpu("Intel Core i7-13700K") == "intel_core_i7_13700k"
    assert normalise_cpu("i7 13700K") == "intel_core_i7_13700k"
    assert normalise_cpu("Core i5-12400F") == "intel_core_i5_12400f"

def test_normalise_gpu_variants():
    assert normalise_gpu("RTX 3070") == "nvidia_geforce_rtx_3070"
    assert normalise_gpu("Nvidia RTX3070") == "nvidia_geforce_rtx_3070"
    assert normalise_gpu("GeForce RTX 3070") == "nvidia_geforce_rtx_3070"
    assert normalise_gpu("3070 8GB") == "nvidia_geforce_rtx_3070"
    assert normalise_gpu("RX 6800 XT") == "amd_radeon_rx_6800_xt"
    assert normalise_gpu("Radeon RX 6800XT") == "amd_radeon_rx_6800_xt"

def test_normalise_storage_variants():
    assert normalise_storage("Samsung 970 EVO 1TB") == "samsung_970_evo_1tb"
    assert normalise_storage("WD Blue SN570 1TB NVMe") == "wd_blue_sn570_1tb"

def test_detect_component_type():
    assert detect_component_type("Ryzen 7 5800X") == "cpu"
    assert detect_component_type("RTX 3080 10GB") == "gpu"
    assert detect_component_type("Samsung 870 EVO 1TB") == "storage"
    assert detect_component_type("32GB DDR4 3200MHz") == "ram"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_normaliser.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement the normaliser**

```python
# app/services/benchmark_normaliser.py
"""
Normalises messy component model strings to canonical slugs.
Used by scraper, benchmark lookup, gem scoring, and listing generator.
"""
import re

# ── CPU normalisation ─────────────────────────────────────────────────────────
_RYZEN_SERIES = {
    "3": "ryzen_3", "5": "ryzen_5", "7": "ryzen_7", "9": "ryzen_9",
}
# Patterns ordered most-specific first
_CPU_PATTERNS = [
    # AMD Ryzen with explicit series: "Ryzen 7 7800X3D", "R7 7800X3D", "7800X3D"
    (re.compile(r'(?:amd\s+)?(?:ryzen\s+|r)(\d)\s+(\d{4}[a-z0-9]*)', re.I),
     lambda m: f"amd_ryzen_{m.group(1)}_{_slug(m.group(2))}"),
    # Threadripper
    (re.compile(r'(?:amd\s+)?(?:ryzen\s+)?threadripper\s+(?:pro\s+)?(\d{4}[a-z0-9]*)', re.I),
     lambda m: f"amd_threadripper_{_slug(m.group(1))}"),
    # Bare model number that matches Ryzen pattern (e.g. "7800X3D", "5600X")
    (re.compile(r'\b(\d{4}[a-z0-9]{1,4})\b', re.I),
     lambda m: _resolve_bare_cpu_model(m.group(1))),
    # Intel Core iN-NNNNN
    (re.compile(r'(?:intel\s+)?(?:core\s+)?i([3579])[- ](\d{4,5}[a-z0-9]*)', re.I),
     lambda m: f"intel_core_i{m.group(1)}_{_slug(m.group(2))}"),
    # Intel Xeon
    (re.compile(r'(?:intel\s+)?xeon\s+([a-z0-9-]+)', re.I),
     lambda m: f"intel_xeon_{_slug(m.group(1))}"),
]

_RYZEN_MODEL_PREFIXES = {
    "3": ("3100", "3300", "3600"),
    "5": ("5600", "5700", "7600", "7500"),
    "7": ("5700", "5800", "7700", "7800"),
    "9": ("5900", "5950", "7900", "7950", "9900", "9950"),
}


def _slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def _resolve_bare_cpu_model(model: str) -> str | None:
    """Try to resolve a bare model number like '7800X3D' to a full AMD slug."""
    m = model.lower()
    for series, prefixes in _RYZEN_MODEL_PREFIXES.items():
        for prefix in prefixes:
            if m.startswith(prefix):
                return f"amd_ryzen_{series}_{_slug(model)}"
    return None


def normalise_cpu(raw: str) -> str:
    """Return a canonical CPU slug or the cleaned input if no pattern matched."""
    s = raw.strip()
    for pattern, builder in _CPU_PATTERNS:
        match = pattern.search(s)
        if match:
            result = builder(match)
            if result:
                return result
    return _slug(s)


# ── GPU normalisation ─────────────────────────────────────────────────────────
_GPU_PATTERNS = [
    # NVIDIA RTX/GTX: "RTX 3070", "GeForce RTX3070", "Nvidia RTX 3070", "3070 8GB"
    (re.compile(r'(?:nvidia\s+)?(?:geforce\s+)?(?:rtx|gtx)\s*(\d{4})(?:\s*ti)?(?:\s*super)?', re.I),
     lambda m, raw: f"nvidia_geforce_{'rtx' if 'rtx' in raw.lower() else 'gtx'}_{m.group(1)}{_ti_super_suffix(raw)}"),
    # Bare RTX/GTX number without brand (e.g. "3070 8GB", "4090")
    (re.compile(r'\b(3\d{3}|4\d{3}|10\d{2}|16\d{2}|20\d{2})\b'), 
     lambda m, raw: f"nvidia_geforce_{'rtx' if int(m.group(1)) >= 2000 else 'gtx'}_{m.group(1)}{_ti_super_suffix(raw)}"),
    # AMD Radeon RX: "RX 6800 XT", "Radeon RX6800XT"
    (re.compile(r'(?:amd\s+)?(?:radeon\s+)?rx\s*(\d{4})(?:\s*xt)?', re.I),
     lambda m, raw: f"amd_radeon_rx_{m.group(1)}{'_xt' if 'xt' in raw.lower() else ''}"),
    # AMD RX without "rx" prefix but numeric 4xxx/5xxx/6xxx/7xxx
    (re.compile(r'\b([5-7]\d{3})\b'),
     lambda m, raw: f"amd_radeon_rx_{m.group(1)}{'_xt' if 'xt' in raw.lower() else ''}"),
]


def _ti_super_suffix(raw: str) -> str:
    r = raw.lower()
    if " ti" in r or "-ti" in r:
        return "_ti"
    if "super" in r:
        return "_super"
    return ""


def normalise_gpu(raw: str) -> str:
    s = raw.strip()
    for pattern, builder in _GPU_PATTERNS:
        match = pattern.search(s)
        if match:
            return builder(match, s)
    return _slug(s)


# ── Storage normalisation ─────────────────────────────────────────────────────
_CAPACITY_RE = re.compile(r'(\d+)\s*(tb|gb)', re.I)


def normalise_storage(raw: str) -> str:
    s = raw.strip()
    cap_match = _CAPACITY_RE.search(s)
    cap = ""
    if cap_match:
        val, unit = cap_match.group(1), cap_match.group(2).lower()
        cap = f"_{val}{unit}"
        s = s[:cap_match.start()] + s[cap_match.end():]
    base = _slug(re.sub(r'\b(nvme|m\.?2|sata|ssd|hdd|drive|solid|state)\b', '', s, flags=re.I))
    base = re.sub(r'_+', '_', base).strip('_')
    return f"{base}{cap}" if cap else base


# ── RAM normalisation ─────────────────────────────────────────────────────────
def normalise_ram(raw: str) -> str:
    return _slug(raw)


# ── Component type detection ──────────────────────────────────────────────────
_CPU_HINTS = re.compile(
    r'\b(ryzen|intel|core\s+i[3579]|xeon|threadripper|athlon|celeron|pentium|i[3579][- ]\d{4})\b', re.I
)
_GPU_HINTS = re.compile(
    r'\b(rtx|gtx|radeon|geforce|rx\s*\d{4}|quadro|tesla\s+[a-z]|a\d{4})\b', re.I
)
_STORAGE_HINTS = re.compile(
    r'\b(ssd|nvme|m\.2|sata\s+ssd|hdd|hard\s+drive|evo|nand|970|870|sn\d{3})\b', re.I
)
_RAM_HINTS = re.compile(
    r'\b(ddr[345]|dimm|sodimm|\d+gb\s+(?:ddr|ram)|ram\s+\d+gb|\d+x\d+gb)\b', re.I
)


def detect_component_type(raw: str) -> str:
    """Return 'cpu' | 'gpu' | 'storage' | 'ram' | 'unknown'."""
    if _CPU_HINTS.search(raw):
        return "cpu"
    if _GPU_HINTS.search(raw):
        return "gpu"
    if _STORAGE_HINTS.search(raw):
        return "storage"
    if _RAM_HINTS.search(raw):
        return "ram"
    return "unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_normaliser.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add app/services/benchmark_normaliser.py tests/test_benchmark_normaliser.py
git commit -m "feat: model name normaliser for CPU/GPU/storage/RAM"
```

---

## Task 3: Benchmark fetcher (PassMark CPU + GPU + disk scraping)

**Files:**
- Create: `pc-flipper-backend/app/services/benchmark_fetcher.py`
- Create: `pc-flipper-backend/tests/test_benchmark_fetcher.py`

- [ ] **Step 1: Write failing tests (unit-level, no network)**

```python
# tests/test_benchmark_fetcher.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.benchmark_fetcher import (
    parse_passmark_cpu_table,
    parse_passmark_gpu_table,
    parse_passmark_disk_table,
    BenchmarkRecord,
)

_CPU_HTML = """
<table id="cputable">
<tr><td>1</td><td><a href="/cpu/AMD-Ryzen-9-9950X">AMD Ryzen 9 9950X</a></td><td>68,985</td></tr>
<tr><td>2</td><td><a href="/cpu/AMD-Ryzen-7-7800X3D">AMD Ryzen 7 7800X3D</a></td><td>34,212</td></tr>
<tr><td>3</td><td><a href="/cpu/Intel-Core-i9-14900K">Intel Core i9-14900K</a></td><td>63,445</td></tr>
</table>
"""

_GPU_HTML = """
<table id="gputable">
<tr><td>1</td><td><a href="/gpu/NVIDIA-GeForce-RTX-4090">NVIDIA GeForce RTX 4090</a></td><td>38,000</td></tr>
<tr><td>2</td><td><a href="/gpu/NVIDIA-GeForce-RTX-3070">NVIDIA GeForce RTX 3070</a></td><td>17,500</td></tr>
</table>
"""

_DISK_HTML = """
<table id="disktable">
<tr><td>1</td><td><a href="/disk/Samsung-970-EVO-1TB">Samsung 970 EVO 1TB</a></td><td>4,500</td></tr>
</table>
"""

def test_parse_passmark_cpu_table():
    records = parse_passmark_cpu_table(_CPU_HTML)
    assert len(records) == 3
    r = records[1]  # 7800X3D
    assert "7800X3D" in r.model
    assert r.overall_score == 34212
    assert r.component_type == "cpu"

def test_parse_passmark_gpu_table():
    records = parse_passmark_gpu_table(_GPU_HTML)
    assert len(records) == 2
    r = records[1]  # RTX 3070
    assert "3070" in r.model
    assert r.overall_score == 17500
    assert r.component_type == "gpu"

def test_parse_passmark_disk_table():
    records = parse_passmark_disk_table(_DISK_HTML)
    assert len(records) == 1
    assert records[0].overall_score == 4500
    assert records[0].component_type == "storage"

def test_benchmark_record_normalised_model():
    records = parse_passmark_cpu_table(_CPU_HTML)
    r7 = next(r for r in records if "7800" in r.model)
    assert r7.normalized_model == "amd_ryzen_7_7800x3d"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_fetcher.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement the fetcher**

```python
# app/services/benchmark_fetcher.py
"""
Fetches benchmark data from PassMark public rankings pages.
Parses HTML tables and returns BenchmarkRecord lists.
All actual HTTP calls are wrapped so tests can mock them.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional
import httpx
from bs4 import BeautifulSoup
import structlog
from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu, normalise_storage, normalise_ram

log = structlog.get_logger(__name__)

PASSMARK_CPU_URL  = "https://www.cpubenchmark.net/cpu_list.php"
PASSMARK_GPU_URL  = "https://www.videocardbenchmark.net/gpu_list.php"
PASSMARK_DISK_URL = "https://www.harddrivebenchmark.net/hdd_list.php"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}


@dataclass
class BenchmarkRecord:
    component_type: str
    model: str
    normalized_model: str
    benchmark_source: str
    overall_score: float
    gaming_score: Optional[float] = None
    workstation_score: Optional[float] = None
    single_thread_score: Optional[float] = None
    multi_thread_score: Optional[float] = None
    storage_score: Optional[float] = None
    vram_gb: Optional[float] = None
    storage_interface: Optional[str] = None
    source_url: Optional[str] = None
    confidence_score: float = 0.8
    notes: str = ""


def _clean_score(raw: str) -> float:
    """'34,212' → 34212.0"""
    return float(re.sub(r'[^\d.]', '', raw) or "0")


def _parse_generic_table(html: str, table_id: str, component_type: str) -> list[BenchmarkRecord]:
    """Parse a PassMark-style <table> with columns: rank | name | score."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": table_id})
    if not table:
        # Fallback: find first table if ID not present
        table = soup.find("table")
    if not table:
        return []

    records: list[BenchmarkRecord] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        # Name is in an <a> tag or plain text in cell[1]
        name_cell = cells[1]
        name = name_cell.get_text(strip=True)
        if not name:
            continue
        score_raw = cells[-1].get_text(strip=True) if len(cells) >= 3 else "0"
        try:
            score = _clean_score(score_raw)
        except ValueError:
            continue
        if score == 0:
            continue

        if component_type == "cpu":
            norm = normalise_cpu(name)
        elif component_type == "gpu":
            norm = normalise_gpu(name)
        elif component_type == "storage":
            norm = normalise_storage(name)
        else:
            norm = name.lower().replace(" ", "_")

        records.append(BenchmarkRecord(
            component_type=component_type,
            model=name,
            normalized_model=norm,
            benchmark_source="passmark",
            overall_score=score,
        ))
    return records


def parse_passmark_cpu_table(html: str) -> list[BenchmarkRecord]:
    return _parse_generic_table(html, "cputable", "cpu")


def parse_passmark_gpu_table(html: str) -> list[BenchmarkRecord]:
    return _parse_generic_table(html, "gputable", "gpu")


def parse_passmark_disk_table(html: str) -> list[BenchmarkRecord]:
    return _parse_generic_table(html, "disktable", "storage")


async def fetch_html(url: str, timeout: int = 30) -> str:
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def fetch_passmark_cpus() -> list[BenchmarkRecord]:
    try:
        html = await fetch_html(PASSMARK_CPU_URL)
        return parse_passmark_cpu_table(html)
    except Exception as exc:
        log.warning("benchmark_fetcher.cpu.failed", error=str(exc))
        return []


async def fetch_passmark_gpus() -> list[BenchmarkRecord]:
    try:
        html = await fetch_html(PASSMARK_GPU_URL)
        return parse_passmark_gpu_table(html)
    except Exception as exc:
        log.warning("benchmark_fetcher.gpu.failed", error=str(exc))
        return []


async def fetch_passmark_disks() -> list[BenchmarkRecord]:
    try:
        html = await fetch_html(PASSMARK_DISK_URL)
        return parse_passmark_disk_table(html)
    except Exception as exc:
        log.warning("benchmark_fetcher.disk.failed", error=str(exc))
        return []
```

- [ ] **Step 4: Run tests**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_fetcher.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/services/benchmark_fetcher.py tests/test_benchmark_fetcher.py
git commit -m "feat: PassMark benchmark fetcher with HTML parsers for CPU/GPU/disk"
```

---

## Task 4: RAM derived scorer + performance/£ engine

**Files:**
- Create: `pc-flipper-backend/app/services/benchmark_scorer.py`
- Create: `pc-flipper-backend/tests/test_benchmark_scorer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_benchmark_scorer.py
from app.services.benchmark_scorer import (
    score_ram,
    calc_performance_per_pound,
    calc_cpu_opportunity_score,
    calc_gpu_opportunity_score,
    is_gem_candidate,
    NEGATIVE_KEYWORDS,
)

def test_score_ram_ddr5_beats_ddr4():
    ddr5 = score_ram(generation="DDR5", capacity_gb=32, speed_mts=6000, cas_latency=30, dual_channel=True)
    ddr4 = score_ram(generation="DDR4", capacity_gb=32, speed_mts=3200, cas_latency=16, dual_channel=True)
    assert ddr5 > ddr4

def test_score_ram_dual_channel_bonus():
    dual = score_ram("DDR4", 32, 3200, 16, dual_channel=True)
    single = score_ram("DDR4", 32, 3200, 16, dual_channel=False)
    assert dual > single

def test_score_ram_capacity_scales():
    s32 = score_ram("DDR4", 32, 3200, 16, dual_channel=True)
    s16 = score_ram("DDR4", 16, 3200, 16, dual_channel=True)
    assert s32 > s16

def test_calc_performance_per_pound_basic():
    ppp = calc_performance_per_pound(benchmark_score=34000.0, price=195.0)
    assert abs(ppp - 174.36) < 1.0

def test_calc_performance_per_pound_zero_price():
    assert calc_performance_per_pound(10000.0, 0.0) == 0.0

def test_calc_cpu_opportunity_score_returns_0_to_100():
    score = calc_cpu_opportunity_score(
        performance_per_pound=174.0,
        marketability_score=80.0,
        demand_score=75.0,
        upgradeability_score=60.0,
        liquidity_score=70.0,
    )
    assert 0.0 <= score <= 100.0

def test_is_gem_candidate_true_when_cheap_and_performant():
    result = is_gem_candidate(
        component_price=195.0,
        avg_sold_price=245.0,
        performance_per_pound=174.0,
        category_avg_ppp=120.0,
    )
    assert result is True

def test_is_gem_candidate_false_when_overpriced():
    result = is_gem_candidate(
        component_price=250.0,
        avg_sold_price=245.0,
        performance_per_pound=90.0,
        category_avg_ppp=120.0,
    )
    assert result is False

def test_negative_keywords_list():
    assert "box only" in NEGATIVE_KEYWORDS
    assert "faulty" in NEGATIVE_KEYWORDS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_scorer.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement the scorer**

```python
# app/services/benchmark_scorer.py
"""
RAM derived scoring + performance/£ calculations + opportunity scoring + gem detection.
Does not hit network — uses data already in DB or passed directly.
"""
from __future__ import annotations
from typing import Optional

NEGATIVE_KEYWORDS = [
    "box only", "empty box", "cooler only", "fan only", "faulty",
    "broken", "untested", "for parts", "not working", "spares repair",
    "no display", "artifacting", "spares or repair",
]

# DDR generation base scores
_DDR_BASE = {"DDR5": 100.0, "DDR4": 60.0, "DDR3": 25.0, "DDR2": 5.0}

# Marketability heuristics for well-known models
_CPU_MARKETABILITY = {
    "amd_ryzen_7_7800x3d": 95, "amd_ryzen_9_7950x3d": 90,
    "amd_ryzen_5_7600x": 75, "amd_ryzen_7_7700x": 80,
    "intel_core_i9_13900k": 85, "intel_core_i7_13700k": 80,
    "intel_core_i5_12400f": 70, "intel_core_i5_13400f": 72,
    "amd_ryzen_5_5600x": 72, "amd_ryzen_7_5800x3d": 88,
}
_GPU_MARKETABILITY = {
    "nvidia_geforce_rtx_4090": 95, "nvidia_geforce_rtx_4080": 90,
    "nvidia_geforce_rtx_4070_ti": 85, "nvidia_geforce_rtx_4070": 82,
    "nvidia_geforce_rtx_3090": 80, "nvidia_geforce_rtx_3080": 82,
    "nvidia_geforce_rtx_3070": 78, "nvidia_geforce_rtx_3060_ti": 75,
    "nvidia_geforce_rtx_3060": 72, "amd_radeon_rx_7900_xtx": 85,
    "amd_radeon_rx_6800_xt": 74, "amd_radeon_rx_6700_xt": 70,
}


def score_ram(
    generation: str,
    capacity_gb: float,
    speed_mts: float,
    cas_latency: float,
    dual_channel: bool = True,
    rgb: bool = False,
    xmp: bool = False,
    expo: bool = False,
) -> float:
    """Derive a comparable RAM performance score from specs (0–200 range)."""
    base = _DDR_BASE.get(generation.upper().replace(" ", ""), 40.0)

    # Speed bonus: normalised to DDR4-3200 = 0 bonus, DDR5-6000 = +40
    speed_bonus = min(40.0, max(0.0, (speed_mts - 2133) / 100.0))

    # CAS latency penalty: lower is better; CL16 = 0, CL40 = -12
    lat_penalty = max(0.0, (cas_latency - 16) * 0.5)

    # Capacity (log-scaled so 128GB doesn't dominate)
    import math
    cap_bonus = math.log2(max(1, capacity_gb)) * 5.0

    dual_bonus = 15.0 if dual_channel else 0.0
    rgb_bonus = 5.0 if rgb else 0.0
    mem_bonus = 8.0 if (xmp or expo) else 0.0

    return round(base + speed_bonus + cap_bonus + dual_bonus + rgb_bonus + mem_bonus - lat_penalty, 1)


def calc_performance_per_pound(benchmark_score: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return round(benchmark_score / price, 2)


def calc_cpu_opportunity_score(
    performance_per_pound: float,
    marketability_score: float,
    demand_score: float,
    upgradeability_score: float,
    liquidity_score: float,
    max_ppp: float = 300.0,
) -> float:
    """Weighted CPU opportunity score, 0–100."""
    ppp_norm = min(100.0, (performance_per_pound / max(max_ppp, 1)) * 100)
    raw = (
        ppp_norm * 0.30
        + marketability_score * 0.25
        + demand_score * 0.20
        + upgradeability_score * 0.15
        + liquidity_score * 0.10
    )
    return round(min(100.0, max(0.0, raw)), 1)


def calc_gpu_opportunity_score(
    performance_per_pound: float,
    marketability_score: float,
    demand_score: float,
    vram_score: float,
    liquidity_score: float,
    max_ppp: float = 250.0,
) -> float:
    """Weighted GPU opportunity score, 0–100."""
    ppp_norm = min(100.0, (performance_per_pound / max(max_ppp, 1)) * 100)
    raw = (
        ppp_norm * 0.35
        + marketability_score * 0.25
        + demand_score * 0.20
        + vram_score * 0.10
        + liquidity_score * 0.10
    )
    return round(min(100.0, max(0.0, raw)), 1)


def calc_build_opportunity_score(
    expected_profit_score: float,
    performance_value_score: float,
    demand_score: float,
    liquidity_score: float,
    marketability_score: float,
    risk_adjustment: float = 0.0,
) -> float:
    """Build-level opportunity score (0–100)."""
    raw = (
        expected_profit_score * 0.25
        + performance_value_score * 0.20
        + demand_score * 0.20
        + liquidity_score * 0.15
        + marketability_score * 0.15
        + risk_adjustment * 0.05
    )
    return round(min(100.0, max(0.0, raw)), 1)


def get_marketability(component_type: str, normalized_model: str) -> float:
    """Return a 0–100 marketability score for known models; 50 for unknown."""
    if component_type == "cpu":
        return float(_CPU_MARKETABILITY.get(normalized_model, 50))
    if component_type == "gpu":
        return float(_GPU_MARKETABILITY.get(normalized_model, 50))
    return 50.0


def is_gem_candidate(
    component_price: float,
    avg_sold_price: float,
    performance_per_pound: float,
    category_avg_ppp: float,
    price_threshold: float = 0.75,
    ppp_threshold: float = 1.25,
) -> bool:
    """True when the component is both cheap vs market AND performant vs category average."""
    if avg_sold_price <= 0 or category_avg_ppp <= 0:
        return False
    price_ok = component_price <= avg_sold_price * price_threshold
    ppp_ok = performance_per_pound >= category_avg_ppp * ppp_threshold
    return price_ok and ppp_ok


def has_negative_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in NEGATIVE_KEYWORDS)


def calc_risk_adjustment(
    seller_suspicious: bool = False,
    price_too_low: bool = False,
    untested: bool = False,
    faulty: bool = False,
    no_photos: bool = False,
) -> float:
    """Return 0–100 risk score (higher = riskier); used as negative adjustment."""
    score = 0.0
    if seller_suspicious: score += 25
    if price_too_low:     score += 20
    if untested:          score += 20
    if faulty:            score += 30
    if no_photos:         score += 15
    return min(100.0, score)
```

- [ ] **Step 4: Run tests**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_scorer.py -v
```
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/services/benchmark_scorer.py tests/test_benchmark_scorer.py
git commit -m "feat: RAM derived scorer + performance/£ engine + gem candidate detection"
```

---

## Task 5: Benchmark refresh job (DB persistence + orchestration)

**Files:**
- Create: `pc-flipper-backend/app/services/benchmark_refresh_job.py`
- Create: `pc-flipper-backend/tests/test_benchmark_refresh_job.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_benchmark_refresh_job.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from app.services.benchmark_refresh_job import (
    is_benchmark_stale,
    build_active_model_list,
)

def test_is_stale_when_never_refreshed():
    assert is_benchmark_stale(last_refreshed_at=None, staleness_days=30) is True

def test_is_stale_when_old():
    old = (datetime.utcnow() - timedelta(days=31)).isoformat()
    assert is_benchmark_stale(last_refreshed_at=old, staleness_days=30) is True

def test_is_not_stale_when_recent():
    recent = (datetime.utcnow() - timedelta(days=5)).isoformat()
    assert is_benchmark_stale(last_refreshed_at=recent, staleness_days=30) is False

def test_build_active_model_list_deduplicates():
    models = build_active_model_list(
        playbook_models=["Ryzen 7 7800X3D", "Ryzen 7 7800X3D", "RTX 3070"],
        listing_models=["RTX 3070", "i7-13700K"],
    )
    # Should be deduplicated
    assert len(models) == len(set(m.raw for m in models))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_refresh_job.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement the refresh job**

```python
# app/services/benchmark_refresh_job.py
"""
Benchmark refresh orchestrator.
- Daily lightweight: refresh active components only
- Weekly full: refresh entire catalogue
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import structlog
from sqlalchemy import select, or_
from app.database import AsyncSessionLocal
from app.models.benchmark import HardwareBenchmark, BenchmarkRefreshRun
from app.services.benchmark_fetcher import fetch_passmark_cpus, fetch_passmark_gpus, fetch_passmark_disks, BenchmarkRecord
from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu, detect_component_type

log = structlog.get_logger(__name__)

STALENESS_DAYS = 30


@dataclass
class ActiveModel:
    raw: str
    normalized: str
    component_type: str


def is_benchmark_stale(last_refreshed_at: Optional[str], staleness_days: int = STALENESS_DAYS) -> bool:
    if not last_refreshed_at:
        return True
    try:
        last = datetime.fromisoformat(last_refreshed_at)
        return (datetime.utcnow() - last) > timedelta(days=staleness_days)
    except Exception:
        return True


def build_active_model_list(
    playbook_models: list[str],
    listing_models: list[str],
) -> list[ActiveModel]:
    seen: set[str] = set()
    result: list[ActiveModel] = []
    for raw in playbook_models + listing_models:
        if not raw or not raw.strip():
            continue
        ct = detect_component_type(raw)
        if ct == "cpu":
            norm = normalise_cpu(raw)
        elif ct == "gpu":
            norm = normalise_gpu(raw)
        else:
            norm = raw.lower().strip().replace(" ", "_")
        if norm in seen:
            continue
        seen.add(norm)
        result.append(ActiveModel(raw=raw, normalized=norm, component_type=ct))
    return result


async def _upsert_benchmark(db, record: BenchmarkRecord) -> bool:
    existing = await db.execute(
        select(HardwareBenchmark).where(
            HardwareBenchmark.normalized_model == record.normalized_model,
            HardwareBenchmark.benchmark_source == record.benchmark_source,
        )
    )
    row = existing.scalar_one_or_none()
    now = datetime.utcnow().isoformat()
    if row:
        row.overall_score = record.overall_score
        row.gaming_score = record.gaming_score
        row.workstation_score = record.workstation_score
        row.last_refreshed_at = now
        row.updated_at = now
        return False  # updated
    else:
        db.add(HardwareBenchmark(
            component_type=record.component_type,
            model=record.model,
            normalized_model=record.normalized_model,
            benchmark_source=record.benchmark_source,
            overall_score=record.overall_score,
            gaming_score=record.gaming_score,
            workstation_score=record.workstation_score,
            single_thread_score=record.single_thread_score,
            multi_thread_score=record.multi_thread_score,
            storage_score=record.storage_score,
            vram_gb=record.vram_gb,
            storage_interface=record.storage_interface,
            source_url=record.source_url,
            confidence_score=record.confidence_score,
            last_refreshed_at=now,
            updated_at=now,
        ))
        return True  # inserted


async def _get_playbook_models(db) -> list[str]:
    from app.models.playbook import Playbook
    result = await db.execute(select(Playbook).where(Playbook.status == "active"))
    playbooks = result.scalars().all()
    models: list[str] = []
    for pb in playbooks:
        us = pb.upgrade_strategy or {}
        for item in (us.get("required") or []) + (us.get("optional") or []):
            target = str(item.get("target") or "").strip()
            if target:
                # Split on "/" to handle "RTX 3060 / RX 6600"
                for part in target.split("/"):
                    if part.strip():
                        models.append(part.strip())
    return models


async def _get_active_listing_models(db) -> list[str]:
    from app.models.listing import Listing, ListingStatus
    result = await db.execute(
        select(Listing.cpu, Listing.gpu)
        .where(Listing.status == ListingStatus.active)
        .limit(500)
    )
    rows = result.all()
    models: list[str] = []
    for cpu, gpu in rows:
        if cpu:
            models.append(cpu)
        if gpu:
            models.append(gpu)
    return models


async def run_benchmark_refresh(run_type: str = "daily") -> dict:
    """
    Main entry point called by scheduler.
    run_type: 'daily' | 'weekly' | 'manual'
    """
    started_at = datetime.utcnow().isoformat()
    run_row = BenchmarkRefreshRun(
        run_type=run_type, started_at=started_at, status="running",
        source="passmark",
    )

    async with AsyncSessionLocal() as db:
        db.add(run_row)
        await db.commit()
        await db.refresh(run_row)
        run_id = run_row.id

    checked = updated = failed = 0
    errors: list[str] = []

    try:
        # Fetch all benchmark data from PassMark
        log.info("benchmark_refresh.fetching", run_type=run_type)
        cpu_records = await fetch_passmark_cpus()
        gpu_records = await fetch_passmark_gpus()
        disk_records = await fetch_passmark_disks()
        all_records = cpu_records + gpu_records + disk_records

        if run_type == "daily":
            # Daily: only upsert models active in listings/playbooks
            async with AsyncSessionLocal() as db:
                pb_models = await _get_playbook_models(db)
                listing_models = await _get_active_listing_models(db)
            active = build_active_model_list(pb_models, listing_models)
            active_norms = {m.normalized for m in active}
            all_records = [r for r in all_records if r.normalized_model in active_norms]

        log.info("benchmark_refresh.upserting", count=len(all_records))
        async with AsyncSessionLocal() as db:
            for record in all_records:
                checked += 1
                try:
                    inserted = await _upsert_benchmark(db, record)
                    updated += 1
                except Exception as exc:
                    failed += 1
                    errors.append(f"{record.model}: {exc}")
            await db.commit()

        # Mark run complete
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(BenchmarkRefreshRun).where(BenchmarkRefreshRun.id == run_id))
            run_row = result.scalar_one_or_none()
            if run_row:
                run_row.completed_at = datetime.utcnow().isoformat()
                run_row.status = "completed"
                run_row.components_checked = checked
                run_row.components_updated = updated
                run_row.components_failed = failed
                run_row.error_log = "; ".join(errors[:20]) if errors else None
            await db.commit()

        log.info("benchmark_refresh.done", checked=checked, updated=updated, failed=failed)
        return {"ok": True, "checked": checked, "updated": updated, "failed": failed}

    except Exception as exc:
        log.error("benchmark_refresh.failed", error=str(exc))
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(BenchmarkRefreshRun).where(BenchmarkRefreshRun.id == run_id))
            run_row = result.scalar_one_or_none()
            if run_row:
                run_row.completed_at = datetime.utcnow().isoformat()
                run_row.status = "failed"
                run_row.error_log = str(exc)
            await db.commit()
        return {"ok": False, "error": str(exc)}
```

- [ ] **Step 4: Run tests**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_refresh_job.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/services/benchmark_refresh_job.py tests/test_benchmark_refresh_job.py
git commit -m "feat: benchmark refresh job — daily/weekly orchestration with DB persistence"
```

---

## Task 6: Register benchmark jobs in scheduler

**Files:**
- Modify: `pc-flipper-backend/app/workers/scheduler.py`

- [ ] **Step 1: Add imports and register two jobs**

In `app/workers/scheduler.py`, after the existing imports block, add:

```python
from app.services.benchmark_refresh_job import run_benchmark_refresh
from functools import partial as _partial
```

In `_job_history` dict, add two new keys (alongside existing ones):

```python
    "benchmark_refresh_daily": deque(maxlen=50),
    "benchmark_refresh_weekly": deque(maxlen=50),
```

In `start_scheduler()`, after the `compliant_market_ingestion` job block, add:

```python
    benchmark_daily_start = now + timedelta(hours=2)
    benchmark_weekly_start = now + timedelta(hours=3)

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="benchmark_refresh_daily",
        name="Benchmark Refresh (Daily)",
        kwargs={"job_id": "benchmark_refresh_daily", "fn": _partial(run_benchmark_refresh, "daily")},
        replace_existing=True,
        max_instances=1,
        next_run_time=benchmark_daily_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(days=7),
        id="benchmark_refresh_weekly",
        name="Benchmark Refresh (Weekly)",
        kwargs={"job_id": "benchmark_refresh_weekly", "fn": _partial(run_benchmark_refresh, "weekly")},
        replace_existing=True,
        max_instances=1,
        next_run_time=benchmark_weekly_start,
    )
```

In `trigger_swarm()`, add two new elif branches before the final `raise ValueError`:

```python
    if swarm_id == "benchmark_refresh_daily":
        return await _run_job_with_history("benchmark_refresh_daily", _partial(run_benchmark_refresh, "daily"))
    if swarm_id == "benchmark_refresh_weekly":
        return await _run_job_with_history("benchmark_refresh_weekly", _partial(run_benchmark_refresh, "weekly"))
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd pc-flipper-backend && python -c "from app.workers.scheduler import start_scheduler; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/workers/scheduler.py
git commit -m "feat: register daily and weekly benchmark refresh jobs in scheduler"
```

---

## Task 7: Benchmark DB migration in main.py + router registration

**Files:**
- Modify: `pc-flipper-backend/app/main.py`
- Create: `pc-flipper-backend/app/api/benchmarks.py`

- [ ] **Step 1: Create the API router**

```python
# app/api/benchmarks.py
"""
Benchmark admin/debug API endpoints.
"""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.benchmark import HardwareBenchmark, BenchmarkRefreshRun
from app.services.benchmark_refresh_job import run_benchmark_refresh

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("/status")
async def get_benchmark_status(db: AsyncSession = Depends(get_db)):
    cpu_count = await db.scalar(
        select(func.count()).select_from(HardwareBenchmark).where(HardwareBenchmark.component_type == "cpu")
    )
    gpu_count = await db.scalar(
        select(func.count()).select_from(HardwareBenchmark).where(HardwareBenchmark.component_type == "gpu")
    )
    storage_count = await db.scalar(
        select(func.count()).select_from(HardwareBenchmark).where(HardwareBenchmark.component_type == "storage")
    )
    total = await db.scalar(select(func.count()).select_from(HardwareBenchmark))

    last_run = await db.execute(
        select(BenchmarkRefreshRun).order_by(desc(BenchmarkRefreshRun.id)).limit(1)
    )
    last_run_row = last_run.scalar_one_or_none()

    return {
        "total_benchmarks": total or 0,
        "cpu_count": cpu_count or 0,
        "gpu_count": gpu_count or 0,
        "storage_count": storage_count or 0,
        "last_run": {
            "run_type": last_run_row.run_type if last_run_row else None,
            "status": last_run_row.status if last_run_row else None,
            "started_at": last_run_row.started_at if last_run_row else None,
            "completed_at": last_run_row.completed_at if last_run_row else None,
            "components_checked": last_run_row.components_checked if last_run_row else 0,
            "components_updated": last_run_row.components_updated if last_run_row else 0,
            "components_failed": last_run_row.components_failed if last_run_row else 0,
        } if last_run_row else None,
    }


@router.get("/top")
async def get_top_benchmarks(
    component_type: str = "cpu",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HardwareBenchmark)
        .where(HardwareBenchmark.component_type == component_type)
        .order_by(desc(HardwareBenchmark.overall_score))
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "model": r.model,
            "normalized_model": r.normalized_model,
            "overall_score": r.overall_score,
            "gaming_score": r.gaming_score,
            "workstation_score": r.workstation_score,
            "last_refreshed_at": r.last_refreshed_at,
            "confidence_score": r.confidence_score,
        }
        for r in rows
    ]


@router.get("/lookup")
async def lookup_benchmark(
    model: str,
    component_type: str = "cpu",
    db: AsyncSession = Depends(get_db),
):
    from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu
    if component_type == "cpu":
        norm = normalise_cpu(model)
    elif component_type == "gpu":
        norm = normalise_gpu(model)
    else:
        norm = model.lower().replace(" ", "_")

    result = await db.execute(
        select(HardwareBenchmark).where(HardwareBenchmark.normalized_model == norm)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"found": False, "normalized_model": norm}
    return {
        "found": True,
        "model": row.model,
        "normalized_model": row.normalized_model,
        "overall_score": row.overall_score,
        "gaming_score": row.gaming_score,
        "workstation_score": row.workstation_score,
        "last_refreshed_at": row.last_refreshed_at,
        "confidence_score": row.confidence_score,
    }


@router.get("/refresh-runs")
async def list_refresh_runs(limit: int = 10, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BenchmarkRefreshRun).order_by(desc(BenchmarkRefreshRun.id)).limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "run_type": r.run_type,
            "status": r.status,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "components_checked": r.components_checked,
            "components_updated": r.components_updated,
            "components_failed": r.components_failed,
            "error_log": r.error_log,
        }
        for r in rows
    ]


@router.post("/refresh")
async def trigger_refresh(run_type: str = "manual"):
    import asyncio
    asyncio.create_task(run_benchmark_refresh(run_type))
    return {"ok": True, "message": f"Benchmark refresh ({run_type}) started in background"}
```

- [ ] **Step 2: Register the router in `main.py`**

Add near the other API imports at the top of `app/main.py`:

```python
from app.api.benchmarks import router as benchmarks_router
```

Add near the other `app.include_router(...)` calls:

```python
app.include_router(benchmarks_router, prefix="/api")
```

- [ ] **Step 3: Verify server starts**

```bash
cd pc-flipper-backend && python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/api/benchmarks.py app/main.py
git commit -m "feat: benchmarks API router — status, top, lookup, refresh-runs, manual trigger"
```

---

## Task 8: Integrate benchmark scores into classifier gem scoring

**Files:**
- Modify: `pc-flipper-backend/app/services/classifier.py`

The `score_listing()` function already accepts `cpu`, `gpu`, `ram_type`, `ram_gb` parameters. We add an optional `benchmark_data` parameter that, when present, adds performance/£ signals.

- [ ] **Step 1: Write failing test**

```python
# tests/test_benchmark_integration.py
from app.services.classifier import score_listing

def test_high_ppp_cpu_boosts_gem_score():
    result_with = score_listing(
        title="Gaming PC Ryzen 7 7800X3D RTX 3070",
        price=195.0,
        estimated_profit=120.0,
        cpu="Ryzen 7 7800X3D",
        ram_gb=32,
        ram_type="DDR5",
        storage_gb=1000,
        gpu="RTX 3070",
        has_psu=True,
        location="UK",
        profit_low=80.0,
        profit_high=160.0,
        benchmark_data={
            "cpu_overall_score": 34000,
            "cpu_performance_per_pound": 174.0,
            "category_avg_ppp": 100.0,
        },
    )
    result_without = score_listing(
        title="Gaming PC Ryzen 7 7800X3D RTX 3070",
        price=195.0,
        estimated_profit=120.0,
        cpu="Ryzen 7 7800X3D",
        ram_gb=32,
        ram_type="DDR5",
        storage_gb=1000,
        gpu="RTX 3070",
        has_psu=True,
        location="UK",
        profit_low=80.0,
        profit_high=160.0,
    )
    assert result_with.score >= result_without.score
    assert any("performance/£" in s for s in result_with.signals)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_integration.py -v
```
Expected: `TypeError` (unexpected keyword argument)

- [ ] **Step 3: Modify `score_listing` in `classifier.py`**

In `classifier.py`, change the `score_listing` function signature to add an optional parameter at the end:

```python
def score_listing(
    title: str,
    price: float,
    estimated_profit: float | None,
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    gpu: str | None,
    has_psu: bool,
    location: str | None,
    profit_low: float | None = None,
    profit_high: float | None = None,
    benchmark_data: dict | None = None,   # NEW
) -> ScoringResult:
```

After the existing "Normalise raw score" line (before `result.score = round(...)`), add this block to apply the benchmark bonus:

```python
    # ── Benchmark performance/£ bonus ────────────────────────────────────────
    if benchmark_data:
        cpu_ppp = benchmark_data.get("cpu_performance_per_pound") or 0
        cat_avg = benchmark_data.get("category_avg_ppp") or 0
        if cpu_ppp > 0 and cat_avg > 0:
            ratio = cpu_ppp / cat_avg
            if ratio >= 1.5:
                result.score += 30
                result.signals.append(f"performance/£ {ratio:.1f}x above average")
            elif ratio >= 1.25:
                result.score += 18
                result.signals.append(f"performance/£ {ratio:.1f}x above average")
            elif ratio >= 1.0:
                result.score += 8
                result.signals.append("performance/£ at market average")
```

- [ ] **Step 4: Run tests**

```bash
cd pc-flipper-backend && python -m pytest tests/test_benchmark_integration.py tests/test_classifier_platform_preference.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add app/services/classifier.py tests/test_benchmark_integration.py
git commit -m "feat: integrate benchmark performance/£ into classifier gem score signals"
```

---

## Task 9: Frontend benchmark admin page

**Files:**
- Create: `pc-flipper/app/benchmarks/page.tsx`
- Modify: `pc-flipper/lib/api.ts` (add benchmark API calls)
- Modify: `pc-flipper/app/layout.tsx` (add nav link)

- [ ] **Step 1: Add benchmark API methods to `lib/api.ts`**

In `pc-flipper/lib/api.ts`, find the `api` export object and add a `benchmarks` key:

```typescript
  benchmarks: {
    status: () => apiFetch<{
      total_benchmarks: number;
      cpu_count: number;
      gpu_count: number;
      storage_count: number;
      last_run: {
        run_type: string | null;
        status: string | null;
        started_at: string | null;
        completed_at: string | null;
        components_checked: number;
        components_updated: number;
        components_failed: number;
      } | null;
    }>("/benchmarks/status"),
    top: (component_type = "cpu", limit = 20) =>
      apiFetch<Array<{
        model: string;
        normalized_model: string;
        overall_score: number;
        gaming_score: number | null;
        last_refreshed_at: string | null;
        confidence_score: number;
      }>>(`/benchmarks/top?component_type=${component_type}&limit=${limit}`),
    refreshRuns: (limit = 10) =>
      apiFetch<Array<{
        id: number;
        run_type: string;
        status: string;
        started_at: string;
        completed_at: string | null;
        components_checked: number;
        components_updated: number;
        components_failed: number;
        error_log: string | null;
      }>>(`/benchmarks/refresh-runs?limit=${limit}`),
    triggerRefresh: (run_type = "manual") =>
      apiFetch<{ ok: boolean; message: string }>("/benchmarks/refresh", {
        method: "POST",
        body: JSON.stringify({}),
        headers: { "Content-Type": "application/json" },
        // Pass run_type as query param
      }).then(() =>
        apiFetch<{ ok: boolean; message: string }>(
          `/benchmarks/refresh?run_type=${run_type}`,
          { method: "POST" }
        )
      ),
  },
```

- [ ] **Step 2: Create the benchmarks page**

```tsx
// pc-flipper/app/benchmarks/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Cpu, Zap, RefreshCw, BarChart3, Clock, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface BenchmarkStatus {
  total_benchmarks: number;
  cpu_count: number;
  gpu_count: number;
  storage_count: number;
  last_run: {
    run_type: string | null;
    status: string | null;
    started_at: string | null;
    completed_at: string | null;
    components_checked: number;
    components_updated: number;
    components_failed: number;
  } | null;
}

interface TopBenchmark {
  model: string;
  normalized_model: string;
  overall_score: number;
  gaming_score: number | null;
  last_refreshed_at: string | null;
  confidence_score: number;
}

interface RefreshRun {
  id: number;
  run_type: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  components_checked: number;
  components_updated: number;
  components_failed: number;
  error_log: string | null;
}

const STATUS_ICON = {
  completed: <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />,
  failed: <XCircle className="w-3.5 h-3.5 text-red-400" />,
  running: <RefreshCw className="w-3.5 h-3.5 text-yellow-400 animate-spin" />,
};

export default function BenchmarksPage() {
  const [status, setStatus] = useState<BenchmarkStatus | null>(null);
  const [topCpus, setTopCpus] = useState<TopBenchmark[]>([]);
  const [topGpus, setTopGpus] = useState<TopBenchmark[]>([]);
  const [runs, setRuns] = useState<RefreshRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<"cpu" | "gpu">("cpu");

  const load = async () => {
    setLoading(true);
    try {
      const [s, cpus, gpus, r] = await Promise.all([
        api.benchmarks.status(),
        api.benchmarks.top("cpu", 20),
        api.benchmarks.top("gpu", 20),
        api.benchmarks.refreshRuns(10),
      ]);
      setStatus(s);
      setTopCpus(cpus as TopBenchmark[]);
      setTopGpus(gpus as TopBenchmark[]);
      setRuns(r as RefreshRun[]);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const triggerRefresh = async (type: "daily" | "weekly" | "manual") => {
    setRefreshing(true);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/benchmarks/refresh?run_type=${type}`, {
        method: "POST",
      });
      setTimeout(() => { void load(); }, 2000);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const topList = activeTab === "cpu" ? topCpus : topGpus;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Cpu className="w-5 h-5" /> Benchmark Intelligence
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Performance data for CPUs, GPUs and storage — powers gem detection and performance/£ scoring
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void triggerRefresh("daily")} disabled={refreshing}>
            <Zap className="w-3.5 h-3.5" /> Run Daily Refresh
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void triggerRefresh("weekly")} disabled={refreshing}>
            <BarChart3 className="w-3.5 h-3.5" /> Run Full Refresh
          </Button>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Benchmarks", value: status?.total_benchmarks ?? 0, color: "text-slate-300" },
          { label: "CPUs", value: status?.cpu_count ?? 0, color: "text-[#00dc82]" },
          { label: "GPUs", value: status?.gpu_count ?? 0, color: "text-cyan-400" },
          { label: "Storage Devices", value: status?.storage_count ?? 0, color: "text-purple-400" },
        ].map(({ label, value, color }) => (
          <Card key={label}>
            <CardContent className="pt-5">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">{label}</div>
              <div className={`text-2xl font-bold ${color}`}>{value.toLocaleString()}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Last run */}
      {status?.last_run && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-slate-400" /> Last Refresh Run
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex flex-wrap gap-6 text-sm">
              <div>
                <span className="text-slate-500">Type: </span>
                <span className="text-slate-200 font-mono">{status.last_run.run_type ?? "—"}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-slate-500">Status: </span>
                {STATUS_ICON[status.last_run.status as keyof typeof STATUS_ICON] ?? <AlertTriangle className="w-3.5 h-3.5 text-slate-500" />}
                <span className="text-slate-200 font-mono">{status.last_run.status ?? "—"}</span>
              </div>
              <div>
                <span className="text-slate-500">Checked: </span>
                <span className="text-slate-200">{status.last_run.components_checked}</span>
              </div>
              <div>
                <span className="text-slate-500">Updated: </span>
                <span className="text-emerald-400">{status.last_run.components_updated}</span>
              </div>
              {status.last_run.components_failed > 0 && (
                <div>
                  <span className="text-slate-500">Failed: </span>
                  <span className="text-red-400">{status.last_run.components_failed}</span>
                </div>
              )}
              <div>
                <span className="text-slate-500">Started: </span>
                <span className="text-slate-400 font-mono text-xs">
                  {status.last_run.started_at ? new Date(status.last_run.started_at).toLocaleString() : "—"}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Top benchmarks table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-3.5 h-3.5 text-[#00dc82]" /> Top Benchmarks
            </CardTitle>
            <div className="flex gap-1">
              {(["cpu", "gpu"] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 rounded text-xs font-mono uppercase tracking-wider transition-colors ${
                    activeTab === tab
                      ? "bg-[#00dc82] text-[#080c14]"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {topList.length === 0 ? (
            <div className="text-center text-sm text-slate-600 py-8">
              No benchmark data yet. Click "Run Full Refresh" to fetch PassMark data.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-[#1e2d45]">
                    <th className="text-left pb-2 pr-4">#</th>
                    <th className="text-left pb-2 pr-4">Model</th>
                    <th className="text-right pb-2 pr-4">Overall Score</th>
                    <th className="text-right pb-2 pr-4">Gaming Score</th>
                    <th className="text-right pb-2">Last Refreshed</th>
                  </tr>
                </thead>
                <tbody>
                  {topList.map((b, i) => (
                    <tr key={b.normalized_model} className="border-b border-[#0f1c2e] hover:bg-[#0a1119] transition-colors">
                      <td className="py-2 pr-4 text-slate-600">{i + 1}</td>
                      <td className="py-2 pr-4">
                        <div className="text-slate-200 font-medium">{b.model}</div>
                        <div className="text-slate-600 font-mono text-[10px]">{b.normalized_model}</div>
                      </td>
                      <td className="py-2 pr-4 text-right text-[#00dc82] font-mono font-semibold">
                        {b.overall_score?.toLocaleString() ?? "—"}
                      </td>
                      <td className="py-2 pr-4 text-right text-cyan-400 font-mono">
                        {b.gaming_score?.toLocaleString() ?? "—"}
                      </td>
                      <td className="py-2 text-right text-slate-600 font-mono text-[10px]">
                        {b.last_refreshed_at ? new Date(b.last_refreshed_at).toLocaleDateString() : "never"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Refresh run history */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-slate-400" /> Refresh History
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0 space-y-2">
          {runs.length === 0 ? (
            <div className="text-xs text-slate-600 text-center py-4">No refresh runs yet.</div>
          ) : runs.map(run => (
            <div key={run.id} className="flex items-center justify-between p-3 rounded-lg bg-[#0a1119] border border-[#1e2d45]">
              <div className="flex items-center gap-3">
                {STATUS_ICON[run.status as keyof typeof STATUS_ICON] ?? <AlertTriangle className="w-3.5 h-3.5 text-slate-500" />}
                <div>
                  <div className="text-xs text-slate-300 font-mono">
                    {run.run_type} · {run.status}
                  </div>
                  <div className="text-[10px] text-slate-600">
                    {new Date(run.started_at).toLocaleString()}
                  </div>
                </div>
              </div>
              <div className="text-right text-xs">
                <div className="text-slate-400">{run.components_checked} checked</div>
                <div className="text-emerald-400">{run.components_updated} updated</div>
                {run.components_failed > 0 && (
                  <div className="text-red-400">{run.components_failed} failed</div>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Add nav link to layout**

In `pc-flipper/app/layout.tsx`, find the nav links array and add a benchmarks entry. Look for the pattern where other page links are defined (e.g. `{ href: "/intel", label: "Analytics" }`). Add:

```typescript
{ href: "/benchmarks", label: "Benchmarks", icon: "Cpu" }
```

(Match the exact structure of existing nav items.)

- [ ] **Step 4: Verify frontend builds**

```bash
cd pc-flipper && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add pc-flipper/app/benchmarks/page.tsx pc-flipper/lib/api.ts pc-flipper/app/layout.tsx
git commit -m "feat: benchmark admin/debug UI with top rankings, refresh status, and run history"
```

---

## Task 10: Build performance summary model

**Files:**
- Create: `pc-flipper-backend/app/services/build_performance_summary.py`
- Create: `pc-flipper-backend/tests/test_build_performance_summary.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_build_performance_summary.py
from app.services.build_performance_summary import (
    generate_build_performance_summary,
    generate_listing_performance_text,
    classify_tier,
)

def test_classify_tier_cpu():
    assert classify_tier("cpu", 60000) == "Flagship"
    assert classify_tier("cpu", 30000) == "High-End"
    assert classify_tier("cpu", 15000) == "Mid-Range"
    assert classify_tier("cpu", 5000) == "Entry"

def test_classify_tier_gpu():
    assert classify_tier("gpu", 30000) == "Flagship"
    assert classify_tier("gpu", 15000) == "High-End"
    assert classify_tier("gpu", 8000) == "Mid-Range"
    assert classify_tier("gpu", 2000) == "Entry"

def test_generate_build_performance_summary_structure():
    summary = generate_build_performance_summary(
        cpu_model="Ryzen 7 7800X3D",
        cpu_score=34000,
        gpu_model="RTX 3070",
        gpu_score=17500,
        vram_gb=8,
        ram_gb=32,
        ram_speed_mts=5600,
        storage_gb=1000,
        storage_interface="PCIe 4.0 NVMe",
    )
    assert "cpu" in summary
    assert "gpu" in summary
    assert "overall" in summary
    assert summary["cpu"]["tier"] == "High-End"
    assert summary["gpu"]["tier"] == "High-End"

def test_generate_listing_performance_text_gaming():
    text = generate_listing_performance_text(
        use_case="gaming",
        cpu_model="Ryzen 7 7800X3D",
        cpu_tier="High-End",
        gpu_model="RTX 3070",
        gpu_tier="High-End",
        ram_gb=32,
        storage_interface="PCIe 4.0 NVMe",
    )
    assert "gaming" in text.lower()
    assert "7800X3D" in text or "Ryzen 7" in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pc-flipper-backend && python -m pytest tests/test_build_performance_summary.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement the module**

```python
# app/services/build_performance_summary.py
"""
Generates buyer-facing performance summaries and listing text from benchmark data.
No network calls — pure data transformation.
"""
from __future__ import annotations
from typing import Optional

# Score thresholds for tier labels
_CPU_TIERS = [(50000, "Flagship"), (25000, "High-End"), (10000, "Mid-Range"), (0, "Entry")]
_GPU_TIERS = [(25000, "Flagship"), (12000, "High-End"), (6000, "Mid-Range"), (0, "Entry")]


def classify_tier(component_type: str, score: float) -> str:
    thresholds = _CPU_TIERS if component_type == "cpu" else _GPU_TIERS
    for threshold, label in thresholds:
        if score >= threshold:
            return label
    return "Entry"


def generate_build_performance_summary(
    cpu_model: str,
    cpu_score: float,
    gpu_model: str,
    gpu_score: float,
    vram_gb: float,
    ram_gb: float,
    ram_speed_mts: float,
    storage_gb: float,
    storage_interface: str,
) -> dict:
    cpu_tier = classify_tier("cpu", cpu_score)
    gpu_tier = classify_tier("gpu", gpu_score)

    cpu_strengths = []
    if cpu_score >= 30000:
        cpu_strengths.append("Excellent multi-core performance")
    if "3D" in cpu_model or "x3d" in cpu_model.lower():
        cpu_strengths.append("3D V-Cache gaming optimised")
    if cpu_score >= 15000:
        cpu_strengths.append("Strong for streaming and encoding")

    gpu_strengths = []
    if vram_gb >= 16:
        gpu_strengths.append(f"{vram_gb:.0f}GB VRAM — AI/4K capable")
    elif vram_gb >= 12:
        gpu_strengths.append(f"{vram_gb:.0f}GB VRAM — excellent 1440p")
    elif vram_gb >= 8:
        gpu_strengths.append(f"{vram_gb:.0f}GB VRAM — solid 1080p/1440p")
    if gpu_score >= 15000:
        gpu_strengths.append("High-FPS 1440p gaming")

    overall_gaming = round((cpu_score * 0.3 + gpu_score * 0.7) / 500, 1)
    overall_workstation = round((cpu_score * 0.6 + gpu_score * 0.4) / 500, 1)
    overall_ai = round((gpu_score * 0.6 + vram_gb * 500 + cpu_score * 0.1) / 500, 1)
    overall_value = round((overall_gaming + overall_workstation) / 2, 1)

    return {
        "cpu": {
            "model": cpu_model,
            "benchmark_score": cpu_score,
            "tier": cpu_tier,
            "strengths": cpu_strengths,
        },
        "gpu": {
            "model": gpu_model,
            "benchmark_score": gpu_score,
            "tier": gpu_tier,
            "vram_gb": vram_gb,
            "strengths": gpu_strengths,
        },
        "ram": {
            "capacity_gb": ram_gb,
            "speed_mts": ram_speed_mts,
            "score": round(ram_gb * (ram_speed_mts / 3200) * 10, 0),
        },
        "storage": {
            "capacity_gb": storage_gb,
            "interface": storage_interface,
            "score": _storage_interface_score(storage_interface),
        },
        "overall": {
            "gaming_score": min(100.0, overall_gaming),
            "workstation_score": min(100.0, overall_workstation),
            "ai_score": min(100.0, overall_ai),
            "value_score": min(100.0, overall_value),
        },
    }


def _storage_interface_score(interface: str) -> float:
    i = (interface or "").lower()
    if "pcie 5" in i or "gen5" in i:
        return 100.0
    if "pcie 4" in i or "gen4" in i:
        return 85.0
    if "pcie 3" in i or "gen3" in i or "nvme" in i:
        return 70.0
    if "sata ssd" in i or "sata" in i:
        return 45.0
    if "hdd" in i:
        return 15.0
    return 50.0


_USE_CASE_TEMPLATES = {
    "gaming": (
        "Built for high-FPS 1080p / 1440p gaming\n"
        "{cpu_model} gaming CPU ({cpu_tier})\n"
        "{gpu_model} graphics ({gpu_tier})\n"
        "{ram_gb}GB RAM\n"
        "{storage_gb}GB {storage_interface}"
    ),
    "workstation": (
        "Built for coding, Docker and multitasking\n"
        "{cpu_model} ({cpu_tier} — multi-core powerhouse)\n"
        "{ram_gb}GB RAM\n"
        "{storage_gb}GB {storage_interface}\n"
        "Ideal for development workloads"
    ),
    "ai": (
        "Designed for local AI experimentation\n"
        "{gpu_model} GPU ({gpu_tier})\n"
        "{ram_gb}GB RAM\n"
        "{storage_gb}GB {storage_interface}\n"
        "Ready for Ollama / Stable Diffusion workloads"
    ),
    "creator": (
        "Built for content creation and streaming\n"
        "{cpu_model} ({cpu_tier})\n"
        "{gpu_model} graphics\n"
        "{ram_gb}GB RAM · {storage_gb}GB {storage_interface}"
    ),
}


def generate_listing_performance_text(
    use_case: str,
    cpu_model: str,
    cpu_tier: str,
    gpu_model: str,
    gpu_tier: str,
    ram_gb: float,
    storage_interface: str,
    storage_gb: float = 1000,
    vram_gb: Optional[float] = None,
) -> str:
    template = _USE_CASE_TEMPLATES.get(use_case, _USE_CASE_TEMPLATES["gaming"])
    return template.format(
        cpu_model=cpu_model,
        cpu_tier=cpu_tier,
        gpu_model=gpu_model,
        gpu_tier=gpu_tier,
        ram_gb=int(ram_gb),
        storage_gb=int(storage_gb),
        storage_interface=storage_interface,
        vram_gb=int(vram_gb) if vram_gb else "?",
    )
```

- [ ] **Step 4: Run tests**

```bash
cd pc-flipper-backend && python -m pytest tests/test_build_performance_summary.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/services/build_performance_summary.py tests/test_build_performance_summary.py
git commit -m "feat: build performance summary and buyer-facing listing performance text generator"
```

---

## Task 11: Wire `_migrate_add_columns` for new tables on startup

**Files:**
- Modify: `pc-flipper-backend/app/main.py`

The three new models (`hardware_benchmarks`, `component_performance_metrics`, `benchmark_refresh_runs`) are created via `Base.metadata.create_all` at startup. However, existing deployments may need an explicit column migration. Add entries to `_migrate_add_columns()`.

- [ ] **Step 1: Add entries**

In `app/main.py`, inside `_migrate_add_columns()`, in the `new_cols` list, append:

```python
        # Benchmark system — new tables created by create_all; no ALTER needed.
        # Listed here so future column additions have a home to land in.
        # (If hardware_benchmarks doesn't exist yet, create_all handles it.)
```

No actual column ALTER entries are needed for the new tables since they're wholly new. The comment is a placeholder for future additions. This task is about ensuring the import is correct.

- [ ] **Step 2: Verify `app/models/__init__.py` imports the new model**

```bash
cd pc-flipper-backend && python -c "from app.models.benchmark import HardwareBenchmark; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Full startup smoke test**

```bash
cd pc-flipper-backend && python -c "
import asyncio
from app.database import engine, Base
from app import models  # noqa
async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created OK')
    await engine.dispose()
asyncio.run(run())
"
```
Expected: `Tables created OK`

- [ ] **Step 4: Run full test suite**

```bash
cd pc-flipper-backend && python -m pytest tests/ -v --tb=short
```
Expected: all previously-passing tests still pass; new tests pass too.

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/models/__init__.py
git commit -m "chore: ensure benchmark models imported for create_all; smoke test passes"
```

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec requirement | Task covering it |
|---|---|
| `hardware_benchmarks` DB table | Task 1 |
| `component_performance_metrics` DB table | Task 1 |
| `benchmark_refresh_runs` DB table | Task 1 |
| Model normalisation layer | Task 2 |
| CPU benchmark retrieval (PassMark) | Task 3 |
| GPU benchmark retrieval (PassMark) | Task 3 |
| Storage benchmark retrieval (PassMark) | Task 3 |
| RAM derived scoring | Task 4 |
| `performance_per_pound` calculation | Task 4 |
| Opportunity score formulas (CPU/GPU/build) | Task 4 |
| `is_gem_candidate` logic | Task 4 |
| Negative keywords anti-garbage | Task 4 |
| Daily + weekly refresh schedule | Tasks 5+6 |
| Staleness detection (30-day rule) | Task 5 |
| Benchmark refresh persisted in DB | Task 5 |
| Active model scoping for daily refresh | Task 5 |
| Scheduler registration | Task 6 |
| Admin/debug API endpoints | Task 7 |
| Benchmark performance/£ integrated into gem scoring | Task 8 |
| Admin UI page (frontend) | Task 9 |
| Build-level performance summary model | Task 10 |
| Buyer-facing listing performance text | Task 10 |
| Missing benchmark data doesn't break system | All — functions return None/fallback gracefully |
| Use-case weighted scoring | Task 4 (scorer), Task 10 (summary text templates) |
| Risk adjustment | Task 4 (`calc_risk_adjustment`) |

**Gaps identified and addressed:**
- The spec asks for `risk_adjustment` in `calc_build_opportunity_score` — added in Task 4.
- The spec asks for `generate_listing_performance_text` for marketing copy — added in Task 10.
- The spec asks for a router to be registered — addressed in Task 7.

**Placeholder scan:** None found — all steps contain actual code.

**Type consistency:** `BenchmarkRecord` defined in Task 3 and used in Task 5; `ActiveModel` defined in Task 5 tested in same task; `build_performance_summary` dict structure defined and tested in Task 10.
