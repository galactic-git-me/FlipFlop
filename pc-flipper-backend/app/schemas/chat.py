from pydantic import BaseModel
from typing import Optional


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    listing_id: Optional[int] = None  # optional context
    flip_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    model_used: str
    listing_context: Optional[dict] = None
