from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.alert_event import AlertEvent

_URGENT_REFUND_CODE_PREFIX = "manual_build_refund_requested_"


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
            q = q.where((AlertEvent.acked == False) | AlertEvent.code.like(f"{_URGENT_REFUND_CODE_PREFIX}%"))  # noqa: E712
        rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "severity": r.severity,
            "source": r.source,
            "message": r.message,
            "link_url": r.link_url,
            "acked": r.acked or r.code.startswith(_URGENT_REFUND_CODE_PREFIX),
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


async def send_manual_build_activity_digest() -> dict:
    """Email current undispatched sales and unresolved urgent buyer requests, if any."""
    from app.database import AsyncSessionLocal
    from app.models.manual_build import ManualBuild
    from app.models.email_event import EmailEvent
    from app.services.email_service import send_email_async

    recipient = "jupiter.ascending.6270@gmail.com"
    async with AsyncSessionLocal() as db:
        builds = (await db.execute(select(ManualBuild).where(
            ManualBuild.status == "sold",
            ManualBuild.dispatch_status.notin_(("dispatched", "delivered")),
        ).order_by(ManualBuild.updated_at.desc()))).scalars().all()
        refund_events = (await db.execute(select(EmailEvent).where(
            EmailEvent.event_type == "refund_requested",
            EmailEvent.manual_build_id.is_not(None),
        ).order_by(EmailEvent.received_at.desc()).limit(50))).scalars().all()
        unresolved_refund_build_ids = {event.manual_build_id for event in refund_events}
        resolution_events = (await db.execute(select(EmailEvent).where(
            EmailEvent.event_type.in_(("refund_approved", "refund_issued", "return_closed", "refund_denied")),
            EmailEvent.manual_build_id.in_(unresolved_refund_build_ids) if unresolved_refund_build_ids else False,
        ).order_by(EmailEvent.received_at.desc()))).scalars().all() if unresolved_refund_build_ids else []
        resolved_ids = {event.manual_build_id for event in resolution_events}
        by_build = {}
        for event in refund_events:
            if event.manual_build_id not in by_build and event.manual_build_id not in resolved_ids:
                by_build[event.manual_build_id] = event
        urgent = list(by_build.values())
        if not builds and not urgent:
            return {"ok": True, "sent": False, "reason": "empty"}
        lines = ["<h2>FlipFlop daily build activity</h2>"]
        if builds:
            lines.append("<h3>Sold, awaiting dispatch</h3><ul>")
            lines.extend(f"<li><a href=\"https://admin.theflipflop.shop/dispatch-zone?tab=delivery&amp;buildId={b.id}\">{b.name} (build #{b.id})</a> — {b.dispatch_status}</li>" for b in builds)
            lines.append("</ul>")
        if urgent:
            lines.append("<h3>Urgent refund or return requests</h3><ul>")
            lines.extend(f"<li><a href=\"https://admin.theflipflop.shop/builds/{e.manual_build_id}\">Build #{e.manual_build_id}</a> — {e.summary}</li>" for e in urgent)
            lines.append("</ul>")
    sent = await send_email_async(recipient, "FlipFlop daily build activity", "".join(lines), reference="manual-build-activity-digest")
    return {"ok": sent, "sent": sent, "sold_builds": len(builds), "urgent_requests": len(urgent)}


async def send_daily_activity_digest() -> dict:
    """Send the urgent buyer-request portion of the daily activity email."""
    from app.database import AsyncSessionLocal
    from app.models.email_event import EmailEvent
    from app.models.manual_build import ManualBuild
    from app.services.email_service import send_email_async

    recipient = "jupiter.ascending.6270@gmail.com"
    async with AsyncSessionLocal() as db:
        refund_events = (await db.execute(select(EmailEvent).where(
            EmailEvent.event_type == "refund_requested",
            EmailEvent.manual_build_id.is_not(None),
        ).order_by(EmailEvent.received_at.desc()).limit(50))).scalars().all()
        build_ids = {event.manual_build_id for event in refund_events}
        resolutions = (await db.execute(select(EmailEvent).where(
            EmailEvent.event_type.in_(("refund_approved", "refund_issued", "return_closed", "refund_denied")),
            EmailEvent.manual_build_id.in_(build_ids) if build_ids else False,
        ).order_by(EmailEvent.received_at.desc()))).scalars().all() if build_ids else []
        resolved_ids = {event.manual_build_id for event in resolutions}
        latest = {}
        for event in refund_events:
            if event.manual_build_id not in latest and event.manual_build_id not in resolved_ids:
                latest[event.manual_build_id] = event
        if not latest:
            return {"ok": True, "sent": False, "reason": "empty"}
        builds = (await db.execute(select(ManualBuild).where(ManualBuild.id.in_(latest)))).scalars().all()
        builds_by_id = {build.id: build for build in builds}
        lines = ["<h2>FlipFlop daily activity</h2><h3>Urgent buyer refund or return requests</h3><ul>"]
        for build_id, event in latest.items():
            build = builds_by_id.get(build_id)
            if not build:
                continue
            lines.append(f"<li><a href=\"https://admin.theflipflop.shop/builds/{build.id}\">{build.name} (build #{build.id})</a> — {event.summary}</li>")
        lines.append("</ul>")
    sent = await send_email_async(recipient, "FlipFlop daily urgent activity", "".join(lines), reference="daily-urgent-activity-digest")
    return {"ok": sent, "sent": sent, "urgent_requests": len(latest)}
