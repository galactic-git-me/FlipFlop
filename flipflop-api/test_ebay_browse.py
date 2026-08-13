#!/usr/bin/env python3
import asyncio
from app.services.ebay_browse import search_active_listings

async def test():
    queries = ['9800X3D processor', '9800X3D CPU']
    for query in queries:
        print(f"Testing: {query}")
        listings = await search_active_listings(query, limit=3)
        print(f'Got {len(listings)} listings\n')
        if listings:
            listing = listings[0]
            print(f'  Title: {str(listing.get("title", "N/A"))[:70]}')
            print(f'  Price: £{listing.get("price")}')
            print(f'  GTIN: {listing.get("gtin")}')
            print(f'  MPN: {listing.get("mpn")}')
            print(f'  Model#: {listing.get("model_number")}')
            print(f'  epid: {listing.get("epid")}')
        print()

asyncio.run(test())
