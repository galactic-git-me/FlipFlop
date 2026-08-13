import asyncio
import json
import traceback
from app.database import get_db
from app.api.gem_radar import submit_scan_queued
from app.gem_radar.schemas import ScanSubmitRequest

payload_dict = {
    "searchRunId": "test-789",
    "searchId": "test",
    "query": "AMD CPU",
    "sourceUrl": "https://www.ebay.co.uk/sch/i.html?_nkw=AMD+CPU",
    "maxCandidatesForDeepResearch": 5,
    "listings": [
        {
            "listingId": "123456",
            "url": "https://www.ebay.co.uk/itm/123456",
            "title": "AMD Ryzen 5 3600",
            "seller": "testseller",
            "sellerFeedbackPercent": 99.5,
            "sellerFeedbackCount": 100,
            "conditionRaw": "Used",
            "conditionNormalised": "used",
            "itemPrice": 50.0,
            "postagePrice": 3.5,
            "currentDeliveredPrice": 53.5,
            "currency": "GBP",
            "listingType": "buy_it_now",
            "bestOfferEnabled": False,
            "bidCount": None,
            "auctionEndAt": None,
            "imageUrl": "https://example.com/img.jpg",
            "sponsored": False,
            "extractedAt": "2026-07-28T06:00:00Z",
        }
    ],
}


async def main():
    payload = ScanSubmitRequest(**payload_dict)
    async for db in get_db():
        try:
            result = await submit_scan_queued(payload=payload, db=db, _=None)
            print("OK:", result)
        except Exception:
            traceback.print_exc()
        break


asyncio.run(main())
