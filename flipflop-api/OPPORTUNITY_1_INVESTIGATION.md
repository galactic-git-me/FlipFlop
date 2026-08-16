# Investigation: Opportunity #1 - Market Price Validation

## Finding: Market Prices Never Populated ❌

### Status
**market_new_price** and **market_used_price** are **declared in ORM model but NEVER SET** during scoring.

### Evidence
1. **Model Declaration** (GemRadarScoredListing)
   - Fields exist: `market_new_price`, `market_used_price`
   - Status: Read-only (never updated)

2. **Scoring Pipeline** (pipeline.py)
   - No code references to `market_new_price` or `market_used_price`
   - Searches return: No matches
   - Conclusion: eBay Browse API integration does NOT exist

3. **Sample Data Verification**
   - All 150 listings in Samples 8-10: `market_prices = null`
   - Confirms fields are never populated

### Root Cause
The ORM model was prepared for market price data, but the eBay Browse API integration was never implemented in the scoring pipeline.

### Impact
- **Opportunity #1** (Market Price Validation): **Blocked** - No data to validate against
- **Potential gain if fixed:** 3-5% additional accuracy (estimated)
- **Effort to implement:** 6-8 hours
  - Add eBay Browse API call to score_listing()
  - Parse market data (new/used prices)
  - Store in GemRadarScoredListing
  - Integrate _is_price_misaligned_to_market() filter

### Recommendation

**Option A: Quick Win (This Quarter)**
```
1. Enable eBay Browse API in score_listing()
2. Fetch market prices during scoring
3. Store in market_new_price / market_used_price
4. Integrate Opportunity #1 filter
5. Expected gain: +3-5% accuracy
6. Effort: 6-8 hours
```

**Option B: Defer (Next Quarter)**
```
- Keep Opportunity #1 for future roadmap
- Proceed with P1+P2+P3 + Opp#3-4 now
- Revisit after stabilizing core filters
- Risk: 3-5% potential accuracy left on table
```

### Decision: Recommend Option A (This Quarter)

Market prices are fundamental to deal scoring. Having this data available would:
- Improve gem quality (validate deals against actual market)
- Reduce false positives (component-specific bounds + market validation = high precision)
- Enable Opportunity #2 (sold price comparison) as follow-up

### Implementation Plan

**Phase 1: Enable market price fetch (4 hours)**
```python
# In pipeline.py score_listing():
market_data = await ebay_browse_adapter.get_market_prices(epid, category)
# Store in result:
scored_listing.market_new_price = market_data.get('new')
scored_listing.market_used_price = market_data.get('used')
```

**Phase 2: Integrate filter (2 hours)**
```python
# In gem_radar.py _fetch_best_gem_for_category():
if _is_price_misaligned_to_market(
    candidate.delivered_price,
    candidate.market_used_price,
    candidate.market_new_price
):
    continue
```

**Phase 3: Test (2 hours)**
```python
# Run measure_opportunity_impact.py with market data populated
# Expected: +3-5% defects caught
```

### Next Steps
1. Check if eBay Browse API adapter exists in codebase
2. Review if browse API has market pricing endpoint
3. Estimate dev time with team
4. Add to sprint if feasible this quarter
