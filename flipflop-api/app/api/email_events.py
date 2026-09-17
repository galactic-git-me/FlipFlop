from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_operator
from app.database import get_db
from app.models.email_event import EmailEvent

router = APIRouter(prefix="/email-events", tags=["email-events"], dependencies=[Depends(require_operator)])


@router.get("")
async def list_email_events(limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(EmailEvent).order_by(EmailEvent.received_at.desc()).limit(limit))).scalars().all()
    return [{"id": r.id, "subject": r.subject, "sender": r.sender, "summary": r.summary,
             "event_type": r.event_type, "marketplace": r.marketplace,
             "received_at": r.received_at.isoformat() if r.received_at else None,
             "link_url": f"/email-events/{r.id}"} for r in rows]


@router.get("/{event_id}")
async def get_email_event(event_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(EmailEvent, event_id)
    if not row:
        raise HTTPException(404, "Email event not found")
    return {"id": row.id, "subject": row.subject, "sender": row.sender, "body": row.body,
            "summary": row.summary, "event_type": row.event_type, "marketplace": row.marketplace,
            "payload": row.payload, "received_at": row.received_at.isoformat() if row.received_at else None}
