"""
eBay legacy Trading API (XML) client — the modern REST Sell APIs don't cover
receiving/responding to a buyer's Best Offer or polling member messages, so
these two calls still go through the older XML API. It accepts the same
OAuth access token as the REST APIs via the X-EBAY-API-IAF-TOKEN header (IAF
= "Identity Assertion Framework"), so app.services.ebay_oauth's token still
works here — no separate legacy auth needed.

Not verifiable against live eBay from this environment (no network egress
to any eBay domain here) — tested against mocked HTTP responses matching
eBay's documented Trading API XML contract.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_TRADING_API_BASE = {
    "production": "https://api.ebay.com/ws/api.dll",
    "sandbox": "https://api.sandbox.ebay.com/ws/api.dll",
}

_NS = "urn:ebay:apis:eBLBaseComponents"


def _headers(call_name: str, token: str) -> dict:
    settings = get_settings()
    return {
        "X-EBAY-API-SITEID": "3",  # eBay UK
        "X-EBAY-API-COMPATIBILITY-LEVEL": "1349",
        "X-EBAY-API-CALL-NAME": call_name,
        "X-EBAY-API-IAF-TOKEN": token,
        "Content-Type": "text/xml",
    }


async def _call(
    call_name: str, body_xml: str, token: str, environment: str | None = None
) -> ET.Element:
    settings = get_settings()
    target_environment = environment or settings.ebay_environment
    root_url = _TRADING_API_BASE.get(target_environment, _TRADING_API_BASE["production"])
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<{call_name}Request xmlns="{_NS}">
{body_xml}
</{call_name}Request>"""

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(root_url, content=envelope, headers=_headers(call_name, token))

    if resp.status_code != 200:
        raise RuntimeError(f"eBay Trading API {call_name} returned HTTP {resp.status_code}: {resp.text[:300]}")

    tree = ET.fromstring(resp.text)
    ack = tree.findtext(f"{{{_NS}}}Ack")
    if ack not in ("Success", "Warning"):
        errors = [e.findtext(f"{{{_NS}}}LongMessage") for e in tree.findall(f"{{{_NS}}}Errors")]
        raise RuntimeError(f"eBay Trading API {call_name} failed: {'; '.join(filter(None, errors)) or ack}")
    return tree


async def revise_fixed_price_item(
    item_id: str,
    title: str,
    description: str,
    price: float,
    image_urls: list[str],
    aspects: dict[str, list[str]],
    token: str,
    environment: str = "production",
) -> str:
    """Replace editable content on an existing fixed-price listing."""
    item = ET.Element("Item")
    ET.SubElement(item, "ItemID").text = item_id
    ET.SubElement(item, "Title").text = title[:80]
    ET.SubElement(item, "Description").text = description
    start_price = ET.SubElement(item, "StartPrice", {"currencyID": "GBP"})
    start_price.text = f"{price:.2f}"

    if image_urls:
        pictures = ET.SubElement(item, "PictureDetails")
        for url in image_urls:
            ET.SubElement(pictures, "PictureURL").text = url

    if aspects:
        specifics = ET.SubElement(item, "ItemSpecifics")
        for name, values in aspects.items():
            if not values:
                continue
            pair = ET.SubElement(specifics, "NameValueList")
            ET.SubElement(pair, "Name").text = name
            for value in values:
                ET.SubElement(pair, "Value").text = value

    await _call(
        "ReviseFixedPriceItem",
        ET.tostring(item, encoding="unicode"),
        token,
        environment=environment,
    )
    return item_id


async def get_item_status(
    item_id: str, token: str, environment: str = "production",
) -> dict:
    """Return eBay's authoritative lifecycle fields for one legacy item ID."""
    tree = await _call(
        "GetItem",
        f"<ItemID>{item_id}</ItemID><DetailLevel>ReturnAll</DetailLevel>",
        token,
        environment=environment,
    )
    item = tree.find(f".//{{{_NS}}}Item")
    if item is None:
        raise RuntimeError(f"eBay GetItem returned no item for {item_id}")
    selling = item.find(f"{{{_NS}}}SellingStatus")
    listing_status = selling.findtext(f"{{{_NS}}}ListingStatus") if selling is not None else None
    quantity_sold_text = selling.findtext(f"{{{_NS}}}QuantitySold") if selling is not None else None
    return {
        "listing_status": listing_status or "Unknown",
        "quantity_sold": int(quantity_sold_text or 0),
        "end_time": item.findtext(f"{{{_NS}}}ListingDetails/{{{_NS}}}EndTime"),
    }


async def get_best_offers(item_id: str, token: str) -> list[dict]:
    """Poll for open Best Offers on a listing (rows 8/45's read side)."""
    body = f"""<ItemID>{item_id}</ItemID>
<BestOfferStatus>Active</BestOfferStatus>
<DetailLevel>ReturnAll</DetailLevel>"""
    tree = await _call("GetBestOffers", body, token)
    offers = []
    for offer_el in tree.findall(f".//{{{_NS}}}BestOffer"):
        offers.append({
            "best_offer_id": offer_el.findtext(f"{{{_NS}}}BestOfferID"),
            "buyer_id": offer_el.findtext(f"{{{_NS}}}Buyer/{{{_NS}}}UserID"),
            "price": float(offer_el.findtext(f"{{{_NS}}}Price") or 0),
            "status": offer_el.findtext(f"{{{_NS}}}Status"),
        })
    return offers


async def respond_to_best_offer(
    item_id: str, best_offer_id: str, action: str, counter_price: Optional[float], token: str,
) -> bool:
    """
    Rows 8/21: post FlipFlop's counter-offer decision back to eBay.
    action: "Counter" | "Accept" | "Decline"
    """
    counter_block = ""
    if action == "Counter" and counter_price is not None:
        counter_block = f"<CounterOfferPrice currencyID=\"GBP\">{counter_price:.2f}</CounterOfferPrice>"

    body = f"""<ItemID>{item_id}</ItemID>
<BestOfferID>{best_offer_id}</BestOfferID>
<Action>{action}</Action>
{counter_block}"""
    await _call("RespondToBestOffer", body, token)
    return True


async def get_member_messages(token: str, days_back: int = 7) -> list[dict]:
    """Row 47: unanswered buyer messages, for the response-time alert job."""
    since = (datetime.utcnow().replace(microsecond=0)).isoformat() + "Z"
    body = f"""<MailMessageType>All</MailMessageType>
<DetailLevel>ReturnHeaders</DetailLevel>
<MessageStatus>Unanswered</MessageStatus>"""
    tree = await _call("GetMemberMessages", body, token)
    messages = []
    for msg_el in tree.findall(f".//{{{_NS}}}MemberMessage"):
        messages.append({
            "message_id": msg_el.findtext(f"{{{_NS}}}MessageID"),
            "sender": msg_el.findtext(f"{{{_NS}}}Sender"),
            "subject": msg_el.findtext(f"{{{_NS}}}Subject"),
            "item_id": msg_el.findtext(f"{{{_NS}}}ItemID"),
            "received_at": msg_el.findtext(f"{{{_NS}}}CreationDate"),
            "response_details": msg_el.findtext(f"{{{_NS}}}ResponseDetails/{{{_NS}}}ResponseEnabled"),
        })
    return messages
