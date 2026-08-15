from sqlalchemy import create_engine, text
from datetime import datetime, timezone

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

# Get today's gem of day
today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

with engine.connect() as conn:
    query = text("""
    SELECT
        s.title,
        s.listing_id,
        s.delivered_price,
        s.seller_name,
        s.source,
        s.url,
        s.deal_score,
        s.classification
    FROM gem_radar_scored_listings s
    WHERE s.scored_at >= :today_start
      AND s.category IN ('cpu', 'gpu', 'ram', 'motherboard', 'ssd', 'psu')
      AND s.classification IN ('GEM', 'SUPER_GEM')
    ORDER BY s.deal_score DESC
    LIMIT 1
    """)

    result = conn.execute(query, {"today_start": today_start})
    row = result.fetchone()

    if row:
        title, listing_id, delivered, seller, source, url, score, classification = row
        print("🔍 CURRENT GEM OF DAY:\n")
        print(f"Title:           {title}")
        print(f"Listing ID:      {listing_id}")
        print(f"Source:          {source}")
        print(f"Classification:  {classification}")
        print(f"Deal Score:      {score}")
        print(f"\n💰 PRICING:")
        print(f"Delivered Price: £{delivered:.2f} ⚠️")
        print(f"\nSeller:          {seller}")
        if url:
            print(f"URL:             {url}")

        # Check if price looks suspicious
        if delivered < 20 and "cpu" in title.lower():
            print(f"\n🚨 CORRUPTED: CPU for £{delivered:.2f} is impossible")
        elif delivered < 50 and ("gpu" in title.lower() or "motherboard" in title.lower()):
            print(f"\n🚨 CORRUPTED: {title[:30]}... for £{delivered:.2f} seems wrong")

        # List all observations for this listing
        print(f"\n📋 PRICE HISTORY FOR THIS LISTING:\n")
        obs_query = text("""
        SELECT
            observed_at,
            delivered_price,
            seller_name,
            source
        FROM gem_radar_listing_observations
        WHERE listing_id = :listing_id
        ORDER BY observed_at DESC
        LIMIT 10
        """)

        obs_result = conn.execute(obs_query, {"listing_id": listing_id})
        obs_rows = obs_result.fetchall()

        print(f"{'Date':<20} {'Price':<12} {'Seller':<20} {'Source':<10}")
        print("-" * 62)
        for obs_date, obs_price, obs_seller, obs_source in obs_rows:
            print(f"{str(obs_date)[:19]:<20} £{obs_price:<11.2f} {str(obs_seller)[:20]:<20} {obs_source:<10}")
    else:
        print("No gem found for today")
