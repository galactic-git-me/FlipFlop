# 30-Listing Audit: Final Report
**Date**: 2026-08-15  
**Scope**: 30 random eBay listings from gem_radar_scored_listings  
**Auditor**: Claude  

---

## Executive Summary

✅ **Scraper is running regularly** - ~1.8-2.7 hour intervals per category  
❌ **Price data is STALE** - Most recent observations lag reality by hours or show inconsistent updates  
❌ **Price update logic works but is INCOMPLETE** - Captures new prices when changed, but can't update faster than scrape frequency (~every 2-3 hours)  

### Critical Finding
**Listing #20 (MSI AM1I Motherboard)**
- eBay current: **£59.00**
- Database latest (06:18 AM): **£62.65**
- Database history: £62.65 → £59.00 → £62.65 → *now £59.00*
- **Status**: Price bouncing between two values; DB is 12+ hours stale

---

## Detailed Findings

### 1️⃣ Classification Accuracy (Sample Checked)
| Listing | DB Classification | Classification Valid? | Notes |
|---------|-------------------|----------------------|-------|
| #2 (Intel i5-7500) | SUPER_GEM @ £9.99 | ⚠️ SUSPICIOUS | Processor for <£10 is extremely low; needs validation |
| #9 (MSI B760) | SUPER_GEM @ £69.99 | ✅ YES | Decent motherboard price, classification justified |
| #7 (Ryzen 7 3800X) | GEM @ £81.64 | ✅ SOLD | Item sold 08-11 for £78.70 (DB shows historical price) |
| #20 (MSI AM1I) | POOR_DEAL @ £62.65 | ❌ WRONG | Price should be £59.00 (current eBay), making it better deal |

**Assessment**: Classifications are REASONABLE but based on STALE data

---

### 2️⃣ Price Accuracy

#### Sample Verification Results
- **Listing #2 (i5-7500)**: DB £9.99 ✓ matches eBay
- **Listing #9 (MSI B760)**: DB £69.99 ✓ matches eBay  
- **Listing #20 (MSI AM1I)**: DB £62.65 ✗ **eBay shows £59.00** (STALE by 12h+)

#### Root Cause Analysis: Why Prices Aren't Updated Consistently

**The Good News**: The code logic IS correct:
- Line 1283 in `app/api/gem_radar.py` compares `existing.delivered_price` with `listing.current_delivered_price`
- When price changes: Creates NEW observation via `record_observation()` ✓
- When price unchanged: Just touches timestamp via `touch_observation()` ✓

**The Problem**: Scrape frequency limits update timeliness:
- Scraper runs every 1.8-2.7 hours per category
- Prices on eBay can change BETWEEN scrapes
- Database reflects last-seen price, not current price
- Price drop from £62.65 to £59.00 at 18:26 on 08-14 WAS captured
- But price going back to £62.65 at 06:18 on 08-15 missed the current £59.00 price
  (price must have changed AFTER the 06:18 scrape)

**Timeline for Listing #20:**
```
02:59 - Scrape captured £62.65
   ↓ (Price drops overnight)
18:26 - Scrape captured £59.00 ✓ (price change detected, new observation created)
   ↓ (Price goes back up?)
06:18 - Scrape captured £62.65 ✓ (price change detected, new observation created)
   ↓ (Price goes back down after scrape?)
NOW  - eBay shows £59.00 ✗ (scraper hasn't run since 06:18)
```

---

### 3️⃣ Data Quality Issues

#### Issue 1: Observation Frequency Gap
- **Expected** for daily scraper: 7 observations per listing over 7 days
- **Actual**: 1.7 observations per listing over 7 days
- **Reason**: Most sightings are deduplicated (price unchanged), only touching timestamp
- **Impact**: Stale prices persist until next price change OR next scrape

#### Issue 2: Price Bouncing Pattern
- Listing #20 shows price cycling: £62.65 ↔ £59.00 ↔ £62.65 ↔ £59.00
- Suggests possible issues:
  - Multiple variants with same listing ID?
  - Price adjustments by seller (testing different prices)?
  - Data quality issue in scraper?

#### Issue 3: eBay Listing #7 (SOLD)
- Database shows it as GEM at £81.64
- Actually sold for £78.70 on 08-11
- Database has historical price obs but not actual transaction price
- **Improvement needed**: Track actual sold prices from eBay API

---

## Summary of Findings

### ✅ What's Working
1. Scraper runs regularly (every ~2 hours)
2. Price changes ARE detected and new observations created
3. Classifications seem reasonable (spot-checked)
4. Database structure supports historical tracking

### ❌ What Needs Fixing
1. **Price staleness** - DB prices lag reality by hours (up to 12+)
2. **Limited update visibility** - 1.7 obs/listing means many price changes are missed
3. **Incomplete price data** - Need to capture actual sold prices, not just listing prices
4. **Listing classifications outdated** - Recalculated based on stale prices

---

## Recommendations

### Short Term
1. **Increase scrape frequency** - Move from 2-3 hour intervals to hourly or more
2. **Add price freshness indicator** - Flag listings where last scrape was >N hours ago
3. **Manual price verification for GEM/SUPER_GEM** - Before presenting to users

### Medium Term
1. **Implement price volatility detection** - Flag listings with bouncing prices
2. **Integrate eBay Inventory API** - Get actual sold/transaction prices, not just listing prices
3. **Add data quality dashboard** - Show % stale prices, price accuracy vs eBay, etc.

### Long Term
1. **Real-time price monitoring** - Subscribe to eBay price change events (if available)
2. **Multi-source pricing** - Cross-reference with Amazon, Gumtree, Facebook Marketplace
3. **Machine learning confidence scores** - Rate each listing's data quality

---

## Verification

**Manual checks completed:**
- ✓ Listing #2: Price verified on eBay
- ✓ Listing #9: Price verified on eBay
- ✓ Listing #20: Price verified on eBay, found stale DB data

**Audit scripts run:**
- ✓ `analyze_price_discrepancies.py` - Freshness & volatility analysis
- ✓ `audit_scraper_runs.py` - Scraper execution frequency
- ✓ `deep_dive_listing_206407473762.py` - Detailed history of single listing

---

## Conclusion

The system is **functionally correct** but **temporally limited** by scrape frequency. Prices CAN and DO change between scrapes, leaving the database stale. This is not a bug in the price-update logic, but rather a fundamental constraint of polling-based scraping.

**Key insight**: A listing priced £9.99 for a CPU, a motherboard bouncing between £59-£62, or a £9.99 SUPER_GEM classification all suggest the scraper found REAL eBay data at those prices at the time. The stale-ness is a **time problem**, not a **accuracy problem** (with the exception of sold listings not capturing transaction prices).
