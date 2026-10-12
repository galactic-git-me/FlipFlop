from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.manual_builds import _getting_ready_generation_snapshot

from app.services.getting_started_service import (
    DriverReviewItem,
    GettingReadyGenerationError,
    GettingReadyManifest,
    REQUIRED_GETTING_READY_PROMPT_INPUTS,
    _component_for_name,
    _authoritative_software_install_plan,
    _render_user_prompt,
    _template_sections,
    _validate_and_bind_manifest_evidence,
    missing_component_manual_models,
    missing_component_driver_models,
    validate_component_driver_outcomes,
)
from app.services import getting_started_service
from app.services.getting_started_guide import guide_snapshot


def test_getting_started_guide_snapshot_normalizes_and_hashes_selected_source():
    guide, metadata = guide_snapshot(
        configured_guide="  Admin guide  ",
        request_guide="Request guide",
        generated_intro="Generated guide",
    )

    assert guide == "Admin guide\n"
    assert metadata == {
        "source": "admin_settings_upload",
        "sha256": sha256(guide.encode("utf-8")).hexdigest(),
    }


def test_getting_started_guide_snapshot_uses_generated_intro_as_hashed_fallback():
    guide, metadata = guide_snapshot(
        configured_guide=None,
        request_guide="  \n",
        generated_intro="  Generated intro  ",
    )

    assert guide == "Generated intro\n"
    assert metadata["source"] == "generated_manifest_intro"
    assert metadata["sha256"] == sha256(guide.encode("utf-8")).hexdigest()


def test_getting_started_guide_snapshot_returns_none_for_empty_candidates():
    assert guide_snapshot(configured_guide=" ", request_guide="\n") == (
        None,
        {"source": "none", "sha256": None},
    )


def _manifest(driver_item: DriverReviewItem) -> GettingReadyManifest:
    return GettingReadyManifest(
        template_version="1.7",
        build_name="Example Build",
        status="ready_for_admin_review",
        plaque={},
        customer_copy={},
        software_install_plan={},
        driver_and_firmware_review=[driver_item],
        manual_library_matches=[],
        upgrade_path={},
        portal_document_manifest=[],
    )


def test_manifest_rejects_unknown_nested_customer_facing_fields():
    payload = _manifest(DriverReviewItem(
        component_id="gpu-1",
        component_name="Example GPU",
        action="review_required",
        reason="Confirm the current driver from the manufacturer.",
    )).model_dump(mode="json")
    payload["customer_copy"]["unreviewed_html"] = "<script>run()</script>"

    with pytest.raises(ValidationError):
        GettingReadyManifest.model_validate(payload)


def test_manifest_rejects_unknown_portal_document_names():
    payload = _manifest(DriverReviewItem(
        component_id="gpu-1",
        component_name="Example GPU",
        action="review_required",
        reason="Confirm the current driver from the manufacturer.",
    )).model_dump(mode="json")
    payload["portal_document_manifest"] = ["workshop_setup_script"]

    with pytest.raises(ValidationError):
        GettingReadyManifest.model_validate(payload)


@pytest.mark.parametrize("template", [
    "# Missing sections",
    "## User prompt\ntext\n## System prompt\ntext\n## Output contract\n{}",
])
def test_prompt_loader_rejects_missing_or_misordered_sections(
    template, tmp_path, monkeypatch
):
    path = tmp_path / "getting-ready-package-prompt.md"
    path.write_text(template, encoding="utf-8")
    monkeypatch.setattr(getting_started_service, "_TEMPLATE_PATH", path)

    with pytest.raises(GettingReadyGenerationError, match="sections in order"):
        getting_started_service._template_sections()


def test_prompt_loader_rejects_template_version_drift_before_generation(
    tmp_path, monkeypatch
):
    path = tmp_path / "getting-ready-package-prompt.md"
    path.write_text(
        "Template version: 9.9\n\n## System prompt\nRules\n"
        "## User prompt\nInput\n## Output contract\n{}",
        encoding="utf-8",
    )
    monkeypatch.setattr(getting_started_service, "_TEMPLATE_PATH", path)

    with pytest.raises(GettingReadyGenerationError, match="version does not match"):
        getting_started_service._template_sections()


def test_prompt_loader_rejects_template_missing_a_required_build_input(
    tmp_path, monkeypatch
):
    path = tmp_path / "getting-ready-package-prompt.md"
    user_inputs = " ".join(
        "{{" + name + "}}"
        for name in sorted(REQUIRED_GETTING_READY_PROMPT_INPUTS - {"benchmark_results_json"})
    )
    path.write_text(
        "Template version: 1.7\n## System prompt\nRules\n"
        f"## User prompt\n{user_inputs}\n## Output contract\n{{}}",
        encoding="utf-8",
    )
    monkeypatch.setattr(getting_started_service, "_TEMPLATE_PATH", path)

    with pytest.raises(GettingReadyGenerationError, match="missing required inputs.*benchmark_results_json"):
        getting_started_service._template_sections()


def test_prompt_renderer_preserves_placeholder_like_text_inside_input_data():
    prompt = _render_user_prompt(
        '"build": {{build_name_json}}, "spec": {{build_specification_json}}',
        {
            "build_name": "Literal {{build_specification_json}} and {{customer_secret}}",
            "build_specification": {"component": "Example"},
        },
    )

    assert '"build":"Literal {{build_specification_json}} and {{customer_secret}}"' in prompt
    assert '"spec":{"component":"Example"}' in prompt


def test_prompt_renderer_rejects_unknown_template_placeholder():
    with pytest.raises(GettingReadyGenerationError, match="unknown input placeholder"):
        _render_user_prompt("{{unexpected_json}}", {})


def test_uploaded_getting_started_guide_is_not_sent_to_the_model():
    _system_prompt, user_template = _template_sections()
    prompt = _render_user_prompt(user_template, {
        "build_name": "Guide privacy test",
        "getting_started_guide_text": "PRIVATE GUIDE CONTENT " * 5000,
    })

    assert "PRIVATE GUIDE CONTENT" not in prompt


def test_component_reference_requires_the_exact_normalized_model_name():
    components = [{
        "component_id": "mb-1",
        "component_name": "MSI B850 GAMING PLUS WIFI",
    }]

    assert _component_for_name("msi b850 gaming plus wifi", components) == components[0]
    assert _component_for_name("MSI B850", components) is None


def test_driver_review_coverage_requires_each_distinct_exact_model_and_representative_id():
    components = [
        {"component_id": "gpu-1", "component_name": "Example RTX 5080"},
        {"component_id": "ram-1", "component_name": "Example DDR5 Kit"},
        {"component_id": "ram-2", "component_name": "Example DDR5 Kit"},
    ]
    manifest = {"driver_and_firmware_review": [
        {"component_id": "gpu-1", "component_name": "Example RTX 5080"},
        {"component_id": "ram-2", "component_name": "Example DDR5 Kit"},
    ]}

    assert missing_component_driver_models(components, manifest) == ["Example DDR5 Kit"]
    manifest["driver_and_firmware_review"][1]["component_id"] = "ram-1"
    assert missing_component_driver_models(components, manifest) == []
    assert missing_component_driver_models([], manifest) == ["(no build components recorded)"]


def test_driver_outcomes_must_match_every_exact_model_and_approved_source():
    components = [
        {"component_id": "cpu-1", "component_name": "Example CPU"},
        {"component_id": "gpu-1", "component_name": "Example GPU"},
    ]
    manifest = {
        "driver_and_firmware_review": [
            {"component_id": "cpu-1", "component_name": "Example CPU"},
            {"component_id": "gpu-1", "component_name": "Example GPU"},
        ],
        "sources": [{
            "component_name": "Example GPU",
            "topic": "driver_firmware",
            "source_url": "https://vendor.example/gpu-driver",
        }],
    }
    outcomes = [
        {"component_id": "cpu-1", "component_name": "Example CPU", "outcome": "no_update_applicable", "details": "Reviewed the exact model; no vendor update applies."},
        {"component_id": "gpu-1", "component_name": "Example GPU", "outcome": "updated", "source_url": "https://vendor.example/gpu-driver", "details": "Installed vendor graphics driver version 1.2.3."},
    ]

    assert len(validate_component_driver_outcomes(components, manifest, outcomes)) == 2
    with pytest.raises(ValueError, match="every exact model"):
        validate_component_driver_outcomes(components, manifest, outcomes[:1])
    outcomes[1]["source_url"] = "https://unapproved.example/driver"
    with pytest.raises(ValueError, match="approved research records"):
        validate_component_driver_outcomes(components, manifest, outcomes)


def test_component_reference_accepts_repeated_identical_parts_as_one_model():
    components = [
        {"component_id": "ram-left", "component_name": "Example DDR5 32GB Kit"},
        {"component_id": "ram-right", "component_name": "Example DDR5 32GB Kit"},
    ]

    assert _component_for_name("Example DDR5 32GB Kit", components) == components[0]


def test_manual_review_completeness_uses_distinct_exact_build_models():
    specification = [
        {"component_id": "cpu-1", "component_name": "Example CPU"},
        {"component_id": "gpu-1", "component_name": "Example GPU"},
        {"component_id": "gpu-2", "component_name": "Example GPU"},
    ]

    assert missing_component_manual_models(specification, {
        "manual_library_matches": [{"component_id": "cpu-1", "component_name": "Example CPU"}],
    }) == ["Example GPU"]
    assert missing_component_manual_models(specification, {
        "manual_library_matches": [{"component_id": "wrong-id", "component_name": "Example CPU"}],
    }) == ["Example CPU", "Example GPU"]
    assert missing_component_manual_models([], {"manual_library_matches": []}) == [
        "(no build components recorded)"
    ]


def test_manifest_fills_missing_component_driver_and_manual_reviews():
    manifest = _manifest(DriverReviewItem(
        component_id="gpu-1",
        component_name="Example GPU",
        action="review_required",
        reason="Confirm the current driver from the manufacturer.",
    ))
    manifest.manual_library_matches = []

    _validate_and_bind_manifest_evidence(manifest, {
        "build_specification": [
            {"component_id": "gpu-1", "component_name": "Example GPU"},
            {"component_id": "cpu-1", "component_name": "Example CPU"},
            {"component_id": "ram-left", "component_name": "Example DDR5 32GB Kit"},
            {"component_id": "ram-right", "component_name": "Example DDR5 32GB Kit"},
        ],
    })

    assert {item.component_name for item in manifest.driver_and_firmware_review} == {
        "Example GPU", "Example CPU", "Example DDR5 32GB Kit",
    }
    assert {item.component_id for item in manifest.driver_and_firmware_review} == {
        "gpu-1", "cpu-1", "ram-left",
    }
    assert all(item.administrator_approval_required for item in manifest.driver_and_firmware_review)
    assert {item.component_name for item in manifest.manual_library_matches} == {
        "Example GPU", "Example CPU", "Example DDR5 32GB Kit",
    }
    assert {item.component_id for item in manifest.manual_library_matches} == {
        "gpu-1", "cpu-1", "ram-left",
    }
    assert all(item.match_status == "needs_research" for item in manifest.manual_library_matches)
    assert all(item.administrator_approval_required for item in manifest.manual_library_matches)


def test_manifest_fallback_preserves_exact_approved_sources_when_model_omits_rows():
    manifest = _manifest(DriverReviewItem(
        component_id="gpu-1",
        component_name="Example GPU",
        action="review_required",
        reason="Confirm the current driver from the manufacturer.",
    ))
    manifest.manual_library_matches = []
    driver_url = "https://vendor.example/support/example-cpu"
    manual_url = "https://vendor.example/manuals/example-cpu.pdf"

    _validate_and_bind_manifest_evidence(manifest, {
        "build_specification": [
            {"component_id": "gpu-1", "component_name": "Example GPU"},
            {"component_id": "cpu-1", "component_name": "Example CPU"},
        ],
        "approved_research_bundle": [
            {
                "topic": "driver_firmware",
                "component_name": "Example CPU",
                "source_url": driver_url,
                "title": "CPU support page",
                "accessed_at": "2026-09-30",
            },
            {
                "topic": "manual",
                "component_name": "Example CPU",
                "source_url": manual_url,
                "title": "CPU manual",
                "accessed_at": "2026-09-30",
            },
        ],
    })

    driver = next(item for item in manifest.driver_and_firmware_review if item.component_name == "Example CPU")
    manual = next(item for item in manifest.manual_library_matches if item.component_name == "Example CPU")
    assert driver.source_url == driver_url
    assert driver.source_title == "CPU support page"
    assert driver.source_accessed_at == "2026-09-30"
    assert driver.administrator_approval_required is True
    assert manual.manual_url == manual_url
    assert manual.manual_title == "CPU manual"
    assert manual.match_status == "needs_admin_confirmation"
    assert manual.administrator_approval_required is True


def test_generated_software_plan_uses_saved_ids_and_authoritative_installer_scope():
    plan = _authoritative_software_install_plan({
        "customer_software_selections": ["Discord.Discord", "7zip.7zip"],
        "software_install_scopes": [
            {"package_id": "Discord.Discord", "scope": "customer_profile"},
            {"package_id": "7zip.7zip", "scope": "machine"},
        ],
    })

    assert plan["selected_package_ids"] == ["Discord.Discord", "7zip.7zip"]
    assert plan["machine_scope_package_ids"] == ["7zip.7zip"]
    assert plan["customer_profile_package_ids"] == ["Discord.Discord"]
    assert plan["unresolved_package_ids"] == []


def test_generated_software_plan_rejects_scope_drift_from_allow_list():
    with pytest.raises(GettingReadyGenerationError, match="does not match the software allow-list"):
        _authoritative_software_install_plan({
            "customer_software_selections": ["Discord.Discord"],
            "software_install_scopes": [{"package_id": "Discord.Discord", "scope": "machine"}],
        })


def test_manifest_rejects_partial_component_name_even_when_unique():
    manifest = _manifest(DriverReviewItem(
        component_id="mb-1",
        component_name="MSI B850",
        action="review_required",
        reason="Check the chipset driver.",
    ))

    with pytest.raises(GettingReadyGenerationError, match="no exact component"):
        _validate_and_bind_manifest_evidence(manifest, {
            "build_specification": [{
                "component_id": "mb-1",
                "component_name": "MSI B850 GAMING PLUS WIFI",
            }],
        })


def test_manifest_binds_exact_component_to_admin_approved_source_metadata():
    source_url = "https://www.msi.com/Motherboard/B850-GAMING-PLUS-WIFI/support"
    manifest = _manifest(DriverReviewItem(
        component_id="model-invented-id",
        component_name="MSI B850 GAMING PLUS WIFI",
        action="review_required",
        reason="Check the chipset driver.",
        source_url=source_url,
        source_title="Model supplied title",
        source_accessed_at="2099-01-01",
    ))
    approved_source = {
        "topic": "driver_firmware",
        "component_name": "MSI B850 GAMING PLUS WIFI",
        "source_url": source_url,
        "title": "Administrator reviewed source title",
        "accessed_at": "2026-09-29",
    }

    _validate_and_bind_manifest_evidence(manifest, {
        "build_specification": [{
            "component_id": "mb-1",
            "component_name": "MSI B850 GAMING PLUS WIFI",
        }],
        "approved_research_bundle": [approved_source],
    })

    bound = manifest.driver_and_firmware_review[0]
    assert bound.component_id == "mb-1"
    assert bound.source_title == "Administrator reviewed source title"
    assert bound.source_accessed_at == "2026-09-29"
    assert bound.administrator_approval_required is True


def test_getting_ready_generation_snapshot_tracks_persisted_build_evidence():
    build = SimpleNamespace(
        name="Example Build",
        status="sold",
        order_id=10,
        customer_id=3,
        components=[{"component_id": "cpu-1", "component_name": "Example CPU"}],
        evidence_data={
            "benchmark_results": {"score": 123},
            "playbook_assignment": {"playbook_id": 4, "budget_tier": "mid_range"},
        },
        delivered_at=None,
    )

    original = _getting_ready_generation_snapshot(build)
    assert _getting_ready_generation_snapshot(build) == original

    build.components[0]["component_name"] = "Different CPU"
    assert _getting_ready_generation_snapshot(build) != original

    build.components[0]["component_name"] = "Example CPU"
    build.evidence_data["benchmark_results"]["score"] = 124
    assert _getting_ready_generation_snapshot(build) != original

    build.evidence_data["benchmark_results"]["score"] = 123
    build.delivered_at = datetime(2026, 9, 29, tzinfo=timezone.utc)
    assert _getting_ready_generation_snapshot(build) != original
