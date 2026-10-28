from app.gem_radar.fan_category import correct_case_fan_cpk, is_standalone_fan


def test_explicit_case_fan_becomes_fan_cpk():
    data = {"cpk": "old", "category": "case", "brand": "nzxt", "model": "f120-rgb-white", "specs": {"type": "fan"}}
    cpk, corrected = correct_case_fan_cpk("NZXT F120 RGB White 120mm PWM Addressable RGB Case Fan", data)
    assert corrected["category"] == "fan"
    assert cpk != "old"


def test_case_with_included_fans_stays_case():
    title = "Corsair FRAME 4500X Mid-Tower PC Case with three RGB fans"
    assert not is_standalone_fan(title)
    cpk, data = correct_case_fan_cpk(title, {"cpk": "case-key", "category": "case", "brand": "corsair", "model": "4500x"})
    assert cpk == "case-key" and data["category"] == "case"


def test_wrong_legacy_fan_spec_does_not_reclassify_a_builder_bundle():
    data = {"cpk": "case-key", "category": "case", "brand": "phanteks", "model": "xt-pro", "specs": {"type": "fan"}}
    assert correct_case_fan_cpk("Phanteks XT Pro Case & AMP GH 850W Gold - Builder Bundle", data)[0] == "case-key"


def test_triple_pack_with_fan_spec_is_fan_even_without_fan_word():
    data = {"cpk": "old", "category": "case", "brand": "nzxt", "model": "f120-rgb-white", "specs": {"type": "fan"}}
    assert correct_case_fan_cpk("NZXT F120 RGB WHITE 120MM PWM TRIPLE PACK", data)[1]["category"] == "fan"
