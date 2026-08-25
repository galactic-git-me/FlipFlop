from app.services.build_wizard import Build, BuildUpgrade, RefinedIntent, _hard_validate


def _intent() -> RefinedIntent:
    return RefinedIntent(
        playbook_name="AI Workstation", playbook_emoji="AI", budget_max=2000,
        target_use_case="ai_workstation", priorities=[], constraints=[], user_notes="",
    )


def _build(base: str, upgrades: list[BuildUpgrade]) -> Build:
    total = 500 + sum(item.cost_estimate for item in upgrades)
    return Build(
        id="test", name="Test", base_spec=base, base_cost=500, upgrades=upgrades,
        total_cost=total, estimated_resale=2400, estimated_profit=2400-total,
        profit_margin_pct=(2400-total)/total*100, risk="low", demand_fit="excellent",
        why="test", sell_platform="eBay", sell_price_target=2400,
    )


def _proper_upgrades() -> list[BuildUpgrade]:
    return [
        BuildUpgrade("gpu", "RTX 4070 Ti Super 16GB", 650, "live", True),
        BuildUpgrade("ram", "64GB DDR5 RAM", 140, "live", True),
        BuildUpgrade("storage", "1TB NVMe SSD", 60, "live", True),
        BuildUpgrade("psu", "750W ATX PSU", 90, "live", True),
    ]


def test_screenshot_style_ai_build_is_rejected_for_office_oem_base():
    build = _build("Dell OptiPlex 7060 i5-8400 16GB no GPU", [
        BuildUpgrade("gpu", "RTX 3060 8GB", 230, "live", True),
        BuildUpgrade("cpu", "Intel Core i7-9700K", 120, "live", False),
    ])
    passed, reason = _hard_validate(build, _intent())
    assert not passed
    assert "office OEM" in reason


def test_ai_build_requires_declared_ram_storage_and_psu():
    build = _build("Custom ATX Ryzen 9 7900X tower", [
        BuildUpgrade("gpu", "RTX 4070 Ti Super 16GB", 650, "live", True),
    ])
    passed, reason = _hard_validate(build, _intent())
    assert not passed
    assert "RAM" in reason


def test_complete_ai_workstation_passes_use_case_gates():
    build = _build("Custom ATX Ryzen 9 7900X tower AM5", _proper_upgrades())
    passed, reason = _hard_validate(build, _intent())
    assert passed, reason


def test_component_cost_is_recalculated_instead_of_trusting_ai_total():
    build = _build("Custom ATX Ryzen 9 7900X tower AM5", _proper_upgrades())
    build.total_cost = 100
    passed, reason = _hard_validate(build, _intent())
    assert passed, reason
    assert build.total_cost == 1440
