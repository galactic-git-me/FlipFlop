from fastapi import APIRouter

from app.services.search_telemetry import latest_by_source, latest_records

router = APIRouter(prefix="/search-telemetry", tags=["search-telemetry"])


@router.get("/recent")
async def get_recent(limit: int = 500):
    return {"items": latest_records(limit=limit)}


@router.get("/by-source")
async def get_recent_by_source(limit: int = 1000):
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
