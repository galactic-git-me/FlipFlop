from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.listing import Listing
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_service import chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def hermes_chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    listing_context = None
    if body.listing_id:
        listing = await db.get(Listing, body.listing_id)
        if listing:
            listing_context = {
                "title": listing.title,
                "price": listing.price,
                "specs": f"{listing.cpu} · {listing.ram_gb}GB {listing.ram_type} · GPU:{listing.gpu or 'none'} · Storage:{listing.storage_gb or 'none'}",
                "estimated_profit": listing.estimated_profit,
                "classification": listing.classification,
            }

    history = [{"role": m.role, "content": m.content} for m in body.history]
    response_text, model_used = await chat(body.message, history, listing_context)

    return ChatResponse(
        response=response_text,
        model_used=model_used,
        listing_context=listing_context,
    )
