from scripts.propose_identity_reconciliation import build_proposal


def product(cpk, **data):
    return {"cpk": cpk, "cpk_data": data}


def test_unique_mpn_match_is_pending_with_high_confidence():
    result = build_proposal(
        {"title": "AMD Ryzen 7 7800X3D", "mpn": "100-100000910WOF", "model": None, "gtin": None},
        [product("a", brand="AMD", model="7800X3D", mpn="100100000910WOF")],
    )
    assert result["suggested_cpk"] == "a"
    assert result["method"] == "exact_identifier"
    assert result["confidence"] == 0.99


def test_conflicting_identifier_never_suggests_a_merge():
    sold = {"title": "RTX 3060", "mpn": "RTX3060", "model": None, "gtin": None}
    result = build_proposal(sold, [product("a", model="RTX3060"), product("b", model="RTX3060")])
    assert result["suggested_cpk"] is None
    assert result["status"] == "ambiguous"


def test_no_candidate_is_unresolved():
    result = build_proposal({"title": "generic DDR4 memory", "mpn": None, "model": None, "gtin": None}, [])
    assert result["status"] == "unresolved"
    assert result["candidate_cpks"] == []
