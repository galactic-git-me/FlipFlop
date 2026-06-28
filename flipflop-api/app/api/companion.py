from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.companion_service import stream_companion

router = APIRouter(prefix="/companion", tags=["companion"])


class CompanionMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CompanionRequest(BaseModel):
    message: str
    history: list[CompanionMessage] = []
    page_context: str = "general"


@router.post("/stream")
async def companion_stream(body: CompanionRequest, db: AsyncSession = Depends(get_db)):
    history = [{"role": m.role, "content": m.content} for m in body.history]
    return StreamingResponse(
        stream_companion(body.message, history, body.page_context, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
