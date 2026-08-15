#!/usr/bin/env python
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("🖥️  ASUS ROG Crosshair X870E Optimal Pairings\n")
print("="*80)

# Find best CPUs (high-end Ryzen for X870E)
cpu_query = text("""
SELECT
    title,
    delivered_price,
    deal_score,
    condition,
    seller_name,
    classification,
    url
FROM gem_radar_scored_listings
WHERE category = 'cpu'
  AND (title ILIKE '%7700X%' OR title ILIKE '%7800X3D%' OR title ILIKE '%7900X%' OR title ILIKE '%7950X%')
  AND classification IN ('GEM', 'SUPER_GEM')
  AND source != 'temu'
ORDER BY deal_score DESC
LIMIT 5
""")

print("\n🎯 BEST CPU PAIRINGS (High-end Ryzen 7000):\n")
with engine.connect() as conn:
    result = conn.execute(cpu_query)
    rows = result.fetchall()

    if rows:
        for i, (title, price, score, condition, seller, classification, url) in enumerate(rows, 1):
            print(f"{i}. {title}")
            print(f"   Price: £{price:.2f} | Deal Score: {score:.1f} | {classification}")
            print(f"   Condition: {condition} | Seller: {seller}\n")
    else:
        print("No high-end CPUs found. Looking for available alternatives...\n")
        alt_query = text("""
        SELECT
            title,
            delivered_price,
            deal_score,
            condition,
            seller_name,
            classification
        FROM gem_radar_scored_listings
        WHERE category = 'cpu'
          AND (title ILIKE '%7%' OR title ILIKE '%9%')
          AND source != 'temu'
        ORDER BY deal_score DESC
        LIMIT 5
        """)
        result = conn.execute(alt_query)
        for i, (title, price, score, condition, seller, classification) in enumerate(result.fetchall(), 1):
            print(f"{i}. {title}")
            print(f"   Price: £{price:.2f} | Deal Score: {score:.1f} | {classification}\n")

# Find best GPUs (RTX 4070 Ti and above)
print("\n" + "="*80)
print("\n🎨 BEST GPU PAIRINGS (High-end Gaming):\n")

gpu_query = text("""
SELECT
    title,
    delivered_price,
    deal_score,
    condition,
    seller_name,
    classification,
    url
FROM gem_radar_scored_listings
WHERE category = 'gpu'
  AND (title ILIKE '%4070 Ti%' OR title ILIKE '%4080%' OR title ILIKE '%4090%' OR title ILIKE '%7900%' OR title ILIKE '%7800 XT%')
  AND classification IN ('GEM', 'SUPER_GEM')
  AND source != 'temu'
ORDER BY deal_score DESC
LIMIT 5
""")

with engine.connect() as conn:
    result = conn.execute(gpu_query)
    rows = result.fetchall()

    if rows:
        for i, (title, price, score, condition, seller, classification, url) in enumerate(rows, 1):
            print(f"{i}. {title}")
            print(f"   Price: £{price:.2f} | Deal Score: {score:.1f} | {classification}")
            print(f"   Condition: {condition} | Seller: {seller}\n")
    else:
        print("No high-end GPUs found. Looking for available alternatives...\n")
        alt_gpu_query = text("""
        SELECT
            title,
            delivered_price,
            deal_score,
            condition,
            seller_name,
            classification
        FROM gem_radar_scored_listings
        WHERE category = 'gpu'
          AND source != 'temu'
        ORDER BY deal_score DESC
        LIMIT 5
        """)
        result = conn.execute(alt_gpu_query)
        for i, (title, price, score, condition, seller, classification) in enumerate(result.fetchall(), 1):
            print(f"{i}. {title}")
            print(f"   Price: £{price:.2f} | Deal Score: {score:.1f} | {classification}\n")

# Price summary
print("="*80)
print("\n💰 BUILD COST SUMMARY:\n")

summary = text("""
SELECT
    'Motherboard' as component,
    0 as price
UNION ALL
SELECT
    'Ryzen 5 7600 (example)',
    139.32
UNION ALL
SELECT
    'X870E Motherboard (typical)',
    400
UNION ALL
SELECT
    'High-end GPU (typical)',
    600
""")

print("ASUS ROG Crosshair X870E + Ryzen 7700X/7800X3D + RTX 4070 Ti/4080")
print("  Estimated build cost: £1,500-2,200 (depending on exact models)")
print("  Target use: 1440p/4K high refresh, content creation, streaming\n")
