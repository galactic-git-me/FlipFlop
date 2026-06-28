from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.market_ingestion import ListingNormalized, ListingRaw, SourceRun


@dataclass
class SourceSpec:
    name: str
    kind: str
    path: str


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _fingerprint(source: str, external_id: str, title: str, price: float | None, location_text: str | None) -> str:
    payload = "|".join(
        [
            source.strip().lower(),
            external_id.strip().lower(),
            title.strip().lower(),
            f"{price:.2f}" if price is not None else "",
            (location_text or "").strip().lower(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_row(source: str, row: dict[str, Any]) -> dict[str, Any]:
    external_id = str(row.get("external_id") or row.get("id") or row.get("listing_id") or "").strip()
    if not external_id:
        raise ValueError("Row is missing external_id/id/listing_id")

    title = str(row.get("title") or "").strip()
    if not title:
        raise ValueError("Row is missing title")

    price = _to_float(row.get("price"))
    location_text = (row.get("location_text") or row.get("location") or "").strip() or None
    url = row.get("url")
    if isinstance(url, str) and "example.com" in url.lower():
        raise ValueError("Blocked reference URL (example.com). Use a real source URL.")

    normalized = {
        "source": source,
        "external_id": external_id,
        "title": title,
        "price": price,
        "currency": (row.get("currency") or "USD"),
        "location_text": location_text,
        "category": row.get("category"),
        "condition": row.get("condition"),
        "url": url,
        "seller_type": row.get("seller_type"),
        "listed_at": _to_dt(row.get("listed_at")),
        "dedupe_fingerprint": _fingerprint(source, external_id, title, price, location_text),
        "last_seen_at": _utcnow(),
    }
    return normalized


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [dict(row) for row in data]
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [dict(row) for row in data["items"]]
    raise ValueError(f"Unsupported JSON payload in {path}")


def _load_source_rows(spec: SourceSpec) -> list[dict[str, Any]]:
    source_path = Path(spec.path).expanduser()
    if not source_path.is_absolute():
        source_path = (Path.cwd() / source_path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source path does not exist: {source_path}")
    if spec.kind == "csv":
        return _read_csv(source_path)
    if spec.kind == "json":
        return _read_json(source_path)
    raise ValueError(f"Unsupported source kind: {spec.kind}")


def _load_manifest(path: str) -> list[SourceSpec]:
    manifest_path = Path(path).expanduser()
    if not manifest_path.is_absolute():
        manifest_path = (Path.cwd() / manifest_path).resolve()
    if not manifest_path.exists():
        return []
    with manifest_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise ValueError("Manifest must be an object with a 'sources' array")
    specs: list[SourceSpec] = []
    for entry in payload["sources"]:
        name = str(entry["name"]).strip()
        lowered_name = name.lower()
        if any(token in lowered_name for token in ("sample", "mock", "dummy", "fake")):
            raise ValueError(f"Blocked non-production source name: {name}")
        specs.append(
            SourceSpec(
                name=name,
                kind=str(entry.get("kind", "")).strip().lower(),
                path=str(entry["path"]).strip(),
            )
        )
    return specs


async def _ingest_source(spec: SourceSpec) -> dict[str, Any]:
    now = _utcnow()
    rows = _load_source_rows(spec)
    source_run = SourceRun(
        source=spec.name,
        status="running",
        records_seen=len(rows),
        started_at=now,
    )

    inserted = 0
    updated = 0
    async with AsyncSessionLocal() as db:
        db.add(source_run)
        await db.flush()
        try:
            for raw in rows:
                normalized = _normalize_row(spec.name, raw)

                existing_raw = await db.scalar(
                    select(ListingRaw).where(
                        ListingRaw.source == spec.name,
                        ListingRaw.external_id == normalized["external_id"],
                    )
                )
                if existing_raw is None:
                    db.add(
                        ListingRaw(
                            source=spec.name,
                            external_id=normalized["external_id"],
                            payload=raw,
                            ingested_at=_utcnow(),
                        )
                    )
                else:
                    existing_raw.payload = raw
                    existing_raw.ingested_at = _utcnow()

                existing_norm = await db.scalar(
                    select(ListingNormalized).where(
                        ListingNormalized.source == spec.name,
                        ListingNormalized.external_id == normalized["external_id"],
                    )
                )
                if existing_norm is None:
                    db.add(ListingNormalized(**normalized))
                    inserted += 1
                else:
                    for key, value in normalized.items():
                        setattr(existing_norm, key, value)
                    updated += 1

            source_run.status = "success"
            source_run.records_inserted = inserted
            source_run.records_updated = updated
            source_run.finished_at = _utcnow()
            source_run.message = f"Ingested {len(rows)} records from {spec.name}"
            await db.commit()
            return {
                "source": spec.name,
                "seen": len(rows),
                "inserted": inserted,
                "updated": updated,
                "ok": True,
            }
        except Exception as exc:
            source_run.status = "failed"
            source_run.finished_at = _utcnow()
            source_run.message = str(exc)
            await db.commit()
            raise


async def run_compliant_market_ingestion() -> dict[str, Any]:
    settings = get_settings()
    specs = _load_manifest(settings.compliant_ingestion_manifest_path)
    if not specs:
        return {"ok": True, "sources": 0, "message": "No compliant ingestion sources configured"}

    results: list[dict[str, Any]] = []
    total_inserted = 0
    total_updated = 0
    for spec in specs:
        result = await _ingest_source(spec)
        results.append(result)
        total_inserted += int(result["inserted"])
        total_updated += int(result["updated"])

    return {
        "ok": True,
        "sources": len(results),
        "inserted": total_inserted,
        "updated": total_updated,
        "results": results,
    }
