#!/usr/bin/env python3
"""Measure impact of each of 6 price accuracy opportunities"""
import json
from pathlib import Path
from statistics import mean, stdev, median
import sys

sys.path.insert(0, str(Path(__file__).parent))
from app.api.gem_radar import (
    _is_price_misaligned_to_market,
    _is_price_vs_sold_suspicious,
    _is_component_price_anomaly,
    _is_statistical_outlier,
)

def load_samples():
    """Load sample JSON files"""
    samples = {}
    for i in [8, 9, 10]:
        path = Path(__file__).parent / "audit_results" / f"sample_{i}.json"
        with open(path) as f:
            samples[i] = json.load(f)
    return samples

def compute_category_stats(all_listings):
    """Compute mean and stdev for each category"""
    by_category = {}
    for listing in all_listings:
        cat = listing.get("category")
        if not cat or "|" in cat or cat == "unknown":
            continue
        price = listing.get("delivered_price")
        if price is None:
            continue

        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(price)

    stats = {}
    for cat, prices in by_category.items():
        if len(prices) < 2:
            continue
        stats[cat] = (mean(prices), stdev(prices))

    return stats

def mock_sold_prices(market_used, market_new, current_price):
    """Mock sold prices from market data"""
    if not market_used and not market_new:
        return None

    # Use market prices as proxy for sold prices
    prices = []
    if market_used:
        prices.append(market_used * 0.95)
        prices.append(market_used * 1.05)
    if market_new:
        prices.append(market_new * 0.85)
    if prices:
        return prices
    return None

def test_all_opportunities():
    """Test all 6 opportunities"""
    samples = load_samples()

    all_listings = []
    for sample_data in samples.values():
        all_listings.extend(sample_data["listings"])

    category_stats = compute_category_stats(all_listings)

    print("\n" + "="*90)
    print("OPPORTUNITY IMPACT MEASUREMENT (Samples 8-10: 150 listings)")
    print("="*90)

    # Track defects per opportunity
    opportunities = {
        "#1: Market Price Validation": [],
        "#2: Sold Price vs Listing": [],
        "#3: Component-Specific Bounds": [],
        "#4: Statistical Outliers": [],
        "#5: Price Jump Detection": [],
        "#6: Seller Anomalies": [],
    }

    for sample_num in [8, 9, 10]:
        listings = samples[sample_num]["listings"]

        for listing in listings:
            title = listing["title"]
            category = listing["category"]
            listing_price = listing["delivered_price"]
            market_new = listing.get("market_prices", {}).get("new") if listing.get("market_prices") else None
            market_used = listing.get("market_prices", {}).get("used") if listing.get("market_prices") else None
            idx = listing["index"]

            # Opportunity #1: Market price validation
            if _is_price_misaligned_to_market(listing_price, market_used, market_new):
                opportunities["#1: Market Price Validation"].append({
                    "sample": sample_num, "index": idx, "title": title[:50],
                    "listing": f"£{listing_price:.2f}",
                    "market_used": f"£{market_used:.2f}" if market_used else "N/A",
                    "market_new": f"£{market_new:.2f}" if market_new else "N/A",
                })

            # Opportunity #2: Sold price vs listing
            sold_prices = mock_sold_prices(market_used, market_new, listing_price)
            if _is_price_vs_sold_suspicious(listing_price, sold_prices):
                opportunities["#2: Sold Price vs Listing"].append({
                    "sample": sample_num, "index": idx, "title": title[:50],
                    "listing": f"£{listing_price:.2f}",
                    "sold_median": f"£{median(sold_prices):.2f}" if sold_prices else "N/A",
                })

            # Opportunity #3: Component-specific bounds
            if _is_component_price_anomaly(category, title, listing_price):
                opportunities["#3: Component-Specific Bounds"].append({
                    "sample": sample_num, "index": idx, "title": title[:50],
                    "category": category, "price": f"£{listing_price:.2f}",
                })

            # Opportunity #4: Statistical outliers
            if _is_statistical_outlier(category, listing_price, category_stats):
                cat_mean, cat_std = category_stats.get(category, (0, 0))
                z_score = abs((listing_price - cat_mean) / cat_std) if cat_std > 0 else 0
                opportunities["#4: Statistical Outliers"].append({
                    "sample": sample_num, "index": idx, "title": title[:50],
                    "category": category, "price": f"£{listing_price:.2f}",
                    "z_score": f"{z_score:.2f}",
                    "mean": f"£{cat_mean:.2f}",
                })

            # Opportunity #5: Price jump detection (mock)
            # We don't have price history in samples, so this stays at 0
            # In production, would compare against historical prices

            # Opportunity #6: Seller anomalies (mock)
            # We don't have seller variance aggregation in samples
            # In production, would compute seller-level statistics

    # Print results
    print("\nDETAILS BY OPPORTUNITY:\n")

    cumulative_defects = set()  # Track unique listings caught by any filter

    for opp_name, defects in opportunities.items():
        count = len(defects)
        pct = count / 150 * 100

        print(f"\n{opp_name}")
        print(f"  Count: {count} / 150 ({pct:.1f}%)")

        if defects and count <= 5:
            for d in defects[:3]:
                print(f"    [{d.get('sample')}[{d.get('index')}]] {d.get('title')}")
                for k, v in d.items():
                    if k not in ["sample", "index", "title"]:
                        print(f"      {k}: {v}")
        elif defects:
            for d in defects[:2]:
                print(f"    [{d.get('sample')}[{d.get('index')}]] {d.get('title')}")

        # Add to cumulative
        for defect in defects:
            cumulative_defects.add((defect["sample"], defect["index"]))

    # Summary
    print("\n" + "="*90)
    print("IMPACT SUMMARY")
    print("="*90)

    print("\nBy Opportunity (individual impact):")
    for opp_name, defects in opportunities.items():
        count = len(defects)
        pct = count / 150 * 100
        print(f"  {opp_name:35} {count:3d} / 150  ({pct:5.1f}%)")

    cumulative_count = len(cumulative_defects)
    cumulative_pct = cumulative_count / 150 * 100

    print(f"\n{'─'*90}")
    print(f"  Total (cumulative, no overlap):    {cumulative_count:3d} / 150  ({cumulative_pct:5.1f}%)")
    print(f"  P1+P2+P3 baseline:                 35 / 150  (23.3%)")
    print(f"  {'─'*90}")
    print(f"  NEW TOTAL with all 6 opportunities:{cumulative_count + 35:3d} / 150  ({(cumulative_count + 35)/150*100:5.1f}%)")

    print("\n" + "="*90)
    print("RECOMMENDATIONS (by impact)")
    print("="*90)

    sorted_opps = sorted(opportunities.items(), key=lambda x: len(x[1]), reverse=True)
    for i, (name, defects) in enumerate(sorted_opps, 1):
        count = len(defects)
        pct = count / 150 * 100
        if count > 0:
            effort = "Low" if count < 5 else "Medium" if count < 15 else "High"
            confidence = "High" if count > 10 else "Medium"
            print(f"\n{i}. {name}")
            print(f"   Impact: {count} defects ({pct:.1f}%)  |  Effort: {effort}  |  Confidence: {confidence}")

if __name__ == "__main__":
    test_all_opportunities()
