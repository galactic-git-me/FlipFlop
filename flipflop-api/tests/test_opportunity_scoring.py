from app.gem_radar.opportunity_scoring import (
    OpportunityPolicy, SoldComparable, category_economics, desirability_score,
    identity_gates, risk_safety_score, robust_sold_market, score_opportunity,
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
    cpu = {"category": "cpu", "brand": "AMD", "model": "Ryzen 7 5800X3D"}
    assert "accessory_or_parts_listing" in identity_gates("Genuine Ryzen 7 5800X3D *BOX*", cpu)


def test_full_system_and_value_variant_identity_gates():
    gpu = {"category": "gpu", "brand": "nvidia", "model": "rtx-3060"}
    assert "whole_system_misclassified_as_component" in identity_gates(
        "Custom White Gaming Desktop RTX 3060 12GB 32GB RAM", gpu
    )
    ssd = {"category": "ssd", "brand": "samsung", "model": "980-pro"}
    assert "multi_variant_listing" in identity_gates(
        "Samsung 980 Pro SSD 250GB 500GB 1TB 2TB", ssd
    )


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


def test_preliminary_cohort_is_evidence_limited():
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
    assert result.classification == "EVIDENCE_LIMITED_DEAL"
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
    assert category_economics("cpu", policy).super_roi_pct == 35
    assert category_economics("motherboard", policy).super_roi_pct == 30
    assert category_economics("gpu", policy).super_roi_pct == 25
    assert category_economics("whole_pc", policy).gem_profit == policy.gem_profit


def test_missing_market_is_not_mislabelled_as_average_deal():
    result = score_opportunity(
        listing_price=50, title="AMD Ryzen 5 5600",
        cpk_data={"category": "cpu", "brand": "AMD", "model": "Ryzen 5 5600"},
        market=None, sold_count_90d=0, active_count=5,
        watch_velocity=None, bid_velocity=None, policy=OpportunityPolicy(),
    )
    assert result.classification == "INSUFFICIENT_DATA"


def test_identity_veto_takes_precedence_over_missing_market():
    result = score_opportunity(
        listing_price=10, title="EMPTY BOX AMD Ryzen 9 5900X CPU",
        cpk_data={"category": "cpu", "brand": "AMD", "model": "Ryzen 9 5900X"},
        market=None, sold_count_90d=0, active_count=0,
        watch_velocity=None, bid_velocity=None, policy=OpportunityPolicy(),
    )
    assert result.classification == "INELIGIBLE"
    assert result.decision == "IGNORE"


def test_active_market_identity_traps_are_hard_vetoes():
    cpu = {"category": "cpu", "brand": "Intel", "model": "i9-10980HK"}
    gpu = {"category": "gpu", "brand": "NVIDIA", "model": "RTX 3070"}
    ram = {"category": "ram", "brand": "Kingston", "model": "Fury Beast"}
    assert "whole_system_misclassified_as_component" in identity_gates("i9-10980HK 32GB laptop notebook", cpu)
    assert "accessory_or_parts_listing" in identity_gates("PCIe GPU riser extension cable", gpu)
    assert "multi_variant_listing" in identity_gates("Kingston Fury 8/16/32GB DDR5", ram)


def test_compatibility_text_cannot_turn_accessories_or_psus_into_components():
    cpu = {"category": "cpu", "brand": "Intel", "model": "i3-12100"}
    gpu = {"category": "gpu", "brand": "NVIDIA", "model": "RTX 5080"}
    case = {"category": "case", "brand": "Lian Li", "model": "A3-mATX"}
    assert "accessory_or_parts_listing" in identity_gates(
        "Intel i3-12100 LGA1700 Stock CPU Cooler Fan", cpu
    )
    assert "category_identity_conflict" in identity_gates(
        "Seasonic 850W 80+ Gold ATX 3.0 PSU RTX 5080 Ready", gpu
    )
    assert "accessory_or_parts_listing" in identity_gates(
        "4x Retaining Clips for Lian Li A3-mATX Case", case
    )
    assert "accessory_or_parts_listing" in identity_gates(
        "Lian Li UNI FAN TL Fan & RGB Controller Black", case
    )


def test_single_active_comparable_is_evidence_limited_not_ok_deal():
    policy = OpportunityPolicy(minimum_sold_comps=5, minimum_source_diversity=1)
    market = robust_sold_market(
        [SoldComparable(180, source_url="https://retailer.test/item")],
        subject_listing_id="subject",
        policy=OpportunityPolicy(minimum_sold_comps=1),
    )
    assert market is not None
    result = score_opportunity(
        listing_price=70, title="AMD Ryzen 7 7800X3D",
        cpk_data={"category": "cpu", "brand": "AMD", "model": "Ryzen 7 7800X3D"},
        market=market, sold_count_90d=0, active_count=3,
        watch_velocity=None, bid_velocity=None, policy=policy,
    )
    assert result.classification == "EVIDENCE_LIMITED_DEAL"
    assert result.decision == "INVESTIGATE"


def test_liquidity_ranks_urgency_but_does_not_veto_a_verified_super_gem():
    policy = OpportunityPolicy()
    market = robust_sold_market(comps([85, 88, 90, 92, 95, 97]), subject_listing_id="999", policy=policy)
    assert market is not None
    result = score_opportunity(
        listing_price=40, title="Noctua NH-D15 CPU Cooler",
        cpk_data={"category": "cooler", "brand": "Noctua", "model": "NH-D15"},
        market=market, sold_count_90d=0, active_count=10,
        watch_velocity=None, bid_velocity=None, policy=policy,
    )
    assert result.liquidity_score is None
    assert result.classification == "SUPER_GEM"


def test_missing_demand_is_unknown_but_observed_demand_is_scored():
    market = robust_sold_market(comps([85, 88, 90]), subject_listing_id="999", policy=OpportunityPolicy())
    unknown = score_opportunity(
        listing_price=40, title="Noctua NH-D15 CPU Cooler",
        cpk_data={"category": "cooler", "brand": "Noctua", "model": "NH-D15"},
        market=market, sold_count_90d=0, active_count=10,
        watch_velocity=None, bid_velocity=None, policy=OpportunityPolicy(),
    )
    observed = score_opportunity(
        listing_price=40, title="Noctua NH-D15 CPU Cooler",
        cpk_data={"category": "cooler", "brand": "Noctua", "model": "NH-D15"},
        market=market, sold_count_90d=0, active_count=10,
        watch_velocity=1.0, bid_velocity=0.0, policy=OpportunityPolicy(),
    )
    assert unknown.liquidity_score is None
    assert observed.liquidity_score == 4.0


def test_risk_flags_have_distinct_severity_and_are_deduplicated():
    assert risk_safety_score(["preliminary_sold_cohort"]) == 90
    assert risk_safety_score(["accessory_or_parts_listing"]) == 45
    assert risk_safety_score(["bundle_listing", "bundle_listing"]) == 65


def test_desirability_separates_modern_build_friendly_parts():
    modern = desirability_score(
        "Samsung 2TB NVMe PCIe 4 SSD",
        {"category": "ssd", "brand": "Samsung", "model": "990 Pro", "specs": {"interface": "nvme"}},
    )
    basic = desirability_score(
        "Generic SATA SSD",
        {"category": "ssd", "brand": "Generic", "model": "SATA SSD", "specs": {"interface": "sata"}},
    )
    assert modern > basic


def test_gem_economics_do_not_require_a_redundant_market_discount_gate():
    policy = OpportunityPolicy(gem_discount_pct=-20.0)
    market = robust_sold_market(comps([100, 100, 100, 100, 100]), subject_listing_id="999", policy=policy)
    assert market is not None
    result = score_opportunity(
        listing_price=82, title="Noctua NH-D15 CPU Cooler",
        cpk_data={"category": "cooler", "brand": "Noctua", "model": "NH-D15"},
        market=market, sold_count_90d=5, active_count=3,
        watch_velocity=1, bid_velocity=1, policy=policy, listing_condition="new",
    )
    assert result.roi_pct and result.roi_pct >= 15
    assert result.classification == "GEM"
    assert result.decision == "BUY_NOW"
    assert 75 <= result.score < 85


def test_strong_economics_with_low_confidence_are_evidence_limited():
    policy = OpportunityPolicy(minimum_sold_comps=3, minimum_source_diversity=1, gem_confidence=100)
    market = robust_sold_market(
        [SoldComparable(value, source_url=f"https://retailer.test/{index}") for index, value in enumerate([100, 150, 200], 1)],
        subject_listing_id="subject", policy=policy,
    )
    assert market is not None and market.confidence < 80
    result = score_opportunity(
        listing_price=70, title="Noctua NH-D15 CPU Cooler",
        cpk_data={"category": "cooler", "brand": "Noctua", "model": "NH-D15"},
        market=market, sold_count_90d=2, active_count=3,
        watch_velocity=None, bid_velocity=None, policy=policy, listing_condition="new",
    )
    assert result.expected_profit and result.expected_profit >= 3
    assert result.roi_pct and result.roi_pct >= 15
    assert result.classification == "EVIDENCE_LIMITED_DEAL"
    assert result.decision == "INVESTIGATE"
    assert 70 <= result.score < 75
