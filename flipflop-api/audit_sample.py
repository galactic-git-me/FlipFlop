#!/usr/bin/env python
import sys
from app.database import get_db_sync
from app.models.gem_radar_ebay_observation import GemRadarEbayObservation
from sqlalchemy import select, func

db = get_db_sync()
query = select(
    GemRadarEbayObservation.listing_id,
    GemRadarEbayObservation.title,
    GemRadarEbayObservation.delivered_price,
    GemRadarEbayObservation.actual_listing_price
).order_by(func.random()).limit(50)

result = db.execute(query)
rows = result.fetchall()

print("Sample of 50 listings:\n")
print(f"{'ID':<20} {'Price':<12} {'Title':<50}")
print("-" * 82)

suspiciously_low = []
for row in rows:
    listing_id, title, delivered, actual = row
    title_short = (title[:47] + "...") if title and len(title) > 50 else title
    print(f"{listing_id:<20} £{delivered:<11.2f} {title_short}")

    # Flag suspiciously low prices (under £20 for anything that looks like a component)
    if delivered and delivered < 20 and title and any(x in title.lower() for x in ['cpu', 'gpu', 'motherboard', 'ram', 'ssd', 'psu']):
        suspiciously_low.append((listing_id, title, delivered))

print("\n\nSuspiciously low prices (<£20 for components):")
print("-" * 82)
if suspiciously_low:
    for listing_id, title, price in suspiciously_low:
        print(f"{listing_id:<20} £{price:<11.2f} {title}")
else:
    print("None found in this sample")
