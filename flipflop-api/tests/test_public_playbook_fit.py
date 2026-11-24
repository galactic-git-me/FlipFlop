from app.services.curated_build_policy import definitions
from app.services.playbook_fit import public_playbook_fit


def test_public_playbook_fit_explains_assignment_without_claiming_a_verified_match():
    cell = definitions()["builds"][0]

    result = public_playbook_fit({
        "curated_build_id": cell["id"],
        "customer_type": cell["segment"],
        "budget_tier": cell["tier"],
        "cell_name": cell["name"],
    })

    assert result["cell_name"] == f"{cell['segment']} · {cell['tier']}"
    assert result["customer_type"] == cell["segment"]
    assert result["budget_tier"] == cell["tier"]
    assert result["intended_use"] == cell["use"]
    assert "assigned" in result["explanation"]
    assert "verified" not in result["explanation"]


def test_public_playbook_fit_omits_unassigned_or_malformed_records():
    assert public_playbook_fit(None) is None
    assert public_playbook_fit({"customer_type": "Business & Office"}) is None
    assert public_playbook_fit({"customer_type": " ", "budget_tier": "Budget"}) is None


def test_public_playbook_fit_does_not_invent_curated_use_for_unknown_cell():
    result = public_playbook_fit({
        "curated_build_id": "missing-cell",
        "customer_type": "Business & Office",
        "budget_tier": "Budget",
    })

    assert result is not None
    assert result["cell_name"] == "Business & Office · Budget"
    assert result["intended_use"] is None
