import hashlib
import io
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers, UploadFile

from app.database import Base, get_db
from app.main import app
from app.models.getting_started_job import GettingStartedJob
from app.models.manual_build import ManualBuild
from app.models.build import Build, BuildStatus, BuildType
from app.models.customer import Customer
from app.models.customer_problem import CustomerProblem
from app.models.customer_problem_notification import CustomerProblemNotification
from app.models.order import Order, OrderStatus
from app.models.portal_access_grant import PortalAccessGrant
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.models.warranty import WarrantyReserve
from app.api import manual_builds as manual_builds_module
from app.api import orders as orders_api
from app.routes.admin_auth import get_current_admin
from app.services import shipment_notifications
from app.services import customer_problem_notifications
from app.services import parcel2go_notifications
from app.services.getting_started_jobs import (
    DISPATCH_BLOCKING_ACTIONS,
    COURIER_BOOKING_BLOCKING_ACTIONS,
    checklist_dispatch_ready,
    incomplete_checklist_actions,
    missing_dispatch_evidence_categories,
    missing_insurance_photo_categories,
)


def test_paid_provider_price_confirmation_compares_exact_gbp_pence():
    from app.api.manual_builds import _gbp_amount_to_pence, _gbp_amounts_match_to_penny

    assert _gbp_amount_to_pence(12.34) == 1234
    assert _gbp_amount_to_pence("12.340") == 1234
    assert _gbp_amount_to_pence(12.35) == 1235
    assert _gbp_amount_to_pence(float("nan")) is None
    assert _gbp_amount_to_pence(float("inf")) is None
    assert _gbp_amounts_match_to_penny(12.34, "12.340")
    assert not _gbp_amounts_match_to_penny(12.34, 12.35)
    assert not _gbp_amounts_match_to_penny(float("nan"), 12.34)


def test_dispatch_readiness_accepts_waivers_only_for_optional_actions():
    complete = {action: "complete" for action in DISPATCH_BLOCKING_ACTIONS}
    assert not checklist_dispatch_ready({**complete, "software_setup": "not_required"})
    assert not checklist_dispatch_ready({**complete, "component_manuals_reviewed": "not_required"})
    assert checklist_dispatch_ready({**complete, "rgb_theme_applied": "not_required"})
    assert checklist_dispatch_ready({**complete, "ai_services_complete": "not_required"})
    assert not checklist_dispatch_ready(
        {**complete, "ai_services_complete": "not_required"},
        purchased_ai_services=[{"id": "local_assistant"}],
    )
    courier_gates = incomplete_checklist_actions(
        {**complete, "software_setup": "not_required"},
        COURIER_BOOKING_BLOCKING_ACTIONS,
    )
    dispatch_gates = incomplete_checklist_actions(
        {**complete, "software_setup": "not_required"},
        DISPATCH_BLOCKING_ACTIONS,
    )
    assert "software_setup" in courier_gates
    assert "software_setup" in dispatch_gates


def test_package_approval_cleanup_removes_customer_and_workshop_archives(tmp_path, monkeypatch):
    from app.api import manual_builds
    from app.services import getting_ready_package

    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path)
    customer_key = "42/customer.zip"
    workshop_key = "42/workshop.zip"
    for key in (customer_key, workshop_key):
        path = getting_ready_package.package_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"package")

    manual_builds._remove_uncommitted_getting_ready_packages(
        {"storage_key": customer_key, "workshop_storage_key": workshop_key},
        build_id=42,
    )

    assert not getting_ready_package.package_path(customer_key).exists()
    assert not getting_ready_package.package_path(workshop_key).exists()


def _create_package_archives(tmp_path, monkeypatch):
    from app.services import getting_ready_package

    monkeypatch.setattr(getting_ready_package, "PACKAGE_ROOT", tmp_path)
    package = {"storage_key": "42/customer.zip", "workshop_storage_key": "42/workshop.zip"}
    for key in package.values():
        path = getting_ready_package.package_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"package")
    return package, getting_ready_package


@pytest.mark.asyncio
async def test_package_approval_flush_failure_rolls_back_and_removes_archives(tmp_path, monkeypatch):
    from app.api.manual_builds import _commit_getting_ready_package_approval

    package, package_service = _create_package_archives(tmp_path, monkeypatch)
    db = SimpleNamespace(
        flush=AsyncMock(side_effect=RuntimeError("flush failed")),
        rollback=AsyncMock(),
        commit=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="flush failed"):
        await _commit_getting_ready_package_approval(db, package, build_id=42)

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    assert not package_service.package_path(package["storage_key"]).exists()
    assert not package_service.package_path(package["workshop_storage_key"]).exists()


@pytest.mark.asyncio
async def test_package_approval_uncertain_commit_retains_both_archives(tmp_path, monkeypatch):
    from app.api.manual_builds import _commit_getting_ready_package_approval

    package, package_service = _create_package_archives(tmp_path, monkeypatch)
    db = SimpleNamespace(
        flush=AsyncMock(),
        rollback=AsyncMock(),
        commit=AsyncMock(side_effect=RuntimeError("commit outcome unclear")),
    )

    with pytest.raises(RuntimeError, match="commit outcome unclear"):
        await _commit_getting_ready_package_approval(db, package, build_id=42)

    db.rollback.assert_awaited_once()
    assert package_service.package_path(package["storage_key"]).is_file()
    assert package_service.package_path(package["workshop_storage_key"]).is_file()


@pytest.mark.asyncio
async def test_package_approval_success_retains_both_archives(tmp_path, monkeypatch):
    from app.api.manual_builds import _commit_getting_ready_package_approval

    package, package_service = _create_package_archives(tmp_path, monkeypatch)
    db = SimpleNamespace(flush=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())

    await _commit_getting_ready_package_approval(db, package, build_id=42)

    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    assert not db.rollback.await_count
    assert package_service.package_path(package["storage_key"]).is_file()
    assert package_service.package_path(package["workshop_storage_key"]).is_file()


@pytest.mark.asyncio
async def test_dispatch_evidence_file_is_removed_when_database_write_fails_before_commit(tmp_path, monkeypatch):
    from app.api import manual_builds

    storage_root = tmp_path / "private-dispatch"
    monkeypatch.setattr(manual_builds, "_PRIVATE_DISPATCH_ROOT", storage_root)
    build = SimpleNamespace(
        id=8801,
        status="sold",
        dispatch_status=None,
        shipment_booking_state="booked",
        tracking_number="TRACK-DB-FAIL",
        shipment_booked_at=datetime.utcnow(),
        delivered_at=None,
        customer_id=17,
    )

    async def locked_build(_db, _build_id):
        return build, None

    monkeypatch.setattr(manual_builds, "lock_manual_build_then_getting_started_job", locked_build)
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=RuntimeError("database unavailable")),
        add=Mock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    upload = UploadFile(
        filename="working-pc.jpg",
        file=io.BytesIO(b"\xff\xd8\xffvalidated-test-fixture"),
        headers=Headers({"content-type": "image/jpeg"}),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await manual_builds.upload_dispatch_evidence(
            8801,
            "working_pc",
            upload,
            SimpleNamespace(id=4, name="Operator"),
            db,
        )

    assert list(storage_root.rglob("*.*")) == []
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_evidence_file_is_retained_when_commit_outcome_is_uncertain(tmp_path, monkeypatch):
    from app.api import manual_builds

    storage_root = tmp_path / "private-dispatch"
    monkeypatch.setattr(manual_builds, "_PRIVATE_DISPATCH_ROOT", storage_root)
    build = SimpleNamespace(
        id=8802,
        status="sold",
        dispatch_status=None,
        shipment_booking_state="booked",
        tracking_number="TRACK-COMMIT-UNCERTAIN",
        shipment_booked_at=datetime.utcnow(),
        delivered_at=None,
        customer_id=17,
    )

    async def locked_build(_db, _build_id):
        return build, None

    monkeypatch.setattr(manual_builds, "lock_manual_build_then_getting_started_job", locked_build)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=Mock(),
        commit=AsyncMock(side_effect=RuntimeError("connection lost during commit")),
        rollback=AsyncMock(),
    )
    upload = UploadFile(
        filename="working-pc.jpg",
        file=io.BytesIO(b"\xff\xd8\xffvalidated-test-fixture"),
        headers=Headers({"content-type": "image/jpeg"}),
    )

    with pytest.raises(RuntimeError, match="connection lost during commit"):
        await manual_builds.upload_dispatch_evidence(
            8802,
            "working_pc",
            upload,
            SimpleNamespace(id=4, name="Operator"),
            db,
        )

    saved_files = list(storage_root.rglob("*.jpg"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == b"\xff\xd8\xffvalidated-test-fixture"
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_required_checklist_actions_cannot_be_waived(evidence_client):
    client, _ = evidence_client
    response = client.patch(
        "/api/manual-builds/1/getting-ready/checklist/software_setup",
        json={"status": "not_required", "note": "This required action is being waived."},
    )
    assert response.status_code == 422
    assert "cannot be marked not required" in response.json()["detail"]

    manual_review = client.patch(
        "/api/manual-builds/1/getting-ready/checklist/component_manuals_reviewed",
        json={"status": "not_required", "note": "This required action is being waived."},
    )
    assert manual_review.status_code == 422
    assert "cannot be marked not required" in manual_review.json()["detail"]

    driver_review = client.patch(
        "/api/manual-builds/1/getting-ready/checklist/driver_firmware_reviewed",
        json={"status": "not_required", "note": "This required action is being waived."},
    )
    assert driver_review.status_code == 422
    assert "cannot be marked not required" in driver_review.json()["detail"]


@pytest.mark.asyncio
async def test_software_script_download_is_admin_gated_by_reviewed_package(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Persisted Script Build",
            status="sold",
        )
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="package_ready",
            customer_software_selections=["7zip.7zip"],
            checklist={"software_selection_submitted": True},
            artifact_index=[{"category": "customer_package", "version": 1, "filename": "customer.zip"}],
            reviewed_at=datetime.utcnow(),
        ))
        approved_build_id = build.id
        unapproved_build = ManualBuild(
            name="Unapproved Script Build",
            status="sold",
        )
        db.add(unapproved_build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=unapproved_build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            customer_software_selections=["7zip.7zip"],
            checklist={"software_selection_submitted": True},
        ))
        unapproved_build_id = unapproved_build.id
        await db.commit()

    approved = client.get(f"/api/manual-builds/{approved_build_id}/getting-ready/software-script")
    assert approved.status_code == 200
    assert "--id '7zip.7zip'" in approved.text
    assert approved.headers["cache-control"] == "private, no-store, max-age=0"
    assert f"FlipFlop-Build-{approved_build_id}-software-install.ps1" in approved.headers["content-disposition"]

    unapproved = client.get(f"/api/manual-builds/{unapproved_build_id}/getting-ready/software-script")
    assert unapproved.status_code == 409


@pytest.mark.asyncio
async def test_package_approval_requires_current_recorded_windows_target(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Target Gate Build",
            status="sold",
            components=[{"component_id": "cpu-1", "component_name": "Example CPU"}],
        )
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            manifest={
                "status": "ready_for_admin_review",
                "build_name": build.name,
                "manual_library_matches": [{
                    "component_id": "cpu-1",
                    "component_name": "Example CPU",
                }],
            },
            generated_at=datetime.utcnow(),
            customer_software_selections=[],
            checklist={
                "software_selection_submitted": True,
                "component_manuals_reviewed": "complete",
            },
        ))
        build_id = build.id
        await db.commit()

    response = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/approve-and-package",
        json={"confirm_manifest_reviewed": True, "confirm_customer_details_checked": True},
    )

    assert response.status_code == 409
    assert "Record and confirm the exact new-build drive" in response.json()["detail"]

    async with session_factory() as db:
        job = (await db.execute(
            select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
        )).scalar_one()
        job.checklist = {
            **job.checklist,
            "windows_target_confirmed": "complete",
            "windows_target": {
                "model": "Test NVMe 2TB",
                "serial": "TEST-SERIAL-OLD",
                "inspected_at_utc": "2020-01-01T12:00:00+00:00",
            },
        }
        await db.commit()

    stale = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/approve-and-package",
        json={"confirm_manifest_reviewed": True, "confirm_customer_details_checked": True},
    )
    assert stale.status_code == 409
    assert "inspection must be current" in stale.json()["detail"]


@pytest.mark.asyncio
async def test_package_approval_requires_manual_review_action(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(name="Manual Review Gate Build", status="sold")
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            manifest={
                "status": "ready_for_admin_review",
                "build_name": build.name,
                "manual_library_matches": [{
                    "component_id": "cpu-1",
                    "component_name": "Example CPU",
                    "match_status": "needs_research",
                    "administrator_approval_required": True,
                }],
            },
            generated_at=datetime.utcnow(),
            customer_software_selections=[],
            checklist={"software_selection_submitted": True},
        ))
        build_id = build.id
        await db.commit()

    response = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/approve-and-package",
        json={"confirm_manifest_reviewed": True, "confirm_customer_details_checked": True},
    )

    assert response.status_code == 409
    assert "Review the exact-model manual results" in response.json()["detail"]


@pytest.mark.asyncio
async def test_manual_review_cannot_complete_against_a_partial_stored_manifest(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Partial Manual List Build",
            status="sold",
            components=[
                {"component_id": "cpu-1", "component_name": "Example CPU"},
                {"component_id": "gpu-1", "component_name": "Example GPU"},
            ],
        )
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            manifest={
                "manual_library_matches": [{
                    "component_id": "cpu-1",
                    "component_name": "Example CPU",
                }],
            },
            generated_at=datetime.utcnow(),
            checklist={},
        ))
        build_id = build.id
        await db.commit()

    response = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/component_manuals_reviewed",
        json={"status": "complete", "note": "Reviewed the available CPU manual record."},
    )

    assert response.status_code == 409
    assert "Example GPU" in response.json()["detail"]


@pytest.mark.asyncio
async def test_driver_firmware_review_cannot_complete_against_a_partial_manifest(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Partial Driver List Build",
            status="sold",
            components=[
                {"component_id": "cpu-1", "component_name": "Example CPU"},
                {"component_id": "gpu-1", "component_name": "Example GPU"},
            ],
        )
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            manifest={
                "driver_and_firmware_review": [{
                    "component_id": "cpu-1",
                    "component_name": "Example CPU",
                }],
            },
            generated_at=datetime.utcnow(),
            checklist={},
        ))
        build_id = build.id
        await db.commit()

    response = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/driver_firmware_reviewed",
        json={"status": "complete", "note": "Reviewed driver recommendations for this build."},
    )

    assert response.status_code == 409
    assert "Example GPU" in response.json()["detail"]


@pytest.mark.asyncio
async def test_driver_installation_cannot_complete_before_per_component_review(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(name="Driver Sequence Build", status="sold")
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            checklist={"driver_firmware_reviewed": "not_ready"},
        ))
        build_id = build.id
        await db.commit()

    response = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/drivers_updates_complete",
        json={"status": "complete", "note": "Driver setup was completed on this build."},
    )

    assert response.status_code == 409
    assert "per-component driver and firmware review" in response.json()["detail"]


@pytest.mark.asyncio
async def test_driver_installation_rechecks_manifest_coverage_against_current_components(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Changed Driver Spec Build",
            status="sold",
            components=[
                {"component_id": "cpu-1", "component_name": "Example CPU"},
                {"component_id": "gpu-1", "component_name": "Example GPU"},
            ],
        )
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            manifest={"driver_and_firmware_review": [{
                "component_id": "cpu-1",
                "component_name": "Example CPU",
            }]},
            checklist={"driver_firmware_reviewed": "complete"},
        ))
        build_id = build.id
        await db.commit()

    response = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/drivers_updates_complete",
        json={"status": "complete", "note": "Driver setup was completed on this build."},
    )

    assert response.status_code == 409
    assert "Example GPU" in response.json()["detail"]


@pytest.mark.asyncio
async def test_driver_review_persists_exact_operator_outcomes(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Recorded Driver Review Build",
            status="sold",
            components=[
                {"component_id": "cpu-1", "component_name": "Example CPU"},
                {"component_id": "gpu-1", "component_name": "Example GPU"},
            ],
        )
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            manifest={"driver_and_firmware_review": [
                {"component_id": "cpu-1", "component_name": "Example CPU"},
                {"component_id": "gpu-1", "component_name": "Example GPU"},
            ], "sources": []},
            checklist={},
        ))
        build_id = build.id
        await db.commit()

    response = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/driver_firmware_reviewed",
        json={
            "status": "complete",
            "note": "Reviewed each listed component and recorded its update outcome.",
            "driver_firmware_outcomes": [
                {"component_id": "cpu-1", "component_name": "Example CPU", "outcome": "no_update_applicable", "details": "Checked the exact manufacturer support page; no update applies."},
                {"component_id": "gpu-1", "component_name": "Example GPU", "outcome": "no_update_applicable", "details": "Checked the exact manufacturer support page; no update applies."},
            ],
        },
    )

    assert response.status_code == 200
    outcomes = response.json()["checklist"]["_driver_firmware_outcomes"]
    assert [item["component_id"] for item in outcomes] == ["cpu-1", "gpu-1"]
    assert all(item["reviewed_by"] == "admin" for item in outcomes)


@pytest.mark.asyncio
async def test_package_approval_rejects_partial_manifest_even_after_manual_review(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Stale Manual Review Build",
            status="sold",
            components=[
                {"component_id": "cpu-1", "component_name": "Example CPU"},
                {"component_id": "gpu-1", "component_name": "Example GPU"},
            ],
        )
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            manifest={
                "status": "ready_for_admin_review",
                "build_name": build.name,
                "manual_library_matches": [{
                    "component_id": "cpu-1",
                    "component_name": "Example CPU",
                }],
            },
            generated_at=datetime.utcnow(),
            customer_software_selections=[],
            checklist={
                "software_selection_submitted": True,
                "component_manuals_reviewed": "complete",
            },
        ))
        build_id = build.id
        await db.commit()

    response = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/approve-and-package",
        json={"confirm_manifest_reviewed": True, "confirm_customer_details_checked": True},
    )

    assert response.status_code == 409
    assert "Example GPU" in response.json()["detail"]


@pytest.mark.asyncio
async def test_uncertain_insurance_creation_requires_provider_check_and_reconciliation(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Insurance Reconciliation Build",
            status="sold",
            sale_price_actual=120.0,
            tracking_number="TRACK-INS-UNSURE",
            shipment_booking_state="booked",
            shipment_booked_at=datetime.utcnow(),
            shipping_insurance_status="creation_uncertain",
            evidence_data={},
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    unchecked = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile",
        json={"resolution": "no_policy", "provider_checked": False, "note": "Checked the insurer account."},
    )
    assert unchecked.status_code == 422

    reconciled = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile",
        json={"resolution": "no_policy", "provider_checked": True, "note": "Checked account; no policy exists."},
    )
    assert reconciled.status_code == 200
    assert reconciled.json()["status"] == "creation_failed"
    repeated = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile",
        json={"resolution": "no_policy", "provider_checked": True, "note": "Checked account; no policy exists."},
    )
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True

    async with session_factory() as db:
        saved = await db.get(ManualBuild, build_id)
        assert saved.shipping_insurance_status == "creation_failed"
        assert saved.evidence_data["insurance_policy_reconciliations"][-1]["resolution"] == "no_policy"


@pytest.mark.asyncio
async def test_uncertain_insurance_creation_can_attach_verified_existing_policy(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Existing Insurance Policy Build",
            status="sold",
            sale_price_actual=120.0,
            tracking_number="TRACK-INS-123",
            shipment_booking_state="booked",
            shipment_booked_at=datetime.utcnow(),
            shipping_insurance_status="creation_uncertain",
            evidence_data={"insurance_policy_creation": {"provider_response": {
                "policy_id": "FIG-123",
                "insured_value_gbp": 120.0,
                "price_gbp": 4.25,
                "currency": "GBP",
                "mode": "production",
            }}},
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    payload = {
        "resolution": "policy_exists",
        "provider_checked": True,
        "note": "Located matching policy in provider account.",
        "policy_id": "FIG-123",
        "invoice_id": "INV-123",
        "provider_tracking_number": "TRACK-INS-123",
        "insured_value_gbp": 120.0,
        "cost_gbp": 4.25,
    }
    mismatched_id = {**payload, "policy_id": "FIG-OTHER"}
    rejected_id = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile", json=mismatched_id
    )
    assert rejected_id.status_code == 409

    async with session_factory() as db:
        saved = await db.get(ManualBuild, build_id)
        evidence = dict(saved.evidence_data)
        attempt = dict(evidence["insurance_policy_creation"])
        provider_response = dict(attempt["provider_response"])
        provider_response["policy_id"] = None
        attempt["provider_response"] = provider_response
        evidence["insurance_policy_creation"] = attempt
        saved.evidence_data = evidence
        await db.commit()
    missing_original_id = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile", json=payload
    )
    assert missing_original_id.status_code == 409
    assert "did not provide this policy ID" in missing_original_id.json()["detail"]
    async with session_factory() as db:
        saved = await db.get(ManualBuild, build_id)
        evidence = dict(saved.evidence_data)
        attempt = dict(evidence["insurance_policy_creation"])
        provider_response = dict(attempt["provider_response"])
        provider_response["policy_id"] = "FIG-123"
        attempt["provider_response"] = provider_response
        evidence["insurance_policy_creation"] = attempt
        saved.evidence_data = evidence
        await db.commit()

    mismatched_premium = {**payload, "cost_gbp": 4.26}
    rejected_returned_premium = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile", json=mismatched_premium
    )
    assert rejected_returned_premium.status_code == 409
    test_mode_response = {**payload}
    async with session_factory() as db:
        saved = await db.get(ManualBuild, build_id)
        evidence = dict(saved.evidence_data)
        attempt = dict(evidence["insurance_policy_creation"])
        provider_response = dict(attempt["provider_response"])
        provider_response["mode"] = "test"
        attempt["provider_response"] = provider_response
        evidence["insurance_policy_creation"] = attempt
        saved.evidence_data = evidence
        await db.commit()
    rejected_test_mode = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile", json=test_mode_response
    )
    assert rejected_test_mode.status_code == 409
    async with session_factory() as db:
        saved = await db.get(ManualBuild, build_id)
        evidence = dict(saved.evidence_data)
        attempt = dict(evidence["insurance_policy_creation"])
        provider_response = dict(attempt["provider_response"])
        provider_response["mode"] = "production"
        attempt["provider_response"] = provider_response
        evidence["insurance_policy_creation"] = attempt
        saved.evidence_data = evidence
        await db.commit()

    reconciled = client.post(f"/api/manual-builds/{build_id}/insurance-policy/reconcile", json=payload)
    assert reconciled.status_code == 200
    assert reconciled.json()["status"] == "created"
    assert reconciled.json()["policy_id"] == "FIG-123"

    repeated = client.post(f"/api/manual-builds/{build_id}/insurance-policy/reconcile", json=payload)
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True

    premium_conflict = {**payload, "cost_gbp": 4.26}
    rejected_premium = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile", json=premium_conflict
    )
    assert rejected_premium.status_code == 409
    insured_value_conflict = {**payload, "insured_value_gbp": 120.01}
    rejected_value = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile", json=insured_value_conflict
    )
    assert rejected_value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_policy, mismatch",
    [
        ({"policy_id": ""}, "policy ID"),
        ({"insured_value_gbp": 119.99}, "insured value"),
        ({"price_gbp": 4.26}, "premium"),
        ({"currency": "EUR"}, "currency"),
        ({"mode": "test"}, "mode"),
    ],
)
async def test_insurer_success_response_mismatch_keeps_dispatch_blocked(
    evidence_client, monkeypatch, provider_policy, mismatch
):
    client, session_factory = evidence_client
    monkeypatch.setattr(
        manual_builds_module,
        "get_settings",
        lambda: SimpleNamespace(
            secursus_live_parcel_creation_enabled=True,
            seller_address_country_iso="GB",
        ),
    )
    monkeypatch.setattr(
        manual_builds_module,
        "get_insurance_quote",
        AsyncMock(return_value=SimpleNamespace(price_gbp=4.25, currency="GBP")),
    )
    # Apply each provider discrepancy without involving an insurer account.
    policy_provider = AsyncMock(return_value=SimpleNamespace(
        policy_id=provider_policy.get("policy_id", "FIG-MISMATCH"),
        invoice_id="INV-MISMATCH",
        insured_value_gbp=provider_policy.get("insured_value_gbp", 120.0),
        price_gbp=provider_policy.get("price_gbp", 4.25),
        currency=provider_policy.get("currency", "GBP"),
        mode=provider_policy.get("mode", "production"),
    ))
    monkeypatch.setattr(manual_builds_module, "create_insurance_policy", policy_provider)
    monkeypatch.setattr(
        manual_builds_module,
        "_missing_verified_dispatch_evidence",
        lambda *_args, **_kwargs: [],
    )
    async with session_factory() as db:
        build = ManualBuild(
            name="Insurer response mismatch build",
            status="sold",
            sale_price_actual=120.0,
            buyer_name="Example Buyer",
            customer_email="buyer@example.test",
            buyer_address_json={
                "address_line1": "1 Test Street",
                "city": "London",
                "postal_code": "SW1A 1AA",
                "country_code": "GB",
            },
            tracking_number="TRACK-MISMATCH",
            shipment_booking_state="booked",
            shipment_booked_at=datetime.utcnow(),
            parcel2go_service_slug="signed-service",
            evidence_data={"shipment_booking_confirmation": {"signature_extra_included": True}},
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    response = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy",
        json={
            "confirm_terms": True,
            "confirm_live_purchase": True,
            "confirm_customer_data_share": True,
            "confirm_signed_for_delivery": True,
            "confirm_double_packaging": True,
            "confirm_discreet_packaging": True,
            "confirm_rigid_outer_container": True,
            "confirm_contents_not_deducible": True,
            "confirm_direct_signature": True,
            "confirm_official_carrier_handover": True,
            "quoted_price_gbp": 4.25,
        },
    )

    assert response.status_code == 409
    assert "Dispatch remains blocked" in response.json()["detail"]
    assert mismatch.lower() in " ".join(response.json()["detail"].split()).lower()
    policy_provider.assert_awaited_once()
    async with session_factory() as db:
        saved = await db.get(ManualBuild, build_id)
        assert saved.shipping_insurance_status == "creation_uncertain"
        assert saved.shipping_insurance_policy_id is None
        expected_policy_id = provider_policy.get("policy_id", "FIG-MISMATCH") or None
        assert saved.evidence_data["insurance_policy_creation"]["provider_response"]["policy_id"] == expected_policy_id

    dispatch_rows = client.get("/api/manual-builds/dispatch-zone")
    assert dispatch_rows.status_code == 200
    row = next(item for item in dispatch_rows.json() if item["id"] == build_id)
    summary = row["insurance_provider_response"]
    assert summary["policy_id"] == expected_policy_id
    assert summary["mismatches"]
    assert set(summary) == {
        "policy_id", "invoice_id", "insured_value_gbp", "price_gbp",
        "currency", "mode", "received_at", "mismatches",
    }


@pytest.mark.asyncio
async def test_insurance_reconciliation_waits_for_in_flight_request_timeout(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="In Flight Insurance Build",
            status="sold",
            sale_price_actual=120.0,
            tracking_number="TRACK-INS-FLIGHT",
            shipment_booking_state="booked",
            shipment_booked_at=datetime.utcnow(),
            shipping_insurance_status="creating",
            evidence_data={"insurance_policy_creation": {"started_at": datetime.utcnow().isoformat() + "Z"}},
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    response = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile",
        json={"resolution": "no_policy", "provider_checked": True, "note": "Checked account; no policy exists."},
    )
    assert response.status_code == 409
    assert "may still be in flight" in response.json()["detail"]


@pytest.mark.asyncio
async def test_windows_install_requires_pre_recorded_target_and_exact_post_install_match(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(name="Target Gate Build", status="sold")
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="preparing",
            checklist={},
        ))
        await db.commit()
        build_id = build.id

    now = datetime.utcnow().isoformat() + "Z"
    inspected_before = (datetime.utcnow() - timedelta(seconds=5)).isoformat() + "Z"
    evidence = {
        "schema_version": "1.0",
        "build_id": build_id,
        "build_name": "Target Gate Build",
        "verified_at_utc": now,
        "edition": "Windows 11 Pro",
        "locale": "en-GB",
        "target_drive_model": "FlipFlop NVMe 2TB",
        "target_drive_serial": "FF-SERIAL-001",
        "target_drive_size_bytes": 2000000000000,
        "verification_method": "FlipFlop read-only post-install verification",
        "installation_method": "Official Windows Setup, technician selected target",
        "target_drive_confirmed": True,
    }
    deployment_payload = {
        "status": "complete",
        "note": "Checked Windows edition and system drive against the pre-install target record.",
        "windows_deployment_evidence": evidence,
    }

    missing_precheck = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/windows_deployment_completed",
        json=deployment_payload,
    )
    assert missing_precheck.status_code == 409

    recorded_target = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/windows_target_confirmed",
        json={
            "status": "complete",
            "note": "Confirmed the exact new-build drive before starting Windows Setup.",
            "windows_target": {
                "model": "FlipFlop NVMe 2TB",
                "serial": "FF-SERIAL-001",
                "inspected_at_utc": inspected_before,
                "confirm_new_build_drive": True,
            },
        },
    )
    assert recorded_target.status_code == 200

    mismatched = {**evidence, "target_drive_serial": "OTHER-SERIAL"}
    mismatch_response = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/windows_deployment_completed",
        json={**deployment_payload, "windows_deployment_evidence": mismatched},
    )
    assert mismatch_response.status_code == 409
    assert "does not match" in mismatch_response.json()["detail"]

    recorded_after_install = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/windows_target_confirmed",
        json={
            "status": "complete",
            "note": "Recorded this intended target after completing Windows Setup.",
            "windows_target": {
                "model": "FlipFlop NVMe 2TB",
                "serial": "FF-SERIAL-001",
                "inspected_at_utc": (datetime.utcnow() + timedelta(seconds=60)).isoformat() + "Z",
                "confirm_new_build_drive": True,
            },
        },
    )
    assert recorded_after_install.status_code == 200
    out_of_order = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/windows_deployment_completed",
        json=deployment_payload,
    )
    assert out_of_order.status_code == 409
    assert "recorded before Windows" in out_of_order.json()["detail"]

    client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/windows_target_confirmed",
        json={
            "status": "complete",
            "note": "Corrected the audited target timestamp from the pre-install check.",
            "windows_target": {
                "model": "FlipFlop NVMe 2TB",
                "serial": "FF-SERIAL-001",
                "inspected_at_utc": inspected_before,
                "confirm_new_build_drive": True,
            },
        },
    )

    accepted = client.patch(
        f"/api/manual-builds/{build_id}/getting-ready/checklist/windows_deployment_completed",
        json=deployment_payload,
    )
    assert accepted.status_code == 200


@pytest.fixture
async def evidence_client(tmp_path, monkeypatch):
    from app.api import manual_builds

    monkeypatch.setattr(manual_builds, "_PRIVATE_DISPATCH_ROOT", tmp_path / "private_dispatch")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_admin():
        return SimpleNamespace(id=42, name="Workshop Admin")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin] = override_admin
    try:
        yield TestClient(app), session_factory
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def _seed_dispatch_notification_event(session_factory, *, order_suffix, ebay_order_id=None, attempts=0):
    async with session_factory() as db:
        customer = Customer(email=f"{order_suffix.lower()}@example.test", name="Dispatch Buyer")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id=f"FF-{order_suffix}",
            customer_id=customer.id,
            specs={},
            customer_price=500,
            component_costs=400,
            overhead_amount=100,
        )
        build = ManualBuild(
            name=f"{order_suffix} Build",
            status="sold",
            ebay_order_id=ebay_order_id,
            tracking_number=f"TRACK-{order_suffix}",
            parcel2go_service_slug="royal-mail-24",
            evidence_data={"shipment_booking_confirmation": {"tracking_url": "https://carrier.example/track"}},
        )
        db.add_all([order, build])
        await db.flush()
        event = ShipmentTrackingEvent(
            order_id=order.id,
            provider="royal_mail",
            provider_event_id=f"dispatch:{build.id}:{order_suffix}",
            status_code="dispatched",
            description="Your build has been handed to the courier.",
            material=True,
            customer_notification_attempts=attempts,
            occurred_at=datetime.utcnow(),
        )
        db.add(event)
        await db.commit()
        return event.id


@pytest.mark.asyncio
async def test_dispatch_evidence_is_attributed_and_download_is_private(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Evidence Test Build",
            status="sold",
            shipment_booking_state="booked",
            tracking_number="TRACK-123",
            shipment_booked_at=datetime.utcnow(),
        )
        db.add(build)
        await db.commit()
        await db.refresh(build)
        build_id = build.id

    response = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/evidence",
        data={"category": "working_pc"},
        files={"file": ("working.jpg", b"\xff\xd8\xffevidence", "image/jpeg")},
    )
    assert response.status_code == 201
    artifact_id = response.json()["id"]

    admin_override = app.dependency_overrides.pop(get_current_admin)
    try:
        unauthenticated_download = client.get(
            f"/api/manual-builds/{build_id}/getting-ready/evidence/{artifact_id}"
        )
        assert unauthenticated_download.status_code == 401
        unauthenticated_checklist = client.get(
            f"/api/manual-builds/{build_id}/getting-ready/dispatch-checklist"
        )
        assert unauthenticated_checklist.status_code == 401
    finally:
        app.dependency_overrides[get_current_admin] = admin_override

    async with session_factory() as db:
        job = (await db.execute(
            select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
        )).scalar_one()
        artifact = next(item for item in job.artifact_index if item["id"] == artifact_id)
        assert artifact["uploaded_by_admin_id"] == 42
        assert artifact["uploaded_by_admin_name"] == "Workshop Admin"
        assert artifact["sha256"]
        assert artifact["uploaded_at"]
        assert artifact["review_status"] == "needs_review"
        assert job.checklist["working_pc_photo"] == "needs_review"

    review = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/evidence/{artifact_id}/review",
        json={"approved": True, "note": "Verified this image shows the correct working build."},
    )
    assert review.status_code == 200
    assert review.json()["review_status"] == "approved"

    async with session_factory() as db:
        job = (await db.execute(
            select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
        )).scalar_one()
        artifact = next(item for item in job.artifact_index if item["id"] == artifact_id)
        assert artifact["reviewed_by_admin_id"] == 42
        assert artifact["review_note"] == "Verified this image shows the correct working build."
        assert job.checklist["working_pc_photo"] == "complete"

    download = client.get(f"/api/manual-builds/{build_id}/getting-ready/evidence/{artifact_id}")
    assert download.status_code == 200
    assert download.content == b"\xff\xd8\xffevidence"
    assert download.headers["cache-control"] == "private, no-store"
    assert download.headers["pragma"] == "no-cache"
    assert download.headers["x-content-type-options"] == "nosniff"

    async with session_factory() as db:
        job = (await db.execute(
            select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
        )).scalar_one()
        artifact = next(item for item in job.artifact_index if item["id"] == artifact_id)
        evidence_path = manual_builds_module._PRIVATE_DISPATCH_ROOT / artifact["storage_key"]
    evidence_path.write_bytes(b"\xff\xd8\xffchanged-after-review")
    tampered_download = client.get(
        f"/api/manual-builds/{build_id}/getting-ready/evidence/{artifact_id}"
    )
    assert tampered_download.status_code == 409


@pytest.mark.asyncio
async def test_dispatch_evidence_stream_is_pinned_to_the_verified_file(evidence_client):
    _client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Pinned Evidence Build",
            status="sold",
            shipment_booking_state="booked",
            tracking_number="TRACK-PINNED",
            shipment_booked_at=datetime.utcnow(),
        )
        db.add(build)
        await db.commit()
        await db.refresh(build)
        build_id = build.id

    upload = _client.post(
        f"/api/manual-builds/{build_id}/getting-ready/evidence",
        data={"category": "working_pc"},
        files={"file": ("working.jpg", b"\xff\xd8\xffverified-bytes", "image/jpeg")},
    )
    assert upload.status_code == 201
    artifact_id = upload.json()["id"]

    async with session_factory() as db:
        response = await manual_builds_module.download_dispatch_evidence(build_id, artifact_id, db)
        async with session_factory() as read_db:
            job = (await read_db.execute(
                select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
            )).scalar_one()
            artifact = next(item for item in job.artifact_index if item["id"] == artifact_id)
        evidence_path = manual_builds_module._PRIVATE_DISPATCH_ROOT / artifact["storage_key"]
        replacement = evidence_path.with_suffix(".replacement")
        replacement.write_bytes(b"\xff\xd8\xffunverified-replacement")
        try:
            os.replace(replacement, evidence_path)
        except PermissionError:
            replacement.unlink(missing_ok=True)
            if response.background:
                await response.background()
            pytest.skip("This platform prevents replacing an open file; descriptor pinning is covered on POSIX CI")

        streamed = b"".join([chunk async for chunk in response.body_iterator])
        if response.background:
            await response.background()

    assert streamed == b"\xff\xd8\xffverified-bytes"


@pytest.mark.asyncio
async def test_dispatch_evidence_download_rejects_another_builds_storage_key(evidence_client):
    client, session_factory = evidence_client
    foreign_bytes = b"\xff\xd8\xffprivate-to-another-build"
    async with session_factory() as db:
        owner_build = ManualBuild(name="Requested build", status="sold")
        foreign_build = ManualBuild(name="Foreign build", status="sold")
        db.add_all([owner_build, foreign_build])
        await db.flush()
        foreign_key = f"{foreign_build.id}/private.jpg"
        db.add(GettingStartedJob(
            manual_build_id=owner_build.id,
            artifact_index=[{
                "id": "cross-build-evidence",
                "category": "working_pc",
                "filename": "private.jpg",
                "content_type": "image/jpeg",
                "size_bytes": len(foreign_bytes),
                "sha256": hashlib.sha256(foreign_bytes).hexdigest(),
                "storage_key": foreign_key,
            }],
        ))
        owner_build_id = owner_build.id
        await db.commit()

    foreign_file = manual_builds_module._PRIVATE_DISPATCH_ROOT / foreign_key
    foreign_file.parent.mkdir(parents=True, exist_ok=True)
    foreign_file.write_bytes(foreign_bytes)
    response = client.get(
        f"/api/manual-builds/{owner_build_id}/getting-ready/evidence/cross-build-evidence"
    )

    assert response.status_code == 404
    assert response.content != foreign_bytes


def test_unreviewed_shipment_files_do_not_clear_evidence_gates():
    job = SimpleNamespace(artifact_index=[
        {"category": "working_pc", "content_type": "image/jpeg", "review_status": "needs_review"},
        {"category": "package_contents", "content_type": "image/jpeg", "review_status": "needs_review"},
        {"category": "sealed_package", "content_type": "image/jpeg", "review_status": "rejected"},
    ])
    assert missing_insurance_photo_categories(job) == ["package_contents", "sealed_package"]
    assert missing_dispatch_evidence_categories(job) == ["working_pc", "package_contents", "sealed_package"]

    for artifact in job.artifact_index:
        artifact["review_status"] = "approved"
    assert missing_insurance_photo_categories(job) == []
    assert missing_dispatch_evidence_categories(job) == []


def test_insurance_and_dispatch_require_approved_files_to_match_build_bound_checksums(tmp_path, monkeypatch):
    from app.api import manual_builds

    monkeypatch.setattr(manual_builds, "_PRIVATE_DISPATCH_ROOT", tmp_path / "private_dispatch")
    build_id = 73
    build_dir = tmp_path / "private_dispatch" / str(build_id)
    build_dir.mkdir(parents=True)
    payload = b"approved evidence"
    evidence_path = build_dir / "contents.jpg"
    evidence_path.write_bytes(payload)
    artifact = {
        "category": "package_contents",
        "content_type": "image/jpeg",
        "review_status": "approved",
        "storage_key": f"{build_id}/contents.jpg",
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    job = SimpleNamespace(artifact_index=[artifact])

    assert manual_builds._missing_verified_dispatch_evidence(job, build_id, ("package_contents",)) == []

    evidence_path.write_bytes(b"tampered evidence")
    assert manual_builds._missing_verified_dispatch_evidence(job, build_id, ("package_contents",)) == ["package_contents"]

    evidence_path.write_bytes(payload)
    artifact["storage_key"] = "74/contents.jpg"
    assert manual_builds._missing_verified_dispatch_evidence(job, build_id, ("package_contents",)) == ["package_contents"]


@pytest.mark.asyncio
async def test_courier_purchase_requires_explicit_api_confirmation(evidence_client, monkeypatch):
    from app.api import manual_builds

    client, session_factory = evidence_client
    quote_provider = AsyncMock()
    monkeypatch.setattr(manual_builds, "get_tracked_quotes", quote_provider)
    async with session_factory() as db:
        build = ManualBuild(name="Courier Confirmation Build", status="sold")
        db.add(build)
        await db.commit()
        await db.refresh(build)
        build_id = build.id

    request = {
        "service_slug": "signed-for",
        "price_gbp": 12.0,
        "signed_for_delivery_confirmed": True,
    }
    missing_confirmation = client.post(
        f"/api/manual-builds/{build_id}/book-shipment",
        json=request,
    )
    assert missing_confirmation.status_code == 409
    assert "Explicit confirmation" in missing_confirmation.json()["detail"]
    quote_provider.assert_not_awaited()
    explicit_confirmation = client.post(
        f"/api/manual-builds/{build_id}/book-shipment",
        json={**request, "confirm_live_purchase": True},
    )
    assert explicit_confirmation.status_code == 400
    assert "delivery address" in explicit_confirmation.json()["detail"]
    quote_provider.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("send_result", [False, True])
async def test_direct_dispatch_notification_persists_success_and_retries_failure_with_backoff(
    evidence_client, monkeypatch, send_result
):
    _client, session_factory = evidence_client
    monkeypatch.setattr(shipment_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=send_result)
    monkeypatch.setattr(shipment_notifications, "send_shipment_update_email", sender)
    event_id = await _seed_dispatch_notification_event(session_factory, order_suffix="DISPATCH-RETRY")

    first_run = await shipment_notifications.retry_pending_dispatch_notifications()
    second_run = await shipment_notifications.retry_pending_dispatch_notifications()

    assert first_run["sent" if send_result else "failed"] == 1
    assert second_run["skipped"] == (0 if send_result else 1)
    assert sender.await_count == 1
    async with session_factory() as db:
        saved = await db.get(ShipmentTrackingEvent, event_id)
        assert saved.customer_notification_attempts == 1
        assert (saved.customer_notified_at is not None) is send_result


@pytest.mark.asyncio
async def test_dispatch_notification_retry_never_emails_marketplace_buyer(evidence_client, monkeypatch):
    _client, session_factory = evidence_client
    monkeypatch.setattr(shipment_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(shipment_notifications, "send_shipment_update_email", sender)
    event_id = await _seed_dispatch_notification_event(
        session_factory,
        order_suffix="MARKETPLACE",
        ebay_order_id="EBAY-ORDER-1",
    )

    result = await shipment_notifications.retry_pending_dispatch_notifications()

    assert result["skipped"] == 1
    sender.assert_not_awaited()
    async with session_factory() as db:
        saved = await db.get(ShipmentTrackingEvent, event_id)
        assert saved.customer_notified_at is None
        assert saved.material is False


@pytest.mark.asyncio
async def test_dispatch_email_exhaustion_alerts_admin_once(evidence_client, monkeypatch):
    _client, session_factory = evidence_client
    monkeypatch.setattr(shipment_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=False)
    alert = AsyncMock()
    monkeypatch.setattr(shipment_notifications, "send_shipment_update_email", sender)
    monkeypatch.setattr(shipment_notifications, "emit_alert", alert)
    event_id = await _seed_dispatch_notification_event(
        session_factory,
        order_suffix="DISPATCH-EXHAUSTED",
        attempts=7,
    )

    first_run = await shipment_notifications.retry_pending_dispatch_notifications()
    second_run = await shipment_notifications.retry_pending_dispatch_notifications()

    assert first_run["failed"] == 1
    assert second_run == {"sent": 0, "skipped": 0, "failed": 0}
    assert sender.await_count == 1
    alert.assert_awaited_once()
    assert alert.await_args.kwargs["code"] == "dispatch_notification_delivery_failed"
    async with session_factory() as db:
        saved = await db.get(ShipmentTrackingEvent, event_id)
        assert saved.customer_notification_attempts == 8


async def _seed_customer_problem_notification(session_factory, *, attempts=0):
    async with session_factory() as db:
        customer = Customer(email="aftercare@example.test", name="Aftercare Buyer")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id=f"FF-CASE-{attempts}", customer_id=customer.id, specs={},
            customer_price=500, component_costs=400, overhead_amount=100,
        )
        db.add(order)
        await db.flush()
        problem = CustomerProblem(
            order_id=order.id, category="warranty", description="GPU stopped working",
            status="repair_in_progress", repair_tracking={"carrier": "Royal Mail", "tracking_number": "RM123"},
        )
        db.add(problem)
        await db.flush()
        notification = CustomerProblemNotification(
            problem_id=problem.id,
            order_id=order.id,
            source_key=f"case-test:{problem.id}",
            status_code=problem.status,
            repair_tracking_snapshot=dict(problem.repair_tracking),
            attempt_count=attempts,
        )
        db.add(notification)
        await db.commit()
        return notification.id


async def _seed_direct_aftercare_case(session_factory, *, customer_email="direct-case@example.test"):
    async with session_factory() as db:
        customer = Customer(email=customer_email, name="Direct Case Buyer")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id=f"FF-DIRECT-CASE-{customer_email or 'NO-EMAIL'}", customer_id=customer.id, specs={},
            customer_price=500, component_costs=400, overhead_amount=100,
        )
        db.add(order)
        await db.flush()
        problem = CustomerProblem(
            order_id=order.id, category="warranty", description="Unexpected shutdown",
            status="received", repair_tracking=None,
        )
        db.add(problem)
        await db.commit()
        return problem.id


@pytest.mark.asyncio
@pytest.mark.parametrize("send_result", [False, True])
async def test_customer_problem_notification_is_durable_and_retries_after_backoff(
    evidence_client, monkeypatch, send_result
):
    _client, session_factory = evidence_client
    monkeypatch.setattr(customer_problem_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=send_result)
    monkeypatch.setattr(customer_problem_notifications, "send_customer_case_status_email", sender)
    notification_id = await _seed_customer_problem_notification(session_factory)

    first = await customer_problem_notifications.deliver_customer_problem_notification(notification_id)
    second = await customer_problem_notifications.deliver_customer_problem_notification(notification_id)

    assert first["status"] == ("sent" if send_result else "pending")
    assert second["status"] == ("not_pending" if send_result else "backoff")
    assert sender.await_count == 1
    async with session_factory() as db:
        saved = await db.get(CustomerProblemNotification, notification_id)
        assert saved.attempt_count == 1
        assert saved.state == ("sent" if send_result else "pending")
        assert saved.status_code == "repair_in_progress"
        assert saved.repair_tracking_snapshot["tracking_number"] == "RM123"


@pytest.mark.asyncio
async def test_customer_problem_notification_exhaustion_alerts_once(evidence_client, monkeypatch):
    _client, session_factory = evidence_client
    monkeypatch.setattr(customer_problem_notifications, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(
        customer_problem_notifications,
        "send_customer_case_status_email",
        AsyncMock(return_value=False),
    )
    alert = AsyncMock()
    monkeypatch.setattr(customer_problem_notifications, "emit_alert", alert)
    notification_id = await _seed_customer_problem_notification(session_factory, attempts=7)

    first = await customer_problem_notifications.deliver_customer_problem_notification(notification_id)
    second = await customer_problem_notifications.deliver_customer_problem_notification(notification_id)

    assert first["status"] == "failed"
    assert second["status"] == "not_pending"
    alert.assert_awaited_once()
    assert alert.await_args.kwargs["code"] == "customer_case_notification_exhausted"


async def _seed_parcel2go_order_event(
    session_factory, *, manual_build=False, indirect_order=False, attempts=0, provider="parcel2go"
):
    async with session_factory() as db:
        customer = Customer(email="parcel2go@example.test", name="Courier Buyer")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id=f"FF-P2G-{manual_build}", customer_id=customer.id, specs={},
            customer_price=500, component_costs=400, overhead_amount=100,
        )
        db.add(order)
        build = ManualBuild(
            name="Marketplace Parcel Build",
            status="sold",
            ebay_order_id="EBAY-123" if manual_build or indirect_order else None,
        ) if manual_build or indirect_order else None
        if build:
            db.add(build)
        await db.flush()
        if indirect_order:
            db.add(Build(
                build_type=BuildType.PREBUILT,
                order_id=order.id,
                manual_build_id=build.id,
                spec_json={},
                status=BuildStatus.FINALISED,
            ))
        event = ShipmentTrackingEvent(
            order_id=None if manual_build else order.id,
            manual_build_id=build.id if manual_build else None,
            provider=provider,
            provider_event_id=f"P2G-EVENT-{manual_build}",
            status_code="dispatched",
            description="Your PC is on its way.",
            material=True,
            customer_notification_attempts=attempts,
            occurred_at=datetime.utcnow(),
        )
        db.add(event)
        await db.commit()
        return event.id


@pytest.mark.asyncio
@pytest.mark.parametrize("send_result", [False, True])
async def test_parcel2go_customer_email_is_durable_and_retried(evidence_client, monkeypatch, send_result):
    _client, session_factory = evidence_client
    monkeypatch.setattr(parcel2go_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=send_result)
    monkeypatch.setattr(parcel2go_notifications, "send_courier_event_email", sender)
    event_id = await _seed_parcel2go_order_event(session_factory)

    first = await parcel2go_notifications.deliver_parcel2go_tracking_notification(event_id)
    second = await parcel2go_notifications.deliver_parcel2go_tracking_notification(event_id)

    assert first["status"] == ("sent" if send_result else "pending")
    assert second["status"] == ("not_pending" if send_result else "backoff")
    assert sender.await_count == 1
    async with session_factory() as db:
        event = await db.get(ShipmentTrackingEvent, event_id)
        assert event.customer_notification_attempts == 1
        assert (event.customer_notified_at is not None) is send_result


@pytest.mark.asyncio
async def test_parcel2go_notification_never_emails_marketplace_build(evidence_client, monkeypatch):
    _client, session_factory = evidence_client
    monkeypatch.setattr(parcel2go_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(parcel2go_notifications, "send_courier_event_email", sender)
    event_id = await _seed_parcel2go_order_event(session_factory, manual_build=True)

    result = await parcel2go_notifications.deliver_parcel2go_tracking_notification(event_id)

    assert result["status"] == "channel_suppressed"
    sender.assert_not_awaited()
    async with session_factory() as db:
        event = await db.get(ShipmentTrackingEvent, event_id)
        assert event.customer_notification_attempts == 8
        assert event.customer_notified_at is None


@pytest.mark.asyncio
async def test_parcel2go_notification_suppresses_order_linked_ebay_build(evidence_client, monkeypatch):
    _client, session_factory = evidence_client
    monkeypatch.setattr(parcel2go_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(parcel2go_notifications, "send_courier_event_email", sender)
    event_id = await _seed_parcel2go_order_event(session_factory, indirect_order=True)

    result = await parcel2go_notifications.deliver_parcel2go_tracking_notification(event_id)

    assert result["status"] == "channel_suppressed"
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_order_shipment_event_uses_durable_notification_path(evidence_client, monkeypatch):
    client, session_factory = evidence_client
    notifier = AsyncMock(return_value={"status": "sent"})
    monkeypatch.setattr(orders_api, "deliver_tracking_event_notification", notifier)
    async with session_factory() as db:
        customer = Customer(email="manual-courier@example.test", name="Direct Buyer")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id="FF-MANUAL-COURIER",
            customer_id=customer.id,
            specs={},
            customer_price=500,
            component_costs=400,
            overhead_amount=100,
        )
        db.add(order)
        await db.commit()
        order_id = order.id

    response = client.post("/api/admin/shipment-events", json={
        "order_id": order_id,
        "provider": "royal_mail",
        "status_code": "in_transit",
        "description": "The parcel is on its way.",
        "occurred_at": datetime.utcnow().isoformat(),
        "material": True,
    })

    assert response.status_code == 201
    assert notifier.await_count == 1
    assert notifier.await_args.args[0] == response.json()["id"]
    async with session_factory() as db:
        event = await db.get(ShipmentTrackingEvent, response.json()["id"])
        assert event.provider_event_id == f"operator:{event.id}"
        assert event.customer_notification_attempts == 0


@pytest.mark.asyncio
async def test_order_linked_manual_build_rejects_build_scoped_delivery_event(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        customer = Customer(email="linked-delivery@example.test", name="Direct Buyer")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id="FF-LINKED-DELIVERY",
            customer_id=customer.id,
            specs={},
            customer_price=700,
            component_costs=500,
            overhead_amount=100,
        )
        physical_build = ManualBuild(name="Linked physical build", status="sold", sale_price_actual=700)
        db.add_all([order, physical_build])
        await db.flush()
        db.add(Build(
            build_type=BuildType.PREBUILT,
            order_id=order.id,
            manual_build_id=physical_build.id,
        ))
        await db.commit()
        order_id = order.id
        manual_build_id = physical_build.id

    response = client.post("/api/admin/shipment-events", json={
        "manual_build_id": manual_build_id,
        "provider": "royal_mail",
        "provider_event_id": "delivery-for-order-linked-build",
        "status_code": "delivered",
        "description": "Delivered to the customer.",
        "occurred_at": datetime.utcnow().isoformat(),
        "material": True,
    })

    assert response.status_code == 409
    assert f"order {order_id}" in response.json()["detail"]
    async with session_factory() as db:
        assert await db.scalar(select(ShipmentTrackingEvent.id).where(
            ShipmentTrackingEvent.provider_event_id == "delivery-for-order-linked-build"
        )) is None
        assert await db.scalar(select(WarrantyReserve.id).where(
            WarrantyReserve.manual_build_id == manual_build_id
        )) is None
        assert await db.scalar(select(WarrantyReserve.id).where(
            WarrantyReserve.order_id == order_id
        )) is None


@pytest.mark.asyncio
async def test_order_delivery_event_updates_linked_physical_build_without_duplicate_reserve(
    evidence_client, monkeypatch
):
    client, session_factory = evidence_client
    notifier = AsyncMock(return_value={"status": "sent"})
    monkeypatch.setattr(orders_api, "deliver_tracking_event_notification", notifier)
    delivered_at = datetime.utcnow().replace(microsecond=0) - timedelta(minutes=5)
    async with session_factory() as db:
        customer = Customer(email="linked-delivery-event@example.test", name="Direct Buyer")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id="FF-LINKED-DELIVERY-EVENT",
            customer_id=customer.id,
            specs={},
            customer_price=700,
            component_costs=500,
            overhead_amount=100,
        )
        physical_build = ManualBuild(name="Linked delivered build", status="sold", sale_price_actual=700)
        db.add_all([order, physical_build])
        await db.flush()
        db.add(Build(
            build_type=BuildType.PREBUILT,
            order_id=order.id,
            manual_build_id=physical_build.id,
        ))
        await db.commit()
        order_id = order.id
        manual_build_id = physical_build.id

    response = client.post("/api/admin/shipment-events", json={
        "order_id": order_id,
        "provider": "royal_mail",
        "provider_event_id": "linked-order-delivery-event",
        "status_code": "delivered",
        "description": "Delivered to the customer.",
        "occurred_at": delivered_at.isoformat(),
        "material": True,
    })

    assert response.status_code == 201
    earlier_delivery = delivered_at - timedelta(minutes=2)
    earlier_response = client.post("/api/admin/shipment-events", json={
        "order_id": order_id,
        "provider": "royal_mail",
        "provider_event_id": "linked-order-delivery-event-earlier",
        "status_code": "proof_of_delivery",
        "description": "Earlier confirmed carrier delivery timestamp.",
        "occurred_at": earlier_delivery.isoformat(),
        "material": True,
    })
    assert earlier_response.status_code == 201
    assert notifier.await_count == 2
    assert notifier.await_args_list[0].args == (response.json()["id"],)
    assert notifier.await_args_list[1].args == (earlier_response.json()["id"],)
    async with session_factory() as db:
        order = await db.get(Order, order_id)
        physical_build = await db.get(ManualBuild, manual_build_id)
        order_reserve = (await db.execute(select(WarrantyReserve).where(
            WarrantyReserve.order_id == order_id
        ))).scalar_one()
        assert order.delivered_at == earlier_delivery
        assert order.status == OrderStatus.COMPLETED
        assert physical_build.delivered_at == earlier_delivery
        assert physical_build.warranty_started_at == earlier_delivery
        assert physical_build.dispatch_status == "delivered"
        assert order_reserve.warranty_started_at == earlier_delivery
        assert await db.scalar(select(WarrantyReserve.id).where(
            WarrantyReserve.manual_build_id == manual_build_id
        )) is None


@pytest.mark.asyncio
async def test_future_operator_delivery_event_does_not_start_warranty_clock(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        customer = Customer(email="future-delivery@example.test", name="Direct Buyer")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id="FF-FUTURE-DELIVERY",
            customer_id=customer.id,
            specs={},
            customer_price=700,
            component_costs=500,
            overhead_amount=100,
        )
        db.add(order)
        await db.commit()
        order_id = order.id

    response = client.post("/api/admin/shipment-events", json={
        "order_id": order_id,
        "provider": "operator",
        "provider_event_id": "future-delivery-event",
        "status_code": "delivered",
        "description": "Incorrect future delivery timestamp.",
        "occurred_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "material": True,
    })

    assert response.status_code == 422
    async with session_factory() as db:
        order = await db.get(Order, order_id)
        assert order.delivered_at is None
        assert order.status != OrderStatus.COMPLETED
        assert await db.scalar(select(ShipmentTrackingEvent.id).where(
            ShipmentTrackingEvent.provider_event_id == "future-delivery-event"
        )) is None
        assert await db.scalar(select(WarrantyReserve.id).where(
            WarrantyReserve.order_id == order_id
        )) is None


@pytest.mark.asyncio
async def test_courier_retry_worker_picks_up_operator_order_events(evidence_client, monkeypatch):
    _client, session_factory = evidence_client
    monkeypatch.setattr(parcel2go_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(parcel2go_notifications, "send_courier_event_email", sender)
    await _seed_parcel2go_order_event(session_factory, provider="royal_mail")

    result = await parcel2go_notifications.retry_pending_tracking_notifications()

    assert result == {"sent": 1, "failed": 0, "deferred": 0}
    sender.assert_awaited_once()


@pytest.mark.asyncio
async def test_parcel2go_notification_exhaustion_alerts_once(evidence_client, monkeypatch):
    _client, session_factory = evidence_client
    monkeypatch.setattr(parcel2go_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=False)
    alert = AsyncMock()
    monkeypatch.setattr(parcel2go_notifications, "send_courier_event_email", sender)
    monkeypatch.setattr(parcel2go_notifications, "emit_alert", alert)
    event_id = await _seed_parcel2go_order_event(session_factory, attempts=7)

    first = await parcel2go_notifications.deliver_parcel2go_tracking_notification(event_id)
    second = await parcel2go_notifications.deliver_parcel2go_tracking_notification(event_id)

    assert first["status"] == "failed"
    assert second["status"] == "exhausted"
    assert sender.await_count == 1
    alert.assert_awaited_once()
    assert alert.await_args.kwargs["code"] == "parcel2go_customer_notification_exhausted"


@pytest.mark.asyncio
async def test_admin_case_update_commits_notification_snapshot_before_background_send(
    evidence_client, monkeypatch
):
    from app.services import customer_problem_notifications

    client, session_factory = evidence_client
    monkeypatch.setattr(customer_problem_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(customer_problem_notifications, "send_customer_case_status_email", sender)
    problem_id = await _seed_direct_aftercare_case(session_factory)

    response = client.patch(
        f"/api/admin/customer-problems/{problem_id}",
        json={"status": "reviewing"},
    )

    assert response.status_code == 200
    sender.assert_awaited_once()
    async with session_factory() as db:
        problem = await db.get(CustomerProblem, problem_id)
        notification = (await db.execute(
            select(CustomerProblemNotification).where(
                CustomerProblemNotification.problem_id == problem_id
            )
        )).scalar_one()
        assert problem.status == "reviewing"
        assert notification.status_code == "reviewing"
        assert notification.state == "sent"


@pytest.mark.asyncio
async def test_admin_case_update_alerts_when_linked_order_has_no_email_recipient(
    evidence_client, monkeypatch
):
    from app.services import customer_problem_notifications

    client, session_factory = evidence_client
    monkeypatch.setattr(customer_problem_notifications, "AsyncSessionLocal", session_factory)
    sender = AsyncMock(return_value=True)
    alert = AsyncMock()
    monkeypatch.setattr(customer_problem_notifications, "send_customer_case_status_email", sender)
    monkeypatch.setattr(customer_problem_notifications, "emit_alert", alert)
    problem_id = await _seed_direct_aftercare_case(session_factory, customer_email="")

    response = client.patch(
        f"/api/admin/customer-problems/{problem_id}",
        json={"status": "reviewing"},
    )

    assert response.status_code == 200
    sender.assert_not_awaited()
    alert.assert_awaited_once()
    assert alert.await_args.kwargs["code"] == "customer_case_notification_unavailable"
    async with session_factory() as db:
        notification = (await db.execute(
            select(CustomerProblemNotification).where(
                CustomerProblemNotification.problem_id == problem_id
            )
        )).scalar_one()
        assert notification.state == "failed"
        assert notification.last_error == "recipient_or_case_unavailable"


@pytest.mark.asyncio
async def test_insurance_policy_purchase_requires_live_gate_and_all_operator_confirmations(
    evidence_client, monkeypatch
):
    from app.api import manual_builds

    client, _session_factory = evidence_client
    quote_provider = AsyncMock()
    policy_provider = AsyncMock()
    monkeypatch.setattr(manual_builds, "get_insurance_quote", quote_provider)
    monkeypatch.setattr(manual_builds, "create_insurance_policy", policy_provider)
    monkeypatch.setattr(
        manual_builds,
        "get_settings",
        lambda: SimpleNamespace(secursus_live_parcel_creation_enabled=True),
    )

    missing_confirmations = client.post(
        "/api/manual-builds/7001/insurance-policy",
        json={"quoted_price_gbp": 2.50},
    )
    assert missing_confirmations.status_code == 422
    quote_provider.assert_not_awaited()
    policy_provider.assert_not_awaited()

    monkeypatch.setattr(
        manual_builds,
        "get_settings",
        lambda: SimpleNamespace(secursus_live_parcel_creation_enabled=False),
    )
    confirmations = {
        "confirm_terms": True,
        "confirm_live_purchase": True,
        "confirm_customer_data_share": True,
        "confirm_signed_for_delivery": True,
        "confirm_double_packaging": True,
        "confirm_discreet_packaging": True,
        "confirm_rigid_outer_container": True,
        "confirm_contents_not_deducible": True,
        "confirm_direct_signature": True,
        "confirm_official_carrier_handover": True,
        "quoted_price_gbp": 2.50,
    }
    disabled_purchase = client.post(
        "/api/manual-builds/7001/insurance-policy",
        json=confirmations,
    )
    assert disabled_purchase.status_code == 409
    quote_provider.assert_not_awaited()
    policy_provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_courier_purchase_requires_printable_claim_for_guest_or_marketplace_buyer(evidence_client, monkeypatch):
    from app.api import manual_builds

    client, session_factory = evidence_client
    quote_provider = AsyncMock()
    monkeypatch.setattr(manual_builds, "get_tracked_quotes", quote_provider)
    async with session_factory() as db:
        build = ManualBuild(
            name="Guest portal booking gate",
            status="sold",
            sale_price_actual=600.0,
            buyer_name="Test Buyer",
            customer_email="buyer@example.com",
            buyer_address_json={"contact_name": "Test Buyer", "address_line1": "1 Test Street", "city": "London", "postal_code": "SW1A 1AA", "country_code": "GB"},
            package_weight_kg=8.0,
            package_length_cm=45.0,
            package_width_cm=25.0,
            package_height_cm=50.0,
        )
        db.add(build)
        await db.flush()
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="ready_for_delivery",
            checklist={action: "complete" for action in manual_builds.COURIER_BOOKING_BLOCKING_ACTIONS},
            purchased_ai_services=[],
            customer_software_selections=[],
            artifact_index=[],
        ))
        await db.commit()
        build_id = build.id

    response = client.post(
        f"/api/manual-builds/{build_id}/book-shipment",
        json={
            "service_slug": "signed-for",
            "price_gbp": 12.0,
            "signed_for_delivery_confirmed": True,
            "confirm_live_purchase": True,
        },
    )

    assert response.status_code == 409
    assert "portal claim" in response.json()["detail"]
    quote_provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_courier_booking_is_idempotent_without_a_new_confirmation(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Already Booked Build",
            status="sold",
            dispatch_status="delivered",
            delivered_at=datetime.utcnow() - timedelta(hours=1),
            shipment_booking_state="booked",
            tracking_number="TRACK-ALREADY-BOOKED",
            shipment_booked_at=datetime.utcnow(),
            parcel2go_order_id="P2G-ALREADY-BOOKED",
        )
        db.add(build)
        await db.commit()
        await db.refresh(build)
        build_id = build.id

    response = client.post(
        f"/api/manual-builds/{build_id}/book-shipment",
        json={"service_slug": "signed-for", "price_gbp": 12.0},
    )

    assert response.status_code == 200
    assert response.json()["parcel2go_order_id"] == "P2G-ALREADY-BOOKED"
    assert "already booked" in response.json()["warning"]
    async with session_factory() as db:
        persisted = await db.get(ManualBuild, build_id)
        assert persisted.dispatch_status == "delivered"
        assert persisted.shipment_booking_state == "booked"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_total, expect_payment", [(12.34, True), (12.35, False), (None, False)])
async def test_courier_purchase_audits_confirmed_price_and_admin_before_provider_calls(
    evidence_client, monkeypatch, provider_total, expect_payment
):
    from app.api import manual_builds

    client, session_factory = evidence_client
    quote = SimpleNamespace(service_slug="signed-for", price_gbp=12.34, signature_tracking=True)
    monkeypatch.setattr(manual_builds, "get_tracked_quotes", AsyncMock(return_value=[quote]))
    pre_provider_confirmation = []

    async def create_order_after_check(**_kwargs):
        async with session_factory() as db:
            saved = await db.get(ManualBuild, build_id)
            pre_provider_confirmation.append(saved.evidence_data["shipment_booking_confirmation"])
        return "P2G-ORDER-AUDIT", "private-hash", "P2G-LINE-AUDIT", provider_total

    create_order = AsyncMock(side_effect=create_order_after_check)
    pay_order = AsyncMock(return_value=SimpleNamespace(
        parcel2go_order_id="P2G-ORDER-AUDIT",
        tracking_number="TRACK-AUDIT",
        label_url="https://parcel2go.example/label/1",
        tracking_url="https://parcel2go.example/track/1",
    ))
    monkeypatch.setattr(manual_builds, "create_parcel2go_order", create_order)
    monkeypatch.setattr(manual_builds, "pay_order_with_prepay", pay_order)

    async with session_factory() as db:
        build = ManualBuild(
            name="Courier Audit Build",
            status="sold",
            sale_price_actual=850.0,
            buyer_name="Test Buyer",
            customer_email="buyer@example.com",
            buyer_address_json={
                "contact_name": "Test Buyer",
                "address_line1": "1 Test Street",
                "city": "London",
                "postal_code": "SW1A 1AA",
                "country_code": "GB",
            },
            package_weight_kg=12.0,
            package_length_cm=50.0,
            package_width_cm=30.0,
            package_height_cm=60.0,
        )
        db.add(build)
        await db.flush()
        job = GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="ready_for_delivery",
            checklist={action: "complete" for action in manual_builds.COURIER_BOOKING_BLOCKING_ACTIONS},
            purchased_ai_services=[],
            customer_software_selections=[],
            artifact_index=[],
        )
        grant = PortalAccessGrant(
            manual_build_id=build.id,
            contact_email="buyer@example.com",
            token_hash="c" * 64,
            channel="ebay",
            expires_at=datetime.utcnow() + timedelta(days=30),
            leaflet_storage_key=f"portal-leaflets/{build.id}/grant.pdf",
        )
        db.add_all([job, grant])
        await db.flush()
        job.checklist = {
            **job.checklist,
            "_audit": [{"action": "leaflet_printed", "status": "complete", "portal_grant_id": grant.id}],
        }
        await db.commit()
        build_id = build.id

    response = client.post(
        f"/api/manual-builds/{build_id}/book-shipment",
        json={
            "service_slug": "signed-for",
            "price_gbp": 12.34,
            "signed_for_delivery_confirmed": True,
            "confirm_live_purchase": True,
        },
    )

    assert response.status_code == 200
    assert create_order.await_count == 1
    assert pay_order.await_count == int(expect_payment)
    assert pre_provider_confirmation[0]["confirmed_price_gbp"] == 12.34
    assert pre_provider_confirmation[0]["confirmed_by_admin_id"] == 42
    assert create_order.await_args.kwargs["upsells"] == ["Signature"]
    async with session_factory() as db:
        saved = await db.get(ManualBuild, build_id)
        confirmation = saved.evidence_data["shipment_booking_confirmation"]
        assert confirmation["live_purchase_confirmed"] is True
        assert confirmation["signed_for_delivery_confirmed"] is True
        assert confirmation["signature_extra_included"] is True
        assert confirmation["provider_order_total_gbp"] == provider_total
        assert confirmation["service_slug"] == "signed-for"
        assert confirmation["confirmed_price_gbp"] == 12.34
        assert confirmation["confirmed_by_admin_id"] == 42
        assert confirmation["confirmed_by_admin_name"] == "Workshop Admin"
        assert confirmation["confirmed_at"]
        if expect_payment:
            assert saved.shipment_booking_state == "booked"
        else:
            assert saved.shipment_booking_state == "reconciliation_required"


@pytest.mark.asyncio
async def test_pre_sale_build_cannot_use_shipment_actions_even_with_stale_booking(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Pre-sale stale booking",
            status="built",
            shipment_booking_state="booked",
            tracking_number="STALE-TRACKING",
            shipment_booked_at=datetime.utcnow(),
            parcel2go_order_id="STALE-ORDER",
        )
        db.add(build)
        await db.commit()
        await db.refresh(build)
        build_id = build.id

    upload = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/evidence",
        data={"category": "working_pc"},
        files={"file": ("working.jpg", b"evidence", "image/jpeg")},
    )
    assert upload.status_code == 409
    assert "after the build is sold" in upload.json()["detail"]

    review = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/evidence/missing/review",
        json={"approved": True, "note": "Verified the correct build evidence."},
    )
    assert review.status_code == 409
    assert "after the build is sold" in review.json()["detail"]

    booking = client.post(
        f"/api/manual-builds/{build_id}/book-shipment",
        json={"service_slug": "signed-for", "price_gbp": 12.0, "signed_for_delivery_confirmed": True},
    )
    assert booking.status_code == 409
    assert "after the build is sold" in booking.json()["detail"]

    dispatch = client.post(
        f"/api/manual-builds/{build_id}/dispatch",
        json={"confirm_physical_handover": True},
    )
    assert dispatch.status_code == 409
    assert "after the build is sold" in dispatch.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("dispatch_status", ["dispatched", "delivered"])
async def test_handed_over_build_rejects_collection_changes_and_new_paid_booking(
    evidence_client, monkeypatch, dispatch_status
):
    from app.api import manual_builds

    client, session_factory = evidence_client
    quote_provider = AsyncMock()
    monkeypatch.setattr(manual_builds, "get_tracked_quotes", quote_provider)
    delivered_at = datetime.utcnow() - timedelta(days=1)
    async with session_factory() as db:
        build = ManualBuild(
            name="Delivered build",
            status="sold",
            dispatch_status=dispatch_status,
            delivered_at=delivered_at if dispatch_status == "delivered" else None,
            shipment_booking_state="failed_retryable",
            buyer_address_json={"country_code": "GB"},
            package_weight_kg=10,
            package_length_cm=50,
            package_width_cm=40,
            package_height_cm=30,
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    collection = client.patch(
        f"/api/manual-builds/{build_id}/collection-date",
        json={"collection_date": (datetime.utcnow() + timedelta(days=2)).isoformat()},
    )
    assert collection.status_code == 409
    assert "after courier handover" in collection.json()["detail"]

    booking = client.post(
        f"/api/manual-builds/{build_id}/book-shipment",
        json={
            "service_slug": "signed-for",
            "price_gbp": 12.0,
            "signed_for_delivery_confirmed": True,
            "confirm_live_purchase": True,
        },
    )
    assert booking.status_code == 409
    assert "after physical handover" in booking.json()["detail"]
    quote_provider.assert_not_awaited()

    async with session_factory() as db:
        persisted = await db.get(ManualBuild, build_id)
        assert persisted.dispatch_status == dispatch_status
        assert persisted.delivered_at == (delivered_at if dispatch_status == "delivered" else None)
        assert persisted.shipment_booking_state == "failed_retryable"


@pytest.mark.asyncio
@pytest.mark.parametrize("dispatch_status", ["dispatched", "delivered"])
async def test_handed_over_build_cannot_be_reopened_by_shipment_reconciliation(
    evidence_client, dispatch_status
):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Delivered uncertain booking",
            status="sold",
            dispatch_status=dispatch_status,
            delivered_at=(datetime.utcnow() - timedelta(hours=1)) if dispatch_status == "delivered" else None,
            shipment_booking_state="reconciliation_required",
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    response = client.post(
        f"/api/manual-builds/{build_id}/shipment-booking/reconcile",
        json={
            "resolution": "no_active_booking",
            "provider_checked": True,
            "note": "Checked provider account; no shipment is active.",
        },
    )
    assert response.status_code == 409
    assert "closed after physical handover" in response.json()["detail"]
    async with session_factory() as db:
        persisted = await db.get(ManualBuild, build_id)
        assert persisted.dispatch_status == dispatch_status
        assert persisted.shipment_booking_state == "reconciliation_required"


@pytest.mark.asyncio
async def test_repeated_dispatch_preserves_delivered_state_without_resending(evidence_client, monkeypatch):
    from app.api import manual_builds

    client, session_factory = evidence_client
    send_email = AsyncMock()
    monkeypatch.setattr(manual_builds, "send_shipment_update_email", send_email)
    delivered_at = datetime.utcnow() - timedelta(hours=2)
    async with session_factory() as db:
        build = ManualBuild(
            name="Already delivered build",
            status="sold",
            dispatch_status="delivered",
            delivered_at=delivered_at,
            tracking_number="TRACK-DELIVERED-ONCE",
            evidence_data={"physical_handover_confirmation": {"confirmed": True}},
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    response = client.post(
        f"/api/manual-builds/{build_id}/dispatch",
        json={"confirm_physical_handover": True},
    )
    assert response.status_code == 200
    assert response.json()["dispatch_status"] == "delivered"
    assert response.json()["already_dispatched"] is True
    send_email.assert_not_awaited()
    async with session_factory() as db:
        persisted = await db.get(ManualBuild, build_id)
        assert persisted.dispatch_status == "delivered"
        assert persisted.delivered_at == delivered_at

    queue = client.get("/api/manual-builds/dispatch-zone")
    assert queue.status_code == 200
    queued_build = next(item for item in queue.json() if item["id"] == build_id)
    assert queued_build["has_physical_handover"] is True


@pytest.mark.asyncio
async def test_handover_closes_manifest_generation_and_package_approval(evidence_client):
    client, session_factory = evidence_client
    async with session_factory() as db:
        build = ManualBuild(
            name="Delivered package lock build",
            status="sold",
            dispatch_status="delivered",
            delivered_at=datetime.utcnow() - timedelta(hours=1),
            shipment_booking_state="booked",
            tracking_number="TRACK-POST-HANDOVER",
            shipment_booked_at=datetime.utcnow() - timedelta(hours=3),
            shipping_insurance_status="creation_uncertain",
            evidence_data={"physical_handover_confirmation": {"confirmed": True}},
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    generated = client.post(f"/api/manual-builds/{build_id}/getting-ready/generate", json={})
    assert generated.status_code == 409
    assert "locked after physical handover" in generated.json()["detail"]

    software_script = client.get(
        f"/api/manual-builds/{build_id}/getting-ready/software-script"
    )
    assert software_script.status_code == 409
    assert "closed after physical handover" in software_script.json()["detail"]

    windows_license_helper = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/windows-license-helper",
        json={"confirm_private_key_release": True},
    )
    assert windows_license_helper.status_code == 409
    assert "closed after physical handover" in windows_license_helper.json()["detail"]

    approved = client.post(
        f"/api/manual-builds/{build_id}/getting-ready/approve-and-package",
        json={"confirm_manifest_reviewed": True, "confirm_customer_details_checked": True},
    )
    assert approved.status_code == 409
    assert "closed after physical handover" in approved.json()["detail"]

    changed_build = client.patch(
        f"/api/manual-builds/{build_id}",
        json={
            "name": "Changed after delivery",
            "components": [{"slot": "CPU", "name": "Replacement CPU", "price_paid": 1}],
        },
    )
    assert changed_build.status_code == 409
    assert "locked after physical handover" in changed_build.json()["detail"]

    archived_build = client.delete(f"/api/manual-builds/{build_id}")
    assert archived_build.status_code == 409
    assert "cannot be archived" in archived_build.json()["detail"]

    async with session_factory() as db:
        persisted = await db.get(ManualBuild, build_id)
        assert persisted.name == "Delivered package lock build"
        assert persisted.is_archived is False


@pytest.mark.asyncio
async def test_sold_build_component_changes_cannot_bypass_order_change_flow(evidence_client):
    client, session_factory = evidence_client
    original_components = [{"slot": "CPU", "name": "Approved CPU", "price_paid": 120}]
    async with session_factory() as db:
        build = ManualBuild(
            name="Sold build component lock",
            status="sold",
            shipping_insurance_status="creation_uncertain",
            components=original_components,
            dispatch_status="dispatched",
            shipment_booking_state="booked",
            tracking_number="TRACK-HANDED-OVER",
            shipment_booked_at=datetime.utcnow(),
        )
        db.add(build)
        await db.commit()
        build_id = build.id

    response = client.patch(
        f"/api/manual-builds/{build_id}",
        json={"components": [{"slot": "CPU", "name": "Unapproved replacement", "price_paid": 1}]},
    )
    assert response.status_code == 409
    assert "locked after physical handover" in response.json()["detail"]
    async with session_factory() as db:
        persisted = await db.get(ManualBuild, build_id)
        assert persisted.components == original_components

    insurance_reconciliation = client.post(
        f"/api/manual-builds/{build_id}/insurance-policy/reconcile",
        json={
            "resolution": "no_policy",
            "provider_checked": True,
            "note": "Verified the insurer account after shipment delivery.",
        },
    )
    assert insurance_reconciliation.status_code == 409
    assert "closed after physical handover" in insurance_reconciliation.json()["detail"]
    async with session_factory() as db:
        persisted = await db.get(ManualBuild, build_id)
        assert persisted.shipping_insurance_status == "creation_uncertain"

@pytest.mark.asyncio
async def test_dispatch_api_rejects_tampering_and_avoids_off_channel_email(evidence_client, tmp_path, monkeypatch):
    from app.api import manual_builds

    client, session_factory = evidence_client
    send_email = AsyncMock(return_value=True)
    monkeypatch.setattr(manual_builds, "send_shipment_update_email", send_email)
    async with session_factory() as db:
        build = ManualBuild(
            name="Tampered Evidence Build",
            status="sold",
            customer_email="marketplace-buyer@example.com",
            dispatch_status="awaiting_dispatch",
            shipment_booking_state="booked",
            parcel2go_order_id="P2G-ORDER-73",
            parcel2go_order_line_id="P2G-LINE-73",
            tracking_number="TRACK-73",
            shipment_booked_at=datetime.utcnow(),
            shipping_insurance_status="created",
            shipping_insurance_policy_id="POLICY-73",
            parcel2go_service_slug="royal-mail-signed-for",
            evidence_data={"shipment_booking_confirmation": {
                "signed_for_delivery_confirmed": True,
                "signature_extra_included": True,
                "tracking_url": "https://tracking.example.test/track/ABC123",
            }},
        )
        db.add(build)
        await db.flush()
        artifact_index = []
        build_dir = tmp_path / "private_dispatch" / str(build.id)
        build_dir.mkdir(parents=True)
        evidence = b"approved evidence"
        for index, category in enumerate(("working_pc", "package_contents", "sealed_package")):
            filename = f"{category}.jpg"
            (build_dir / filename).write_bytes(evidence)
            artifact_index.append({
                "id": f"evidence-{index}",
                "category": category,
                "content_type": "image/jpeg",
                "review_status": "approved",
                "storage_key": f"{build.id}/{filename}",
                "size_bytes": len(evidence),
                "sha256": hashlib.sha256(evidence).hexdigest(),
            })
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="ready_for_delivery",
            checklist={action: "complete" for action in DISPATCH_BLOCKING_ACTIONS},
            artifact_index=artifact_index,
        ))
        await db.commit()
        build_id = build.id

    tampered_path = tmp_path / "private_dispatch" / str(build_id) / "package_contents.jpg"
    tampered_path.write_bytes(b"tampered evidence")
    response = client.post(
        f"/api/manual-builds/{build_id}/dispatch",
        json={"confirm_physical_handover": True},
    )

    assert response.status_code == 409
    assert "package_contents" in response.json()["detail"]
    async with session_factory() as db:
        persisted_build = await db.get(ManualBuild, build_id)
        assert persisted_build.dispatch_status != "dispatched"

    tampered_path.write_bytes(b"approved evidence")
    dispatched = client.post(
        f"/api/manual-builds/{build_id}/dispatch",
        json={"confirm_physical_handover": True},
    )
    assert dispatched.status_code == 200
    async with session_factory() as db:
        persisted_build = await db.get(ManualBuild, build_id)
        handover = persisted_build.evidence_data["physical_handover_confirmation"]
        assert handover["confirmed"] is True
        assert handover["confirmed_by_admin_id"] == 42
        assert handover["tracking_number"] == "TRACK-73"
    send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_guest_dispatch_reuses_preissued_claim_and_sends_tracking(evidence_client, tmp_path, monkeypatch):
    from app.api import manual_builds

    client, session_factory = evidence_client
    send_email = AsyncMock(return_value=True)
    claim_email = AsyncMock(return_value=True)
    issue_claim = AsyncMock()
    monkeypatch.setattr(manual_builds, "send_shipment_update_email", send_email)
    monkeypatch.setattr(manual_builds, "send_dispatched_guest_portal_email", claim_email)
    monkeypatch.setattr(manual_builds, "issue_direct_order_portal_claim", issue_claim)
    async with session_factory() as db:
        customer = Customer(name="Direct Buyer", email="verified@example.com")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id="FF-DIRECT-DISPATCH-1",
            customer_id=customer.id,
            specs={"build_name": "Direct Build"},
            customer_price=1500,
            component_costs=1100,
            overhead_amount=75,
        )
        build = ManualBuild(
            name="Direct Build",
            status="sold",
            customer_id=customer.id,
            customer_email="stale-unverified@example.com",
            dispatch_status="awaiting_dispatch",
            shipment_booking_state="booked",
            parcel2go_order_id="P2G-DIRECT-1",
            tracking_number="TRACK-DIRECT-1",
            shipment_booked_at=datetime.utcnow(),
            shipping_insurance_status="created",
            shipping_insurance_policy_id="POLICY-DIRECT-1",
            parcel2go_service_slug="royal-mail-signed-for",
            evidence_data={"shipment_booking_confirmation": {
                "signed_for_delivery_confirmed": True,
                "signature_extra_included": True,
                "tracking_url": "https://tracking.example.test/track/ABC123",
            }},
        )
        db.add_all([order, build])
        await db.flush()
        db.add(Build(
            build_type=BuildType.PREBUILT,
            order_id=order.id,
            manual_build_id=build.id,
            spec_json={"build_name": "Direct Build"},
            status=BuildStatus.FINALISED,
        ))
        grant = PortalAccessGrant(
            order_id=order.id,
            contact_email="verified@example.com",
            token_hash="d" * 64,
            channel="direct_guest",
            expires_at=datetime.utcnow() + timedelta(days=60),
            leaflet_storage_key=f"portal-leaflets/{order.id}/grant.pdf",
        )
        db.add(grant)
        await db.flush()
        grant_id = grant.id
        artifact_index = []
        build_dir = tmp_path / "private_dispatch" / str(build.id)
        build_dir.mkdir(parents=True)
        evidence = b"approved evidence"
        for index, category in enumerate(("working_pc", "package_contents", "sealed_package")):
            filename = f"{category}.jpg"
            (build_dir / filename).write_bytes(evidence)
            artifact_index.append({
                "id": f"direct-evidence-{index}",
                "category": category,
                "content_type": "image/jpeg",
                "review_status": "approved",
                "storage_key": f"{build.id}/{filename}",
                "size_bytes": len(evidence),
                "sha256": hashlib.sha256(evidence).hexdigest(),
            })
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            order_id=order.id,
            customer_id=customer.id,
            source_type="ready_to_ship",
            status="ready_for_delivery",
            checklist={action: "complete" for action in DISPATCH_BLOCKING_ACTIONS},
            artifact_index=artifact_index,
        ))
        await db.commit()
        build_id = build.id
        order_id = order.id

    response = client.post(
        f"/api/manual-builds/{build_id}/dispatch",
        json={"confirm_physical_handover": True},
    )

    assert response.status_code == 200
    assert response.json()["portal_grant_id"] == grant_id
    send_email.assert_awaited_once()
    claim_email.assert_not_awaited()
    issue_claim.assert_not_awaited()
    assert send_email.await_args.args[:3] == (
        "verified@example.com",
        "Direct Buyer",
        "FF-DIRECT-DISPATCH-1",
    )
    assert send_email.await_args.args[-1] == order_id
    assert send_email.await_args.args[5] == "https://tracking.example.test/track/ABC123"
    async with session_factory() as db:
        persisted_grant = await db.get(PortalAccessGrant, grant_id)
        assert persisted_grant is not None
        assert persisted_grant.revoked is False
        dispatch_event = (await db.execute(
            select(ShipmentTrackingEvent).where(
                ShipmentTrackingEvent.order_id == order_id,
                ShipmentTrackingEvent.status_code == "dispatched",
            )
        )).scalar_one()
        assert dispatch_event.tracking_url == "https://tracking.example.test/track/ABC123"
