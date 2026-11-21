import pytest
from datetime import datetime
from types import SimpleNamespace
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app  # noqa: F401 - register all model metadata
from app.models.build import Build, BuildStatus, BuildType
from app.models.customer import Customer
from app.models.getting_started_job import GettingStartedJob
from app.models.manual_build import ManualBuild
from app.models.order import Order, OrderStatus
from app.services.getting_started_jobs import ensure_order_job, ensure_manual_build_job
from app.routes.admin import _ensure_order_dispatch_build
from app.api.orders import _getting_started_portal_summary


@pytest.mark.asyncio
async def test_indirect_sale_backfills_one_private_build_scoped_getting_ready_job():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            build = ManualBuild(
                name="Marketplace build",
                status="sold",
                customer_id=None,
                evidence_data={
                    "fulfilment_type": "ready_to_ship",
                    "playbook_assignment": {
                        "playbook_id": 3,
                        "software_profile": {"recommended_package_ids": ["7zip.7zip", "unknown.package"]},
                    },
                },
            )
            db.add(build)
            await db.flush()

            first = await ensure_manual_build_job(db, manual_build_id=build.id)
            second = await ensure_manual_build_job(db, manual_build_id=build.id)
            await db.flush()

            assert first.id == second.id
            assert first.manual_build_id == build.id
            assert first.order_id is None
            assert first.customer_id is None
            assert first.source_type == "ready_to_ship"
            assert first.customer_software_selections == ["7zip.7zip"]
            assert first.checklist["components_ordered"] is True
            assert await db.scalar(
                select(func.count()).select_from(GettingStartedJob).where(
                    GettingStartedJob.manual_build_id == build.id
                )
            ) == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize("guest", [False, True])
def test_customer_portal_getting_ready_summary_exposes_only_allowlisted_progress(guest):
    updated_at = datetime(2026, 9, 29, 12, 30)
    reviewed_at = datetime(2026, 9, 29, 12, 15)
    job = GettingStartedJob(
        status="awaiting_admin_review",
        source_type="curated_for_you",
        updated_at=updated_at,
        reviewed_at=reviewed_at,
        order_id=314,
        manifest={
            "build_name": "Customer build",
            "driver_and_firmware_review": [{
                "component_name": "Private motherboard",
                "source_url": "https://internal-review.example/private-source",
            }],
            "sources": [{"claim": "Private operator research note"}],
        },
        artifact_index=[{
            "category": "customer_package",
            "version": 2,
            "filename": "customer-documents-v2.zip",
            "size_bytes": 2048,
            "sha256": "a" * 64,
            "customer_safe": True,
            "documents": [
                "01-build-plaque.pdf",
                "04-getting-started-guide.md",
                "startup-automation.ps1",
            ],
        }],
        customer_software_selections=["7zip.7zip"],
        purchased_ai_services=[
            {
                "id": "local_llm_setup",
                "name": "Local AI model setup",
                "description": "A reviewed local model setup.",
                "price_gbp": 99.0,
                "payment_status": "paid",
                "stripe_payment_intent_id": "pi_private-canary",
                "client_secret": "secret_private-canary",
                "purchase_id": 912,
            },
            {"id": "unconfirmed", "payment_status": "pending", "stripe_payment_intent_id": "pi_pending-canary"},
        ],
        checklist={
            "software_selection_submitted": True,
            "qa_recheck_passed": "complete",
            "windows_target": {"model": "Private drive", "serial": "PRIVATE-SERIAL"},
            "internal_operator_notes": "Private workshop note",
            "audit_actor_email": "admin@example.com",
        },
        admin_notes="Private review note",
    )

    summary = _getting_started_portal_summary(job, guest=guest)

    assert summary["status"] == "awaiting_admin_review"
    assert summary["last_updated"] == updated_at.isoformat()
    assert summary["checklist"] == {
        "software_selection_submitted": True,
        "qa_recheck_passed": "complete",
    }
    assert summary["software_selections"] == ["7zip.7zip"]
    assert summary["software_selection"] == {
        "submitted": True,
        "apps": [{
            "package_id": "7zip.7zip",
            "name": "7-Zip",
            "category": "Utilities",
            "estimated_minutes_saved": 4,
            "license_note": "Free/open-source; check the publisher's terms for the current package.",
        }],
        "estimated_time_saved_minutes": 4,
        "time_estimate_basis": "Indicative internal estimate for avoiding manual search/download/setup; it is not benchmarked or guaranteed.",
    }
    assert summary["purchased_ai_services"] == [{
        "id": "local_llm_setup",
        "name": "Local AI model setup",
        "description": "A reviewed local model setup.",
        "price_gbp": 99.0,
        "payment_status": "paid",
    }]
    assert "customer_manifest" not in summary
    assert "Private motherboard" not in repr(summary)
    assert "internal-review.example" not in repr(summary)
    assert "Private operator research note" not in repr(summary)
    assert "pi_private-canary" not in repr(summary)
    assert "secret_private-canary" not in repr(summary)
    assert "pi_pending-canary" not in repr(summary)
    assert summary["customer_package"] == {
        "version": 2,
        "filename": "customer-documents-v2.zip",
        "size_bytes": 2048,
        "sha256": "a" * 64,
        "download_url": (
            "/api/orders/guest-portal/package" if guest
            else "/api/orders/314/getting-started/package"
        ),
    }
    assert summary["customer_documents"] == [
        {
            "title": "Your build plaque",
            "filename": "01-build-plaque.pdf",
            "download_url": (
                "/api/orders/guest-portal/document?name=01-build-plaque.pdf" if guest
                else "/api/orders/314/getting-started/document?name=01-build-plaque.pdf"
            ),
            "media_type": "application/pdf",
        },
        {
            "title": "Getting started guide",
            "filename": "04-getting-started-guide.md",
            "download_url": (
                "/api/orders/guest-portal/document?name=04-getting-started-guide.md" if guest
                else "/api/orders/314/getting-started/document?name=04-getting-started-guide.md"
            ),
            "media_type": "text/markdown; charset=utf-8",
        },
    ]
    assert "startup-automation.ps1" not in repr(summary)
    assert "admin_notes" not in summary
    assert "audit_actor_email" not in summary
    assert "PRIVATE-SERIAL" not in repr(summary)
    assert "Private workshop note" not in repr(summary)


def test_customer_portal_hides_unsubmitted_software_defaults():
    job = GettingStartedJob(
        status="awaiting_admin_review",
        source_type="ready_to_ship",
        customer_software_selections=["7zip.7zip", "unknown.package"],
        checklist={"software_selection_submitted": False},
    )

    summary = _getting_started_portal_summary(job, guest=True)

    assert summary["software_selections"] == []
    assert summary["software_selection"] == {
        "submitted": False,
        "apps": [],
        "estimated_time_saved_minutes": 0,
        "time_estimate_basis": "Indicative internal estimate for avoiding manual search/download/setup; it is not benchmarked or guaranteed.",
    }


@pytest.mark.asyncio
async def test_ready_to_ship_sale_attaches_existing_pre_sale_job_once():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            customer = Customer(id=51, name="Ready Buyer", email="ready@example.com")
            db.add(customer)
            await db.flush()
            order = Order(
                order_id="FF-READY-PORTAL-1",
                customer_id=customer.id,
                specs={"build_name": "Voyager"},
                customer_price=2400,
                component_costs=1750,
                overhead_amount=100,
            )
            wrong_order = Order(
                order_id="FF-READY-PORTAL-2",
                customer_id=customer.id,
                specs={"build_name": "Different Build"},
                customer_price=1000,
                component_costs=700,
                overhead_amount=100,
            )
            build = ManualBuild(
                name="Voyager",
                status="sold",
                customer_id=customer.id,
                customer_email=customer.email,
                components=[{"type": "GPU", "model": "Graphics Card Model"}],
            )
            db.add_all([order, wrong_order, build])
            await db.flush()
            pre_sale_orchestration_build = Build(
                build_type=BuildType.PREBUILT,
                manual_build_id=build.id,
                spec_json=build.components,
                status=BuildStatus.FINALISED,
            )
            db.add(pre_sale_orchestration_build)
            await db.flush()
            pre_sale_orchestration_build_id = pre_sale_orchestration_build.id
            job = GettingStartedJob(
                manual_build_id=build.id,
                customer_id=None,
                source_type="ready_to_ship",
                status="awaiting_admin_review",
                checklist={"content_manifest": "needs_review", "components_ordered": True},
                artifact_index=[{
                    "id": "presale-report",
                    "category": "benchmark_results",
                    "storage_key": f"{build.id}/benchmarks.json",
                }],
                admin_notes="Benchmarked before listing.",
            )
            db.add(job)
            await db.flush()
            job_id = job.id

            linked = await ensure_order_job(
                db,
                order_id=order.id,
                customer_id=customer.id,
                playbook_id=None,
                source_type="ready_to_ship",
                manual_build_id=build.id,
            )
            await db.flush()

            persisted = await db.get(GettingStartedJob, job_id)
            assert linked.id == job_id
            assert persisted.order_id == order.id
            linked_build = await db.get(Build, pre_sale_orchestration_build_id)
            assert linked_build.order_id == order.id
            assert linked_build.manual_build_id == build.id
            assert linked_build.spec_json == build.components
            assert await db.scalar(
                select(func.count()).select_from(Build).where(Build.manual_build_id == build.id)
            ) == 1

            conflict_order = Order(
                order_id="FF-READY-PORTAL-CONFLICT",
                customer_id=customer.id,
                specs={"build_name": "Conflicting Build"},
                customer_price=1000,
                component_costs=700,
                overhead_amount=100,
            )
            conflict_build = ManualBuild(
                name="Conflicting Build",
                status="sold",
                customer_id=customer.id,
                customer_email=customer.email,
            )
            db.add_all([conflict_order, conflict_build])
            await db.flush()
            db.add_all([
                GettingStartedJob(
                    order_id=conflict_order.id,
                    customer_id=customer.id,
                    source_type="ready_to_ship",
                    status="awaiting_admin_review",
                    checklist={},
                ),
                GettingStartedJob(
                    manual_build_id=conflict_build.id,
                    customer_id=customer.id,
                    source_type="ready_to_ship",
                    status="awaiting_admin_review",
                    checklist={},
                ),
            ])
            await db.flush()
            with pytest.raises(ValueError, match="Conflicting Getting Ready jobs"):
                await ensure_order_job(
                    db,
                    order_id=conflict_order.id,
                    customer_id=customer.id,
                    playbook_id=None,
                    source_type="ready_to_ship",
                    manual_build_id=conflict_build.id,
                )
            assert persisted.manual_build_id == build.id
            assert persisted.customer_id == customer.id
            assert persisted.artifact_index[0]["id"] == "presale-report"
            assert persisted.admin_notes == "Benchmarked before listing."
            count = await db.scalar(
                select(func.count())
                .select_from(GettingStartedJob)
                .where(GettingStartedJob.manual_build_id == build.id)
            )
            assert count == 1
            with pytest.raises(ValueError, match="already linked to a different order"):
                await ensure_order_job(
                    db,
                    order_id=wrong_order.id,
                    customer_id=customer.id,
                    playbook_id=None,
                    source_type="ready_to_ship",
                    manual_build_id=build.id,
                )
            assert persisted.order_id == order.id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("source_type", ["curated_for_you", "made-by-you"])
async def test_paid_made_to_order_sale_creates_one_order_linked_portal_shell(source_type):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            customer = Customer(name="Made-to-order Buyer", email="buyer@example.com")
            db.add(customer)
            await db.flush()
            order = Order(
                order_id=f"FF-{source_type}-PORTAL",
                customer_id=customer.id,
                specs={
                    "build_name": "Order Linked Build",
                    "delivery_address": {"line1": "10 Market Street", "postcode": "AB1 2CD"},
                    "billing_address": {"line1": "11 Finance Road", "postcode": "EF3 4GH"},
                    "delivery": {"line1": "13 Nested Address Road", "postcode": "GH5 6IJ"},
                    "billing": {"line1": "14 Nested Billing Road", "postcode": "KL7 8MN"},
                    "customer_contact": {
                        "name": "Made-to-order Buyer",
                        "email": "buyer@example.com",
                        "phone": "07123456789",
                    },
                    "workshop_notes": {
                        "customer_phone": "07123456789",
                        "shipping_address": {"line1": "12 Hidden Lane", "postcode": "ZZ9 9ZZ"},
                    },
                    "component_specs": [
                        {"model": "GPU Model", "contact_email": "buyer@example.com"},
                        {"model": "Motherboard Model", "addressable_rgb_header": True},
                    ],
                },
                customer_price=1800,
                component_costs=1200,
                overhead_amount=80,
            )
            db.add(order)
            await db.flush()

            job = await ensure_order_job(
                db,
                order_id=order.id,
                customer_id=customer.id,
                playbook_id=None,
                source_type=source_type,
            )
            first_job_id = job.id
            await db.flush()
            retried = await ensure_order_job(
                db,
                order_id=order.id,
                customer_id=customer.id,
                playbook_id=None,
                source_type=source_type,
            )
            await db.flush()

            shell = (await db.execute(select(Build).where(Build.order_id == order.id))).scalar_one()
            assert retried.id == first_job_id
            assert job.source_type == source_type.replace("-", "_")
            assert job.status == "awaiting_build"
            assert job.order_id == order.id
            assert job.customer_id == customer.id
            assert job.manual_build_id is None
            assert shell.build_type == BuildType.MADE_TO_ORDER
            assert shell.status == BuildStatus.SOURCING
            assert shell.spec_json == {
                "build_name": "Order Linked Build",
                "component_specs": [
                    {"model": "GPU Model"},
                    {"model": "Motherboard Model", "addressable_rgb_header": True},
                ],
            }
            assert await db.scalar(
                select(func.count()).select_from(GettingStartedJob).where(GettingStartedJob.order_id == order.id)
            ) == 1
            assert await db.scalar(
                select(func.count()).select_from(Build).where(Build.order_id == order.id)
            ) == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize("preexisting_job", [True, False])
def test_ready_to_ship_bridge_creates_or_advances_job_to_admin_review(tmp_path, preexisting_job):
    database_path = tmp_path / f"ready_to_ship_bridge_{preexisting_job}.db"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            customer = Customer(name="Curated Buyer", email="curated@example.com")
            db.add(customer)
            db.flush()
            order = Order(
                order_id="FF-CURATED-READY-TO-SHIP",
                customer_id=customer.id,
                status=OrderStatus.QA,
                specs={
                    "fulfilment_type": "curated_for_you",
                    "benchmark_results": {"overall_score": 100},
                    "benchmark_evidence_review": {"confirmed_measured_results": True},
                    "slots": [{"slot_type": "CPU", "title": "Reviewed CPU", "variant_id": 12}],
                    "case_id": 7,
                    "case_name": "Reviewed Case",
                    "software_package_ids": ["7zip.7zip"],
                },
                customer_price=1700,
                component_costs=1200,
                overhead_amount=80,
            )
            db.add(order)
            db.flush()
            shell = Build(
                build_type=BuildType.MADE_TO_ORDER,
                order_id=order.id,
                playbook_id=None,
                spec_json={"paid_order_spec": True},
                status=BuildStatus.SOURCING,
            )
            job = GettingStartedJob(
                order_id=order.id,
                customer_id=customer.id,
                source_type="curated_for_you",
                status="awaiting_build",
                checklist={"components_ordered": True},
                customer_software_selections=["7zip.7zip"],
            ) if preexisting_job else None
            db.add(shell)
            if job:
                db.add(job)
            db.flush()

            manual_build = _ensure_order_dispatch_build(
                db,
                order,
                SimpleNamespace(email="admin@example.com"),
            )
            db.flush()
            job = db.query(GettingStartedJob).filter(GettingStartedJob.order_id == order.id).one()

            assert manual_build.status == "sold"
            assert job.manual_build_id == manual_build.id
            assert job.status == "awaiting_admin_review"
            assert job.checklist["benchmark_results_recorded"] is True
            assert job.customer_software_selections == ["7zip.7zip"]
            assert job.source_type == "curated_for_you"
            assert job.customer_id == customer.id
            assert db.query(GettingStartedJob).filter(GettingStartedJob.order_id == order.id).count() == 1
            assert shell.manual_build_id == manual_build.id
            assert shell.status == BuildStatus.FINALISED
            db.commit()
    finally:
        engine.dispose()
