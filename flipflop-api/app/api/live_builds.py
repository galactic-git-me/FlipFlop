"""Operator-facing inventory activity for builds currently for sale."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_operator
from app.database import get_db
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.services import ebay_trading_api
from app.services.ebay_token_manager import get_valid_ebay_access_token

router = APIRouter(prefix="/live-builds", tags=["live-builds"], dependencies=[Depends(require_operator)])


class EbayMessageReplyIn(BaseModel):
    message_id: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=2000)


class EbayOfferResponseIn(BaseModel):
    best_offer_id: str = Field(min_length=1, max_length=100)
    action: Literal["Accept", "Decline", "Counter"]
    counter_price: float | None = Field(default=None, gt=0)


async def _channel_row(db: AsyncSession, build: ManualBuild) -> ChannelListing:
    row = (await db.execute(
        select(ChannelListing)
        .where(ChannelListing.manual_build_id == build.id, ChannelListing.channel == "ebay_uk")
        .order_by(ChannelListing.id.desc())
    )).scalars().first()
    if row:
        return row
    row = ChannelListing(
        manual_build_id=build.id,
        channel="ebay_uk",
        status="published",
        external_listing_id=build.ebay_listing_id,
        listing_url=build.ebay_listing_url,
    )
    db.add(row)
    await db.flush()
    return row


async def _ebay_token(db: AsyncSession) -> tuple[str | None, str | None]:
    from app.config import get_settings

    environment = get_settings().ebay_listing_environment
    try:
        token = await get_valid_ebay_access_token(environment, db=db)
    except ValueError:
        token = None
    return token, environment


@router.get("/ebay-activity")
async def ebay_activity(db: AsyncSession = Depends(get_db)):
    """Read unanswered eBay questions and active Best Offers for current builds."""
    token, environment = await _ebay_token(db)
    if not token:
        return {"connected": False, "messages": [], "offers": [], "message": "Connect the eBay seller account in Settings."}

    builds = (await db.execute(
        select(ManualBuild).where(
            ManualBuild.is_archived.is_(False),
            ManualBuild.status != "sold",
            ManualBuild.ebay_listing_status == "active",
            ManualBuild.ebay_listing_id.is_not(None),
        ).order_by(ManualBuild.updated_at.desc()).limit(100)
    )).scalars().all()
    build_by_item = {str(build.ebay_listing_id): build for build in builds if build.ebay_listing_id}
    try:
        raw_messages = await ebay_trading_api.get_member_messages(
            token, days_back=30, environment=environment
        )
    except Exception as exc:
        return {"connected": True, "messages": [], "offers": [], "message": f"eBay messages could not be read: {str(exc)[:240]}"}

    messages = []
    for message in raw_messages:
        build = build_by_item.get(str(message.get("item_id") or ""))
        if not build or not message.get("message_id"):
            continue
        messages.append({
            "build_id": build.id,
            "channel": "ebay_uk",
            "message_id": str(message["message_id"]),
            "item_id": str(build.ebay_listing_id),
            "sender": message.get("sender") or "eBay buyer",
            "subject": message.get("subject") or "Question about your listing",
            "body": message.get("body") or "eBay returned a message without its body. Open the conversation in eBay to review it.",
            "received_at": message.get("received_at"),
            "response_enabled": str(message.get("response_details") or "").lower() == "true",
            "listing_url": build.ebay_listing_url,
        })

    offers = []
    offer_errors = []
    for build in builds:
        try:
            for offer in await ebay_trading_api.get_best_offers(
                str(build.ebay_listing_id), token, environment=environment
            ):
                if str(offer.get("status") or "").lower() != "active":
                    continue
                offers.append({
                    "build_id": build.id,
                    "channel": "ebay_uk",
                    "best_offer_id": offer.get("best_offer_id"),
                    "buyer": offer.get("buyer_id") or "eBay buyer",
                    "price": offer.get("price"),
                    "status": offer.get("status"),
                    "listing_url": build.ebay_listing_url,
                })
        except Exception:
            offer_errors.append(build.id)
    return {
        "connected": True,
        "checked_builds": len(builds),
        "messages": messages,
        "offers": offers,
        "offer_check_incomplete_for_builds": offer_errors,
        "message": None,
    }


@router.post("/ebay/{build_id}/messages/reply")
async def reply_to_ebay_message(build_id: int, body: EbayMessageReplyIn, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build or not build.ebay_listing_id:
        raise HTTPException(404, "eBay listing not found for this build")
    if build.status == "sold" or build.ebay_listing_status != "active":
        raise HTTPException(409, "Only a currently active eBay listing can receive a reply")
    token, environment = await _ebay_token(db)
    if not token:
        raise HTTPException(503, "Connect the eBay seller account in Settings")
    messages = await ebay_trading_api.get_member_messages(
        token, days_back=30, environment=environment, item_id=str(build.ebay_listing_id)
    )
    target = next((message for message in messages if str(message.get("message_id") or "") == body.message_id), None)
    if not target or str(target.get("item_id") or "") != str(build.ebay_listing_id):
        raise HTTPException(409, "That unanswered eBay question is no longer available for this listing")
    if str(target.get("response_details") or "").lower() != "true":
        raise HTTPException(409, "eBay does not currently allow a reply to this question")
    try:
        await ebay_trading_api.respond_to_member_message(
            str(build.ebay_listing_id), body.message_id, body.body, token, environment
        )
    except (ValueError, ebay_trading_api.EbayTradingApiError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)[:400]) from exc
    row = await _channel_row(db, build)
    db.add(ListingPublishEvent(
        channel_listing_id=row.id,
        event_type="buyer_message_reply_sent",
        message="A reply was sent to the eBay buyer.",
        event_metadata={"message_id": body.message_id, "reply_body": body.body, "listing_id": build.ebay_listing_id},
    ))
    await db.commit()
    return {"success": True, "message": "Reply sent through eBay."}


@router.post("/ebay/{build_id}/offers/respond")
async def respond_to_ebay_offer(build_id: int, body: EbayOfferResponseIn, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build or not build.ebay_listing_id:
        raise HTTPException(404, "eBay listing not found for this build")
    if build.status == "sold" or build.ebay_listing_status != "active":
        raise HTTPException(409, "Only an active eBay listing can receive an offer response")
    if (body.action == "Counter") != (body.counter_price is not None):
        raise HTTPException(422, "Enter a counter price only when countering an offer")
    token, environment = await _ebay_token(db)
    if not token:
        raise HTTPException(503, "Connect the eBay seller account in Settings")
    active = await ebay_trading_api.get_best_offers(
        str(build.ebay_listing_id), token, environment=environment
    )
    target = next((offer for offer in active if str(offer.get("best_offer_id") or "") == body.best_offer_id and str(offer.get("status") or "").lower() == "active"), None)
    if not target:
        raise HTTPException(409, "That offer is no longer active for this eBay listing")
    try:
        await ebay_trading_api.respond_to_best_offer(
            str(build.ebay_listing_id), body.best_offer_id, body.action,
            body.counter_price, token, environment,
        )
    except (ValueError, ebay_trading_api.EbayTradingApiError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)[:400]) from exc
    row = await _channel_row(db, build)
    db.add(ListingPublishEvent(
        channel_listing_id=row.id,
        event_type="buyer_offer_responded",
        message=f"{body.action} response sent for an eBay buyer offer.",
        event_metadata={"best_offer_id": body.best_offer_id, "action": body.action, "counter_price": body.counter_price, "offer_price": target.get("price")},
    ))
    await db.commit()
    return {"success": True, "message": f"{body.action} sent through eBay."}
