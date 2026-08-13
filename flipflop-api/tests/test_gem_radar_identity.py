"""Tests for app.gem_radar.identity — pure regex extraction, no DB, no network.

Covers the model-extraction gap found by the Gem Radar classification audit:
resolve_identity() used to return exact_sku_confidence=0.0 for EVERY ssd/
motherboard/cooler listing, no matter how clearly branded/identifiable, since
only cpu/gpu/ram had model-extraction logic at all. That silently forced
these categories onto a generic category-wide benchmark instead of their own
product line's real market price.
"""
from app.gem_radar.identity import is_likely_accessory, resolve_identity


class TestSsdIdentity:
    def test_samsung_pro_series(self):
        r = resolve_identity("Samsung 980 PRO 250GB M.2 NVMe 2280 Gen4 Solid State Drive (SSD) Grade A")
        assert r.category == "ssd"
        assert r.model is not None and "980" in r.model
        assert r.exact_sku_confidence > 0

    def test_samsung_part_number(self):
        r = resolve_identity("Samsung MZ-VLB256B 256GB M.2 PM981a NVMe PCIe Gen3x4 SSD")
        assert r.model is not None
        assert r.exact_sku_confidence > 0

    def test_wd_sn_series(self):
        r = resolve_identity("Western Digital WD Blue SN500 500GB M.2 2280 NVMe Internal SSD")
        assert r.model is not None and "SN500" in r.model.upper()
        assert r.exact_sku_confidence > 0

    def test_kingston_nv_series(self):
        r = resolve_identity("Kingston 1TB NV2 SSD M.2 PCIe 4.0 NVMe SNV2S/1000G")
        assert r.model is not None
        assert r.exact_sku_confidence > 0

    def test_intel_part_number(self):
        r = resolve_identity("Intel 670p Series 512GB M.2 2280 NVMe PCIe 3.0 x4 SSD - SSDPEKNU512GZ - Used UK")
        assert r.model is not None
        assert r.exact_sku_confidence > 0

    def test_generic_unbranded_ssd_stays_zero_confidence(self):
        # No real product line named — must NOT fabricate a model.
        r = resolve_identity("128GB 2242 M.2 NVMe SSD Solid State Drive Various Brands Error Free M-Key")
        assert r.model is None
        assert r.exact_sku_confidence == 0.0


class TestMotherboardIdentity:
    def test_msi_part_number(self):
        r = resolve_identity("MSI MS-7061 VER: 1 KM400 8237 Socket 462 / Socket A Motherboard")
        assert r.model is not None and "MS-7061" in r.model.upper()
        assert r.exact_sku_confidence > 0

    def test_gigabyte_part_number(self):
        r = resolve_identity("Gigabyte GA-H110M-S2H LGA1151 DDR4 Micro ATX Motherboard + Shield & Cooler")
        assert r.model is not None and "GA-H110M-S2H" in r.model.upper()
        assert r.exact_sku_confidence > 0

    def test_amd_chipset_code(self):
        r = resolve_identity("ASUS ROG Strix B650-A Gaming WiFi AMD AM5 ATX MOTHERBOARD")
        assert r.model is not None and "B650" in r.model.upper()
        assert r.exact_sku_confidence > 0

    def test_intel_chipset_code(self):
        r = resolve_identity("MSI Z370 Gaming PLUS ATX motherboard LGA1151 for Intel 8th 9th gen")
        assert r.model is not None and "Z370" in r.model.upper()
        assert r.exact_sku_confidence > 0

    def test_model_walk_stops_at_generic_descriptor_words(self):
        r = resolve_identity("ASUS PRIME A520M-A II mATX AM4 DDR4 Motherboard  NO I/0 PLATE")
        assert r.model is not None
        assert "ddr4" not in r.model.lower()
        assert "motherboard" not in r.model.lower()

    def test_non_chipset_shaped_model_number_not_matched_as_chipset(self):
        # "A13" here is an AIO liquid cooler's own product code embedded in a
        # cross-compatibility blurb, not an AMD A-series chipset (which is
        # always exactly 3 digits, e.g. A320/A520/A620) — must not be
        # fabricated into a motherboard identity.
        r = resolve_identity("MSI MAG Coreliquid A13 360 WHITE Motherboard, Processor All-in-one liquid cooler")
        assert r.model is None or "a13" not in (r.model or "").lower()

    def test_wifi_antenna_not_treated_as_motherboard(self):
        assert is_likely_accessory("2.4Ghz/5Ghz Dual Band WiFi Antenna For ASUS Z390 Z490 X570 Motherboard")

    def test_bios_chip_not_treated_as_motherboard(self):
        assert is_likely_accessory("MOTHERBOARD BIOS CHIP FOR ASUS H110M-A - FULLY PROGRAMMED")

    def test_compatibility_cable_not_treated_as_cooler(self):
        assert is_likely_accessory("USB Interface Cable for CORSAIR h80i V2 h90 h100i h110i")


class TestCoolerIdentity:
    def test_noctua_model(self):
        r = resolve_identity("Noctua NH-U9S chromax.black, 92mm Single-Tower CPU Cooler (Black)")
        assert r.model is not None and "NH-U9S" in r.model.upper()
        assert r.exact_sku_confidence > 0

    def test_be_quiet_product_line(self):
        r = resolve_identity("be quiet! Pure Rock Slim 2 CPU Cooler – Quiet Compact Air Cooler")
        assert r.model is not None
        assert r.exact_sku_confidence > 0

    def test_thermalright_product_line(self):
        r = resolve_identity("Thermalright AQUA ELITE 120 V3 Liquid CPU Cooler Double PWM ARGB Fans")
        assert r.model is not None
        assert r.exact_sku_confidence > 0

    def test_generic_cooler_without_brand_line_stays_zero_confidence(self):
        r = resolve_identity("Generic 120mm CPU Cooler Fan")
        assert r.model is None
        assert r.exact_sku_confidence == 0.0


class TestRamIdentityFillerWords:
    """RAM extraction previously required capacity and DDR-generation to sit
    immediately adjacent ("8GB DDR4") — real titles routinely put a filler
    word in between ("8GB Memory DDR4", "16GB Desktop RAM DDR4"), which
    silently zeroed out confidence for otherwise perfectly identifiable
    branded RAM."""

    def test_filler_word_between_capacity_and_generation(self):
        r = resolve_identity("Samsung M378A1K43CB2-CRC 8GB Memory DDR4 UDIMM 1Rx8 2400T-U RAM")
        assert r.model is not None
        assert r.exact_sku_confidence > 0

    def test_still_matches_adjacent_form(self):
        r = resolve_identity("Crucial 8GB DDR4 3200 UDIMM Performance RAM Module")
        assert r.model is not None
        assert r.exact_sku_confidence > 0
