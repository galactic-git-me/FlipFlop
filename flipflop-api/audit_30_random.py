from sqlalchemy import create_engine, text
import random

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

with engine.connect() as conn:
    # Get 30 random listings with their scores
    query = text("""
    SELECT
        listing_id,
        title,
        delivered_price,
        deal_score,
        classification,
        category,
        condition,
        seller_name,
        source
    FROM gem_radar_scored_listings
    WHERE source = 'ebay'
      AND scored_at >= NOW() - INTERVAL '3 days'
    ORDER BY RANDOM()
    LIMIT 30
    """)

    result = conn.execute(query)
    listings = result.fetchall()

    print("🔍 RANDOM AUDIT OF 30 eBay LISTINGS\n")
    print("="*100)
    print(f"{'#':<3} {'Listing ID':<15} {'Classification':<12} {'DB Price':<10} {'Category':<15} {'Title':<40}")
    print("="*100)

    for i, (listing_id, title, price, score, classification, category, condition, seller, source) in enumerate(listings, 1):
        title_short = (title[:37] + "...") if len(title) > 40 else title
        ebay_url = f"https://www.ebay.co.uk/itm/{listing_id}"

        print(f"{i:<3} {listing_id:<15} {classification:<12} £{price:<9.2f} {category:<15} {title_short}")
        print(f"    URL: {ebay_url}")

        # Get price history
        hist_query = text("""
        SELECT
            observed_at::date,
            delivered_price,
            search_run_id
        FROM gem_radar_listing_observations
        WHERE listing_id = :listing_id
        ORDER BY observed_at DESC
        LIMIT 5
        """)

        hist_result = conn.execute(hist_query, {"listing_id": listing_id})
        hist_rows = hist_result.fetchall()

        if hist_rows:
            print(f"    Price history: ", end="")
            for obs_date, obs_price, run_id in hist_rows:
                print(f"£{obs_price:.2f}({obs_date.strftime('%m-%d')}) ", end="")
            print()
        print()

print("\n" + "="*100)
print("\nNow verify each listing on eBay for:")
print("  1. Is the classification (GEM/SUPER_GEM) justified by the deal?")
print("  2. Does the price match the actual eBay listing?")
print("  3. If price doesn't match, has it been updated in subsequent scans?")
print("\nStart checking from the URLs above...")
