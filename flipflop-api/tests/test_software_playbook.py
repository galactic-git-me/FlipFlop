from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from types import SimpleNamespace

from app.models.curated_build_segment import CuratedBuildSegment
from app.models.playbook import Playbook
from app.api.orders import _getting_started_recommendation_profile
from app.schemas.product_checkout import ProductCheckoutIntentRequest, ProductCheckoutOptionsRequest
from app.services.product_software import software_profile_for_playbook_cell_from_db
from app.services.getting_started_service import (
    customer_software_selection_changed,
    invalidate_ready_to_ship_reviewed_package,
)
from app.services.software_catalogue import (
    SOFTWARE_BY_ID,
    default_software_profile_for_playbook,
    estimate_saved_minutes,
    normalize_software_profile,
    create_customer_profile_software_install_script,
    create_master_setup_script,
    create_software_install_script,
    customer_software_selection_from_metadata,
    initial_customer_software_selection,
    serialize_customer_software_selection,
    updated_customer_software_selection,
)


@pytest.mark.parametrize(("playbook_name", "expected_ids"), [
    ("Great-value Gaming", ["Valve.Steam", "Discord.Discord", "VideoLAN.VLC", "7zip.7zip"]),
    ("High-performance Gaming", ["Valve.Steam", "Discord.Discord", "OBSProject.OBSStudio", "VideoLAN.VLC", "7zip.7zip"]),
    ("Student Hybrid", ["Mozilla.Firefox", "Notepad++.Notepad++", "VideoLAN.VLC", "7zip.7zip"]),
    ("Business & Office", ["Mozilla.Firefox", "Notepad++.Notepad++", "ShareX.ShareX", "7zip.7zip"]),
    ("Content Creation", ["GIMP.GIMP", "BlenderFoundation.Blender", "OBSProject.OBSStudio", "VideoLAN.VLC", "7zip.7zip"]),
    ("AI Workstation", ["Microsoft.VisualStudioCode", "Git.Git", "Python.Python.3.12", "BlenderFoundation.Blender", "7zip.7zip"]),
    ("Software Development", ["Microsoft.VisualStudioCode", "Git.Git", "Python.Python.3.12", "7zip.7zip"]),
    ("Family & Home", ["Mozilla.Firefox", "VideoLAN.VLC", "ShareX.ShareX", "7zip.7zip"]),
])
def test_canonical_playbook_uses_its_reviewed_software_profile(playbook_name, expected_ids):
    profile = default_software_profile_for_playbook(playbook_name)

    assert profile["profile_source"] == "reviewed_default_v1"
    assert profile["recommended_package_ids"] == expected_ids
    assert all(package_id in SOFTWARE_BY_ID for package_id in expected_ids)
    assert profile["rationale"].strip()


def test_saved_time_estimate_uses_only_the_customer_selected_apps():
    selected = ["7zip.7zip", "Valve.Steam"]

    assert estimate_saved_minutes(selected) == 9
    assert estimate_saved_minutes([]) == 0


def test_documented_recommendations_and_time_estimates_match_runtime_profiles():
    workspace = Path(__file__).resolve().parents[2]
    document = (workspace / "docs" / "playbook" / "software-playbook.md").read_text(encoding="utf-8")
    section = document.split("## Reviewed use-case recommendations", 1)[1].split("## Approved application catalogue", 1)[0]

    rows = [line for line in section.splitlines() if line.startswith("|")]
    for row in rows[2:]:  # skip table header and separator
        use_case, documented_apps, documented_minutes, _rationale = [cell.strip() for cell in row.strip("|").split("|")]
        profile = default_software_profile_for_playbook(use_case)
        runtime_apps = [SOFTWARE_BY_ID[package_id]["name"] for package_id in profile["recommended_package_ids"]]

        assert documented_apps.split(", ") == runtime_apps
        assert int(documented_minutes) == estimate_saved_minutes(profile["recommended_package_ids"])


def test_ready_to_ship_selection_change_retires_reviewed_archives_and_reopens_review():
    reviewed_at = datetime(2026, 9, 29, 12)
    job = SimpleNamespace(
        artifact_index=[
            {"category": "customer_package", "version": 3, "storage_key": "42/customer.zip"},
            {"category": "portal_leaflet", "grant_id": "claim-1"},
        ],
        reviewed_at=reviewed_at,
        private_storage_key="42/customer.zip",
        manifest={"software_plan": {"package_ids": ["7zip.7zip"]}},
        generated_at=reviewed_at,
        status="ready_for_delivery",
        checklist={"customer_package": "complete", "customer_selections_locked": "complete"},
    )
    build = SimpleNamespace(evidence_data={"getting_ready": {"package": {"version": 3}, "status": "package_ready"}})

    invalidated = invalidate_ready_to_ship_reviewed_package(job, build)

    assert invalidated is True
    assert job.artifact_index[0]["category"] == "superseded_customer_package"
    assert job.artifact_index[0]["version"] == 3
    assert job.artifact_index[1]["category"] == "portal_leaflet"
    assert job.reviewed_at is None
    assert job.private_storage_key is None
    assert job.manifest is None
    assert job.generated_at is None
    assert job.status == "awaiting_admin_review"
    assert job.checklist["customer_package"] == "not_ready"
    assert "package" not in build.evidence_data["getting_ready"]


def test_changed_windows_target_retires_package_without_unlocking_customer_choices():
    job = SimpleNamespace(
        artifact_index=[{"category": "customer_package", "version": 2, "storage_key": "build/customer.zip"}],
        reviewed_at=datetime(2026, 9, 29, 12),
        private_storage_key="build/customer.zip",
        manifest={"windows_target": "old"},
        generated_at=datetime(2026, 9, 29, 12),
        status="ready_for_delivery",
        checklist={"customer_selections_locked": "complete", "customer_package": "complete"},
    )
    build = SimpleNamespace(evidence_data={"getting_ready": {"package": {"version": 2}}})

    invalidated = invalidate_ready_to_ship_reviewed_package(
        job,
        build,
        checklist_reset_keys=("content_manifest", "artifacts_generated", "artifacts_reviewed", "customer_package"),
    )

    assert invalidated is True
    assert job.artifact_index[0]["category"] == "superseded_customer_package"
    assert job.checklist["customer_selections_locked"] == "complete"
    assert job.checklist["customer_package"] == "not_ready"
    assert "package" not in build.evidence_data["getting_ready"]


def test_manifest_regeneration_reset_set_retires_package_and_both_driver_gates():
    job = SimpleNamespace(
        artifact_index=[{"category": "customer_package", "version": 4, "storage_key": "build/customer.zip", "workshop_storage_key": "build/workshop.zip"}],
        reviewed_at=datetime(2026, 9, 29, 12),
        private_storage_key="build/customer.zip",
        manifest={"old": True},
        generated_at=datetime(2026, 9, 29, 12),
        status="ready_for_delivery",
        checklist={
            "component_manuals_reviewed": "complete",
            "driver_firmware_reviewed": "complete",
            "drivers_updates_complete": "complete",
            "customer_package": "complete",
        },
    )
    build = SimpleNamespace(evidence_data={"getting_ready": {"package": {"version": 4}}})

    invalidate_ready_to_ship_reviewed_package(
        job,
        build,
        checklist_reset_keys=(
            "customer_selections_locked", "content_manifest", "artifacts_generated",
            "artifacts_reviewed", "customer_package", "component_manuals_reviewed",
            "driver_firmware_reviewed", "drivers_updates_complete",
        ),
    )

    assert job.artifact_index[0]["category"] == "superseded_customer_package"
    assert job.private_storage_key is None
    assert job.checklist["driver_firmware_reviewed"] == "not_ready"
    assert job.checklist["drivers_updates_complete"] == "not_ready"
    assert job.checklist["customer_package"] == "not_ready"


def test_resubmitting_same_software_selection_is_idempotent_and_order_independent():
    job = SimpleNamespace(
        customer_software_selections=["7zip.7zip", "Valve.Steam"],
        checklist={"software_selection_submitted": True},
    )

    assert customer_software_selection_changed(job, ["Valve.Steam", "7zip.7zip"]) is False
    assert customer_software_selection_changed(job, ["7zip.7zip"]) is True


def test_first_software_selection_submission_invalidates_even_when_it_matches_saved_seed():
    job = SimpleNamespace(
        customer_software_selections=["7zip.7zip"],
        checklist={"software_selection_submitted": False},
    )

    assert customer_software_selection_changed(job, ["7zip.7zip"]) is True


def test_ready_to_ship_checkout_distinguishes_unsubmitted_and_empty_software_choices():
    addresses = {
        "delivery": {
            "contact_name": "Customer One", "address_line1": "1 Test Road",
            "city": "London", "postal_code": "SW1A 1AA",
        },
        "billing": {
            "contact_name": "Customer One", "address_line1": "1 Test Road",
            "city": "London", "postal_code": "SW1A 1AA",
        },
    }

    unsubmitted = ProductCheckoutIntentRequest(checkout_addresses=addresses)
    choose_none = ProductCheckoutIntentRequest(checkout_addresses=addresses, software_package_ids=[])
    unchanged = ProductCheckoutOptionsRequest(intent_id="pi_12345678", checkout_addresses=addresses)
    clear_selection = ProductCheckoutOptionsRequest(
        intent_id="pi_12345678", checkout_addresses=addresses, software_package_ids=[]
    )

    assert unsubmitted.software_package_ids is None
    assert choose_none.software_package_ids == []
    assert unchanged.software_package_ids is None
    assert clear_selection.software_package_ids == []


def test_software_selection_defaults_once_then_preserves_explicit_and_saved_choices():
    recommended = ["7zip.7zip", "VideoLAN.VLC"]
    assert initial_customer_software_selection(None, recommended) == recommended
    assert initial_customer_software_selection([], recommended) == []
    encoded_none = serialize_customer_software_selection([])
    assert encoded_none and encoded_none != ""
    assert customer_software_selection_from_metadata(
        {"software_package_ids": encoded_none}, recommended
    ) == []
    assert customer_software_selection_from_metadata({}, recommended) == recommended
    assert updated_customer_software_selection(
        None, {"software_package_ids": "Mozilla.Firefox"}, recommended
    ) == ["Mozilla.Firefox"]
    assert updated_customer_software_selection(
        None, {"software_package_ids": ""}, recommended
    ) == []
    assert updated_customer_software_selection([], {"software_package_ids": "7zip.7zip"}, recommended) == []
    assert updated_customer_software_selection(None, {}, recommended) == recommended
    with pytest.raises(ValueError, match="Unsupported software package IDs"):
        updated_customer_software_selection(
            None, {"software_package_ids": "Unknown.Unreviewed"}, recommended
        )


def test_software_profile_rejects_package_ids_outside_the_reviewed_allow_list():
    with pytest.raises(ValueError, match="Unsupported software package IDs"):
        normalize_software_profile({
            "recommended_package_ids": ["Unknown.UnreviewedInstaller"],
            "rationale": "Must be rejected rather than passed into the installer.",
        })


def test_audit_mode_installer_explicitly_uses_machine_scope_and_skips_user_only_apps():
    script = create_software_install_script(["7zip.7zip", "Discord.Discord"])

    assert "--id '7zip.7zip' --exact --source winget --scope machine" in script
    assert "Discord.Discord" not in script
    assert "--accept-package-agreements" not in script


def test_user_scoped_app_installer_leaves_agreements_for_customer_to_review():
    script = create_customer_profile_software_install_script(["Discord.Discord"])

    assert "--id 'Discord.Discord' --exact --source winget --scope user" in script
    assert "--silent" in script
    assert "--disable-interactivity" not in script
    assert "--accept-source-agreements" not in script
    assert "--accept-package-agreements" not in script
    assert "customer-apps-installed.json" in script
    assert "EndsWith('-500')" in script
    assert "FlipFlop will retry this setup at your next sign-in" in script
    assert "--scope machine" not in script
    assert "--accept-package-agreements" not in script


def test_master_setup_schedules_customer_profile_installer_after_oobe():
    script = create_master_setup_script(
        build_name="Customer Build",
        portal_url="https://theflipflop.shop/my-builds/9001",
        customer_profile_apps_selected=True,
    )

    assert "scheduled_for_customer_first_sign_in" in script
    assert "CommonStartup" in script
    assert "FlipFlop Customer Apps.lnk" in script
    assert "install-customer-profile-apps.ps1" in script


@pytest.mark.asyncio
async def test_made_by_you_uses_the_customer_declared_playbook_budget_cell(db: AsyncSession):
    db.add(CuratedBuildSegment(
        customer_type="Software Development",
        budget_level="High-end",
        software_profile={
            "recommended_package_ids": ["Git.Git", "Microsoft.VisualStudioCode"],
            "rationale": "Reviewed High-end developer setup.",
        },
    ))
    await db.flush()

    profile = await software_profile_for_playbook_cell_from_db(
        db,
        "Software Development",
        "High-end",
    )

    assert profile["profile_source"] == "admin_reviewed_playbook_cell"
    assert profile["budget_tier"] == "High-end"
    assert profile["recommended_package_ids"] == ["Git.Git", "Microsoft.VisualStudioCode"]
    assert profile["playbook_cell"] == "Software Development / High-end"


@pytest.mark.asyncio
async def test_made_by_you_uses_reviewed_use_case_fallback_if_cell_profile_is_missing(db: AsyncSession):
    profile = await software_profile_for_playbook_cell_from_db(
        db,
        "Business & Office",
        "Budget",
    )

    assert profile["budget_tier"] == "Budget"
    assert profile["profile_source"] == "reviewed_default_v1"
    assert profile["recommended_package_ids"] == default_software_profile_for_playbook("Business & Office")["recommended_package_ids"]


@pytest.mark.asyncio
async def test_made_by_you_rejects_an_unrecognized_budget_tier(db: AsyncSession):
    with pytest.raises(ValueError, match="Choose Budget, Mid-range, or High-end"):
        await software_profile_for_playbook_cell_from_db(db, "Business & Office", "Premium")


@pytest.mark.asyncio
async def test_legacy_order_without_saved_profile_recovers_the_reviewed_budget_cell(db: AsyncSession):
    playbook = Playbook(
        name="Software Development",
        software_profile={
            "recommended_package_ids": ["7zip.7zip"],
            "rationale": "Playbook-wide fallback.",
        },
    )
    db.add(playbook)
    db.add(CuratedBuildSegment(
        customer_type="Software Development",
        budget_level="High-end",
        software_profile={
            "recommended_package_ids": ["Git.Git", "Microsoft.VisualStudioCode"],
            "rationale": "Reviewed High-end cell profile.",
        },
    ))
    await db.flush()
    order = SimpleNamespace(specs={"budget_tier": "High-end"}, playbook_id=playbook.id)
    job = SimpleNamespace(playbook_id=None, source_type="made_by_you")

    profile = await _getting_started_recommendation_profile(db, order, job, None)

    assert profile["profile_source"] == "admin_reviewed_playbook_cell"
    assert profile["recommended_package_ids"] == ["Git.Git", "Microsoft.VisualStudioCode"]
    assert profile["rationale"] == "Reviewed High-end cell profile."


@pytest.mark.asyncio
async def test_legacy_curated_order_without_saved_profile_recovers_its_curated_cell(db: AsyncSession):
    from app.services.curated_build_policy import definitions

    cell = definitions()["builds"][0]
    playbook = Playbook(name=cell["segment"], software_profile=None)
    authored_profile = {
        "recommended_package_ids": ["Mozilla.Firefox", "7zip.7zip"],
        "rationale": "Reviewed curated cell setup.",
    }
    db.add(playbook)
    db.add(CuratedBuildSegment(
        customer_type=cell["segment"],
        budget_level=cell["tier"],
        software_profile=authored_profile,
    ))
    await db.flush()
    order = SimpleNamespace(specs={"curated_build_id": cell["id"]})
    job = SimpleNamespace(playbook_id=playbook.id, source_type="curated_for_you")

    profile = await _getting_started_recommendation_profile(db, order, job, None)

    assert profile["profile_source"] == "admin_reviewed_curated_cell"
    assert profile["curated_build_id"] == cell["id"]
    assert profile["recommended_package_ids"] == authored_profile["recommended_package_ids"]
    assert profile["rationale"] == authored_profile["rationale"]
