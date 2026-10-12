from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.getting_started_job import GettingStartedJob
from app.models.build import Build, BuildStatus, BuildType
from app.models.manual_build import ManualBuild
from app.models.order import Order
from app.models.playbook import Playbook
from app.services.software_catalogue import SOFTWARE_BY_ID


DEFAULT_CHECKLIST = {
    "source_data_complete": "not_ready",
    "customer_selections_locked": "not_ready",
    "content_manifest": "not_ready",
    "component_manuals_reviewed": "not_ready",
    "driver_firmware_reviewed": "not_ready",
    "artifacts_generated": "not_ready",
    "artifacts_reviewed": "not_ready",
    "customer_package": "not_ready",
    "software_setup": "pending_customer_selection",
    "usb_verified": "not_ready",
    "machine_setup_run": "not_ready",
    "windows_target_confirmed": "not_ready",
    "windows_deployment_completed": "not_ready",
    "windows_activation_checked": "not_ready",
    "drivers_updates_complete": "not_ready",
    "ai_services_complete": "not_required",
    "rgb_theme_applied": "not_ready",
    "qa_recheck_passed": "not_ready",
    "portal_published": "not_ready",
    "leaflet_printed": "not_ready",
    "working_pc_photo": "not_ready",
    "package_contents_photo": "not_ready",
    "sealed_package_photo": "not_ready",
}


async def lock_manual_build_then_getting_started_job(
    db: AsyncSession,
    build_id: int,
) -> tuple[ManualBuild | None, GettingStartedJob | None]:
    """Lock the physical build before its preparation job in every writer path."""
    build = (await db.execute(
        select(ManualBuild)
        .where(ManualBuild.id == build_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if build is None:
        return None, None
    job = (await db.execute(
        select(GettingStartedJob)
        .where(GettingStartedJob.manual_build_id == build_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    return build, job

_PRIVATE_BUILD_SPEC_KEYS = {
    "address", "addressline1", "addressline2", "billing", "billingaddress", "billingdetails",
    "buyer", "buyeraddress", "buyercontact",
    "buyeremail", "buyername", "buyerphone", "contactemail", "contactname",
    "contact", "contactphone", "customeraddress", "customercontact", "customeremail", "customername",
    "contactdetails", "customerdetails", "customerphone", "delivery", "deliveryaddress",
    "deliverydetails", "email", "fulladdress", "fullname", "deliverycontact",
    "mobile", "phone", "postalcode", "postcode", "recipient", "recipientdetails",
    "recipientcontact", "recipientemail", "recipientname", "recipientphone", "shippingaddress",
    "shipping", "shippingcontact", "shippingdetails", "telephone",
}
_PRIVATE_BUILD_SPEC_KEY_MARKERS = ("address", "contact", "email", "phone", "telephone", "mobile")


def _is_private_build_spec_key(normalized_key: str) -> bool:
    if normalized_key in _PRIVATE_BUILD_SPEC_KEYS:
        return True
    for marker in _PRIVATE_BUILD_SPEC_KEY_MARKERS:
        if marker not in normalized_key:
            continue
        if marker == "address" and "addressable" in normalized_key:
            continue
        if marker in {"phone", "telephone"} and any(
            technical in normalized_key for technical in ("microphone", "headphone", "earphone")
        ):
            continue
        return True
    return False


def _customer_safe_build_spec_value(value):
    """Copy JSON build data while removing personal contact and address fields."""
    if isinstance(value, dict):
        safe = {}
        for key, nested in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if _is_private_build_spec_key(normalized_key):
                continue
            safe_value = _customer_safe_build_spec_value(nested)
            if isinstance(nested, dict) and not safe_value:
                continue
            safe[key] = safe_value
        return safe
    if isinstance(value, list):
        safe_items = []
        for item in value:
            safe_item = _customer_safe_build_spec_value(item)
            if isinstance(item, dict) and not safe_item:
                continue
            safe_items.append(safe_item)
        return safe_items
    return value

CHECKLIST_STATUSES = {
    "not_ready", "ready", "in_progress", "blocked", "needs_review",
    "complete", "failed", "not_required", "pending_customer_selection",
}

DISPATCH_BLOCKING_ACTIONS = (
    "source_data_complete",
    "customer_selections_locked",
    "content_manifest",
    "component_manuals_reviewed",
    "driver_firmware_reviewed",
    "artifacts_generated",
    "artifacts_reviewed",
    "customer_package",
    "software_setup",
    "usb_verified",
    "machine_setup_run",
    "windows_target_confirmed",
    "windows_deployment_completed",
    "windows_activation_checked",
    "drivers_updates_complete",
    "ai_services_complete",
    "rgb_theme_applied",
    "qa_recheck_passed",
    "portal_published",
    "leaflet_printed",
    "working_pc_photo",
    "package_contents_photo",
    "sealed_package_photo",
)

# Workshop readiness is required before a courier purchase, but packing
# evidence is intentionally collected after the tracking number exists and
# before the insurance policy and physical handover.
DISPATCH_PHOTO_ACTIONS = (
    "working_pc_photo",
    "package_contents_photo",
    "sealed_package_photo",
)
COURIER_BOOKING_BLOCKING_ACTIONS = tuple(
    action for action in DISPATCH_BLOCKING_ACTIONS
    if action not in DISPATCH_PHOTO_ACTIONS
)
INSURANCE_REQUIRED_PHOTO_CATEGORIES = (
    "package_contents",
    "sealed_package",
)

OPERATOR_CHECKLIST_ACTIONS = {
    "source_data_complete",
    "customer_selections_locked",
    "component_manuals_reviewed",
    "driver_firmware_reviewed",
    "software_setup",
    "usb_verified",
    "machine_setup_run",
    "windows_target_confirmed",
    "windows_deployment_completed",
    "windows_activation_checked",
    "drivers_updates_complete",
    "ai_services_complete",
    "rgb_theme_applied",
    "qa_recheck_passed",
    "portal_published",
    "leaflet_printed",
}

# Only explicitly optional add-on work can be waived. Required preparation,
# verification, evidence and handover actions must never become dispatch-ready
# via `not_required`, even when the endpoint is called outside the admin UI.
OPTIONAL_CHECKLIST_ACTIONS = {
    "ai_services_complete",
    "rgb_theme_applied",
}


def checklist_with_defaults(
    value: dict | None,
    purchased_ai_services: list | None = None,
) -> dict:
    checklist = {**DEFAULT_CHECKLIST, **(value or {})}
    # AI setup is optional only when nothing was purchased. Once a paid
    # service is attached to the job, an old/default `not_required` value
    # must not let the order pass courier or dispatch readiness.
    if purchased_ai_services:
        if checklist.get("ai_services_complete") == "not_required":
            checklist["ai_services_complete"] = "not_ready"
    return checklist


def checklist_dispatch_ready(
    value: dict | None,
    purchased_ai_services: list | None = None,
) -> bool:
    return not incomplete_checklist_actions(value, DISPATCH_BLOCKING_ACTIONS, purchased_ai_services)


def incomplete_checklist_actions(
    value: dict | None,
    actions: tuple[str, ...] | list[str],
    purchased_ai_services: list | None = None,
) -> list[str]:
    """Return gates that are not complete under the shared waiver policy."""
    checklist = checklist_with_defaults(value, purchased_ai_services)
    return [
        action for action in actions
        if checklist.get(action) != "complete"
        and not (
            checklist.get(action) == "not_required"
            and action in OPTIONAL_CHECKLIST_ACTIONS
        )
    ]


def validate_ai_setup_checklist_update(
    *, action: str, status: str, purchased_ai_services: list | None, scope_confirmed: bool,
) -> None:
    """Enforce customer approval for paid AI completion at the API boundary."""
    if action != "ai_services_complete" or not purchased_ai_services:
        return
    if status == "not_required":
        raise ValueError("This build has paid AI services; complete the purchased setup before dispatch")
    if status == "complete" and not scope_confirmed:
        raise ValueError(
            "Confirm the customer's approval of the exact AI application/model and account/data permissions before completing paid AI setup"
        )


def missing_insurance_photo_categories(job: GettingStartedJob | None) -> list[str]:
    """List required pre-shipment evidence categories without a saved image."""
    artifacts = list(job.artifact_index or []) if job else []
    missing = []
    for category in INSURANCE_REQUIRED_PHOTO_CATEGORIES:
        if not any(
            isinstance(item, dict)
            and item.get("category") == category
            and str(item.get("content_type") or "").startswith("image/")
            and item.get("review_status") == "approved"
            for item in artifacts
        ):
            missing.append(category)
    return missing


def missing_dispatch_evidence_categories(job: GettingStartedJob | None) -> list[str]:
    """Require working-build media and insurer photos before dispatch."""
    missing = missing_insurance_photo_categories(job)
    artifacts = list(job.artifact_index or []) if job else []
    has_working_media = any(
        isinstance(item, dict)
        and item.get("category") == "working_pc"
        and str(item.get("content_type") or "").startswith(("image/", "video/"))
        and item.get("review_status") == "approved"
        for item in artifacts
    )
    if not has_working_media:
        missing.insert(0, "working_pc")
    return missing


def normalize_source_type(value: str) -> str:
    """Map checkout/product labels to the durable Getting Ready workflow key."""
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "prebuilt": "ready_to_ship",
        "ready_to_ship": "ready_to_ship",
        "curated": "curated_for_you",
        "curated_for_you": "curated_for_you",
        "custom": "made_by_you",
        "made_by_you": "made_by_you",
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise ValueError(f"Unsupported Getting Ready source type: {value!r}") from error


async def ensure_order_job(
    db: AsyncSession,
    *,
    order_id: int,
    customer_id: int,
    playbook_id: int | None,
    source_type: str,
    manual_build_id: int | None = None,
) -> GettingStartedJob:
    """Create or attach the per-build portal preparation record idempotently."""
    source_type = normalize_source_type(source_type)
    order = (await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )).scalar_one_or_none()
    if order is None:
        raise ValueError(f"Cannot create Getting Ready job for missing order {order_id}")
    if order.customer_id != customer_id:
        raise ValueError("Getting Ready job customer does not own the order")

    manual_build = None
    if manual_build_id is not None:
        manual_build = (await db.execute(
            select(ManualBuild).where(ManualBuild.id == manual_build_id).with_for_update()
        )).scalar_one_or_none()
        if manual_build is None:
            raise ValueError(f"Cannot link Getting Ready job to missing build {manual_build_id}")
        if manual_build.customer_id not in (None, customer_id):
            raise ValueError("Getting Ready job customer does not own the physical build")

    build_spec = _customer_safe_build_spec_value(order.specs or {})
    build_query = select(Build).where(Build.order_id == order_id)
    if manual_build_id is not None:
        build_query = select(Build).where(
            or_(Build.order_id == order_id, Build.manual_build_id == manual_build_id)
        )
    matching_builds = (await db.execute(build_query.with_for_update())).scalars().all()
    if len(matching_builds) > 1:
        raise ValueError("Conflicting orchestration builds already exist for this order/build; reconcile them before linking")
    build = matching_builds[0] if matching_builds else None
    if build and build.order_id not in (None, order_id):
        raise ValueError("This physical build is already linked to a different order")
    if build and manual_build_id is not None and build.manual_build_id not in (None, manual_build_id):
        raise ValueError("This order's customer portal is already linked to a different physical build")

    statement = select(GettingStartedJob).where(GettingStartedJob.order_id == order_id)
    if manual_build_id is not None:
        statement = select(GettingStartedJob).where(
            (GettingStartedJob.order_id == order_id)
            | (GettingStartedJob.manual_build_id == manual_build_id)
        )
    matching_jobs = (await db.execute(statement.with_for_update())).scalars().all()
    if len(matching_jobs) > 1:
        raise ValueError(
            "Conflicting Getting Ready jobs already exist for this order/build; reconcile them before linking"
        )
    job = matching_jobs[0] if matching_jobs else None
    if job and manual_build_id is not None:
        if job.order_id not in (None, order_id):
            raise ValueError("This physical build is already linked to a different order")
        if job.manual_build_id not in (None, manual_build_id):
            raise ValueError("This order's Getting Ready job is already linked to a different physical build")
    if job is None:
        initial_checklist = dict(DEFAULT_CHECKLIST)
        if source_type == "ready_to_ship":
            # These builds are complete stock; their components were ordered
            # before listing and the post-sale cancellation window is closed.
            initial_checklist["components_ordered"] = True
        job = GettingStartedJob(
            order_id=order_id,
            manual_build_id=manual_build_id,
            customer_id=customer_id,
            playbook_id=playbook_id,
            source_type=source_type,
            status="awaiting_build" if source_type in {"curated_for_you", "made_by_you"} else "awaiting_admin_review",
            checklist=initial_checklist,
        )
        db.add(job)
    else:
        job.order_id = order_id
        job.manual_build_id = manual_build_id or job.manual_build_id
        job.customer_id = customer_id
        job.playbook_id = playbook_id or job.playbook_id
        job.source_type = source_type
        job.checklist = checklist_with_defaults(job.checklist, job.purchased_ai_services)
        if source_type == "ready_to_ship":
            job.checklist["components_ordered"] = True
        job.updated_at = datetime.utcnow()

    # Create the per-order physical build portal at sale time. Ready-to-Ship
    # units may already have a workshop record; made-to-order builds begin as
    # an order-linked shell and are enriched as sourcing/build evidence arrives.
    build_type = BuildType.PREBUILT if source_type == "ready_to_ship" else BuildType.MADE_TO_ORDER
    build_status = BuildStatus.FINALISED if source_type == "ready_to_ship" else BuildStatus.SOURCING
    if build is None:
        db.add(Build(
            build_type=build_type,
            order_id=order_id,
            manual_build_id=manual_build_id,
            playbook_id=playbook_id,
            spec_json=build_spec,
            status=build_status,
        ))
    else:
        build.build_type = build_type
        preserve_prebuilt_spec = (
            source_type == "ready_to_ship"
            and manual_build_id is not None
            and build.manual_build_id == manual_build_id
        )
        build.order_id = order_id
        build.manual_build_id = manual_build_id or build.manual_build_id
        build.playbook_id = playbook_id or build.playbook_id
        if not preserve_prebuilt_spec:
            build.spec_json = build_spec
        build.status = build_status

    # Callers use the returned job's identifier immediately (including when
    # retrying the sale hook in the same transaction), so materialize both
    # the job and its linked portal shell before returning.
    await db.flush()

    if playbook_id and not (job.checklist or {}).get("software_selection_submitted"):
        order_specs = (order.specs or {}) if order else {}
        snapshot = order_specs.get("software_profile")
        assignment = ((manual_build.evidence_data or {}).get("playbook_assignment") or {}) if manual_build else {}
        snapshot = snapshot or assignment.get("software_profile")
        if assignment.get("playbook_id"):
            job.playbook_id = job.playbook_id or assignment["playbook_id"]
        playbook = await db.get(Playbook, playbook_id) if not snapshot else None
        profile = snapshot or ((playbook.software_profile or {}) if playbook else {})
        selected_in_checkout = order_specs.get("software_package_ids")
        recommended = selected_in_checkout if isinstance(selected_in_checkout, list) else profile.get("recommended_package_ids", [])
        job.customer_software_selections = [package_id for package_id in recommended if package_id in SOFTWARE_BY_ID]
        if isinstance(selected_in_checkout, list):
            job.checklist = {**(job.checklist or {}), "software_selection_submitted": True}
    return job


async def ensure_manual_build_job(
    db: AsyncSession,
    *,
    manual_build_id: int,
) -> GettingStartedJob:
    """Backfill a private, build-scoped preparation job for a sold indirect build.

    New Ready-to-Ship builds receive a job at Built. This idempotent fallback
    covers legacy/exception sale routes without creating or attaching a buyer
    account from marketplace data.
    """
    build, job = await lock_manual_build_then_getting_started_job(db, manual_build_id)
    if build is None:
        raise ValueError(f"Cannot create Getting Ready job for missing build {manual_build_id}")
    if job is not None:
        return job

    evidence = build.evidence_data if isinstance(build.evidence_data, dict) else {}
    assignment = evidence.get("playbook_assignment") if isinstance(evidence.get("playbook_assignment"), dict) else {}
    profile = assignment.get("software_profile") if isinstance(assignment.get("software_profile"), dict) else {}
    recommended = profile.get("recommended_package_ids")
    selections = [
        package_id for package_id in recommended
        if isinstance(package_id, str) and package_id in SOFTWARE_BY_ID
    ] if isinstance(recommended, list) else []
    source_type = normalize_source_type(evidence.get("fulfilment_type") or "ready_to_ship")
    checklist = {**DEFAULT_CHECKLIST, "components_ordered": True}
    job = GettingStartedJob(
        manual_build_id=build.id,
        customer_id=None,
        playbook_id=assignment.get("playbook_id"),
        source_type=source_type,
        status="awaiting_admin_review",
        checklist=checklist,
        customer_software_selections=selections,
    )
    db.add(job)
    await db.flush()
    return job
