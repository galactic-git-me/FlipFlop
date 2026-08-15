#!/usr/bin/env python
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("🔍 Searching for DDR5 RAM SUPER GEMs...\n")
print("="*90)

# Find best DDR5 RAM with SUPER_GEM classification
query = text("""
SELECT
    title,
    delivered_price,
    deal_score,
    condition,
    seller_name,
    classification,
    source,
    url
FROM gem_radar_scored_listings
WHERE category = 'ram'
  AND title ILIKE '%DDR5%'
  AND classification = 'SUPER_GEM'
  AND source != 'temu'
ORDER BY deal_score DESC
LIMIT 10
""")

with engine.connect() as conn:
    result = conn.execute(query)
    rows = result.fetchall()

    if rows:
        print(f"\n🎯 Found {len(rows)} DDR5 RAM SUPER GEMs:\n")
        for i, (title, price, score, condition, seller, classification, source, url) in enumerate(rows, 1):
            print(f"{i}. {title}")
            print(f"   💰 Price: £{price:.2f}")
            print(f"   ⭐ Deal Score: {score:.1f} ({classification})")
            print(f"   📦 Condition: {condition}")
            if seller:
                print(f"   👤 Seller: {seller}")
            print(f"   📍 Source: {source}")
            if url:
                print(f"   🔗 {url}")
            print()
    else:
        print("No DDR5 SUPER GEMs found. Checking for GEMs...\n")

        query2 = text("""
        SELECT
            title,
            delivered_price,
            deal_score,
            condition,
            seller_name,
            classification,
            source,
            url
        FROM gem_radar_scored_listings
        WHERE category = 'ram'
          AND title ILIKE '%DDR5%'
          AND classification IN ('GEM', 'SUPER_GEM')
          AND source != 'temu'
        ORDER BY deal_score DESC
        LIMIT 10
        """)

        result = conn.execute(query2)
        rows = result.fetchall()

        if rows:
            print(f"Found {len(rows)} DDR5 GEMs/SUPER GEMs:\n")
            for i, (title, price, score, condition, seller, classification, source, url) in enumerate(rows, 1):
                gem_icon = "🔥" if classification == "SUPER_GEM" else "💎"
                print(f"{i}. {gem_icon} {title}")
                print(f"   💰 Price: £{price:.2f}")
                print(f"   ⭐ Deal Score: {score:.1f} ({classification})")
                print(f"   📦 Condition: {condition}")
                if seller:
                    print(f"   👤 Seller: {seller}")
                print(f"   📍 Source: {source}")
                if url:
                    print(f"   🔗 {url}")
                print()
        else:
            print("No DDR5 gems found. Showing top 10 DDR5 listings:\n")

            query3 = text("""
            SELECT
                title,
                delivered_price,
                deal_score,
                condition,
                seller_name,
                classification,
                source
            FROM gem_radar_scored_listings
            WHERE category = 'ram'
              AND title ILIKE '%DDR5%'
              AND source != 'temu'
            ORDER BY deal_score DESC
            LIMIT 10
            """)

            result = conn.execute(query3)
            for i, (title, price, score, condition, seller, classification, source) in enumerate(result.fetchall(), 1):
                print(f"{i}. {title}")
                print(f"   Price: £{price:.2f} | Score: {score:.1f} | {classification}\n")

print("="*90)
