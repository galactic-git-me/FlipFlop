from base64 import b64encode
import hashlib
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from xml.etree import ElementTree
from zipfile import ZipFile

from app.api.orders import _customer_package_archive_response, _read_customer_package_document
from app.services import getting_ready_package
from app.services.getting_ready_package import (
    GettingReadyPackageError,
    _portal_leaflet_pdf,
    _paid_ai_setup_runbook,
    _prepare_customer_oobe_script,
    _windows_deployment_script,
    _windows_setup_answer_file,
    render_dispatch_checklist,
)
from app.services.software_catalogue import create_rainmeter_install_script
from app import template_paths


def test_order_specific_portal_leaflet_is_a_two_page_pdf():
    leaflet = _portal_leaflet_pdf(
        build_name="Example Build",
        access_url="https://flipflop.shop/my-builds/123#private-claim",
        claim_code=True,
    )

    assert leaflet.startswith(b"%PDF-")
    assert len(re.findall(rb"/Type\s*/Page(?!s)\b", leaflet)) == 2


def test_api_packaged_dispatch_templates_match_canonical_and_resolve_without_repo_docs(monkeypatch, tmp_path):
    repository_root = Path(__file__).resolve().parents[2] / "templates" / "dispatch"
    packaged_root = Path(template_paths.__file__).resolve().parent / "templates" / "dispatch"
    names = (
        "getting-ready-package-prompt.md",
        "dispatch-checklist.md",
        "rainmeter/FlipFlop.ini",
    )

    for name in names:
        assert (packaged_root / name).read_bytes() == (repository_root / name).read_bytes()

    monkeypatch.setattr(template_paths, "_REPOSITORY_TEMPLATE_ROOT", tmp_path / "templates" / "dispatch")
    monkeypatch.setattr(template_paths, "_PACKAGED_TEMPLATE_ROOT", packaged_root)
    for name in names:
        assert template_paths.dispatch_template_path(name) == packaged_root / name
    assert template_paths.dispatch_template_path() == packaged_root

    canonical_root = tmp_path / "canonical" / "dispatch"
    canonical_root.mkdir(parents=True)
    (canonical_root / names[0]).write_text("canonical", encoding="utf-8")
    monkeypatch.setattr(template_paths, "_REPOSITORY_TEMPLATE_ROOT", canonical_root)
    assert template_paths.dispatch_template_path(names[0]) == canonical_root / names[0]


def _assemble_test_package(tmp_path, monkeypatch, purchases):
    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path / "packages")
    manifest = {
        "status": "ready_for_admin_review",
        "build_name": "Runbook Test Build",
        "plaque": {},
        "customer_copy": {"getting_started_intro": "Read the current getting started guide."},
        "manual_library_matches": [],
        "driver_and_firmware_review": [],
        "upgrade_path": {},
        "warnings": [],
    }
    source_inputs = {
        "getting_started_guide_text": "Follow the included setup guide.",
        "purchased_ai_services": purchases,
    }
    artifact = getting_ready_package.assemble_getting_ready_package(
        build_id=9001,
        build_name="Runbook Test Build",
        version=1,
        specification=[],
        benchmark_results={},
        manifest=manifest,
        software_package_ids=[],
        source_inputs=source_inputs,
        portal_url=None,
        target_drive_model="Test NVMe 2TB",
        target_drive_serial="TEST-SERIAL-9001",
        target_drive_inspected_at_utc="2026-09-29T12:00:00+00:00",
    )
    return tmp_path / "packages" / "9001" / artifact["workshop_filename"]


def test_paid_ai_runbook_uses_only_confirmed_paid_services():
    runbook = _paid_ai_setup_runbook([{
        "id": "ai_assistant_automation_pack",
        "name": "AI assistant and automation setup",
        "payment_status": "paid",
    }])

    assert runbook is not None
    assert "Confirm the assistant choice" in runbook
    assert "do not assume Hermes, OpenClaw" in runbook
    assert "Research brief" in runbook
    assert "never request, copy or store passwords" in runbook


def test_local_model_runbook_requires_recorded_vram_and_customer_model_choice():
    runbook = _paid_ai_setup_runbook([{
        "id": "local_llm_setup",
        "name": "Local AI model setup",
        "payment_status": "paid",
    }])

    assert runbook is not None
    assert "measured GPU VRAM is at least 12 GB" in runbook
    assert "Confirm the exact model with the customer" in runbook
    assert "Configure local-only access" in runbook


def test_ai_runbook_is_omitted_without_a_paid_service():
    assert _paid_ai_setup_runbook([]) is None
    assert _paid_ai_setup_runbook(None) is None


@pytest.mark.parametrize("purchase", [
    {"id": "ai_assistant_automation_pack", "name": "AI assistant and automation setup", "payment_status": "pending"},
    {"id": "unreviewed_installer", "name": "Installer", "payment_status": "paid"},
    {"id": "local_llm_setup", "name": "Wrong offer name", "payment_status": "paid"},
])
def test_ai_runbook_rejects_unpaid_unknown_or_changed_offer_records(purchase):
    with pytest.raises(GettingReadyPackageError):
        _paid_ai_setup_runbook([purchase])


def test_package_contains_ai_runbook_for_paid_offer_only(tmp_path, monkeypatch):
    archive_path = _assemble_test_package(tmp_path, monkeypatch, [{
        "id": "local_llm_setup",
        "name": "Local AI model setup",
        "payment_status": "paid",
    }])

    with ZipFile(archive_path) as archive:
        name = "05-workshop-setup/AI/paid-ai-setup-runbook.md"
        assert name in archive.namelist()
        assert b"measured GPU VRAM is at least 12 GB" in archive.read(name)


def test_package_omits_ai_runbook_when_no_ai_service_was_purchased(tmp_path, monkeypatch):
    archive_path = _assemble_test_package(tmp_path, monkeypatch, [])

    with ZipFile(archive_path) as archive:
        assert "05-workshop-setup/AI/paid-ai-setup-runbook.md" not in archive.namelist()


def test_user_scope_app_is_deferred_to_customer_profile_and_disclosed(tmp_path, monkeypatch):
    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path / "packages")
    manifest = {
        "status": "ready_for_admin_review",
        "build_name": "Customer Profile Test",
        "plaque": {},
        "customer_copy": {},
        "manual_library_matches": [],
        "driver_and_firmware_review": [],
        "upgrade_path": {},
        "warnings": [],
    }
    artifact = getting_ready_package.assemble_getting_ready_package(
        build_id=9002,
        build_name="Customer Profile Test",
        version=1,
        specification=[],
        benchmark_results={},
        manifest=manifest,
        software_package_ids=["Discord.Discord"],
        source_inputs={"getting_started_guide_text": "Welcome to your build."},
        portal_url="https://theflipflop.shop/my-builds/9002",
        target_drive_model="Test NVMe 2TB",
        target_drive_serial="TEST-SERIAL-9002",
        target_drive_inspected_at_utc="2026-09-29T12:00:00+00:00",
    )

    archive_path = tmp_path / "packages" / "9002" / artifact["filename"]
    workshop_path = tmp_path / "packages" / "9002" / artifact["workshop_filename"]
    with ZipFile(workshop_path) as archive:
        deployment_script = archive.read("06-windows-setup/Deploy-Windows11-Pro.ps1").decode("utf-8-sig")
        assert b64encode(b"Test NVMe 2TB").decode("ascii") in deployment_script
        assert b64encode(b"TEST-SERIAL-9002").decode("ascii") in deployment_script
        assert b64encode(b"2026-09-29T12:00:00+00:00").decode("ascii") in deployment_script
        assert "targetInspectionAge.TotalDays -gt 30" in deployment_script
        assert "ExpectedDiskModel" not in deployment_script
        assert "ExpectedDiskSerial" not in deployment_script
        user_installer_path = "05-workshop-setup/install-customer-profile-apps.ps1"
        assert user_installer_path in archive.namelist()
        assert "--scope user" in archive.read(user_installer_path).decode("utf-8-sig")
        master = archive.read("05-workshop-setup/run-getting-ready.ps1").decode("utf-8-sig")
        assert "scheduled_for_customer_first_sign_in" in master
        guide = archive.read("04-getting-started-guide.md").decode("utf-8")
        assert "Discord" in guide
        assert "first sign-in" in guide
        assert "FlipFlop does not accept package terms for you" in guide
    with ZipFile(archive_path) as customer_archive:
        assert "04-getting-started-guide.md" in customer_archive.namelist()
        assert not any(name.endswith((".ps1", ".xml")) for name in customer_archive.namelist())


def test_customer_package_contains_customer_documents_only(tmp_path, monkeypatch):
    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path / "packages")
    artifact = getting_ready_package.assemble_getting_ready_package(
        build_id=9003,
        build_name="Portal Safety Build",
        version=1,
        specification=[],
        benchmark_results={},
        manifest={
            "status": "ready_for_admin_review",
            "build_name": "Portal Safety Build",
            "plaque": {},
            "customer_copy": {},
            "manual_library_matches": [],
            "driver_and_firmware_review": [],
            "upgrade_path": {},
            "warnings": [],
        },
        software_package_ids=[],
        source_inputs={"getting_started_guide_text": "Customer guide."},
        portal_url="https://theflipflop.shop/my-builds/9003",
        target_drive_model="Test NVMe 2TB",
        target_drive_serial="TEST-SERIAL-9003",
        target_drive_inspected_at_utc="2026-09-29T12:00:00+00:00",
    )

    customer_path = tmp_path / "packages" / "9003" / artifact["filename"]
    workshop_path = tmp_path / "packages" / "9003" / artifact["workshop_filename"]
    with ZipFile(customer_path) as customer_archive:
        names = customer_archive.namelist()
        assert "01-build-plaque.pdf" in names
        assert "04-getting-started-guide.md" in names
        assert "CHECKSUMS.sha256" in names
        assert not any(name.endswith((".ps1", ".xml")) for name in names)
        assert not any("workshop" in name or "dispatch-checklist" in name or "portal-manifest" in name for name in names)
    with ZipFile(workshop_path) as workshop_archive:
        assert "06-windows-setup/Deploy-Windows11-Pro.ps1" in workshop_archive.namelist()
        assert "05-workshop-setup/run-getting-ready.ps1" in workshop_archive.namelist()


def test_customer_safe_flag_does_not_allow_workshop_zip_to_be_downloaded(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path / "packages")
    artifact = getting_ready_package.assemble_getting_ready_package(
        build_id=9005,
        build_name="Wrong Archive Safety Build",
        version=1,
        specification=[],
        benchmark_results={},
        manifest={
            "status": "ready_for_admin_review",
            "build_name": "Wrong Archive Safety Build",
            "plaque": {},
            "customer_copy": {},
            "manual_library_matches": [],
            "driver_and_firmware_review": [],
            "upgrade_path": {},
            "warnings": [],
        },
        software_package_ids=[],
        source_inputs={"getting_started_guide_text": "Customer guide."},
        portal_url=None,
        target_drive_model="Test NVMe 2TB",
        target_drive_serial="TEST-SERIAL-9005",
        target_drive_inspected_at_utc="2026-09-29T12:00:00+00:00",
    )
    mislinked_artifact = {
        **artifact,
        "storage_key": artifact["workshop_storage_key"],
        "sha256": artifact["workshop_sha256"],
    }

    with pytest.raises(HTTPException) as error:
        _customer_package_archive_response(mislinked_artifact)
    assert error.value.status_code == 409


def test_getting_started_guide_provenance_rejects_changed_snapshot():
    from hashlib import sha256

    from app.services.getting_ready_package import (
        GettingReadyPackageError,
        _validate_getting_started_guide_provenance,
    )

    with pytest.raises(GettingReadyPackageError, match="changed after manifest generation"):
        _validate_getting_started_guide_provenance(
            "Changed guide\n",
            {
                "source": "admin_settings_upload",
                "sha256": sha256(b"Approved guide\n").hexdigest(),
            },
        )


def test_package_assembly_rejects_changed_getting_started_guide_before_creating_zip(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path / "packages")
    with pytest.raises(GettingReadyPackageError, match="changed after manifest generation"):
        getting_ready_package.assemble_getting_ready_package(
            build_id=9010,
            build_name="Guide Integrity Build",
            version=1,
            specification=[],
            benchmark_results={},
            manifest={
                "status": "ready_for_admin_review",
                "build_name": "Guide Integrity Build",
                "plaque": {},
                "customer_copy": {},
                "manual_library_matches": [],
                "driver_and_firmware_review": [],
                "upgrade_path": {},
                "warnings": [],
            },
            software_package_ids=[],
            source_inputs={
                "getting_started_guide_text": "Changed guide\n",
                "getting_started_guide_metadata": {
                    "source": "admin_settings_upload",
                    "sha256": hashlib.sha256(b"Approved guide\n").hexdigest(),
                },
            },
            portal_url=None,
            target_drive_model="Test NVMe 2TB",
            target_drive_serial="TEST-SERIAL-9010",
            target_drive_inspected_at_utc="2026-09-29T12:00:00+00:00",
        )

    assert not (tmp_path / "packages" / "9010").exists()


def test_getting_started_guide_provenance_accepts_exact_normalized_snapshot():
    from hashlib import sha256

    from app.services.getting_ready_package import _validate_getting_started_guide_provenance

    guide = "Approved guide\n"
    _validate_getting_started_guide_provenance(
        guide,
        {
            "source": "generated_manifest_intro",
            "sha256": sha256(guide.encode("utf-8")).hexdigest(),
        },
    )


def test_customer_safe_archive_rejects_duplicate_allowlisted_members(tmp_path, monkeypatch):
    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path / "packages")
    artifact = getting_ready_package.assemble_getting_ready_package(
        build_id=9006,
        build_name="Duplicate Archive Member Build",
        version=1,
        specification=[],
        benchmark_results={},
        manifest={
            "status": "ready_for_admin_review",
            "build_name": "Duplicate Archive Member Build",
            "plaque": {},
            "customer_copy": {},
            "manual_library_matches": [],
            "driver_and_firmware_review": [],
            "upgrade_path": {},
            "warnings": [],
        },
        software_package_ids=[],
        source_inputs={"getting_started_guide_text": "Customer guide."},
        portal_url=None,
        target_drive_model="Test NVMe 2TB",
        target_drive_serial="TEST-SERIAL-9006",
        target_drive_inspected_at_utc="2026-09-29T12:00:00+00:00",
    )
    archive_path = tmp_path / "packages" / "9006" / artifact["filename"]
    with ZipFile(archive_path) as source:
        entries = [(name, source.read(name)) for name in source.namelist()]
    with ZipFile(archive_path, "w") as duplicate_archive:
        for name, content in entries:
            duplicate_archive.writestr(name, content)
        duplicate_archive.writestr("04-getting-started-guide.md", b"ambiguous duplicate")
    duplicate_artifact = {
        **artifact,
        "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    }

    with pytest.raises(HTTPException) as error:
        _customer_package_archive_response(duplicate_artifact)
    assert error.value.status_code == 409


def test_legacy_mixed_archive_is_filtered_before_customer_download(tmp_path, monkeypatch):
    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path / "packages")
    legacy_path = tmp_path / "packages" / "legacy" / "legacy-mixed.zip"
    legacy_path.parent.mkdir(parents=True)
    with ZipFile(legacy_path, "w") as archive:
        archive.writestr("01-build-plaque.pdf", b"plaque")
        archive.writestr("05-workshop-setup/run-getting-ready.ps1", b"private script")
        archive.writestr("06-windows-setup/Autounattend.xml", b"private answer file")
        archive.writestr("07-component-manuals/../../escape.pdf", b"unsafe path")

    artifact = {
        "category": "customer_package",
        "filename": "legacy-mixed.zip",
        "storage_key": "legacy/legacy-mixed.zip",
        "sha256": hashlib.sha256(legacy_path.read_bytes()).hexdigest(),
        "documents": [
            "01-build-plaque.pdf",
            "05-workshop-setup/run-getting-ready.ps1",
            "06-windows-setup/Autounattend.xml",
            "07-component-manuals/../../escape.pdf",
        ],
    }
    response = _customer_package_archive_response(artifact)

    from io import BytesIO
    with ZipFile(BytesIO(response.body)) as customer_archive:
        names = customer_archive.namelist()
        assert "01-build-plaque.pdf" in names
        assert "CHECKSUMS.sha256" in names
        assert not any(name.endswith((".ps1", ".xml")) for name in names)
        assert not any("escape.pdf" in name for name in names)
    job = SimpleNamespace(artifact_index=[artifact], reviewed_at=object())
    with pytest.raises(HTTPException) as unsafe_document_error:
        _read_customer_package_document(job, "07-component-manuals/../../escape.pdf")
    assert unsafe_document_error.value.status_code == 404


def test_customer_downloads_reject_package_bytes_changed_after_review(tmp_path, monkeypatch):
    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path / "packages")
    artifact = getting_ready_package.assemble_getting_ready_package(
        build_id=9004,
        build_name="Integrity Build",
        version=1,
        specification=[],
        benchmark_results={},
        manifest={
            "status": "ready_for_admin_review",
            "build_name": "Integrity Build",
            "plaque": {},
            "customer_copy": {},
            "manual_library_matches": [],
            "driver_and_firmware_review": [],
            "upgrade_path": {},
            "warnings": [],
        },
        software_package_ids=[],
        source_inputs={"getting_started_guide_text": "Customer guide."},
        portal_url=None,
        target_drive_model="Test NVMe 2TB",
        target_drive_serial="TEST-SERIAL-9004",
        target_drive_inspected_at_utc="2026-09-29T12:00:00+00:00",
    )
    archive_path = tmp_path / "packages" / "9004" / artifact["filename"]
    archive_path.write_bytes(archive_path.read_bytes() + b"changed after review")

    with pytest.raises(HTTPException) as archive_error:
        _customer_package_archive_response(artifact)
    assert archive_error.value.status_code == 409

    artifact["category"] = "customer_package"
    job = SimpleNamespace(artifact_index=[artifact], reviewed_at=object())
    with pytest.raises(HTTPException) as document_error:
        _read_customer_package_document(job, "04-getting-started-guide.md")
    assert document_error.value.status_code == 409


def test_internal_dispatch_checklist_is_separate_from_customer_package(tmp_path, monkeypatch):
    archive_path = _assemble_test_package(tmp_path, monkeypatch, [])

    with ZipFile(archive_path) as archive:
        assert not any("dispatch-checklist" in name for name in archive.namelist())
        assert "06-windows-setup/Autounattend.xml" in archive.namelist()
        assert "06-windows-setup/Deploy-Windows11-Pro.ps1" in archive.namelist()
        assert "05-workshop-setup/prepare-customer-oobe.ps1" in archive.namelist()

    checklist = render_dispatch_checklist("Example Atlas Build")
    assert checklist.startswith("# Dispatch checklist — Example Atlas Build")
    assert "explicitly confirm the exact selected service and current price" in checklist
    assert "explicitly confirm the current premium and approve the live policy purchase" in checklist
    assert "explicitly confirm physical handover in Dispatch Centre" in checklist
    assert "This checklist does not authorise disk erasure, Windows deployment" in checklist


def test_rainmeter_theme_is_machine_wide_and_starts_for_customer_profiles():
    script = create_rainmeter_install_script()

    assert "--scope machine" in script
    assert "CommonStartup" in script
    assert "ProgramFiles\\Rainmeter" not in script  # the discovered installer path is used
    assert "MyDocuments" not in script
    assert "FlipFlop Rainmeter Theme.lnk" in script


def test_windows_answer_file_sets_en_gb_audit_mode_without_choosing_or_wiping_a_disk():
    answer_file = _windows_setup_answer_file()
    root = ElementTree.fromstring(answer_file)
    text = answer_file.decode("utf-8")

    assert root.tag.endswith("unattend")
    assert "en-GB" in text
    assert "<Mode>Audit</Mode>" in text
    assert "DiskConfiguration" not in text
    assert "WillWipeDisk" not in text
    assert "InstallTo" not in text
    assert "ProductKey" not in text
    assert "LocalAccount" not in text


def test_windows_deployment_script_is_bound_to_exact_drive_and_requires_two_explicit_gates():
    script = _windows_deployment_script(
        build_id=774,
        build_name="Atlas 'Pro' Build",
        target_drive_model="FlipFlop NVMe 2TB",
        target_drive_serial="FF-SERIAL-001",
        target_drive_inspected_at_utc="2026-09-29T12:00:00+00:00",
    )

    assert "$buildId = 774" in script
    assert "$buildName = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(" in script
    assert b64encode(b"Atlas 'Pro' Build").decode("ascii") in script
    assert "Atlas ''Pro'' Build" not in script
    assert "ExpectedDiskModel" not in script and "ExpectedDiskSerial" not in script
    assert b64encode(b"FlipFlop NVMe 2TB").decode("ascii") in script
    assert b64encode(b"FF-SERIAL-001").decode("ascii") in script
    assert b64encode(b"2026-09-29T12:00:00+00:00").decode("ascii") in script
    assert "targetInspectionAge.TotalDays -gt 30" in script
    assert "No reviewed target drive identity" not in script
    assert "Windows 11 Pro" in script
    assert "required en-GB language" in script
    assert "The reviewed Autounattend.xml is missing" in script
    assert "IsBoot" in script and "IsSystem" in script
    assert "BusType -in @('USB','SD')" in script
    assert "ERASE-DISK $($target.Serial)" in script
    assert "INSTALL WINDOWS 11 PRO ON BUILD $buildId" in script
    assert "Clear-Disk -Number $target.Number -RemoveData -RemoveOEM" in script
    assert "Audit Mode" in script

    injected_name = _windows_deployment_script(build_id=775, build_name="Atlas'\nthrow 'BAD'")
    assert "throw 'BAD'" not in injected_name
    assert "no reviewed target drive identity and inspection time" in injected_name


def test_customer_oobe_handoff_requires_audit_mode_and_typed_approval():
    script = _prepare_customer_oobe_script()

    assert "EndsWith('-500')" in script
    assert "PREPARE-FOR-CUSTOMER" in script
    assert "master-setup-report.json" in script
    assert "Sysprep.exe" in script
    assert "'/oobe /shutdown'" in script
