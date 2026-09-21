"""
Fetches benchmark data from PassMark public rankings pages.
Parses HTML tables and returns BenchmarkRecord lists.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional
import httpx
from bs4 import BeautifulSoup
import structlog
from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu, normalise_storage

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


def _parse_generic_table(
    html: str, table_id: str | tuple[str, ...], component_type: str
) -> list[BenchmarkRecord]:
    soup = BeautifulSoup(html, "html.parser")
    table_ids = (table_id,) if isinstance(table_id, str) else table_id
    table = next(
        (soup.find("table", {"id": candidate}) for candidate in table_ids if soup.find("table", {"id": candidate})),
        None,
    )
    if not table:
        return []

    headers = [header.get_text(" ", strip=True).lower() for header in table.find_all("th")]
    name_index = next(
        (index for index, header in enumerate(headers) if "name" in header or "model" in header),
        None,
    )
    score_index = next(
        (
            index
            for index, header in enumerate(headers)
            if "mark" in header and "rank" not in header and "value" not in header
        ),
        None,
    )

    records: list[BenchmarkRecord] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        if name_index is not None and name_index < len(cells):
            resolved_name_index = name_index
        else:
            resolved_name_index = next(
                (index for index, cell in enumerate(cells) if cell.find("a")), None
            )
        if resolved_name_index is None:
            continue

        name_cell = cells[resolved_name_index]
        name = name_cell.get_text(strip=True)
        if not name or not re.search(r"[A-Za-z]", name):
            continue
        if score_index is not None and score_index < len(cells):
            score_raw = cells[score_index].get_text(strip=True)
        else:
            score_raw = next(
                (
                    cell.get_text(strip=True)
                    for cell in cells[resolved_name_index + 1 :]
                    if _clean_score(cell.get_text(strip=True)) > 0
                ),
                "0",
            )
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
    # PassMark currently uses ``cputable`` on both CPU and GPU list pages;
    # retain the historical ID for archived fixtures and older source pages.
    return _parse_generic_table(html, ("cputable", "gputable"), "gpu")


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
