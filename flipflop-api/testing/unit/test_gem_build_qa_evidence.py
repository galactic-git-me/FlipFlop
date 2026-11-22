from types import SimpleNamespace

from app.services import gem_build_qa


def test_unreviewed_configurator_fields_are_not_promoted_by_exact_capture(monkeypatch):
    listing = SimpleNamespace(
        url="https://vendor.example/product/1",
        title="CPU listing",
        raw_specs={
            "configurator": {
                "source_url": "https://vendor.example/product/1",
                "reviewed": False,
                "socket": "am5",
                "power_w": 999,
                "cpu_id": "unsupported-id",
            },
            "playbook_product_capture": {
                "url": "https://vendor.example/product/1",
                "product_properties": {"Socket": "AM5"},
            },
        },
    )
    received = {}

    def capture(role, source_listing, source, engineering, *, allow_title_facts):
        received["engineering"] = engineering
        received["allow_title_facts"] = allow_title_facts
        return {**engineering, "socket": "am5", "reviewed": True}

    monkeypatch.setattr("app.services.playbook_service._apply_exact_source_core_engineering", capture)
    facts = gem_build_qa._engineering("cpu", listing, listing.title)

    assert received["engineering"] == {"reviewed": False}
    assert received["allow_title_facts"] is False
    assert "power_w" not in facts
    assert "cpu_id" not in facts
    assert facts["socket"] == "am5"
