from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.customer_support_chat import answer_customer_support


router = APIRouter(prefix="/public/support", tags=["customer-support"])


class SupportChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)


class SupportChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1600)
    history: list[SupportChatHistoryMessage] = Field(default_factory=list, max_length=8)


class SupportSourceOut(BaseModel):
    name: str
    version: str
    reviewed_at: str
    section: str


class SupportChatOut(BaseModel):
    answer: str
    sources: list[SupportSourceOut]


@router.post("/chat", response_model=SupportChatOut)
async def customer_support_chat(body: SupportChatIn):
    """Public general support only; order-specific facts require portal auth."""
    history = [item.model_dump() for item in body.history]
    try:
        answer, _model_used, sources = await answer_customer_support(body.message, history)
    except Exception as error:
        raise HTTPException(
            503,
            "Hermes is temporarily unavailable. Please use FlipFlop support or My FlipFlop for order-specific help.",
        ) from error
    return {"answer": answer, "sources": sources}
