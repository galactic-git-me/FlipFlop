from fastapi import APIRouter

from app.services.search_telemetry import (
    latest_by_source,
    latest_by_source_db,
    latest_records,
    latest_records_db,
)
from app.database import AsyncSessionLocal
from app.models.search_telemetry import SearchTelemetry
from sqlalchemy import select

router = APIRouter(prefix="/search-telemetry", tags=["search-telemetry"])


@router.get("/recent")
async def get_recent(limit: int = 500):
    try:
        return {"items": await latest_records_db(limit=limit)}
    except Exception:
        return {"items": latest_records(limit=limit)}


@router.get("/by-source")
async def get_recent_by_source(limit: int = 1000):
    try:
        grouped = await latest_by_source_db(limit=limit)
    except Exception:
        grouped = latest_by_source(limit=limit)
    summary = {
        source: {
            "terms": len(rows),
            "found_total": sum(int(r.get("found", 0)) for r in rows),
            "new_total": sum(int(r.get("new", 0)) for r in rows),
            "errors": sum(1 for r in rows if r.get("error")),
        }
        for source, rows in grouped.items()
    }
    return {"summary": summary, "items": grouped}


@router.get("/case-runs")
async def get_case_source_runs(limit: int = 50):
    """Run-level audit trail for the fast-delivery PC-case suppliers.

    A case catalogue run is only successful when both Amazon and
    Overclockers return at least one listing without a scrape error.
    """
    row_limit = max(1, min(limit, 250)) * 50
    async with AsyncSessionLocal() as db:
        rows = list((await db.execute(
            select(SearchTelemetry)
            .where(
                SearchTelemetry.run_id.like("cases-%"),
                SearchTelemetry.source.in_(("Cases:Amazon", "Cases:Overclockers")),
            )
            .order_by(SearchTelemetry.ts.desc())
            .limit(row_limit)
        )).scalars().all())

    grouped: dict[str, dict] = {}
    for row in rows:
        if not row.run_id:
            continue
        run = grouped.setdefault(row.run_id, {
            "runId": row.run_id,
            "startedAt": row.ts,
            "finishedAt": row.ts,
            "sources": {},
        })
        run["startedAt"] = min(run["startedAt"], row.ts)
        run["finishedAt"] = max(run["finishedAt"], row.ts)
        source_name = str(row.source or "").removeprefix("Cases:")
        source = run["sources"].setdefault(source_name, {
            "found": 0, "terms": 0, "errors": [], "finished": False,
        })
        source["found"] += int(row.found or 0)
        if not str(row.term or "").startswith("__run_"):
            source["terms"] += 1
        if row.error:
            source["errors"].append(str(row.error))
        if row.term == "__run_finished__":
            source["finished"] = True

    output = []
    for run in grouped.values():
        for expected in ("Amazon", "Overclockers"):
            source = run["sources"].setdefault(expected, {
                "found": 0, "terms": 0, "errors": [], "finished": False,
            })
            source["completed"] = source["finished"] and source["found"] > 0 and not source["errors"]
        run["completed"] = all(s["completed"] for s in run["sources"].values())
        run["status"] = "running" if not all(s["finished"] for s in run["sources"].values()) else ("success" if run["completed"] else "failed")
        run["startedAt"] = run["startedAt"].isoformat()
        run["finishedAt"] = run["finishedAt"].isoformat()
        output.append(run)
    output.sort(key=lambda item: item["startedAt"], reverse=True)
    return output[:max(1, min(limit, 250))]
