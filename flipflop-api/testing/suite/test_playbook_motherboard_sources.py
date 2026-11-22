from app.services.playbook_motherboard_sources import extract_official_board_facts, _known_official_candidates


def test_captures_literal_msi_spec_fields_from_matching_official_page():
    html = """<html><head><title>MSI X870 GAMING PLUS WIFI Specifications</title></head>
    <body><h1>MSI X870 GAMING PLUS WIFI</h1>
    <p>AMD Socket AM5. AMD X870 chipset. 4 x DDR5 UDIMM.
    Maximum Memory Capacity 256GB. ATX Form Factor. 3 x M.2 slots.
    4 x SATA 6G. Wi-Fi 7.</p></body></html>"""

    result = extract_official_board_facts(
        html,
        "MSI X870 GAMING PLUS WIFI Motherboard (Socket AM5/X870/DDR5/ATX)",
        "https://www.msi.com/Motherboard/X870-GAMING-PLUS-WIFI/Specification",
    )

    assert result is not None
    assert result["facts"] == {
        "socket": "am5",
        "chipset": "x870",
        "ram_type": "ddr5",
        "ram_slots": 4,
        "max_ram_gb": 256,
        "form_factor": "atx",
        "m2_slots": 3,
        "sata_ports": 4,
        "wifi": True,
    }
    assert result["review_required"] is True
    assert set(result["facts"]).issubset(result["field_evidence"])


def test_rejects_an_official_page_for_a_different_board_model():
    html = """<html><head><title>MSI X870 GAMING PLUS WIFI</title></head>
    <body><h1>MSI X870 GAMING PLUS WIFI</h1><p>Socket AM5 DDR5 4 DIMM</p></body></html>"""

    result = extract_official_board_facts(
        html,
        "MSI MAG B850 GAMING PLUS MAX WIFI Motherboard, AM5, DDR5",
        "https://www.msi.com/Motherboard/X870-GAMING-PLUS-WIFI/Specification",
    )

    assert result is None


def test_captures_explicit_gigabyte_memory_and_m2_specs():
    html = """<html><head><title>X870 AORUS ELITE X3D ICE Motherboard Specifications</title></head>
    <body><h1>X870 AORUS ELITE X3D ICE</h1><p>AMD Socket AM5. AMD X870.
    4 x DDR5 DIMM sockets supporting up to 256 GB. 4 x M.2 Slots. 4 x SATA ports.</p></body></html>"""

    result = extract_official_board_facts(
        html,
        "GIGABYTE X870 AORUS ELITE X3D ICE Motherboard - Supports AMD Ryzen 9000 CPUs",
        "https://www.gigabyte.com/eu/Motherboard/X870-AORUS-ELITE-X3D-ICE/sp",
    )

    assert result is not None
    assert result["facts"]["socket"] == "am5"
    assert result["facts"]["ram_type"] == "ddr5"
    assert result["facts"]["ram_slots"] == 4
    assert result["facts"]["max_ram_gb"] == 256
    assert result["facts"]["m2_slots"] == 4


def test_captures_explicit_asus_socket_and_board_layout():
    html = """<html><head><title>ROG STRIX Z890-F GAMING WIFI Specifications</title></head>
    <body><h1>ROG STRIX Z890-F GAMING WIFI</h1><p>Intel LGA1851. Intel Z890.
    DDR5 memory, 4 x DIMM slots supporting up to 256 GB. ATX Form Factor.
    5 x M.2 slots. 4 x SATA 6Gb/s ports. WiFi 7.</p></body></html>"""

    result = extract_official_board_facts(
        html,
        "ASUS ROG STRIX Z890-F GAMING WIFI Motherboard, Intel LGA1851, DDR5",
        "https://rog.asus.com/motherboards/rog-strix/rog-strix-z890-f-gaming-wifi/spec/",
    )

    assert result is not None
    assert result["facts"]["socket"] == "lga1851"
    assert result["facts"]["chipset"] == "z890"
    assert result["facts"]["ram_slots"] == 4
    assert result["facts"]["form_factor"] == "atx"


def test_asus_title_matching_stops_before_trailing_cpu_socket_descriptors():
    html = """<html><head><title>ROG STRIX Z890-F GAMING WIFI | ROG</title></head>
    <body><h1>ROG STRIX Z890-F GAMING WIFI</h1>
    CPU Intel Socket LGA1851 for Intel Core Ultra Processors.
    Chipset Intel Z890 Chipset. Memory 4 x DIMM slots, max. 256GB, DDR5.
    Form Factor ATX Form Factor. Storage Supports 5 x M.2 slots and 4 x SATA 6Gb/s ports.
    </body></html>"""

    result = extract_official_board_facts(
        html,
        "ASUS ROG Strix Z890-F Gaming WiFi Intel LGA 1851 ATX Motherboard, DDR5",
        "https://rog.asus.com/motherboards/rog-strix/rog-strix-z890-f-gaming-wifi/spec/",
    )

    assert result is not None
    assert result["facts"]["socket"] == "lga1851"
    assert result["facts"]["chipset"] == "z890"
    assert result["facts"]["ram_type"] == "ddr5"
    assert result["facts"]["ram_slots"] == 4


def test_known_asus_product_paths_are_prioritised_for_all_supported_board_families():
    rog = _known_official_candidates("ASUS ROG Strix Z890-F Gaming WiFi Intel LGA 1851 ATX Motherboard")
    prime = _known_official_candidates("ASUS Prime B760M-K D4, an Intel B760 LGA 1700 mATX motherboard")
    tuf = _known_official_candidates("ASUS TUF Gaming X870-PLUS WIFI Motherboard, AM5 DDR5")

    assert rog[0]["source_url"] == "https://rog.asus.com/motherboards/rog-strix/rog-strix-z890-f-gaming-wifi/spec/"
    assert rog[1]["source_url"].endswith("rog-strix-z890-f-gaming-wifi-model/spec/")
    assert prime[0]["source_url"].endswith("/prime/prime-b760m-k-d4/techspec/")
    assert tuf[0]["source_url"].endswith("/tuf-gaming/tuf-gaming-x870-plus-wifi/techspec/")
