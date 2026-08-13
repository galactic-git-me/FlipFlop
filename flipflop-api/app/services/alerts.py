from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.alert_event import AlertEvent


async def emit_alert(code: str, source: str, message: str, severity: str = "warning", link_url: str | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        row = AlertEvent(code=code, source=source, message=message, severity=severity, link_url=link_url)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return {
            "id": row.id,
            "code": row.code,
            "severity": row.severity,
            "source": row.source,
            "message": row.message,
            "link_url": row.link_url,
            "acked": row.acked,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


async def list_alerts(limit: int = 100, include_acked: bool = False) -> list[dict]:
    async with AsyncSessionLocal() as db:
        q = select(AlertEvent).order_by(AlertEvent.created_at.desc()).limit(max(1, min(1000, limit)))
        if not include_acked:
            q = q.where(AlertEvent.acked == False)  # noqa: E712
        rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "severity": r.severity,
            "source": r.source,
            "message": r.message,
            "link_url": r.link_url,
            "acked": r.acked,
            "acked_at": r.acked_at.isoformat() if r.acked_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def ack_alert(alert_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        row = await db.get(AlertEvent, alert_id)
        if not row:
            return {"ok": False, "reason": "not_found"}
        row.acked = True
        row.acked_at = datetime.utcnow()
        await db.commit()
        return {"ok": True, "id": alert_id}


async def check_stale_retrain_checkpoint(stale_hours: int = 24) -> dict:
    from app.models.outcome_event import RetrainCheckpoint

    async with AsyncSessionLocal() as db:
        ckpt = (await db.execute(select(RetrainCheckpoint).where(RetrainCheckpoint.name == "policy"))).scalar_one_or_none()
        if not ckpt or not ckpt.ready:
            return {"ok": True, "emitted": False}

        if ckpt.updated_at and (datetime.utcnow() - ckpt.updated_at) < timedelta(hours=stale_hours):
            return {"ok": True, "emitted": False}

    await emit_alert(
        code="stale_retrain_checkpoint",
        source="retraining",
        severity="warning",
        message=f"Retrain checkpoint has been ready for more than {stale_hours}h without promotion.",
    )
    return {"ok": True, "emitted": True}
