from app.gem_radar.opportunity_scoring import (
    OpportunityPolicy, SoldComparable, category_economics, identity_gates, robust_sold_market, score_opportunity,
)


def comps(values, subject="999"):
    return [SoldComparable(value, source_url=f"https://www.ebay.co.uk/itm/{index}") for index, value in enumerate(values, 1)] + [
        SoldComparable(1.0, source_url=f"https://www.ebay.co.uk/itm/{subject}")
    ]


def test_market_is_leave_one_out_and_robust_to_extreme_outlier():
    policy = OpportunityPolicy(minimum_sold_comps=5)
    market = robust_sold_market(comps([190, 195, 200, 205, 210, 1500]), subject_listing_id="999", policy=policy)
    assert market is not None
    assert market.raw_sample_size == 6
    assert market.sample_size == 5
    assert market.median == 200
    assert market.upper < 300
    assert all("/999" not in url for url in market.comparable_urls)


def test_same_subject_cannot_contribute_to_own_market():
    policy = OpportunityPolicy(minimum_sold_comps=5)
    market = robust_sold_market(comps([100, 101, 102, 103]), subject_listing_id="999", policy=policy)
    assert market is None


def test_accessory_and_retro_platform_are_hard_gates():
    identity = {"category": "gpu", "brand": "nvidia", "model": "rtx-3070"}
    assert "accessory_or_parts_listing" in identity_gates("RTX 3070 RGB backplate", identity)
    assert "retro_platform_excluded" in identity_gates("AM3 DDR3 motherboard", identity)
    assert "retro_platform_excluded" not in identity_gates("AM3 DDR3 motherboard", identity, "retro_budget")


def test_super_gem_requires_profit_roi_confidence_liquidity_and_no_veto():
    policy = OpportunityPolicy()
    market = robust_sold_market(comps([590, 600, 610, 620, 630, 640]), subject_listing_id="999", policy=policy)
    assert market is not None
    result = score_opportunity(
        listing_price=350, title="AMD Ryzen 7 7800X3D", cpk_data={"category": "cpu", "brand": "amd", "model": "7800x3d", "specs": {"socket": "am5"}},
        market=market, sold_count_90d=20, active_count=5, watch_velocity=1.0, bid_velocity=0.5,
        policy=policy,
    )
    assert result.classification == "SUPER_GEM"
    assert result.decision == "BUY_NOW"
    assert result.expected_profit and result.expected_profit >= 50


def test_good_price_cannot_hide_identity_failure():
    policy = OpportunityPolicy()
    market = robust_sold_market(comps([590, 600, 610, 620, 630, 640]), subject_listing_id="999", policy=policy)
    result = score_opportunity(
        listing_price=20, title="RTX 3070 fan only", cpk_data={"category": "gpu", "brand": "nvidia", "model": "rtx-3070"},
        market=market, sold_count_90d=30, active_count=2, watch_velocity=5, bid_velocity=2, policy=policy,
    )
    assert result.classification not in {"SUPER_GEM", "GEM"}
    assert result.decision != "BUY_NOW"
    assert "accessory_or_parts_listing" in result.risk_flags


def test_preliminary_cohort_can_only_be_emerging():
    policy = OpportunityPolicy(minimum_sold_comps=3)
    market = robust_sold_market(
        [SoldComparable(180, source_url=f"https://ebay.test/{i}") for i in range(3)],
        subject_listing_id="subject", policy=policy,
    )
    result = score_opportunity(
        listing_price=70, title="AMD Ryzen 7 7800X3D",
        cpk_data={"category": "cpu", "brand": "AMD", "model": "Ryzen 7 7800X3D", "specs": {"socket": "am5"}},
        market=market, sold_count_90d=3, active_count=2,
        watch_velocity=2, bid_velocity=1, policy=policy, delivery_cost=0,
        extra_risk_flags=("preliminary_sold_cohort",),
    )
    assert result.classification == "EMERGING_OPPORTUNITY"
    assert result.decision == "INVESTIGATE"
    assert not result.eligible


def test_component_does_not_repeat_whole_build_fulfilment_costs():
    policy = OpportunityPolicy(delivery_fallback=15, packaging_cost=6, testing_refurbishment_cost=10)
    market = robust_sold_market(comps([100, 102, 104, 106, 108]), subject_listing_id="999", policy=policy)
    result = score_opportunity(
        listing_price=60, title="Used AMD Ryzen 5 5600 CPU",
        cpk_data={"category": "cpu", "brand": "AMD", "model": "Ryzen 5 5600"},
        market=market, sold_count_90d=8, active_count=3,
        watch_velocity=1, bid_velocity=1, policy=policy,
    )
    assert result.cost_breakdown["delivery"] == 0
    assert result.cost_breakdown["packaging"] == 0
    assert result.cost_breakdown["testing_refurbishment"] == 3
    assert result.expected_profit and result.expected_profit > 30


def test_category_economics_preserve_higher_gpu_and_build_cash_hurdles():
    policy = OpportunityPolicy()
    assert category_economics("cpu", policy).gem_profit == 5
    assert category_economics("gpu", policy).gem_profit == 20
    assert category_economics("whole_pc", policy).gem_profit == policy.gem_profit


def test_missing_market_is_not_mislabelled_as_average_deal():
    result = score_opportunity(
        listing_price=50, title="AMD Ryzen 5 5600",
        cpk_data={"category": "cpu", "brand": "AMD", "model": "Ryzen 5 5600"},
        market=None, sold_count_90d=0, active_count=5,
        watch_velocity=None, bid_velocity=None, policy=OpportunityPolicy(),
    )
    assert result.classification == "INSUFFICIENT_DATA"
