"""
Public social-proof feed — real order/login events with a resolved location,
for the storefront's live globe widget. No auth required (display names are
already reduced to first-name + initial before they ever reach the DB).
"""
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.social_proof_event import SocialProofEvent
from app.services.social_proof import broadcaster, serialize_event

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/public/social-proof", tags=["public-social-proof"])


@router.get("/recent")
async def recent_events(db: AsyncSession = Depends(get_db)):
    """Last 20 events, newest first — populates the globe on initial page load."""
    result = await db.execute(
        select(SocialProofEvent).order_by(SocialProofEvent.created_at.desc()).limit(20)
    )
    events = result.scalars().all()
    return [serialize_event(e) for e in reversed(events)]


@router.websocket("/ws")
async def social_proof_ws(websocket: WebSocket):
    """Live push — one JSON event per message, as orders/logins happen."""
    await broadcaster.connect(websocket)
    try:
        while True:
            # No client -> server messages expected; just keep the connection
            # alive and notice disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("social_proof.ws_error", error=str(exc))
    finally:
        broadcaster.disconnect(websocket)
