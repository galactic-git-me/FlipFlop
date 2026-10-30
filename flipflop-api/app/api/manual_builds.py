import json
import asyncio
import re
import uuid
import os
import io
import html
import hashlib
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote
from urllib.parse import urlparse
import shutil
import httpx
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from jose import jwt
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, or_
from app.database import AsyncSessionLocal, get_db
from app.models.manual_build import ManualBuild
from app.models.getting_started_job import GettingStartedJob
from app.models.ai_setup_purchase import AISetupPurchase
from app.models.component_manual import ComponentManual
from app.models.app_settings import AppSettings
from app.models.gem_radar_intelligence import ComponentRatingEvent, PreferredComponent
from app.models.build import Build, BuildType, BuildStatus
from app.models.product import Product, ProductType, ProductStatus
from app.models.order import Order, OrderStatus
from app.models.playbook import Playbook
from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
from app.models.price_alert import PriceAlert
from app.models.admin_user import AdminUser
from app.models.customer import Customer
from app.models.os_component import OSComponent
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.models.portal_access_grant import PortalAccessGrant
from app.schemas.manual_build import (
    ManualBuildCreate, ManualBuildPatch, ManualBuildOut, ManualBuildSummary,
    EvaluationResult, EvaluationSuggestion, GenerateListingResult,
    PostToEbayRequest, PostToEbayResult, SetHeroPhotoRequest, RemovePhotoRequest,
    ListOnStorefrontRequest, ListOnStorefrontResult, ReorderPhotosRequest,
    UpdateAspectsRequest, UpdateEbayListingConfigRequest, FulfillmentPolicyOut,
    CourierQuoteOut, InsuranceQuoteOut, SyncEbayOrderResult, BuyerAddressOut, BookShipmentRequest,
    BookShipmentResult, ShipmentBookingReconciliationRequest, UpdateEvidenceDataRequest, UpdateListingTitleRequest,
)
from app.services import ai_service
from app.services.getting_started_service import (
    invalidate_ready_to_ship_reviewed_package,
    generate_getting_ready_manifest,
    GettingReadyGenerationError,
    GettingReadyPromptSizeError,
    missing_component_manual_models,
    validate_component_driver_outcomes,
)
from app.services.getting_ready_package import (
    assemble_getting_ready_package,
    package_path,
    render_dispatch_checklist,
    GettingReadyPackageError,
)
from app.services.getting_started_guide import guide_snapshot
from app.services.getting_started_jobs import (
    CHECKLIST_STATUSES,
    COURIER_BOOKING_BLOCKING_ACTIONS,
    DISPATCH_BLOCKING_ACTIONS,
    INSURANCE_REQUIRED_PHOTO_CATEGORIES,
    OPTIONAL_CHECKLIST_ACTIONS,
    OPERATOR_CHECKLIST_ACTIONS,
    checklist_dispatch_ready,
    checklist_with_defaults,
    incomplete_checklist_actions,
    lock_manual_build_then_getting_started_job,
    validate_ai_setup_checklist_update,
)
from app.services.software_catalogue import (
    validate_package_ids,
    estimate_saved_minutes,
    create_software_install_script,
    SOFTWARE_BY_ID,
)
from app.services.product_software import software_profile_for_curated_cell_from_db
from app.services.ebay_listing_poster import EbayListingPoster, post_flip_to_ebay, prepare_ebay_listing_description
from app.services.ebay_specifics_generator import (
    generate_item_specifics,
    repair_legacy_aspect_cardinality,
    validate_aspects_for_ebay,
)
from app.services.ebay_fulfillment_policies import (
    list_fulfillment_policies,
    EbayFulfillmentPoliciesError,
)
from app.services.parcel2go_courier import get_tracked_quotes, Parcel2GoError
from app.services.figural_insurance import get_insurance_quote, create_insurance_policy, FiguralError
from app.services.ebay_order_sync import find_order_for_listing, EbayOrderSyncError, BuyerAddress
from app.services.parcel2go_booking import (
    create_order as create_parcel2go_order,
    pay_order_with_prepay,
    _safe_provider_tracking_url,
    Parcel2GoBookingError,
)
from app.services.ebay_shipping_fulfillment import mark_order_shipped, EbayShippingFulfillmentError
from app.services.ebay_listing_withdraw import withdraw_listing_by_sku, EbayListingWithdrawError
from app.services.cross_channel_guard import withdraw_storefront_for_sold_build
from app.services.meshy_generation import generate_multi_image_asset
from app.services.product_faqs import FAQ_BANK, FAQ_BY_ID, selected_faqs, render_ebay_faq_html
from app.services import pricing_engine
from app.services.email_service import (
    send_dispatched_guest_portal_email,
    send_shipment_update_email,
)
from app.services.portal_access import (
    find_printable_portal_claim,
    issue_direct_order_portal_claim,
    record_portal_claim_email_result,
)
import structlog

log = structlog.get_logger(__name__)
from app.config import get_settings
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/manual-builds", tags=["manual-builds"], dependencies=[Depends(get_current_admin)])


def _getting_ready_generation_snapshot(build: ManualBuild) -> str:
    """Fingerprint the persisted facts used to draft a Getting Ready manifest."""
    evidence = build.evidence_data or {}
    delivered_at = build.delivered_at
    return json.dumps(
        {
            "build_name": build.name,
            "build_status": getattr(build.status, "value", build.status),
            "order_id": build.order_id,
            "customer_id": build.customer_id,
            "components": build.components or [],
            "benchmark_results": evidence.get("benchmark_results") or evidence.get("performance_card"),
            "playbook_assignment": evidence.get("playbook_assignment"),
            "delivered_at": delivered_at.isoformat() if delivered_at else None,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


class ComponentRatingInput(BaseModel):
    component_slot: str
    component_key: str
    overall_rating: int = Field(ge=1, le=5)


class ApprovedResearchSource(BaseModel):
    """A human-reviewed primary source allowed into the content-generation prompt."""

    model_config = {"extra": "forbid"}

    component_name: str = Field(min_length=2, max_length=240)
    topic: Literal["driver_firmware", "manual", "rgb", "software", "compatibility"]
    source_url: AnyHttpUrl
    publisher: str = Field(min_length=2, max_length=160)
    title: str = Field(min_length=2, max_length=300)
    accessed_at: date
    claim: str = Field(min_length=8, max_length=1200)
    operator_approved: Literal[True]

    @field_validator("source_url")
    @classmethod
    def require_https_source(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("Research sources must use HTTPS")
        return value


class GettingReadyGenerationRequest(BaseModel):
    playbook_id: int | None = None
    curated_build_id: str | None = None
    playbook_segment: str | None = None
    customer_software_selections: list[str] | None = None
    approved_research_bundle: list[ApprovedResearchSource] = Field(default_factory=list, max_length=40)
    approved_component_manuals: list[dict] = Field(default_factory=list, max_length=40)
    getting_started_guide_text: str | None = None
    upgrade_policy: dict = Field(default_factory=dict)


class ComponentResearchDiscoveryRequest(BaseModel):
    model_config = {"extra": "forbid"}

    component_name: str = Field(min_length=2, max_length=240)
    topic: Literal["driver_firmware", "manual", "rgb", "software", "compatibility"]


class GettingReadyPackageApproval(BaseModel):
    confirm_manifest_reviewed: bool = False
    confirm_customer_details_checked: bool = False
    confirm_windows_license_handling: bool = False
    confirm_playbook_defaults_for_indirect_customer: bool = False
    reviewer_notes: str | None = Field(default=None, max_length=2000)


class WindowsLicenseHelperRequest(BaseModel):
    confirm_private_key_release: bool = False


class WindowsDeploymentEvidence(BaseModel):
    schema_version: Literal["1.0"]
    build_id: int = Field(ge=1)
    build_name: str = Field(min_length=1, max_length=200)
    verified_at_utc: str = Field(min_length=1, max_length=64)
    edition: Literal["Windows 11 Pro"]
    locale: Literal["en-GB"]
    target_drive_model: str = Field(min_length=1, max_length=200)
    target_drive_serial: str = Field(min_length=1, max_length=200)
    target_drive_size_bytes: int = Field(gt=0)
    verification_method: Literal["FlipFlop read-only post-install verification"]
    installation_method: str = Field(min_length=1, max_length=300)
    target_drive_confirmed: Literal[True]


class WindowsTargetSelection(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    serial: str = Field(min_length=1, max_length=200)
    inspected_at_utc: str = Field(min_length=1, max_length=64)
    confirm_new_build_drive: Literal[True]


def _insurance_provider_response_summary(evidence_data: dict | None) -> dict | None:
    """Expose only safe insurer reconciliation values to the admin queue."""
    attempt = (evidence_data or {}).get("insurance_policy_creation")
    provider = attempt.get("provider_response") if isinstance(attempt, dict) else None
    if not isinstance(provider, dict):
        return None

    def safe_amount(key: str):
        value = provider.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return value if _gbp_amount_to_pence(value) is not None else None

    def safe_reference(key: str):
        value = provider.get(key)
        if not isinstance(value, str) or len(value) > 200 or any(ord(char) < 32 or ord(char) == 127 for char in value):
            return None
        return value or None

    mismatches = provider.get("mismatches")
    return {
        "policy_id": safe_reference("policy_id"),
        "invoice_id": safe_reference("invoice_id"),
        "insured_value_gbp": safe_amount("insured_value_gbp"),
        "price_gbp": safe_amount("price_gbp"),
        "currency": safe_reference("currency"),
        "mode": safe_reference("mode"),
        "received_at": safe_reference("received_at"),
        "mismatches": [item[:200] for item in mismatches[:8] if isinstance(item, str)]
        if isinstance(mismatches, list) else [],
    }


def _manual_build_has_physical_handover(build: ManualBuild) -> bool:
    """Treat recorded handover, carrier delivery, and later states as irreversible."""
    evidence_data = getattr(build, "evidence_data", None)
    evidence = evidence_data if isinstance(evidence_data, dict) else {}
    handover = evidence.get("physical_handover_confirmation")
    return bool(
        build.dispatch_status in {"dispatched", "delivered"}
        or build.delivered_at is not None
        or (isinstance(handover, dict) and handover.get("confirmed") is True)
    )


async def _assigned_windows_pro_key(db: AsyncSession, build_id: int, job: GettingStartedJob | None) -> str | None:
    linked_order_id = job.order_id if job else None
    if linked_order_id is None:
        linked_order_id = (await db.execute(
            select(Build.order_id)
            .where(Build.manual_build_id == build_id, Build.order_id.is_not(None))
            .order_by(Build.id.desc())
            .limit(1)
        )).scalar_one_or_none()
    if linked_order_id is None:
        return None
    component = (await db.execute(
        select(OSComponent).where(OSComponent.assigned_to_order_id == linked_order_id)
    )).scalar_one_or_none()
    if not component or str(component.os_type or "").casefold() not in {
        "windows_pro", "windows 11 pro", "windows_11_pro"
    }:
        return None
    key = re.sub(r"[-\s]", "", str(component.license_key or "")).upper()
    if not re.fullmatch(r"[A-Z0-9]{25}", key):
        raise HTTPException(409, "The assigned Windows Pro licence key is invalid; correct the order's OS component before using Getting Ready")
    return key


class GettingReadyChecklistUpdate(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=1000)
    evidence_ref: str | None = Field(default=None, max_length=500)
    windows_deployment_evidence: WindowsDeploymentEvidence | None = None
    windows_target: WindowsTargetSelection | None = None
    confirm_paid_ai_scope: bool = False
    driver_firmware_outcomes: list[dict] | None = Field(default=None, max_length=100)


class CreateInsurancePolicyRequest(BaseModel):
    confirm_terms: bool = False
    confirm_live_purchase: bool = False
    confirm_customer_data_share: bool = False
    confirm_signed_for_delivery: bool = False
    confirm_double_packaging: bool = False
    confirm_discreet_packaging: bool = False
    confirm_rigid_outer_container: bool = False
    confirm_contents_not_deducible: bool = False
    confirm_direct_signature: bool = False
    confirm_official_carrier_handover: bool = False
    quoted_price_gbp: float = Field(gt=0)
    reliability_rating: int | None = Field(default=None, ge=1, le=5)
    installation_rating: int | None = Field(default=None, ge=1, le=5)
    aesthetics_rating: int | None = Field(default=None, ge=1, le=5)
    value_rating: int | None = Field(default=None, ge=1, le=5)
    customer_appeal_rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class ReconcileInsurancePolicyRequest(BaseModel):
    resolution: Literal["policy_exists", "no_policy"]
    provider_checked: bool
    note: str = Field(min_length=12, max_length=1000)
    policy_id: str | None = Field(default=None, max_length=200)
    invoice_id: str | None = Field(default=None, max_length=200)
    provider_tracking_number: str | None = Field(default=None, max_length=200)
    insured_value_gbp: float | None = Field(default=None, gt=0)
    cost_gbp: float | None = Field(default=None, ge=0)

    @field_validator("note")
    @classmethod
    def validate_reconciliation_note(cls, value: str) -> str:
        if len(value.strip()) < 12:
            raise ValueError("Record a meaningful insurer-account check note (at least 12 characters)")
        return value.strip()


class ComponentRatingsInput(BaseModel):
    ratings: list[ComponentRatingInput]


class ComponentPurchaseInput(BaseModel):
    price_paid: float | None = Field(default=None, ge=0)
    source: str | None = None


class FaqSelectionInput(BaseModel):
    selected_ids: list[str] = Field(max_length=10)
    answer_overrides: dict[str, str] = Field(default_factory=dict)


class QueueBuild3DAssetsInput(BaseModel):
    assets: dict[str, list[str]]


class CollectionDateInput(BaseModel):
    collection_date: datetime


class DispatchBuildInput(BaseModel):
    confirm_physical_handover: bool = False


class ReviewDispatchEvidenceRequest(BaseModel):
    approved: bool
    note: str = Field(min_length=12, max_length=1000)

    @field_validator("note")
    @classmethod
    def note_must_be_meaningful(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 12:
            raise ValueError("Record at least 12 characters describing the evidence review")
        return value


def _build_customer_hub_dir(build_id: int) -> Path:
    """Return the canonical local output directory for a build's Customer Hub."""
    return _BUILD_ASSETS_ROOT / str(build_id) / "Customer Hub"


def _write_customer_hub_entrypoint(build_id: int, order_id: int, token: str, frontend_url: str) -> Path:
    """Create a local entry point for the deployed customer hub.

    The customer-facing application remains the deployed ``/my-builds`` route;
    this local file gives operators a build-owned website artifact without
    duplicating the storefront source into every build directory.
    """
    customer_hub_dir = _build_customer_hub_dir(build_id)
    customer_hub_dir.mkdir(parents=True, exist_ok=True)
    portal_url = (
        f"{frontend_url.rstrip('/')}/my-builds/{order_id}"
        f"?preview={quote(token)}"
    )
    escaped_url = html.escape(portal_url, quote=True)
    entrypoint = customer_hub_dir / "index.html"
    entrypoint.write_text(
        "<!doctype html>\n"
        "<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>FlipFlop Customer Hub</title></head><body>"
        "<p>Opening your FlipFlop Customer Hub&hellip;</p>"
        f"<p><a href=\"{escaped_url}\">Continue to Customer Hub</a></p>"
        f"<script>window.location.replace({json.dumps(portal_url)});</script>"
        "</body></html>\n",
        encoding="utf-8",
    )
    return entrypoint


@router.post("/{build_id}/portal-preview")
async def create_build_portal_preview(
    build_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Create a read-only owner-portal preview for a completed physical build."""
    build = (await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id)
    )).scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    if build.status not in {"built", "listed", "sold"}:
        raise HTTPException(status_code=409, detail="The customer portal is created when the build reaches Built")
    if not build.model_3d_url:
        raise HTTPException(status_code=409, detail="Complete the build's 3D model to create its customer portal")

    product = None
    if build.storefront_product_id:
        product = (await db.execute(
            select(Product).where(Product.id == build.storefront_product_id)
        )).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    settings = get_settings()
    token = jwt.encode(
        {
            "typ": "portal_preview",
            "build_id": build.id,
            "order_id": product.sold_order_id if product else None,
            "scope": "read",
            "iat": now,
            "exp": now + timedelta(minutes=15),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    order_id = product.sold_order_id if product and product.sold_order_id else build.id
    customer_hub_entrypoint = _write_customer_hub_entrypoint(
        build.id,
        order_id,
        token,
        settings.frontend_url,
    )
    return {
        # The storefront route historically calls this value order_id. Before
        # sale, the build id provides a stable route segment; the signed token
        # remains the authority for selecting portal data.
        "order_id": order_id,
        "build_id": build.id,
        "token": token,
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
        "customer_hub_path": str(customer_hub_entrypoint),
    }


async def _run_build_3d_generation(
    build_id: int,
    requested: dict[str, list[str]],
    source_refs: dict[str, list[str]] | None = None,
) -> None:
    """Run Meshy jobs off-request, mirror expiring results, then persist once."""
    # Make it visible that the background task actually started. Previously
    # the row stayed "queued" throughout Meshy's (potentially ten-minute)
    # generation, which was indistinguishable from a dead worker.
    async with AsyncSessionLocal() as session:
        build = (await session.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
        if not build:
            return
        assets = dict(build.model_3d_assets or {})
        started_at = datetime.utcnow().isoformat()
        for asset_type in requested:
            current = dict(assets.get(asset_type) or {})
            current.update(status="processing", progress=0, meshy_status="SUBMITTING", started_at=started_at)
            assets[asset_type] = current
        build.model_3d_assets = assets
        await session.commit()
    log.info("manual_build.3d_generation_started", build_id=build_id, asset_types=list(requested))

    async def persist_progress(asset_type: str, progress: int, status: str, task_id: str | None = None) -> None:
        async with AsyncSessionLocal() as session:
            build = (await session.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
            if not build:
                return
            assets = dict(build.model_3d_assets or {})
            asset = dict(assets.get(asset_type) or {})
            asset.update(progress=progress, meshy_status=status, status="processing")
            if task_id:
                asset["task_id"] = task_id
            assets[asset_type] = asset
            build.model_3d_assets = assets
            await session.commit()

    results = await asyncio.gather(
        *(
            generate_multi_image_asset(
                urls,
                progress_callback=lambda progress, status, task_id=None, asset_type=asset_type: persist_progress(
                    asset_type, progress, status, task_id
                ),
            )
            for asset_type, urls in requested.items()
        ),
        return_exceptions=True,
    )
    completed: dict[str, dict] = {}
    for (asset_type, source_urls), result in zip(requested.items(), results):
        # Never persist uploaded data URIs. They are retained in memory only
        # until Meshy has accepted the background job.
        persisted_sources = (source_refs or {}).get(asset_type, source_urls)
        entry = {"provider": "meshy", "source_image_urls": persisted_sources, "textured": True, "pbr": True}
        if isinstance(result, Exception) or result is None:
            entry.update(status="failed", error=str(result) if result else "Meshy did not accept the task")
        elif result.status != "SUCCEEDED" or not result.glb_url:
            entry.update(status="failed", task_id=result.task_id, error=f"Meshy task ended as {result.status}")
        else:
            try:
                filename = f"build_{build_id}_{asset_type}_{uuid.uuid4().hex}.glb"
                local_path, public_url = _build_3d_asset_path(build_id, filename)
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    response = await client.get(result.glb_url)
                    response.raise_for_status()
                local_path.write_bytes(response.content)
                if not local_path.is_file() or local_path.stat().st_size == 0:
                    raise RuntimeError(f"Downloaded GLB was not persisted at {local_path}")
                _persist_build_model_download(build_id, filename, local_path)
                entry.update(
                    status="succeeded",
                    progress=result.progress,
                    task_id=result.task_id,
                    glb_url=public_url,
                    preview_url=result.thumbnail_url,
                    completed_at=datetime.utcnow().isoformat(),
                )
            except Exception as exc:
                entry.update(status="failed", task_id=result.task_id, error=f"Could not store GLB: {exc}")
        completed[asset_type] = entry

    async with AsyncSessionLocal() as session:
        build = (await session.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
        if not build:
            return
        assets = dict(build.model_3d_assets or {})
        assets.update(completed)
        build.model_3d_assets = assets
        if completed.get("complete_build", {}).get("status") == "succeeded":
            build.model_3d_url = completed["complete_build"]["glb_url"]
        await session.commit()
    log.info("manual_build.3d_generation_finished", build_id=build_id, statuses={key: value.get("status") for key, value in completed.items()})


@router.post("/{build_id}/model-3d/generate", status_code=202)
async def queue_build_3d_generation(
    build_id: int,
    body: QueueBuild3DAssetsInput,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    unknown = set(body.assets) - {"complete_build"}
    if unknown:
        raise HTTPException(status_code=422, detail="Only complete-build photos can be selected manually")
    complete_build_urls = body.assets.get("complete_build", [])
    if not complete_build_urls:
        raise HTTPException(status_code=422, detail="Select photos of the real completed PC")
    valid_urls = {p.get("url") for p in (build.photos or []) if p.get("kind") == "photo"}
    if not 1 <= len(complete_build_urls) <= 4:
        raise HTTPException(status_code=422, detail="The complete build needs 1 to 4 photos")
    if len(set(complete_build_urls)) != len(complete_build_urls) or any(url not in valid_urls for url in complete_build_urls):
        raise HTTPException(status_code=422, detail="The complete build contains an invalid or duplicate photo")

    requested = {"complete_build": complete_build_urls}

    assets = dict(build.model_3d_assets or {})
    queued_at = datetime.utcnow().isoformat()
    for asset_type, urls in requested.items():
        assets[asset_type] = {
            "provider": "meshy",
            "status": "queued",
            "source_image_urls": urls,
            "queued_at": queued_at,
        }
    build.model_3d_assets = assets
    await db.commit()
    background_tasks.add_task(_run_build_3d_generation, build_id, requested)
    return {"queued": list(requested), "assets": assets}


@router.post("/{build_id}/model-3d/generate-upload", status_code=202)
async def queue_build_3d_generation_with_uploads(
    build_id: int,
    background_tasks: BackgroundTasks,
    selected_urls: str = Form("[]"),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
):
    """Queue a mixed saved-photo/uploaded-image Meshy generation.

    Uploaded source images are retained in the build's Media directory so the
    complete source set can be backed up and reused for later model work.
    """
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    try:
        urls = json.loads(selected_urls)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="selected_urls must be a JSON array")
    if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
        raise HTTPException(status_code=422, detail="selected_urls must be a JSON array of photo URLs")

    valid_urls = {p.get("url") for p in (build.photos or []) if p.get("kind") == "photo"}
    if len(set(urls)) != len(urls) or any(url not in valid_urls for url in urls):
        raise HTTPException(status_code=422, detail="The selection contains an invalid or duplicate saved photo")
    if not 1 <= len(urls) + len(files) <= 4:
        raise HTTPException(status_code=422, detail="Meshy requires 1 to 4 source pictures in total")

    generation_inputs = list(urls)
    source_labels = list(urls)
    for index, file in enumerate(files, start=1):
        content_type = file.content_type or ""
        if content_type not in {"image/jpeg", "image/png"}:
            raise HTTPException(status_code=415, detail="Temporary 3D source pictures must be JPEG or PNG")
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail=f"{file.filename or 'Uploaded picture'} is empty")
        if len(image_bytes) > _MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Each source picture must be 15 MB or smaller")
        ext = {"image/jpeg": "jpg", "image/png": "png"}[content_type]
        filename = f"meshy-source-{uuid.uuid4().hex}.{ext}"
        local_path, public_url = _build_media_asset_path(build_id, filename)
        local_path.write_bytes(image_bytes)
        generation_inputs.append(public_url)
        source_labels.append(public_url)

    requested = {"complete_build": generation_inputs}
    assets = dict(build.model_3d_assets or {})
    assets["complete_build"] = {
        "provider": "meshy",
        "status": "queued",
        "source_image_urls": source_labels,
        "queued_at": datetime.utcnow().isoformat(),
        "textured": True,
        "pbr": True,
    }
    build.model_3d_assets = assets
    await db.commit()
    background_tasks.add_task(
        _run_build_3d_generation,
        build_id,
        requested,
        {"complete_build": source_labels},
    )
    return {"queued": ["complete_build"], "assets": assets}


def _description_with_selected_faqs(description: str, build: ManualBuild) -> str:
    """Replace any previously-rendered FAQ block with the current selection."""
    without_old = re.sub(
        r'<section data-flipflop-faq="true".*?</section>',
        "",
        description,
        flags=re.DOTALL,
    )
    items = selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides)
    return without_old + (render_ebay_faq_html(items) if items else "")

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB
_MAX_DISPATCH_VIDEO_BYTES = 500 * 1024 * 1024
_PRIVATE_DISPATCH_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "private_dispatch"


def _missing_verified_dispatch_evidence(
    job: GettingStartedJob | None,
    build_id: int,
    categories: tuple[str, ...],
) -> list[str]:
    """Require approved evidence files to still match their build-bound checksum and size."""
    artifacts = deepcopy(job.artifact_index or []) if job else []
    root = _PRIVATE_DISPATCH_ROOT.resolve()
    build_dir = (root / str(build_id)).resolve()
    allowed_media = {
        "working_pc": ("image/", "video/"),
        "package_contents": ("image/",),
        "sealed_package": ("image/",),
    }
    missing: list[str] = []
    build_dir_is_scoped = root in build_dir.parents
    for category in categories:
        if not build_dir_is_scoped:
            missing.append(category)
            continue
        valid_artifact = False
        for artifact in artifacts:
            if not isinstance(artifact, dict) or artifact.get("category") != category:
                continue
            if artifact.get("review_status") != "approved":
                continue
            content_type = str(artifact.get("content_type") or "")
            if not content_type.startswith(allowed_media.get(category, ())):
                continue
            try:
                path = (root / str(artifact.get("storage_key") or "")).resolve()
                if root not in path.parents or build_dir not in path.parents or not path.is_file():
                    continue
                expected_size = int(artifact.get("size_bytes"))
                if path.stat().st_size != expected_size:
                    continue
                digest = hashlib.sha256()
                with path.open("rb") as evidence_file:
                    while chunk := evidence_file.read(1024 * 1024):
                        digest.update(chunk)
                if digest.hexdigest() != artifact.get("sha256"):
                    continue
            except (OSError, TypeError, ValueError):
                continue
            valid_artifact = True
            break
        if not valid_artifact:
            missing.append(category)
    return missing


def _remove_uncommitted_getting_ready_packages(package: dict, *, build_id: int) -> None:
    """Remove package files only when the database transaction is known not to have committed."""
    for key in ("storage_key", "workshop_storage_key"):
        storage_key = package.get(key)
        if not storage_key:
            continue
        try:
            package_path(str(storage_key)).unlink(missing_ok=True)
        except (GettingReadyPackageError, OSError) as error:
            log.error(
                "getting_ready_package_cleanup_failed",
                build_id=build_id,
                storage_key=str(storage_key),
                error=str(error),
            )


async def _commit_getting_ready_package_approval(db: AsyncSession, package: dict, *, build_id: int) -> None:
    """Persist package metadata, cleaning files only before COMMIT is attempted."""
    try:
        await db.flush()
    except BaseException:
        try:
            await db.rollback()
        except Exception:
            log.exception("getting_ready_package_flush_rollback_failed", build_id=build_id)
        _remove_uncommitted_getting_ready_packages(package, build_id=build_id)
        raise
    try:
        await db.commit()
    except BaseException:
        try:
            await db.rollback()
        except Exception:
            log.exception("getting_ready_package_commit_rollback_failed", build_id=build_id)
        log.exception(
            "getting_ready_package_commit_outcome_uncertain",
            build_id=build_id,
            storage_key=package.get("storage_key"),
            workshop_storage_key=package.get("workshop_storage_key"),
        )
        raise


def _remove_uncommitted_getting_ready_packages(package: dict, *, build_id: int) -> None:
    """Remove private ZIPs only when their database transaction did not commit."""
    for key in ("storage_key", "workshop_storage_key"):
        storage_key = package.get(key)
        if not storage_key:
            continue
        try:
            package_path(str(storage_key)).unlink(missing_ok=True)
        except (GettingReadyPackageError, OSError) as error:
            log.error(
                "getting_ready_package_cleanup_failed",
                build_id=build_id,
                storage_key=str(storage_key),
                error=str(error),
            )


def _gbp_amount_to_pence(value: object) -> int | None:
    """Convert a finite non-negative GBP amount to its displayed penny value."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            return None
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _gbp_amounts_match_to_penny(left: object, right: object) -> bool:
    """Compare the two-decimal GBP amounts the operator actually reviewed."""
    left_pence = _gbp_amount_to_pence(left)
    right_pence = _gbp_amount_to_pence(right)
    return left_pence is not None and right_pence is not None and left_pence == right_pence


async def _portal_grant_required_for_build(
    db: AsyncSession, build: ManualBuild,
) -> tuple[bool, PortalAccessGrant | None]:
    """Resolve whether dispatch needs a current guest/printed portal claim."""
    linked_order = (await db.execute(
        select(Order)
        .join(Build, Build.manual_build_id == build.id)
        .outerjoin(Product, Product.build_id == Build.id)
        .where(or_(Build.order_id == Order.id, Product.sold_order_id == Order.id))
        .limit(1)
        .with_for_update(of=Order)
    )).scalar_one_or_none()
    direct_storefront_sale = bool(
        linked_order and linked_order.customer_id and not build.ebay_order_id
    )
    if build.storefront_product_id:
        sold_product = await db.get(Product, build.storefront_product_id)
        if sold_product and sold_product.sold_via_channel is not None:
            channel = getattr(sold_product.sold_via_channel, "value", sold_product.sold_via_channel)
            direct_storefront_sale = channel == "storefront"
    if direct_storefront_sale:
        if not linked_order or not linked_order.customer_id:
            raise HTTPException(409, "A linked customer order is required to verify portal access before delivery")
        customer = await db.get(Customer, linked_order.customer_id)
        if not customer:
            raise HTTPException(409, "The linked customer record is unavailable; verify portal ownership before delivery")
        if customer.password_hash or customer.google_id or customer.github_id:
            return False, None
        return True, await find_printable_portal_claim(
            db, order_id=linked_order.id, channel="direct_guest"
        )
    return True, await find_printable_portal_claim(db, manual_build_id=build.id)


_UPLOADS_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "manual_builds"
_PUBLIC_MEDIA_ROOT = Path(__file__).resolve().parents[3].parent / "FlipFlop.shop" / "public" / "media"
_MODELS_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "models"
_BUILD_ASSETS_ROOT = Path(__file__).resolve().parents[3] / "builds"
_BUILD_3D_SUBDIR = "3D Build"
_BUILD_ASSET_SUBDIRS = {"Media", "Performance", "Registration", "Specifications"}
# Served directly by this process (see app.mount("/api/uploads", ...) in
# main.py) — files never leave this container, so no cross-host sync needed.
_PUBLIC_API_BASE = "https://www.theflipflop.shop/api"
_SELLING_PRINCIPLES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "selling_principles.md"
_EBAY_LISTING_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "ebay_listing_system_prompt.md"


def _build_asset_path(build_id: int, filename: str, subdir: str) -> tuple[Path, str]:
    """Return the on-disk path and public URL for a build-owned asset."""
    if subdir not in _BUILD_ASSET_SUBDIRS and subdir != _BUILD_3D_SUBDIR:
        raise ValueError(f"Unsupported build asset directory: {subdir}")
    numeric_dir = _BUILD_ASSETS_ROOT / str(build_id)
    padded_dir = _BUILD_ASSETS_ROOT / f"{build_id:03d}"
    build_dir = numeric_dir if numeric_dir.exists() else padded_dir if padded_dir.exists() else numeric_dir
    asset_dir = build_dir / subdir
    asset_dir.mkdir(parents=True, exist_ok=True)
    relative_dir = build_dir.relative_to(_BUILD_ASSETS_ROOT).as_posix()
    public_url = f"{_PUBLIC_API_BASE}/builds/{quote(relative_dir)}/{quote(subdir)}/{quote(filename)}"
    return asset_dir / filename, public_url


def _build_3d_asset_path(build_id: int, filename: str) -> tuple[Path, str]:
    """Return the on-disk path and public URL for a build-owned 3D asset."""
    return _build_asset_path(build_id, filename, _BUILD_3D_SUBDIR)


def _build_media_asset_path(build_id: int, filename: str) -> tuple[Path, str]:
    """Return the on-disk path and public URL for a build image."""
    return _build_asset_path(build_id, filename, "Media")


def _build_named_asset_path(build_id: int, filename: str, subdir: str) -> tuple[Path, str]:
    return _build_asset_path(build_id, filename, subdir)


def _existing_build_model_path(build_id: int, filename: str) -> Path | None:
    """Find a model in the current build-owned or legacy model locations."""
    numeric_dir = _BUILD_ASSETS_ROOT / str(build_id)
    padded_dir = _BUILD_ASSETS_ROOT / f"{build_id:03d}"
    roots = [numeric_dir, padded_dir]
    candidates = [root / folder / filename for root in roots for folder in ("3D Build", "3D Model")]
    candidates.extend([
        _UPLOADS_ROOT / str(build_id) / filename,
        _MODELS_ROOT / filename,
    ])
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _build_model_download_dir(build_id: int) -> Path:
    """Return the canonical local directory used for downloaded build models.

    Keep this path unpadded even when older builds still live in a padded
    directory such as ``builds/002``.  The download location is part of the
    operator-facing contract: ``builds/<build_id>/3D Model``.
    """
    return _BUILD_ASSETS_ROOT / str(build_id) / "3D Model"


def _persist_build_model_download(build_id: int, filename: str, source: Path) -> Path:
    """Keep a canonical operator copy of a saved GLB in ``3D Model``."""
    download_dir = _build_model_download_dir(build_id)
    download_dir.mkdir(parents=True, exist_ok=True)
    download_path = download_dir / filename
    if source.resolve() != download_path.resolve():
        shutil.copy2(source, download_path)
    return download_path

# HERO_IMAGE_URL is the one listing-template placeholder the LLM is
# instructed NOT to fill in itself (see ebay_listing_system_prompt.md) — it
# varies per build, so only this backend can know the right value. Filled in
# deterministically below from build.hero_photo_url, which is set the moment
# a build's first photo is uploaded (see the photo-upload endpoint below).
# The flipflop logo URL used to be a similarly LLM-filled placeholder too,
# but that one never varies between builds, so it's now hardcoded straight
# into the template itself — nothing left to substitute for it here.

# eBay Item Specifics for category 179 (PC Desktops & All-in-Ones), fetched
# from the Taxonomy API's get_item_aspects_for_category. "Brand" and "Type"
# are eBay-required; the rest are recommended and materially improve
# listing visibility/trust when filled in.
_EBAY_CATEGORY_179_ASPECTS = [
    "Brand", "Type", "Model", "Most Suitable For", "MPN", "Form Factor",
    "Storage Type", "Hard Drive Capacity", "Processor", "Processor Speed",
    "RAM Size", "Operating System", "Connectivity", "Features", "GPU",
    "Series", "Graphics Processing Type", "Manufacturer Warranty",
    "Country of Origin", "Colour", "Maximum RAM Capacity",
    "Motherboard Model", "Release Year", "SSD Capacity",
]

_PC_BUILD_PLATFORM_CATEGORY_ID = "179"
_PC_BUILD_PLATFORM_CATEGORY_NAME = "PC Desktops & All-in-Ones"


def _direct_storefront_item_specifics(build: ManualBuild) -> dict[str, str]:
    """Flatten saved eBay aspects for the direct storefront only."""
    return {
        name: ", ".join(str(value) for value in values if value is not None)
        for name, values in (build.generated_aspects or {}).items()
        if isinstance(values, list) and any(value is not None for value in values)
    }


def _load_selling_principles() -> str:
    """Read fresh on every call so edits to the file take effect immediately."""
    try:
        return _SELLING_PRINCIPLES_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_ebay_listing_system_prompt() -> str:
    """Read fresh on every call so edits to the file take effect immediately."""
    return _EBAY_LISTING_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _load_build_performance_evidence(build_name: str) -> dict | None:
    """Load reviewed, build-specific evidence when it is not yet in the DB."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", build_name.lower()).strip("-")
    path = _EBAY_LISTING_SYSTEM_PROMPT_PATH.parent / "build_evidence" / f"{slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_section(text: str, start_marker: str, end_markers: list[str]) -> str:
    """Extract text between a section header and whichever of the given
    next-section headers appears first — tolerant of the model reformatting
    the exact separator characters around each header."""
    m = re.search(re.escape(start_marker), text, re.IGNORECASE)
    if not m:
        return ""
    start = m.end()
    end = len(text)
    for marker in end_markers:
        m2 = re.search(re.escape(marker), text[start:], re.IGNORECASE)
        if m2:
            end = min(end, start + m2.start())
    return text[start:end].strip()


def _extract_recommended_title(text: str) -> str | None:
    # Find section B
    b_idx = text.upper().find("B.")
    if b_idx < 0:
        return None
    # Find where section B ends (at C. or end of text)
    c_idx = text.upper().find("\nC.", b_idx)
    if c_idx < 0:
        c_idx = len(text)
    section = text[b_idx:c_idx]

    # Extract title-like lines (skip the header "B. Three eBay titles")
    for line in section.splitlines()[1:]:  # Skip first line (the header)
        stripped = line.strip()
        if stripped and len(stripped) < 85 and not stripped.startswith(("-", "*", "#")):
            return stripped
    return None


def _extract_html_section(text: str) -> str | None:
    # Find section D
    d_idx = text.upper().find("\nD.")
    if d_idx < 0:
        # Try without newline (if D. is at start)
        d_idx = text.upper().find("D.")
    if d_idx < 0:
        return None

    # Find where section D ends (at E. or end of text)
    e_idx = text.upper().find("\nE.", d_idx)
    if e_idx < 0:
        e_idx = len(text)
    section = text[d_idx:e_idx].strip()

    # Skip the header line "D. Complete branded HTML description"
    lines = section.splitlines()
    section = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # Look for the start of HTML
    html_match = re.search(r"<(div|html|!doctype)", section, re.IGNORECASE)
    if html_match:
        return section[html_match.start():].strip()

    return None


@router.post("/", response_model=ManualBuildOut, status_code=201)
async def create_build(body: ManualBuildCreate, db: AsyncSession = Depends(get_db)):
    if bool(body.playbook_id) != bool(body.curated_build_id):
        raise HTTPException(422, "Choose both a Playbook and a curated budget cell, or neither")
    evidence_data: dict = {}
    if body.playbook_id and body.curated_build_id:
        playbook = await db.get(Playbook, body.playbook_id)
        if not playbook:
            raise HTTPException(404, "Playbook not found")
        try:
            profile = await software_profile_for_curated_cell_from_db(
                db, body.curated_build_id, playbook.name, playbook.software_profile
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        from app.services.curated_build_policy import definitions
        cell = next(item for item in definitions()["builds"] if item["id"] == body.curated_build_id)
        evidence_data["playbook_assignment"] = {
            "playbook_id": playbook.id,
            "curated_build_id": body.curated_build_id,
            "customer_type": cell["segment"],
            "budget_tier": cell["tier"],
            "cell_name": cell["name"],
            "software_profile": profile,
            "assigned_at": datetime.utcnow().isoformat(),
        }
    build = ManualBuild(
        name=body.name,
        components=[],
        total_cost=None,
        evidence_data=evidence_data,
        warranty_reserve_pct=body.warranty_reserve_pct,
    )
    db.add(build)
    await db.flush()
    await db.refresh(build)
    return build


@router.get("/", response_model=list[ManualBuildSummary])
async def list_builds(include_archived: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(ManualBuild).order_by(ManualBuild.updated_at.desc())
    if not include_archived:
        query = query.where(ManualBuild.is_archived.is_(False))
    result = await db.execute(query)
    builds = result.scalars().all()

    # The list page must reflect a currently purchasable channel, not the
    # historical workflow value in ManualBuild.status. Reconcile eBay when
    # needed, then check the direct storefront product in the same response.
    for build in builds:
        if build.ebay_listing_id:
            try:
                from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
                await reconcile_manual_build_listing(build, db)
            except Exception as exc:
                log.warning("manual_build.ebay_reconcile_on_list_failed", build_id=build.id, error=str(exc))
                build.ebay_listing_status = "unknown"
        else:
            build.ebay_listing_status = "draft" if (build.ebay_offer_id or build.ebay_draft_id) else "never_listed"

    storefront_product_ids = {build.storefront_product_id for build in builds if build.storefront_product_id}
    storefront_products: dict[int, Product] = {}
    if storefront_product_ids:
        product_result = await db.execute(
            select(Product).where(Product.id.in_(storefront_product_ids))
        )
        storefront_products = {product.id: product for product in product_result.scalars().all()}

    summaries = []
    for build in builds:
        ebay_live = build.ebay_listing_status == "active"
        storefront_live = bool(
            build.storefront_product_id
            and storefront_products.get(build.storefront_product_id)
            and storefront_products[build.storefront_product_id].status == ProductStatus.LISTED
        )
        live_status = "listed" if ebay_live or storefront_live else (
            "built" if build.status == "listed" else build.status
        )
        summaries.append(
            ManualBuildSummary(
                id=build.id,
                name=build.name,
                total_cost=build.total_cost,
                component_count=len(build.components or []),
                status=live_status,
                updated_at=build.updated_at,
            )
        )
    return summaries


@router.get("/deletion-audit")
async def get_manual_build_deletion_audit(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Show blocked hard-deletion attempts and normal archive activity."""
    rows = (await db.execute(text("""
        SELECT id, manual_build_id, build_name, action, attempted_at,
               database_user, application_name, client_address
        FROM manual_build_deletion_audit
        ORDER BY attempted_at DESC
        LIMIT :limit
    """), {"limit": limit})).mappings().all()
    return {"items": [dict(row) for row in rows]}


@router.get("/ebay-fulfillment-policies", response_model=list[FulfillmentPolicyOut])
async def get_ebay_fulfillment_policies(db: AsyncSession = Depends(get_db)):
    """Real shipping-destination options for the Shipping & Delivery section
    — fetched live from the seller's own eBay account, not a hardcoded list.
    Uses whichever environment (sandbox/production) is currently configured
    for listing, same as post_to_ebay. MUST stay registered before
    GET /{build_id} below — Starlette matches routes by position, and
    /{build_id} would otherwise swallow this path first and 422 on failing
    to parse "ebay-fulfillment-policies" as an int."""
    settings = get_settings()
    try:
        # The Settings OAuth flow stores the newly consented seller token in
        # AppSettings. Use that token here; falling back directly to the old
        # EBAY_PRODUCTION_REFRESH_TOKEN made reconnect appear successful while
        # this endpoint kept refreshing the obsolete environment token.
        from app.services.ebay_oauth import get_valid_access_token

        access_token = await get_valid_access_token(db)
        if not access_token:
            raise EbayFulfillmentPoliciesError(
                "No valid connected eBay seller token is available. Reconnect eBay in Settings.",
                401,
            )
        policies = await list_fulfillment_policies(
            settings.ebay_listing_environment,
            access_token=access_token,
        )
    except EbayFulfillmentPoliciesError as e:
        raise HTTPException(
            e.status_code or 502,
            f"Couldn't fetch fulfillment policies from eBay: {e}. "
            "Reconnect eBay in Settings if authorization has expired; if this is "
            "a 403, re-authorize with the sell.account scope.",
        )
    return [
        FulfillmentPolicyOut(
            policy_id=p.policy_id,
            name=p.name,
            marketplace_id=p.marketplace_id,
            ship_to_regions=p.ship_to_regions,
            handling_time_days=p.handling_time_days,
        )
        for p in policies
    ]


@router.get("/{build_id}/faqs")
async def get_build_faqs(build_id: int, db: AsyncSession = Depends(get_db)):
    build = (
        await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    ).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    effective = selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides)
    return {
        "bank": FAQ_BANK,
        "selected_ids": [item["id"] for item in effective],
        "uses_defaults": build.selected_faq_ids is None,
        "answer_overrides": build.selected_faq_answer_overrides or {},
        "maximum": 10,
    }


@router.put("/{build_id}/faqs")
async def update_build_faqs(
    build_id: int, body: FaqSelectionInput, db: AsyncSession = Depends(get_db)
):
    build = (
        await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    ).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if len(body.selected_ids) != len(set(body.selected_ids)):
        raise HTTPException(400, "FAQ selections must be unique")
    unknown = [item_id for item_id in body.selected_ids if item_id not in FAQ_BY_ID]
    if unknown:
        raise HTTPException(400, f"Unknown FAQ IDs: {', '.join(unknown)}")
    unknown_overrides = [item_id for item_id in body.answer_overrides if item_id not in FAQ_BY_ID]
    if unknown_overrides:
        raise HTTPException(400, f"Unknown FAQ override IDs: {', '.join(unknown_overrides)}")
    cleaned_overrides = {
        item_id: answer.strip()
        for item_id, answer in body.answer_overrides.items()
        if answer.strip() and answer.strip() != FAQ_BY_ID[item_id]["answer"]
    }
    build.selected_faq_ids = body.selected_ids
    build.selected_faq_answer_overrides = cleaned_overrides
    if build.generated_description:
        build.generated_description = prepare_ebay_listing_description(
            _description_with_selected_faqs(build.generated_description, build)
        )
    if build.storefront_product_id:
        product = (
            await db.execute(select(Product).where(Product.id == build.storefront_product_id))
        ).scalar_one_or_none()
        if product:
            product.selected_faqs = selected_faqs(build.id, body.selected_ids, cleaned_overrides)
    build.updated_at = datetime.utcnow()
    await db.flush()
    return {"selected_ids": body.selected_ids, "answer_overrides": cleaned_overrides, "selected_faqs": selected_faqs(build.id, body.selected_ids, cleaned_overrides)}


@router.get("/dispatch-zone")
async def dispatch_zone(db: AsyncSession = Depends(get_db)):
    """Show built/listed units for pre-sale preparation and sold units for dispatch."""
    rows = (await db.execute(select(ManualBuild).where(
        ManualBuild.status.in_(("built", "listed", "sold")),
        ManualBuild.is_archived == False,
    ).order_by(ManualBuild.updated_at.desc()))).scalars().all()  # noqa: E712
    jobs = (await db.execute(select(GettingStartedJob).where(GettingStartedJob.manual_build_id.in_([b.id for b in rows])))).scalars().all() if rows else []
    jobs_by_build = {job.manual_build_id: job for job in jobs}
    build_order_rows = (await db.execute(
        select(Build.manual_build_id, Build.order_id).where(
            Build.manual_build_id.in_([b.id for b in rows]), Build.order_id.is_not(None)
        )
    )).all() if rows else []
    order_by_build = {build_id: order_id for build_id, order_id in build_order_rows}
    storefront_product_ids = [b.storefront_product_id for b in rows if b.storefront_product_id]
    storefront_products = (await db.execute(
        select(Product.id, Product.sold_order_id, Product.sold_via_channel).where(
            Product.id.in_(storefront_product_ids)
        )
    )).all() if storefront_product_ids else []
    products_by_id = {product_id: (order_id, channel) for product_id, order_id, channel in storefront_products}
    linked_order_ids = {
        order_id
        for build in rows
        for order_id in (
            jobs_by_build.get(build.id).order_id if jobs_by_build.get(build.id) else None,
            order_by_build.get(build.id),
            products_by_id.get(build.storefront_product_id, (None, None))[0]
            if build.storefront_product_id else None,
        )
        if order_id is not None
    }
    order_contacts = (await db.execute(
        select(Order.id, Customer.email, Customer.name)
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.id.in_(linked_order_ids))
    )).all() if linked_order_ids else []
    contacts_by_order = {order_id: (email, name) for order_id, email, name in order_contacts}
    grants = (await db.execute(
        select(PortalAccessGrant)
        .where(or_(
            PortalAccessGrant.order_id.in_(linked_order_ids) if linked_order_ids else False,
            PortalAccessGrant.manual_build_id.in_([b.id for b in rows]) if rows else False,
        ))
        .order_by(PortalAccessGrant.created_at.desc(), PortalAccessGrant.id.desc())
    )).scalars().all() if linked_order_ids or rows else []
    latest_grant_by_order = {}
    latest_grant_by_build = {}
    for grant in grants:
        if grant.order_id is not None:
            latest_grant_by_order.setdefault(grant.order_id, grant)
        if grant.manual_build_id is not None:
            latest_grant_by_build.setdefault(grant.manual_build_id, grant)
    # Pre-sale records appear only after mark-built has opened their Getting
    # Ready job. Sold builds remain visible even when migrating older data.
    rows = [build for build in rows if build.status == "sold" or build.id in jobs_by_build]
    response_rows = []
    for b in rows:
        job = jobs_by_build.get(b.id)
        product_link = products_by_id.get(b.storefront_product_id, (None, None)) if b.storefront_product_id else (None, None)
        linked_order_id = (job.order_id if job and job.order_id else None) or order_by_build.get(b.id) or product_link[0]
        linked_order_email, linked_order_name = contacts_by_order.get(linked_order_id, (None, None))
        product_channel = getattr(product_link[1], "value", product_link[1])
        portal_is_direct = bool(
            linked_order_id
            and not b.ebay_order_id
            and (product_channel is None or product_channel == "storefront")
        )
        portal_grant = (
            latest_grant_by_order.get(linked_order_id)
            if portal_is_direct
            else latest_grant_by_build.get(b.id)
        )
        job_checklist = checklist_with_defaults(
            job.checklist,
            job.purchased_ai_services,
        ) if job else {}
        response_rows.append({"id": b.id, "name": b.name, "status": b.status, "dispatch_status": b.dispatch_status,
             "has_physical_handover": _manual_build_has_physical_handover(b),
             "playbook_assignment": (b.evidence_data or {}).get("playbook_assignment"),
             "sale_price": b.sale_price_actual or b.ebay_price, "buyer_name": b.buyer_name or (linked_order_name if portal_is_direct else None),
             "customer_email": (linked_order_email if portal_is_direct else None) or b.customer_email,
             "portal_order_id": linked_order_id if portal_is_direct else None,
             "portal_grant_id": portal_grant.id if portal_grant else None,
             "portal_claim_email_status": portal_grant.email_status if portal_grant else None,
             "buyer_address": b.buyer_address_json,
             "collection_date": b.collection_date.isoformat() if b.collection_date else None,
             "tracking_number": b.tracking_number, "shipping_label_url": b.shipping_label_url,
             "parcel2go_order_id": b.parcel2go_order_id,
             "parcel2go_order_line_id": b.parcel2go_order_line_id,
             "shipment_booked_at": b.shipment_booked_at.isoformat() if b.shipment_booked_at else None,
             "shipment_booking_state": b.shipment_booking_state,
             "insurance_status": b.shipping_insurance_status,
             "insurance_policy_id": b.shipping_insurance_policy_id,
             "insurance_cost_gbp": b.shipping_insurance_cost_gbp,
             "insurance_provider_response": _insurance_provider_response_summary(b.evidence_data),
             "warranty_started_at": b.warranty_started_at.isoformat() if b.warranty_started_at else None,
             "getting_started": ({"status": job.status,
                                  "order_id": job.order_id,
                                  "software_selections": job.customer_software_selections or [],
                                  "purchased_ai_services": job.purchased_ai_services or [],
                                  "checklist": job_checklist,
                                  "shipment_evidence": [
                                      item for item in (job.artifact_index or [])
                                      if item.get("category") in {"working_pc", "package_contents", "sealed_package"}
                                  ],
                                  "manifest": job.manifest,
                                  "cached_component_manuals": (((b.evidence_data or {}).get("getting_ready") or {}).get("source_inputs") or {}).get("cached_component_manuals", []),
                                  "approved_research_bundle": (((b.evidence_data or {}).get("getting_ready") or {}).get("source_inputs") or {}).get("approved_research_bundle", []),
                                  "latest_package": max(
                                      [item for item in (job.artifact_index or []) if item.get("category") == "customer_package"],
                                      key=lambda item: int(item.get("version") or 0),
                                      default=None,
                                  ),
                                  "generated_at": job.generated_at.isoformat() if job.generated_at else None}
                                 if job else None)})
    return response_rows


@router.post("/{build_id}/getting-ready/source-suggestions")
async def suggest_getting_ready_research_sources(
    build_id: int,
    body: ComponentResearchDiscoveryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find untrusted manufacturer-source candidates for one exact component.

    Results are neither saved nor approved. The administrator must verify each
    page and enter the supported claim before it can reach the LLM prompt.
    """
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    from app.services.component_manual_library import normalize_manual_key

    requested = normalize_manual_key(body.component_name)
    component_matches = []
    identity_fields = (
        "component_name", "name", "title", "model", "model_number", "mpn",
        "manufacturer_part_number", "part_number", "sku",
    )
    for component in build.components or []:
        identities = (
            [component.get(field) for field in identity_fields]
            if isinstance(component, dict)
            else [component]
        )
        if any(
            isinstance(value, (str, int))
            and normalize_manual_key(str(value)) == requested
            for value in identities
        ):
            component_matches.append(component)
    if not requested or len(component_matches) != 1:
        raise HTTPException(422, "Research must target exactly one component identity recorded on this build")

    exact_component = component_matches[0]
    if isinstance(exact_component, dict):
        canonical_name = next((
            str(exact_component[field]).strip()
            for field in identity_fields
            if exact_component.get(field)
        ), body.component_name.strip())
    else:
        canonical_name = str(exact_component).strip()
    cached_manual_matches = []
    if body.topic == "manual":
        cached_manual_rows = (await db.execute(
            select(ComponentManual).where(ComponentManual.is_active.is_(True))
        )).scalars().all()
        from app.services.component_manual_library import matching_manuals

        cached_manual_matches = matching_manuals([exact_component], cached_manual_rows)
        if cached_manual_matches:
            return {
                "build_id": build_id,
                "component_name": canonical_name,
                "topic": body.topic,
                "suggestions": [],
                "cached_manual_matches": cached_manual_matches,
                "cache_checked": True,
                "review_required": True,
                "saved": False,
                "downloaded": False,
            }
    from app.services.component_research_search import discover_component_sources

    try:
        suggestions = await discover_component_sources(canonical_name, body.topic)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        log.warning("getting_ready.source_discovery_failed", build_id=build_id, topic=body.topic, error=type(error).__name__)
        raise HTTPException(502, "Source search is temporarily unavailable. No files were downloaded or added to the build.") from error
    return {
        "build_id": build_id,
        "component_name": canonical_name,
        "topic": body.topic,
        "suggestions": suggestions,
        "cached_manual_matches": cached_manual_matches,
        "cache_checked": body.topic == "manual",
        "review_required": True,
        "saved": False,
        "downloaded": False,
    }


@router.post("/{build_id}/getting-ready/generate")
async def generate_getting_ready_package_content(
    build_id: int,
    body: GettingReadyGenerationRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate the review-only content manifest for a build's dispatch pack.

    Inputs are grounded in recorded build evidence and admin-approved research.
    ZIP assembly, installer execution and dispatch approval remain separate
    deterministic/admin-controlled actions.
    """
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Getting Ready content is locked after physical handover")
    generation_snapshot = _getting_ready_generation_snapshot(build)
    evidence = build.evidence_data or {}
    from app.services.component_manual_library import matching_manuals, normalize_manual_key
    normalized_components = [normalize_manual_key(str(component)) for component in (build.components or [])]
    for source in body.approved_research_bundle:
        component_name = normalize_manual_key(source.component_name)
        if len(component_name) < 8 or not any(component_name in component for component in normalized_components):
            raise HTTPException(
                422,
                f"Research component '{source.component_name}' does not match an exact component in this build",
            )
    cached_manual_rows = (await db.execute(
        select(ComponentManual).where(ComponentManual.is_active.is_(True))
    )).scalars().all()
    cached_manual_matches = matching_manuals(build.components or [], cached_manual_rows)
    job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
    )).scalar_one_or_none()
    job_snapshot = (
        job.updated_at if job else None,
        list(job.customer_software_selections or []) if job else [],
        list(job.purchased_ai_services or []) if job else [],
        job.order_id if job else None,
        job.status if job else None,
        bool((job.checklist or {}).get("software_selection_submitted")) if job else False,
    )
    assignment = dict((evidence.get("playbook_assignment") or {}))
    if body.curated_build_id:
        if not body.playbook_id:
            raise HTTPException(422, "Playbook ID is required with a curated cell")
        playbook = await db.get(Playbook, body.playbook_id)
        if not playbook:
            raise HTTPException(404, "Playbook not found")
        try:
            profile = await software_profile_for_curated_cell_from_db(
                db, body.curated_build_id, playbook.name, playbook.software_profile
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        from app.services.curated_build_policy import definitions
        cell = next(item for item in definitions()["builds"] if item["id"] == body.curated_build_id)
        assignment = {
            "playbook_id": playbook.id,
            "curated_build_id": body.curated_build_id,
            "customer_type": cell["segment"],
            "budget_tier": cell["tier"],
            "cell_name": cell["name"],
            "software_profile": profile,
            "assigned_at": datetime.utcnow().isoformat(),
        }
    elif not (assignment.get("playbook_id") and assignment.get("software_profile")):
        raise HTTPException(422, "Select a Playbook customer-type × budget cell before generating this Ready-to-Ship package")
    profile = assignment["software_profile"]
    if job and (job.checklist or {}).get("software_selection_submitted"):
        default_software_ids = list(job.customer_software_selections or [])
    elif body.customer_software_selections is not None:
        if job and job.order_id:
            raise HTTPException(409, "For a customer order, use the customer's saved software choices instead of an admin override")
        default_software_ids = body.customer_software_selections
    elif job and job.customer_software_selections:
        default_software_ids = list(job.customer_software_selections)
    else:
        default_software_ids = list(profile.get("recommended_package_ids") or [])
    try:
        selected_software_ids = validate_package_ids(default_software_ids)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    settings = get_settings()
    from app.api.settings_router import GETTING_STARTED_GUIDE_PATH
    guide_path = GETTING_STARTED_GUIDE_PATH
    try:
        configured_guide = guide_path.read_text(encoding="utf-8") if guide_path.is_file() else None
    except OSError as error:
        raise HTTPException(500, "The configured Getting Started guide could not be read") from error
    guide_text, guide_metadata = guide_snapshot(
        configured_guide=configured_guide,
        request_guide=body.getting_started_guide_text,
    )
    research_reviewed_at = datetime.utcnow().isoformat()
    reviewed_research_bundle = [
        {
            **item.model_dump(mode="json"),
            "reviewed_by": getattr(admin, "email", None) or "admin",
            "reviewed_at": research_reviewed_at,
        }
        for item in body.approved_research_bundle
    ]
    inputs = {
        "build_name": build.name,
        "playbook_segment": f"{assignment['customer_type']} / {assignment['budget_tier']} · {assignment['cell_name']}",
        "build_specification": build.components or [],
        "benchmark_results": evidence.get("benchmark_results") or evidence.get("performance_card"),
        "customer_software_selections": selected_software_ids,
        "software_install_scopes": [
            {
                "package_id": package_id,
                "name": SOFTWARE_BY_ID[package_id]["name"],
                "scope": SOFTWARE_BY_ID[package_id].get("install_scope", "machine"),
                "timing": "customer_first_sign_in" if SOFTWARE_BY_ID[package_id].get("install_scope") == "customer_profile" else "workshop_pre_dispatch",
            }
            for package_id in selected_software_ids
        ],
        "purchased_ai_services": list(job.purchased_ai_services or []) if job else [],
        "warranty_start_date": build.delivered_at.isoformat() if build.delivered_at else None,
        "support_base_url": getattr(settings, "storefront_base_url", None),
        "approved_research_bundle": reviewed_research_bundle,
        "approved_component_manuals": [*body.approved_component_manuals, *cached_manual_matches],
        "getting_started_guide_text": guide_text,
        "upgrade_policy": body.upgrade_policy,
    }
    try:
        manifest = await generate_getting_ready_manifest(inputs)
    except GettingReadyPromptSizeError as error:
        raise HTTPException(413, str(error)) from error
    except GettingReadyGenerationError as error:
        raise HTTPException(502, str(error)) from error
    if guide_text is None:
        guide_text, guide_metadata = guide_snapshot(
            configured_guide=None,
            request_guide=None,
            generated_intro=manifest.customer_copy.get("getting_started_intro"),
        )
        if guide_text is None:
            raise HTTPException(502, "The generated Getting Started guide was empty; regenerate the package.")
        inputs["getting_started_guide_text"] = guide_text
    current_build, current_job = await lock_manual_build_then_getting_started_job(db, build_id)
    if current_build is None:
        raise HTTPException(404, "Build not found")
    if _getting_ready_generation_snapshot(current_build) != generation_snapshot:
        raise HTTPException(409, "Build specification or evidence changed during generation. Generate a fresh review manifest.")
    build = current_build
    evidence = dict(build.evidence_data or {})
    current_snapshot = (
        current_job.updated_at if current_job else None,
        list(current_job.customer_software_selections or []) if current_job else [],
        list(current_job.purchased_ai_services or []) if current_job else [],
        current_job.order_id if current_job else None,
        current_job.status if current_job else None,
        bool((current_job.checklist or {}).get("software_selection_submitted")) if current_job else False,
    )
    if current_snapshot != job_snapshot:
        raise HTTPException(409, "Getting Ready inputs changed during generation. Generate a fresh review manifest.")
    job = current_job
    if body.curated_build_id:
        current_playbook = (await db.execute(
            select(Playbook)
            .where(Playbook.id == body.playbook_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
        if current_playbook is None:
            raise HTTPException(409, "The Playbook changed during generation. Select the current cell and regenerate.")
        try:
            current_profile = await software_profile_for_curated_cell_from_db(
                db,
                body.curated_build_id,
                current_playbook.name,
                current_playbook.software_profile,
                lock_profile=True,
            )
        except ValueError as error:
            raise HTTPException(409, "The Playbook cell changed during generation. Select the current cell and regenerate.") from error
        if current_profile != profile:
            raise HTTPException(409, "The Playbook software profile changed during generation. Regenerate the package content.")
    if job is not None:
        invalidate_ready_to_ship_reviewed_package(
            job,
            build,
            checklist_reset_keys=(
                "customer_selections_locked",
                "content_manifest",
                "artifacts_generated",
                "artifacts_reviewed",
                "customer_package",
                "component_manuals_reviewed",
                "driver_firmware_reviewed",
                "drivers_updates_complete",
            ),
        )
        job.checklist = {**(job.checklist or {}), "_driver_firmware_outcomes": []}
        evidence = dict(build.evidence_data or {})
    updated_evidence = dict(evidence)
    updated_evidence["getting_ready"] = {
        "manifest": manifest.model_dump(mode="json"),
        "generated_at": datetime.utcnow().isoformat(),
        "status": "ready_for_admin_review",
        "source_inputs": {
            "software_selections": selected_software_ids,
            "purchased_ai_services": list(job.purchased_ai_services or []) if job else [],
            "playbook_segment": f"{assignment['customer_type']} / {assignment['budget_tier']} · {assignment['cell_name']}",
            "approved_research_bundle": reviewed_research_bundle,
            "approved_component_manuals": body.approved_component_manuals,
            "cached_component_manuals": cached_manual_matches,
            "getting_started_guide_metadata": guide_metadata,
            "getting_started_guide_text": guide_text,
            "upgrade_policy": body.upgrade_policy,
        },
        "software_install_script": (
            create_software_install_script(selected_software_ids)
            if build.status == "sold" and job is not None
            and (job.checklist or {}).get("software_selection_submitted")
            else None
        ),
        "software_time_saving_estimate": {
            "minutes": estimate_saved_minutes(selected_software_ids),
            "apps": [SOFTWARE_BY_ID[item_id] for item_id in selected_software_ids],
            "basis": "Indicative internal estimate for download/search and installer clicks; not measured or guaranteed.",
        },
    }
    updated_evidence["playbook_assignment"] = assignment
    build.evidence_data = updated_evidence
    build.updated_at = datetime.utcnow()
    if job is None:
        job = GettingStartedJob(
            manual_build_id=build.id,
            customer_id=build.customer_id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            checklist=checklist_with_defaults(None),
        )
        db.add(job)
    job.playbook_id = assignment["playbook_id"]
    job.customer_software_selections = selected_software_ids
    job.manifest = manifest.model_dump(mode="json")
    job.status = "awaiting_admin_review"
    package_checklist = {
        **checklist_with_defaults(job.checklist, job.purchased_ai_services),
        "component_manuals_reviewed": "needs_review",
        "driver_firmware_reviewed": "needs_review",
        "drivers_updates_complete": "not_ready",
        "source_data_complete": "complete" if build.components and inputs["benchmark_results"] else "needs_review",
        "content_manifest": "needs_review",
    }
    job.checklist = package_checklist
    job.generated_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    await db.commit()
    return updated_evidence["getting_ready"]


@router.patch("/{build_id}/getting-ready/checklist/{action}")
async def update_getting_ready_checklist_action(
    build_id: int,
    action: str,
    body: GettingReadyChecklistUpdate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if action not in OPERATOR_CHECKLIST_ACTIONS:
        raise HTTPException(422, "This checklist action is system-managed or unknown")
    if body.status not in CHECKLIST_STATUSES:
        raise HTTPException(422, f"Unknown checklist status: {body.status}")
    if body.status == "not_required" and action not in OPTIONAL_CHECKLIST_ACTIONS:
        raise HTTPException(422, "This preparation action is required and cannot be marked not required")
    if body.status in {"complete", "not_required"} and len((body.note or "").strip()) < 12:
        raise HTTPException(422, "Record a meaningful operator note for this completion or exception")
    build, job = await lock_manual_build_then_getting_started_job(db, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "The dispatch checklist is locked after courier handover")
    if action == "windows_deployment_completed":
        if body.status != "complete":
            raise HTTPException(422, "Windows deployment must be verified complete before dispatch; it cannot be marked not required")
        deployment = body.windows_deployment_evidence
        if deployment is None:
            raise HTTPException(422, "Import the read-only Windows deployment evidence report")
        if deployment.build_id != build_id:
            raise HTTPException(422, "The Windows evidence report belongs to a different build")
        if deployment.build_name != build.name:
            raise HTTPException(422, "The Windows evidence report build name does not match this build")
        if any(not value.strip() for value in (
            deployment.target_drive_model,
            deployment.target_drive_serial,
            deployment.installation_method,
        )):
            raise HTTPException(422, "Target-drive details and installation method cannot be blank")
        try:
            verified_at = datetime.fromisoformat(deployment.verified_at_utc.replace("Z", "+00:00"))
        except ValueError as error:
            raise HTTPException(422, "The Windows evidence timestamp is invalid") from error
        if verified_at.tzinfo is None:
            raise HTTPException(422, "The Windows evidence timestamp must include a timezone")
        age = datetime.now(timezone.utc) - verified_at.astimezone(timezone.utc)
        if age.total_seconds() < -300 or age > timedelta(days=30):
            raise HTTPException(422, "The Windows evidence report must be current (no more than 30 days old)")
        if len((body.note or "").strip()) < 12:
            raise HTTPException(422, "Add an operator note describing the Windows deployment verification")
    if not job:
        raise HTTPException(404, "Getting Ready job not found")
    if action == "component_manuals_reviewed" and body.status == "complete":
        if not isinstance(job.manifest, dict):
            raise HTTPException(409, "Generate the component manual review list before recording its review")
        missing_models = missing_component_manual_models(build.components or [], job.manifest)
        if missing_models:
            raise HTTPException(
                409,
                "Regenerate the manual review list; it is missing exact build models: "
                + ", ".join(missing_models),
            )
    if action == "driver_firmware_reviewed" and body.status == "complete":
        if not isinstance(job.manifest, dict):
            raise HTTPException(409, "Generate the driver and firmware review list before recording its review")
        try:
            validated_driver_outcomes = validate_component_driver_outcomes(
                build.components or [], job.manifest, body.driver_firmware_outcomes
            )
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
    if action == "drivers_updates_complete" and body.status == "complete":
        checklist_before_update = checklist_with_defaults(job.checklist, job.purchased_ai_services)
        if checklist_before_update.get("driver_firmware_reviewed") != "complete":
            raise HTTPException(409, "Complete the per-component driver and firmware review before recording installation")
        if not isinstance(job.manifest, dict):
            raise HTTPException(409, "Generate the driver and firmware review list before recording installation")
        try:
            validate_component_driver_outcomes(
                build.components or [],
                job.manifest,
                checklist_before_update.get("_driver_firmware_outcomes"),
            )
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
    try:
        validate_ai_setup_checklist_update(
            action=action,
            status=body.status,
            purchased_ai_services=job.purchased_ai_services,
            scope_confirmed=body.confirm_paid_ai_scope,
        )
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    checklist = checklist_with_defaults(job.checklist, job.purchased_ai_services)
    target_identity_changed = False
    leaflet_portal_grant_id = None
    if action == "leaflet_printed" and body.status == "complete":
        grant_required, portal_grant = await _portal_grant_required_for_build(db, build)
        if grant_required and portal_grant is None:
            raise HTTPException(409, "Issue the final buyer portal claim before printing and recording its QR leaflet")
        leaflet_portal_grant_id = portal_grant.id if portal_grant else None
    if action == "windows_target_confirmed":
        target = body.windows_target
        if body.status != "complete" or target is None:
            raise HTTPException(422, "Record and confirm the intended new-build drive before installing Windows")
        if not target.model.strip() or not target.serial.strip():
            raise HTTPException(422, "The intended target drive model and serial are required")
        try:
            inspected_at = datetime.fromisoformat(target.inspected_at_utc.replace("Z", "+00:00"))
        except ValueError as error:
            raise HTTPException(422, "The target-drive inspection timestamp is invalid") from error
        if inspected_at.tzinfo is None:
            raise HTTPException(422, "The target-drive inspection timestamp must include a timezone")
        age = datetime.now(timezone.utc) - inspected_at.astimezone(timezone.utc)
        if age.total_seconds() < -300 or age > timedelta(days=30):
            raise HTTPException(422, "Recheck the target drive; the recorded inspection must be current")
        prior_target = checklist.get("windows_target")
        target_identity_changed = not isinstance(prior_target, dict) or (
            str(prior_target.get("serial", "")).strip().casefold() != target.serial.strip().casefold()
            or str(prior_target.get("model", "")).strip().casefold() != target.model.strip().casefold()
        )
        if isinstance(prior_target, dict) and (
            str(prior_target.get("serial", "")).strip().casefold() != target.serial.strip().casefold()
            or str(prior_target.get("model", "")).strip().casefold() != target.model.strip().casefold()
        ):
            checklist["windows_deployment_completed"] = "not_ready"
        checklist["windows_target"] = target.model_dump(mode="json")
    elif action == "windows_deployment_completed":
        target = checklist.get("windows_target")
        deployment = body.windows_deployment_evidence
        if not isinstance(target, dict) or deployment is None:
            raise HTTPException(409, "Record and confirm the intended target drive before installing Windows")
        if (
            str(target.get("serial", "")).strip().casefold() != deployment.target_drive_serial.strip().casefold()
            or str(target.get("model", "")).strip().casefold() != deployment.target_drive_model.strip().casefold()
        ):
            raise HTTPException(409, "The installed Windows system drive does not match the target recorded before installation")
        try:
            target_inspected_at = datetime.fromisoformat(str(target.get("inspected_at_utc") or "").replace("Z", "+00:00"))
            system_verified_at = datetime.fromisoformat(deployment.verified_at_utc.replace("Z", "+00:00"))
        except ValueError as error:
            raise HTTPException(409, "The pre-install target inspection time is invalid") from error
        if target_inspected_at.tzinfo is None or system_verified_at.tzinfo is None:
            raise HTTPException(409, "The target inspection and Windows evidence must include timezone-aware timestamps")
        install_gap = system_verified_at.astimezone(timezone.utc) - target_inspected_at.astimezone(timezone.utc)
        if install_gap.total_seconds() < 0:
            raise HTTPException(409, "The target drive must be recorded before Windows is installed")
        if install_gap > timedelta(days=30):
            raise HTTPException(409, "Reconfirm the target drive; its inspection is more than 30 days before this installation")
    checklist[action] = body.status
    if action == "driver_firmware_reviewed" and body.status != "complete":
        checklist["drivers_updates_complete"] = "not_ready"
        checklist["_driver_firmware_outcomes"] = []
    elif action == "driver_firmware_reviewed" and body.status == "complete":
        reviewed_at = datetime.utcnow().isoformat()
        reviewer = getattr(admin, "email", None) or "admin"
        checklist["_driver_firmware_outcomes"] = [
            {**item, "reviewed_by": reviewer, "reviewed_at": reviewed_at}
            for item in validated_driver_outcomes
        ]
    audit = list(checklist.get("_audit") or [])
    audit.append({
        "action": action,
        "status": body.status,
        "note": body.note,
        "evidence_ref": body.evidence_ref,
        "paid_ai_scope_confirmed": (
            body.confirm_paid_ai_scope
            if action == "ai_services_complete" and body.status == "complete" and job.purchased_ai_services
            else None
        ),
        "windows_deployment_evidence": (
            body.windows_deployment_evidence.model_dump(mode="json")
            if action == "windows_deployment_completed" and body.windows_deployment_evidence is not None
            else None
        ),
        "windows_target": (
            body.windows_target.model_dump(mode="json")
            if action == "windows_target_confirmed" and body.windows_target is not None
            else None
        ),
        "portal_grant_id": leaflet_portal_grant_id if action == "leaflet_printed" else None,
        "driver_firmware_outcomes": (
            checklist.get("_driver_firmware_outcomes")
            if action == "driver_firmware_reviewed" and body.status == "complete"
            else None
        ),
        "actor": getattr(admin, "email", None) or "admin",
        "recorded_at": datetime.utcnow().isoformat(),
    })
    checklist["_audit"] = audit[-250:]
    job.checklist = checklist
    if action == "windows_target_confirmed" and target_identity_changed and any(
        isinstance(item, dict) and item.get("category") == "customer_package"
        for item in (job.artifact_index or [])
    ):
        invalidate_ready_to_ship_reviewed_package(
            job,
            build,
            checklist_reset_keys=(
                "content_manifest",
                "artifacts_generated",
                "artifacts_reviewed",
                "customer_package",
            ),
        )
        checklist = job.checklist
    if checklist_dispatch_ready(checklist, job.purchased_ai_services):
        job.status = "ready_for_delivery"
    job.updated_at = datetime.utcnow()
    await db.commit()
    return {"action": action, "status": body.status, "checklist": checklist}


@router.post("/{build_id}/getting-ready/approve-and-package", status_code=201)
async def approve_and_assemble_getting_ready_package(
    build_id: int,
    body: GettingReadyPackageApproval,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve reviewed content and deterministically create a private ZIP.

    This action creates files only. It cannot install software, alter a PC,
    publish externally, book a courier, or buy insurance.
    """
    if not body.confirm_manifest_reviewed or not body.confirm_customer_details_checked:
        raise HTTPException(409, "Confirm the manifest review and customer/build details before creating the package")
    build, job = await lock_manual_build_then_getting_started_job(db, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Getting Ready package approval is closed after physical handover")
    if build.status != "sold":
        raise HTTPException(409, "Create the customer package only after the build is sold")
    if not job or not job.manifest or not job.generated_at:
        raise HTTPException(409, "Generate the Getting Ready review manifest first")
    checklist = checklist_with_defaults(job.checklist, job.purchased_ai_services)
    if checklist.get("component_manuals_reviewed") != "complete":
        raise HTTPException(409, "Review the exact-model manual results for every component and record the outcome before approving the customer package")
    missing_models = missing_component_manual_models(build.components or [], job.manifest)
    if missing_models:
        raise HTTPException(
            409,
            "Regenerate the manual review list; it is missing exact build models: "
            + ", ".join(missing_models),
        )
    windows_target = checklist.get("windows_target")
    if checklist.get("windows_target_confirmed") != "complete" or not isinstance(windows_target, dict):
        raise HTTPException(409, "Record and confirm the exact new-build drive in Dispatch Centre before approving the workshop package")
    target_model = str(windows_target.get("model") or "").strip()
    target_serial = str(windows_target.get("serial") or "").strip()
    if not target_model or not target_serial:
        raise HTTPException(409, "The recorded Windows target must include both drive model and serial")
    try:
        target_inspected_at = datetime.fromisoformat(
            str(windows_target.get("inspected_at_utc") or "").replace("Z", "+00:00")
        )
    except ValueError as error:
        raise HTTPException(409, "The recorded Windows target has an invalid inspection time; confirm it again") from error
    if target_inspected_at.tzinfo is None:
        raise HTTPException(409, "The recorded Windows target inspection time must include a timezone")
    target_age = datetime.now(timezone.utc) - target_inspected_at.astimezone(timezone.utc)
    if target_age.total_seconds() < -300 or target_age > timedelta(days=30):
        raise HTTPException(409, "Reconfirm the intended Windows drive; its inspection must be current before package approval")
    if job.order_id:
        pending_ai_purchase = (await db.execute(
            select(AISetupPurchase.id).where(
                AISetupPurchase.order_id == job.order_id,
                AISetupPurchase.status == "pending",
            ).limit(1)
        )).scalar_one_or_none()
        if pending_ai_purchase:
            raise HTTPException(409, "An AI setup payment is still pending. Reconcile it before approving the customer package")
    if job.order_id and not (job.checklist or {}).get("software_selection_submitted"):
        raise HTTPException(409, "Wait for the customer to save their software choices in the build portal before approving the package")
    if (
        not job.order_id
        and not (job.checklist or {}).get("software_selection_submitted")
        and not body.confirm_playbook_defaults_for_indirect_customer
    ):
        raise HTTPException(409, "Explicitly confirm that the Playbook's recommended software list will be used for this indirect-channel customer")
    evidence = dict(build.evidence_data or {})
    ready_evidence = dict(evidence.get("getting_ready") or {})
    source_inputs = dict(ready_evidence.get("source_inputs") or {})
    existing_packages = [
        item for item in (job.artifact_index or [])
        if item.get("category") in {"customer_package", "superseded_customer_package"}
    ]
    version = max([int(item.get("version") or 0) for item in existing_packages] or [0]) + 1
    settings = get_settings()
    portal_url = f"{settings.frontend_url.rstrip('/')}/my-builds/{job.order_id}" if job.order_id else None
    active_leaflet_grant = (await db.execute(
        select(PortalAccessGrant)
        .where(
            PortalAccessGrant.manual_build_id == build.id,
            PortalAccessGrant.claimed_at.is_(None),
            PortalAccessGrant.revoked.is_(False),
            PortalAccessGrant.expires_at >= datetime.utcnow(),
            PortalAccessGrant.leaflet_storage_key.isnot(None),
        )
        .order_by(PortalAccessGrant.created_at.desc(), PortalAccessGrant.id.desc())
        .limit(1)
    )).scalar_one_or_none()
    portal_leaflet_path = None
    if active_leaflet_grant and active_leaflet_grant.leaflet_storage_key:
        try:
            portal_leaflet_path = package_path(active_leaflet_grant.leaflet_storage_key)
        except GettingReadyPackageError as error:
            raise HTTPException(409, str(error)) from error
    cached_manual_snapshots = list(source_inputs.get("cached_component_manuals") or [])
    from app.services.component_manual_library import matching_manuals
    cached_manual_ids = {
        int(item["manual_id"])
        for item in cached_manual_snapshots
        if isinstance(item, dict) and str(item.get("manual_id", "")).isdigit()
    }
    cached_manual_files: list[dict] = []
    if cached_manual_ids:
        cached_rows = (await db.execute(
            select(ComponentManual).where(ComponentManual.id.in_(cached_manual_ids))
        )).scalars().all()
        current_matches = matching_manuals(build.components or [], cached_rows)
        current_by_id = {int(item["manual_id"]): item for item in current_matches}
        snapshot_by_id = {
            int(item["manual_id"]): item for item in cached_manual_snapshots
            if isinstance(item, dict) and str(item.get("manual_id", "")).isdigit()
        }
        if len(cached_rows) != len(cached_manual_ids) or set(current_by_id) != cached_manual_ids:
            raise HTTPException(409, "A cached component manual changed or no longer exactly matches this build. Regenerate and review the manifest.")
        for manual in cached_rows:
            snapshot = snapshot_by_id.get(manual.id)
            if (not manual.is_active or not snapshot
                    or snapshot.get("sha256") != manual.sha256
                    or snapshot.get("component_key") != manual.component_key):
                raise HTTPException(409, "A cached component manual changed after manifest generation. Regenerate and review the manifest.")
            try:
                manual_file_path = package_path(manual.storage_key)
                manual_content = manual_file_path.read_bytes()
            except (GettingReadyPackageError, OSError) as error:
                raise HTTPException(409, "A matched cached component manual is unavailable. Regenerate and review the manifest.") from error
            if hashlib.sha256(manual_content).hexdigest() != manual.sha256:
                raise HTTPException(409, "A matched cached component manual failed its SHA-256 check.")
            cached_manual_files.append({
                "id": manual.id,
                "component_key": manual.component_key,
                "component_name": manual.component_name,
                "source_url": manual.source_url,
                "filename": manual.filename,
                "sha256": manual.sha256,
                "content": manual_content,
            })
    windows_license_key = await _assigned_windows_pro_key(db, build.id, job)
    if windows_license_key and not body.confirm_windows_license_handling:
        raise HTTPException(409, "Confirm that the assigned Windows licence helper will be downloaded separately from Dispatch Centre, never stored in the package or sent to AI/customer documents, and removed from the USB folder after installation")
    try:
        package = assemble_getting_ready_package(
            build_id=build.id,
            build_name=build.name,
            version=version,
            specification=list(build.components or []),
            benchmark_results=evidence.get("benchmark_results") or evidence.get("performance_card"),
            manifest=dict(job.manifest),
            software_package_ids=list(job.customer_software_selections or []),
            source_inputs=source_inputs,
            portal_url=portal_url,
            portal_leaflet_path=portal_leaflet_path,
            cached_component_manuals=cached_manual_files,
            windows_license_key_present=bool(windows_license_key),
            target_drive_model=target_model,
            target_drive_serial=target_serial,
            target_drive_inspected_at_utc=target_inspected_at.isoformat(),
        )
    except (GettingReadyPackageError, ValueError) as error:
        raise HTTPException(409, str(error)) from error

    artifact = {
        "id": uuid.uuid4().hex,
        "category": "customer_package",
        **package,
        "windows_license_helper_required": bool(windows_license_key),
        "reviewed_by": getattr(admin, "email", None) or "admin",
        "reviewed_at": datetime.utcnow().isoformat(),
    }
    job.artifact_index = [*(job.artifact_index or []), artifact]
    job.private_storage_key = package["storage_key"]
    job.reviewed_at = datetime.utcnow()
    job.status = "package_ready"
    job.admin_notes = body.reviewer_notes
    package_checklist = {
        **checklist_with_defaults(job.checklist, job.purchased_ai_services),
        "customer_selections_locked": "complete",
        "content_manifest": "complete",
        "artifacts_generated": "complete",
        "artifacts_reviewed": "complete",
        "customer_package": "complete",
    }
    job.checklist = package_checklist
    if windows_license_key:
        audit = list(job.checklist.get("_audit") or [])
        audit.append({
            "action": "windows_license_helper_required",
            "status": "complete",
            "note": "Administrator confirmed that the order-assigned key will be downloaded separately and excluded from the ZIP, LLM and customer documents.",
            "actor": getattr(admin, "email", None) or "admin",
            "recorded_at": datetime.utcnow().isoformat(),
        })
        job.checklist["_audit"] = audit[-250:]
    if not job.order_id and not package_checklist.get("software_selection_submitted"):
        # Indirect-channel buyers may not have an authenticated FlipFlop
        # account. Package review is the explicit operator acceptance of the
        # Playbook defaults for those builds.
        package_checklist["software_selection_submitted"] = True
        package_checklist["_software_selection_decision"] = {
            "source": "admin_accepted_playbook_defaults",
            "operator_confirmed": True,
            "actor": getattr(admin, "email", None) or "admin",
            "recorded_at": datetime.utcnow().isoformat(),
            "software_package_ids": list(job.customer_software_selections or []),
        }
    job.checklist = package_checklist
    if checklist_dispatch_ready(job.checklist, job.purchased_ai_services):
        job.status = "ready_for_delivery"
    job.updated_at = datetime.utcnow()
    ready_evidence["package"] = {
        key: value for key, value in package.items()
        if key not in {"storage_key", "workshop_storage_key"}
    }
    ready_evidence["status"] = "package_ready"
    evidence["getting_ready"] = ready_evidence
    build.evidence_data = evidence
    build.updated_at = datetime.utcnow()
    await _commit_getting_ready_package_approval(db, package, build_id=build.id)
    return {
        **package,
        "windows_license_helper_required": bool(windows_license_key),
        "download_url": f"/api/manual-builds/{build.id}/getting-ready/package/{version}",
    }


@router.post("/{build_id}/getting-ready/windows-license-helper")
async def download_windows_license_helper(
    build_id: int,
    body: WindowsLicenseHelperRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Release a one-build Windows key helper only after explicit admin confirmation.

    The response is generated in memory and is never stored in the ZIP, logs,
    or customer document index.
    """
    if not body.confirm_private_key_release:
        raise HTTPException(409, "Confirm the private Windows key release before downloading the helper")
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Windows licence helper release is closed after physical handover")
    if build.status != "sold":
        raise HTTPException(409, "The private Windows licence helper is available only after the build is sold")
    job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
    )).scalar_one_or_none()
    if not job:
        raise HTTPException(409, "Getting Ready job is not linked to this build")
    latest_reviewed_package = max(
        [item for item in (job.artifact_index or []) if item.get("category") == "customer_package"],
        key=lambda item: int(item.get("version") or 0),
        default=None,
    )
    if not latest_reviewed_package or not latest_reviewed_package.get("windows_license_helper_required"):
        raise HTTPException(409, "The latest reviewed package does not expect a Windows licence helper")
    key = await _assigned_windows_pro_key(db, build_id, job)
    if not key:
        raise HTTPException(404, "No Windows Pro licence is assigned to this order")
    from app.services.software_catalogue import create_windows_license_activation_script
    script = create_windows_license_activation_script(key)
    checklist = checklist_with_defaults(job.checklist, job.purchased_ai_services)
    audit = list(checklist.get("_audit") or [])
    audit.append({
        "action": "windows_license_helper_downloaded",
        "status": "complete",
        "note": "A one-build Windows Pro activation helper was released to the authenticated administrator; the key is not stored in this audit record.",
        "actor": getattr(admin, "email", None) or "admin",
        "recorded_at": datetime.utcnow().isoformat(),
    })
    checklist["_audit"] = audit[-250:]
    job.checklist = checklist
    job.updated_at = datetime.utcnow()
    await db.commit()
    return Response(
        content=script,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="FlipFlop-Build-{build_id}-install-windows-license.ps1"',
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/{build_id}/getting-ready/software-script")
async def download_getting_ready_software_script(
    build_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate the reviewed machine-scope script from the locked saved selection."""
    build, job = await lock_manual_build_then_getting_started_job(db, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Software script download is closed after physical handover")
    if build.status != "sold":
        raise HTTPException(409, "The software script is available only after the build is sold")
    if not job or not (job.checklist or {}).get("software_selection_submitted"):
        raise HTTPException(409, "Submit customer software choices or confirm the indirect-channel Playbook defaults first")
    latest_package = max(
        [item for item in (job.artifact_index or []) if item.get("category") == "customer_package"],
        key=lambda item: int(item.get("version") or 0),
        default=None,
    )
    if not latest_package or not job.reviewed_at:
        raise HTTPException(409, "Approve and create the reviewed workshop package before downloading its software script")
    try:
        script = create_software_install_script(list(job.customer_software_selections or []))
    except ValueError as error:
        raise HTTPException(409, "The saved software selection is invalid; regenerate and review the package") from error
    return Response(
        content=script,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="FlipFlop-Build-{build_id}-software-install.ps1"',
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/{build_id}/getting-ready/package/{version}")
async def download_getting_ready_package(
    build_id: int,
    version: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status != "sold":
        raise HTTPException(409, "The customer package is available only after the build is sold")
    job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
    )).scalar_one_or_none()
    artifact = next((
        item for item in (job.artifact_index or [])
        if item.get("category") == "customer_package" and int(item.get("version") or 0) == version
    ), None) if job else None
    if not artifact:
        raise HTTPException(404, "Getting Ready package not found")
    # New packages keep the customer ZIP and workshop USB ZIP separate. Older
    # package records have only storage_key and remain downloadable as before.
    storage_key = artifact.get("workshop_storage_key") or artifact.get("storage_key")
    filename = artifact.get("workshop_filename") or artifact.get("filename")
    if not storage_key or not filename:
        raise HTTPException(404, "Getting Ready workshop package not found")
    try:
        path = package_path(str(storage_key))
    except GettingReadyPackageError as error:
        raise HTTPException(404, str(error)) from error
    if not path.is_file():
        raise HTTPException(404, "Getting Ready package file is missing")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=str(filename),
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{build_id}/getting-ready/dispatch-checklist")
async def download_getting_ready_dispatch_checklist(
    build_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Serve the operator-only checklist separately from the customer ZIP."""
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    try:
        checklist = render_dispatch_checklist(build.name)
    except GettingReadyPackageError as error:
        raise HTTPException(500, "Dispatch checklist template is unavailable") from error
    return Response(
        content=checklist,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="FlipFlop-Build-{build_id}-dispatch-checklist.md"',
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{build_id}/getting-ready/evidence", status_code=201)
async def upload_dispatch_evidence(
    build_id: int,
    category: str = Form(...),
    file: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Store private dispatch photos/videos for later insurance evidence."""
    build, job = await lock_manual_build_then_getting_started_job(db, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status != "sold":
        raise HTTPException(409, "Shipment evidence is available only after the build is sold")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Dispatch evidence must be captured before courier handover.")
    if build.shipment_booking_state != "booked" or not build.tracking_number or not build.shipment_booked_at:
        raise HTTPException(409, "Book the signed-for courier and obtain tracking before uploading shipment evidence.")
    if category not in {"working_pc", "package_contents", "sealed_package"}:
        raise HTTPException(422, "category must be working_pc, package_contents or sealed_package")
    media_types = {
        "image/jpeg": ("jpg", b"\xff\xd8\xff"),
        "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
        "image/webp": ("webp", b"RIFF"),
        "video/mp4": ("mp4", b"ftyp"),
        "video/quicktime": ("mov", b"ftyp"),
        "video/webm": ("webm", b"\x1a\x45\xdf\xa3"),
    }
    content_type = file.content_type or ""
    if content_type not in media_types:
        raise HTTPException(415, "Upload a JPEG, PNG, WebP, MP4, MOV, or WebM file")
    if category != "working_pc" and content_type.startswith("video/"):
        raise HTTPException(415, "Contents-before-packing and sealed-parcel evidence must be still images")
    suffix, signature = media_types[content_type]
    max_bytes = _MAX_DISPATCH_VIDEO_BYTES if content_type.startswith("video/") else _MAX_IMAGE_BYTES
    artifact_id = uuid.uuid4().hex
    build_dir = (_PRIVATE_DISPATCH_ROOT / str(build_id)).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    destination = (build_dir / f"{artifact_id}.{suffix}").resolve()
    if _PRIVATE_DISPATCH_ROOT.resolve() not in destination.parents:
        raise HTTPException(400, "Invalid evidence path")

    digest = hashlib.sha256()
    size = 0
    first_chunk = True
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"Evidence file exceeds the {max_bytes // (1024 * 1024)} MB limit")
                if first_chunk:
                    if content_type in {"video/mp4", "video/quicktime"}:
                        valid_signature = b"ftyp" in chunk[:16]
                    elif content_type == "image/webp":
                        valid_signature = len(chunk) >= 12 and chunk[:4] == b"RIFF" and chunk[8:12] == b"WEBP"
                    else:
                        valid_signature = chunk.startswith(signature)
                    if not valid_signature:
                        raise HTTPException(415, "The file contents do not match the selected media type")
                    first_chunk = False
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "Evidence file is empty")
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    commit_attempted = False
    try:
        result = await db.execute(select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id))
        job = result.scalar_one_or_none()
        if job is None:
            job = GettingStartedJob(
                manual_build_id=build_id,
                customer_id=build.customer_id,
                source_type="ready_to_ship",
                status="awaiting_admin_review",
                checklist=checklist_with_defaults(None),
            )
            db.add(job)
        artifacts = list(job.artifact_index or [])
        artifacts.append({
            "id": artifact_id,
            "category": category,
            "filename": Path(file.filename or f"evidence.{suffix}").name[:160],
            "content_type": content_type,
            "size_bytes": size,
            "sha256": digest.hexdigest(),
            "storage_key": f"{build_id}/{artifact_id}.{suffix}",
            "uploaded_at": datetime.utcnow().isoformat(),
            "uploaded_by_admin_id": admin.id,
            "uploaded_by_admin_name": admin.name,
        })
        job.artifact_index = artifacts
        category_action = {
            "working_pc": "working_pc_photo",
            "package_contents": "package_contents_photo",
            "sealed_package": "sealed_package_photo",
        }[category]
        artifacts[-1]["review_status"] = "needs_review"
        job.checklist = {
            **checklist_with_defaults(job.checklist, job.purchased_ai_services),
            category_action: "needs_review",
        }
        job.status = "awaiting_admin_review"
        commit_attempted = True
        await db.commit()
    except BaseException:
        try:
            await db.rollback()
        except BaseException:
            pass
        if not commit_attempted:
            destination.unlink(missing_ok=True)
        else:
            # A lost connection during COMMIT has an uncertain outcome: the
            # database may have committed the metadata. Keep the file so that
            # a committed artifact reference can never point at deleted bytes.
            log.error(
                "dispatch_evidence_commit_outcome_uncertain",
                build_id=build_id,
                artifact_id=artifact_id,
                storage_key=f"{build_id}/{artifact_id}.{suffix}",
            )
        raise
    return {"id": artifact_id, "category": category, "content_type": content_type, "size_bytes": size}


@router.get("/{build_id}/getting-ready/evidence/{artifact_id}")
async def download_dispatch_evidence(
    build_id: int,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
):
    job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build_id)
    )).scalar_one_or_none()
    artifact = next((item for item in (job.artifact_index or []) if item.get("id") == artifact_id), None) if job else None
    if not artifact:
        raise HTTPException(404, "Evidence file not found")
    storage_root = _PRIVATE_DISPATCH_ROOT.resolve()
    build_directory = (storage_root / str(build_id)).resolve()
    path = (_PRIVATE_DISPATCH_ROOT / str(artifact.get("storage_key") or "")).resolve()
    if (
        storage_root not in build_directory.parents
        or storage_root not in path.parents
        or build_directory not in path.parents
        or not path.is_file()
    ):
        raise HTTPException(404, "Evidence file not found")
    evidence_file = None
    try:
        expected_size = int(artifact.get("size_bytes"))
        expected_digest = str(artifact.get("sha256") or "")
        evidence_file = path.open("rb")
        if os.fstat(evidence_file.fileno()).st_size != expected_size:
            raise HTTPException(409, "Evidence file changed after upload; re-upload it before review")
        digest = hashlib.sha256()
        while chunk := evidence_file.read(1024 * 1024):
            digest.update(chunk)
        if not expected_digest or digest.hexdigest() != expected_digest:
            raise HTTPException(409, "Evidence file checksum mismatch; re-upload it before review")
        evidence_file.seek(0)
    except HTTPException:
        if evidence_file is not None:
            evidence_file.close()
        raise
    except (OSError, TypeError, ValueError) as exc:
        if evidence_file is not None:
            evidence_file.close()
        raise HTTPException(409, "Evidence file metadata is invalid; re-upload it before review") from exc

    def stream_verified_file():
        try:
            while chunk := evidence_file.read(1024 * 1024):
                yield chunk
        finally:
            evidence_file.close()

    filename = str(artifact.get("filename") or "shipment-evidence")
    return StreamingResponse(
        stream_verified_file(),
        media_type=artifact.get("content_type"),
        headers={
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "Content-Length": str(expected_size),
        },
        background=BackgroundTask(evidence_file.close),
    )


@router.post("/{build_id}/getting-ready/evidence/{artifact_id}/review")
async def review_dispatch_evidence(
    build_id: int,
    artifact_id: str,
    body: ReviewDispatchEvidenceRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Record an explicit admin review before evidence can satisfy shipment gates."""
    build, job = await lock_manual_build_then_getting_started_job(db, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status != "sold":
        raise HTTPException(409, "Shipment evidence can be reviewed only after the build is sold")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Shipment evidence cannot be reviewed after courier handover")
    artifacts = deepcopy(job.artifact_index or []) if job else []
    artifact = next((item for item in artifacts if item.get("id") == artifact_id), None)
    if not artifact or artifact.get("category") not in {"working_pc", "package_contents", "sealed_package"}:
        raise HTTPException(404, "Shipment evidence not found")
    path = (_PRIVATE_DISPATCH_ROOT / str(artifact.get("storage_key") or "")).resolve()
    if _PRIVATE_DISPATCH_ROOT.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "Shipment evidence file not found")
    review_digest = hashlib.sha256()
    with path.open("rb") as evidence_file:
        while chunk := evidence_file.read(1024 * 1024):
            review_digest.update(chunk)
    if review_digest.hexdigest() != artifact.get("sha256"):
        raise HTTPException(409, "Evidence checksum mismatch; upload the file again before review")

    artifact.update({
        "review_status": "approved" if body.approved else "rejected",
        "reviewed_at": datetime.utcnow().isoformat(),
        "reviewed_by_admin_id": admin.id,
        "reviewed_by_admin_name": admin.name,
        "review_note": body.note.strip(),
    })
    category_actions = {
        "working_pc": ("working_pc_photo", ("image/", "video/")),
        "package_contents": ("package_contents_photo", ("image/",)),
        "sealed_package": ("sealed_package_photo", ("image/",)),
    }
    action, allowed_prefixes = category_actions[artifact["category"]]
    approved_copy_exists = any(
        isinstance(item, dict)
        and item.get("category") == artifact["category"]
        and item.get("review_status") == "approved"
        and str(item.get("content_type") or "").startswith(allowed_prefixes)
        for item in artifacts
    )
    checklist = checklist_with_defaults(job.checklist, job.purchased_ai_services)
    checklist[action] = "complete" if approved_copy_exists else "needs_review"
    job.checklist = checklist
    job.artifact_index = artifacts
    job.status = "ready_for_delivery" if checklist_dispatch_ready(checklist, job.purchased_ai_services) else "awaiting_admin_review"
    job.updated_at = datetime.utcnow()
    await db.commit()
    return {
        "id": artifact_id,
        "category": artifact["category"],
        "review_status": artifact["review_status"],
        "reviewed_at": artifact["reviewed_at"],
        "reviewed_by_admin_id": admin.id,
    }


@router.get("/{build_id}", response_model=ManualBuildOut)
async def get_build(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    # FastAPI background tasks live in the API process. If that process was
    # restarted during a Meshy job, there is no task left to update the row.
    # Surface that interruption as a retryable failure instead of displaying
    # "Queued" forever.
    assets = dict(build.model_3d_assets or {})
    assets_changed = False
    stale_before = datetime.utcnow() - timedelta(minutes=15)
    for asset_type, raw_asset in list(assets.items()):
        asset = dict(raw_asset or {})
        if asset.get("status") not in {"queued", "processing"}:
            continue
        timestamp = asset.get("started_at") or asset.get("queued_at")
        try:
            queued_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).replace(tzinfo=None)
        except (TypeError, ValueError):
            queued_at = build.updated_at or datetime.utcnow()
        if queued_at < stale_before:
            asset.update(
                status="failed",
                error="The 3D generation worker was interrupted or timed out. Select the pictures and try again.",
                failed_at=datetime.utcnow().isoformat(),
            )
            assets[asset_type] = asset
            assets_changed = True
    if assets_changed:
        build.model_3d_assets = assets
        await db.flush()

    # eBay is authoritative. Poll at most once per minute while this detail
    # view is being opened/refreshed; a transient API failure remains unknown
    # and never grants permission to create a duplicate listing.
    if build.ebay_listing_id:
        try:
            from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
            await reconcile_manual_build_listing(build, db)
        except Exception as exc:
            log.warning("manual_build.ebay_reconcile_on_read_failed", build_id=build.id, error=str(exc))
            build.ebay_listing_status = "unknown"
        if build.status == "listed":
            build.status = "built"
    build.ebay_live = build.ebay_listing_status == "active"
    build.storefront_live = False
    if build.storefront_product_id:
        from app.models.product import Product, ProductStatus
        product_result = await db.execute(
            select(Product).where(Product.id == build.storefront_product_id)
        )
        product = product_result.scalar_one_or_none()
        build.storefront_live = bool(product and product.status == ProductStatus.LISTED)
    if build.ebay_live or build.storefront_live:
        build.status = "listed"
    elif build.status == "listed":
        # "listed" is reserved for a currently live sales channel. Keep
        # historical eBay state in ebay_listing_status instead.
        build.status = "built"

    return build


@router.patch("/{build_id}", response_model=ManualBuildOut)
async def patch_build(build_id: int, body: ManualBuildPatch, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id).with_for_update()
    )
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Build identity and component specification are locked after physical handover")
    if body.components is not None and build.status == "sold":
        raise HTTPException(
            409,
            "A sold build's component specification cannot be edited directly; use an approved customer order-change flow",
        )
    if body.name is not None:
        build.name = body.name
    if body.components is not None:
        build.components = [c.model_dump() for c in body.components]
        build.total_cost = sum(c.price_paid for c in body.components)
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/components/{slot}/purchase", response_model=ManualBuildOut)
async def purchase_build_component(
    build_id: int,
    slot: str,
    body: ComponentPurchaseInput,
    db: AsyncSession = Depends(get_db),
):
    """Record an external component purchase and reserve it to this draft."""
    from app.services.inventory_lifecycle import add_event, orchestration_build_for

    build = await db.get(ManualBuild, build_id)
    if not build or build.is_archived:
        raise HTTPException(404, "Build not found")
    if build.status != "in_progress":
        raise HTTPException(400, "Only draft builds can record component purchases")
    components = list(build.components or [])
    index = next((i for i, component in enumerate(components) if component.get("slot") == slot), None)
    if index is None:
        raise HTTPException(404, f"Component slot {slot} not found")
    component = dict(components[index])
    if component.get("inventory_item_id"):
        component["purchased"] = True
        components[index] = component
        build.components = components
        await db.flush()
        await db.refresh(build)
        return build

    component_type_by_slot = {
        "cpu": "cpu", "gpu": "gpu", "ram": "ram", "motherboard": "motherboard",
        "storage": "ssd", "ssd": "ssd", "psu": "psu", "pc case": "case",
        "case": "case", "cpu cooler": "cooler", "cooler": "cooler",
    }
    item = InventoryItem(
        component_name=component.get("name") or slot,
        component_type=component_type_by_slot.get(slot.lower(), slot.lower().replace(" ", "_")),
        quantity=1,
        base_price=body.price_paid if body.price_paid is not None else float(component.get("price_paid") or 0),
        shipping_cost=0,
        discount_amount=0,
        purchase_date=datetime.utcnow(),
        source=body.source or "Build purchase",
        notes=f"Purchased for draft build: {build.name}",
        listing_url=component.get("listing_url"),
        purchase_status="PURCHASED",
        reconciliation_status="PENDING" if component.get("listing_url") else "NOT_APPLICABLE",
    )
    db.add(item)
    await db.flush()
    orchestration = await orchestration_build_for(db, build)
    allocation = InventoryAllocation(
        inventory_item_id=item.id,
        build_id=orchestration.id,
        flip_id=None,
        quantity_allocated=1,
        cost_per_unit_at_allocation=item.actual_cost,
        notes=f"Reserved for draft build: {build.name}",
    )
    db.add(allocation)
    component["price_paid"] = item.actual_cost
    component["purchased"] = True
    component["inventory_item_id"] = item.id
    components[index] = component
    build.components = components
    build.total_cost = sum(float(existing.get("price_paid") or 0) for existing in components)
    add_event(db, inventory_item_id=item.id, manual_build_id=build.id, event_type="purchased", quantity=1,
              detail={"source": item.source, "listing_url": item.listing_url})
    add_event(db, inventory_item_id=item.id, manual_build_id=build.id, event_type="reserved", quantity=1,
              detail={"build_name": build.name})
    await db.flush()
    await db.refresh(build)
    return build


@router.delete("/{build_id}", status_code=204)
async def delete_build(build_id: int, db: AsyncSession = Depends(get_db)):
    """Archives the build rather than deleting it.

    A hard delete here previously left any live eBay listing (ebay_listing_id/
    ebay_sku) with no local record at all — orphaned from every reprice, Best
    Offer, and relist automation, and untraceable since the delete wasn't
    logged. Archiving keeps the row (and those eBay identifiers) intact so
    it can still be found and reconciled later.
    """
    result = await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id).with_for_update()
    )
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "A handed-over build cannot be archived or have its inventory released")
    from app.services.inventory_lifecycle import release_manual_build_inventory
    await release_manual_build_inventory(db, build, reason="draft archived")
    build.is_archived = True
    build.updated_at = datetime.utcnow()
    await db.flush()


@router.post("/{build_id}/restore", response_model=ManualBuildOut)
async def restore_build(build_id: int, db: AsyncSession = Depends(get_db)):
    """Restore an archived build to the normal Pre-Built list."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    build.is_archived = False
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/evaluate", response_model=EvaluationResult)
async def evaluate_build(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.components:
        raise HTTPException(400, "Build has no components to evaluate")

    # Format component list for the prompt
    lines = []
    for c in build.components:
        name = c["name"] if isinstance(c, dict) else c.name
        slot = c["slot"] if isinstance(c, dict) else c.slot
        price = c["price_paid"] if isinstance(c, dict) else c.price_paid
        lines.append(f"  - {slot}: {name} (paid £{price:.0f})")
    component_text = "\n".join(lines)
    total = build.total_cost or sum(
        (c["price_paid"] if isinstance(c, dict) else c.price_paid)
        for c in build.components
    )

    prompt = f"""I have assembled a PC build for resale in the UK secondhand market. Here are the components and what I paid:

{component_text}

Total cost: £{total:.0f}

Please assess this build and respond with ONLY valid JSON (no markdown, no code fences) in this exact format:
{{
  "low": <number>,
  "mid": <number>,
  "high": <number>,
  "narrative": "<2-3 sentence assessment>",
  "suggestions": [
    {{"text": "<actionable suggestion>", "uplift": <number>}},
    {{"text": "<actionable suggestion>", "uplift": <number>}},
    {{"text": "<actionable suggestion>", "uplift": <number>}}
  ]
}}

low/mid/high = estimated resale prices in GBP. uplift = estimated price increase in GBP from that suggestion. Max 3 suggestions. Be realistic about UK eBay/Gumtree prices."""

    response_text, _model = await ai_service.chat(prompt, history=[])
    if _model == "none":
        raise HTTPException(503, response_text)

    # Parse JSON from response — strip any accidental markdown fences
    raw = response_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON object from response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise HTTPException(502, f"LLM returned unparseable response: {raw[:200]}")
        data = json.loads(match.group())

    result = EvaluationResult(
        low=float(data.get("low", 0)),
        mid=float(data.get("mid", 0)),
        high=float(data.get("high", 0)),
        narrative=data.get("narrative", ""),
        suggestions=[
            EvaluationSuggestion(text=s["text"], uplift=float(s.get("uplift", 0)))
            for s in data.get("suggestions", [])[:3]
        ],
    )

    # Persist evaluation result back to the build
    build.last_evaluation = result.model_dump()
    build.updated_at = datetime.utcnow()
    await db.flush()

    return result


@router.post("/{build_id}/mark-built", response_model=ManualBuildOut)
async def mark_built(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id).with_for_update()
    )
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status not in {"in_progress", "built"}:
        raise HTTPException(409, f"A build in {build.status!r} cannot transition to Built")
    if not build.components:
        raise HTTPException(400, "Build has no components")

    unpurchased = [
        (c["slot"] if isinstance(c, dict) else c.slot)
        for c in build.components
        if not (c.get("purchased") if isinstance(c, dict) else c.purchased)
    ]
    if unpurchased:
        raise HTTPException(
            400,
            f"Every component must be marked purchased first — still waiting on: {', '.join(unpurchased)}",
        )

    build.status = "built"
    build.updated_at = datetime.utcnow()
    assignment = (build.evidence_data or {}).get("playbook_assignment") or {}
    software_profile = assignment.get("software_profile") or {}
    existing_job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build.id)
    )).scalar_one_or_none()
    if existing_job is None:
        db.add(GettingStartedJob(
            manual_build_id=build.id,
            customer_id=build.customer_id,
            playbook_id=assignment.get("playbook_id"),
            source_type="ready_to_ship",
            status="awaiting_sale_and_customer_choices",
            customer_software_selections=list(software_profile.get("recommended_package_ids") or []),
            checklist={
                "specification": "pending",
                "benchmark_results": "pending",
                "getting_started_guide": "pending",
                "software_setup": "pending_customer_selection",
                "drivers_and_firmware": "pending_review",
                "component_manuals": "pending_research",
                "upgrade_path": "pending",
                "private_media_evidence": "pending",
            },
        ))
    else:
        existing_job.playbook_id = assignment.get("playbook_id") or existing_job.playbook_id
        if not (existing_job.checklist or {}).get("software_selection_submitted") and software_profile:
            existing_job.customer_software_selections = list(software_profile.get("recommended_package_ids") or [])
    from app.services.inventory_lifecycle import record_consumption
    await record_consumption(db, build)

    # Rows 10/33/19/20: demand check + initial pricing anchor/floor fire
    # automatically once cost is finalized (all components purchased), no
    # click needed — mirrors the retired Flip system's create_flip hook.
    try:
        from app.services import demand_check as demand_check_service
        from app.services.pricing_engine import _component_spec

        signal = await demand_check_service.check_demand(
            _component_spec(build, "CPU"), _component_spec(build, "GPU")
        )
        build.demand_sold_count_90d = signal.sold_count_90d
        build.demand_active_count = signal.active_count
        build.demand_checked_at = signal.checked_at
    except Exception as exc:
        log.warning("manual_builds.demand_check.failed", build_id=build.id, error=str(exc))

    try:
        await pricing_engine.recalculate_manual_build_pricing(build, db)
    except Exception as exc:
        log.warning("manual_builds.pricing_recalc.failed", build_id=build.id, error=str(exc))

    await db.flush()
    await db.refresh(build)
    return build


@router.get("/{build_id}/component-ratings")
async def get_component_ratings(build_id: int, db: AsyncSession = Depends(get_db)):
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    ratings = (await db.execute(
        select(ComponentRatingEvent).where(ComponentRatingEvent.build_id == build_id)
    )).scalars().all()
    return [{
        "component_slot": rating.component_slot, "component_key": rating.component_key,
        "overall_rating": rating.overall_rating, "reliability_rating": rating.reliability_rating,
        "installation_rating": rating.installation_rating, "aesthetics_rating": rating.aesthetics_rating,
        "value_rating": rating.value_rating, "customer_appeal_rating": rating.customer_appeal_rating,
        "notes": rating.notes,
    } for rating in ratings]


@router.put("/{build_id}/component-ratings")
async def save_component_ratings(
    build_id: int,
    body: ComponentRatingsInput,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status not in ("built", "listed", "sold"):
        raise HTTPException(400, "Component ratings become available after the build is marked built")
    valid_components = {
        (str(component.get("slot", "")).lower(), str(component.get("name", "")).strip().lower())
        for component in build.components if isinstance(component, dict)
    }
    alerts_created = 0
    alerts_updated = 0
    for incoming in body.ratings:
        identity = (incoming.component_slot.lower(), incoming.component_key.strip().lower())
        if identity not in valid_components:
            raise HTTPException(400, f"{incoming.component_slot}: component does not match this build")
        rating = (await db.execute(select(ComponentRatingEvent).where(
            ComponentRatingEvent.build_id == build_id,
            ComponentRatingEvent.component_slot == incoming.component_slot,
            ComponentRatingEvent.component_key == incoming.component_key,
        ))).scalar_one_or_none()
        values = incoming.model_dump()
        was_five_star = rating is not None and rating.overall_rating == 5
        if rating is None:
            rating = ComponentRatingEvent(build_id=build_id, **values)
            db.add(rating)
        else:
            for key, value in values.items():
                setattr(rating, key, value)
            rating.updated_at = datetime.utcnow()

        preferred = (await db.execute(select(PreferredComponent).where(
            PreferredComponent.component_key == incoming.component_key
        ))).scalar_one_or_none()
        if incoming.overall_rating == 5 and not was_five_star:
            if preferred is None:
                db.add(PreferredComponent(
                    component_key=incoming.component_key, component_slot=incoming.component_slot,
                    sample_count=1, average_rating=5.0, status="preferred",
                    last_build_id=build_id, last_used_at=datetime.utcnow(),
                ))
            else:
                preferred.average_rating = (
                    preferred.average_rating * preferred.sample_count + incoming.overall_rating
                ) / (preferred.sample_count + 1)
                preferred.sample_count += 1
                preferred.status = "preferred"
                preferred.last_build_id = build_id
                preferred.last_used_at = datetime.utcnow()
        if incoming.overall_rating == 5:
            component = next(
                item for item in build.components
                if str(item.get("slot", "")).lower() == incoming.component_slot.lower()
                and str(item.get("name", "")).strip().lower() == incoming.component_key.strip().lower()
            )
            # A five-star rating requests monitoring; it does not prove market
            # identity. Only an upstream CPK may arm the component alert.
            component_cpk = str(component.get("cpk") or "").strip() or None
            condition_cohort = str(component.get("condition") or "used").lower()
            if condition_cohort not in {"new", "used"}:
                condition_cohort = "used"
            alert = (await db.execute(select(PriceAlert).where(
                PriceAlert.alert_type == "component",
                PriceAlert.owner_admin_id == admin.id,
                (PriceAlert.cpk == component_cpk) if component_cpk else (PriceAlert.component_key == incoming.component_key),
            ))).scalar_one_or_none()
            if alert is None:
                db.add(PriceAlert(
                    manual_build_id=None,
                    owner_admin_id=admin.id,
                    alert_type="component",
                    component_key=incoming.component_key,
                    component_slot=incoming.component_slot,
                    cpk=component_cpk,
                    condition_cohort=condition_cohort,
                    monitoring_status="pending_evidence" if component_cpk else "pending_identity",
                    market_reference_price_gbp=None,
                    reference_basis=None,
                    reference_evidence_json={
                        "purchase_price_gbp": component.get("price_paid"),
                        "note": "Purchase price is informational and is not market evidence",
                    },
                    discount_threshold_pct=15.0,
                    target_price_gbp=None,
                    user_email=admin.email,
                    is_active=True,
                ))
                alerts_created += 1
            else:
                alert.component_slot = incoming.component_slot
                alert.owner_admin_id = admin.id
                if alert.monitoring_status == "pending_identity" and component_cpk:
                    alert.cpk = component_cpk
                    alert.monitoring_status = "pending_evidence"
                alert.condition_cohort = condition_cohort
                alert.discount_threshold_pct = 15.0
                alert.user_email = admin.email
                alert.is_active = True
                alerts_updated += 1
    await db.flush()
    return {
        "saved": len(body.ratings),
        "preferred_added": sum(r.overall_rating == 5 for r in body.ratings),
        "alerts_created": alerts_created,
        "alerts_updated": alerts_updated,
    }


@router.post("/{build_id}/generate-listing", response_model=GenerateListingResult)
async def generate_listing(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status not in ("built", "listed", "sold"):
        raise HTTPException(400, "Build must be marked built before generating a listing")

    lines = []
    for c in build.components:
        name = c["name"] if isinstance(c, dict) else c.name
        slot = c["slot"] if isinstance(c, dict) else c.slot
        lines.append(f"  - {slot}: {name}")
    component_text = "\n".join(lines)

    system_prompt = _load_ebay_listing_system_prompt()
    selling_principles = _load_selling_principles()

    # This build's own evidence — spec card and registration plate data are
    # entirely derivable from fields already on the build (components,
    # name), so they're auto-populated unless the seller has uploaded more
    # specific JSON via PUT /{build_id}/evidence-data. Performance data has
    # no such fallback — it only exists if uploaded for this exact build.
    # All of it goes to the LLM as plain JSON text, never as an image —
    # no vision model involved.
    evidence = build.evidence_data or {}
    spec_card_data = evidence.get("spec_card") or {
        "pc_name": build.name,
        "components": [
            {"slot": (c["slot"] if isinstance(c, dict) else c.slot), "name": (c["name"] if isinstance(c, dict) else c.name)}
            for c in build.components
        ],
    }
    registration_plate_data = evidence.get("registration_plate") or {"pc_name": build.name}
    performance_card_data = evidence.get("performance_card") or _load_build_performance_evidence(build.name)

    shipping_labels = {
        "tracked": "Tracked courier delivery",
        "untracked": "Untracked delivery",
        "local_pickup": "Local pickup",
    }
    delivery_method = shipping_labels.get(build.shipping_method, build.shipping_method or "Not set")

    materials = f"""ITEM TYPE: Desktop PC
BRAND: flipflop
PRODUCT NAME: {build.name}
EBAY CATEGORY: PC Desktops & All-in-Ones
CONDITION SELECTION: {build.ebay_condition or "Not set"}

FULL SPECIFICATIONS:
{component_text}

SPECIFICATION CARD DATA (JSON):
{json.dumps(spec_card_data, indent=2)}

REGISTRATION PLATE DATA (JSON):
{json.dumps(registration_plate_data, indent=2)}

MEASURED BENCHMARKS / TEMPERATURES / STABILITY RESULTS (JSON):
{json.dumps(performance_card_data, indent=2) if performance_card_data else "None supplied — omit the PERFORMANCE YOU CAN COUNT ON section or place it under INFORMATION REQUIRED"}

RETURNS POLICY: {f"{build.return_days} day returns" if build.return_days else "No voluntary returns period set"}
CHANGE-OF-MIND RETURN POSTAGE: Customer pays the return postage. The PC must be returned securely packed and in the condition received.
FAULTY / DAMAGED / MISDESCRIBED RETURN POSTAGE: flipflop pays the reasonable return postage.
CONSUMER RIGHTS: The buyer's UK statutory rights are not affected. A faulty or misdescribed item remains covered by those rights regardless of the voluntary returns period.
SUPPORT: Direct setup and after-sales support is available from flipflop. Manufacturer warranties are passed on where transferable.

DELIVERY METHOD: {delivery_method}
DISPATCH TIME: {build.handling_time_days} business day(s)
COLLECTION AVAILABLE: No — delivery only, collection is never offered on any listing
COLLECTION TESTING AVAILABLE: Not applicable — no collection offered

PRICE: {f"£{build.ebay_price}" if build.ebay_price else "Not yet set"}
BEST OFFER ENABLED: {"Yes" if build.allow_offers else "No"}
"""

    if selling_principles:
        materials += f"\n\nADDITIONAL SELLER GUIDANCE (house style — follow alongside the system instructions above):\n{selling_principles}\n"

    try:
        raw_response, _model = await ai_service.generate_ebay_listing(system_prompt, materials)
    except ValueError as e:
        raise HTTPException(503, f"OpenRouter API not configured: {str(e)}")
    except Exception as e:
        raise HTTPException(502, f"Listing generation failed: {str(e)}")

    title = _extract_recommended_title(raw_response)
    description_html = _extract_html_section(raw_response)

    if not title or not description_html:
        raise HTTPException(
            502,
            "The AI response didn't include a parseable title or HTML section — "
            f"raw response (first 800 chars): {raw_response[:800]}",
        )

    if build.hero_photo_url:
        description_html = description_html.replace("{{HERO_IMAGE_URL}}", build.hero_photo_url)
    elif "{{HERO_IMAGE_URL}}" in description_html:
        import structlog

        structlog.get_logger(__name__).warning(
            "generate_listing.hero_image_placeholder_unfilled",
            build_id=build_id,
            reason="build has no hero_photo_url set — upload a photo first",
        )

    prepared_description = prepare_ebay_listing_description(
        _description_with_selected_faqs(description_html, build)
    )
    build.generated_title = title[:80]
    build.generated_description = prepared_description
    build.updated_at = datetime.utcnow()
    await db.flush()

    return GenerateListingResult(
        titles=[title],
        description=prepared_description,
        aspects=build.generated_aspects or {},
    )


@router.post("/{build_id}/generate-specifics", response_model=GenerateListingResult)
async def generate_specifics(build_id: int, db: AsyncSession = Depends(get_db)):
    """Generate eBay Item Specifics using LLM with validated eBay values only."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.components:
        raise HTTPException(400, "Build must have components to generate specifics")

    selling_principles = _load_selling_principles()
    aspects = await generate_item_specifics(build, selling_principles)

    build.generated_aspects = aspects
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)

    return GenerateListingResult(
        titles=build.generated_title.split(",") if build.generated_title else [],
        description=build.generated_description or "",
        aspects=aspects
    )


@router.patch("/{build_id}/collection-date")
async def set_collection_date(
    build_id: int,
    body: CollectionDateInput,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    build = (await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id).with_for_update()
    )).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Collection cannot be changed after courier handover")
    build.collection_date = body.collection_date
    build.dispatch_status = "collection_scheduled"
    build.updated_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "collection_date": body.collection_date.isoformat(), "dispatch_status": build.dispatch_status}


@router.post("/{build_id}/courier-quote", response_model=list[CourierQuoteOut])
async def get_courier_quote(
    build_id: int, delivery_country: str | None = None, db: AsyncSession = Depends(get_db)
):
    """Cheapest real tracked-delivery quote for this build's saved package
    dimensions, via Parcel2Go — see app/services/parcel2go_courier.py.
    Requires package_weight_kg/length_cm/width_cm/height_cm to already be
    set on the build (via PATCH .../ebay-config) — deliberately doesn't
    guess them from components."""
    import structlog
    log = structlog.get_logger(__name__)

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    log.info("courier_quote.request", build_id=build_id,
             weight=build.package_weight_kg, length=build.package_length_cm,
             width=build.package_width_cm, height=build.package_height_cm,
             ebay_price=build.ebay_price, total_cost=build.total_cost)

    missing = [
        field
        for field in ("package_weight_kg", "package_length_cm", "package_width_cm", "package_height_cm")
        if getattr(build, field) is None
    ]
    if missing:
        log.warning("courier_quote.missing_dimensions", build_id=build_id, missing=missing)
        raise HTTPException(
            400,
            f"Set the build's package dimensions first (missing: {', '.join(missing)}) "
            "before requesting a courier quote.",
        )

    # Prefer the real sale price once the build has actually sold and synced
    # (see sync_ebay_order below) — ebay_price/total_cost are pre-sale
    # estimates. Parcel2Go requires a non-zero insurance value either way.
    value_gbp = build.sale_price_actual or build.ebay_price or build.total_cost
    if not value_gbp or value_gbp <= 0:
        log.warning("courier_quote.zero_value", build_id=build_id, ebay_price=build.ebay_price, total_cost=build.total_cost)
        raise HTTPException(
            400,
            "Set either ebay_price or total_cost (must be > £0) before requesting a courier quote."
        )

    # If the real buyer address has been synced, default to their actual
    # country rather than assuming domestic GBR.
    resolved_country = delivery_country
    if resolved_country is None:
        resolved_country = (build.buyer_address_json or {}).get("country_code")
        if resolved_country == "GB":
            resolved_country = "GBR"
    resolved_country = resolved_country or "GBR"

    try:
        quotes = await get_tracked_quotes(
            weight_kg=build.package_weight_kg,
            length_cm=build.package_length_cm,
            width_cm=build.package_width_cm,
            height_cm=build.package_height_cm,
            value_gbp=value_gbp,
            delivery_country=resolved_country,
        )
    except Parcel2GoError as e:
        raise HTTPException(e.status_code or 502, str(e))

    if not quotes:
        raise HTTPException(404, "No tracked courier service found for this destination/parcel size")

    return [CourierQuoteOut(
        courier_name=quote.courier_name, service_name=quote.service_name,
        price_gbp=quote.price_gbp, tracked=quote.tracked,
        estimated_days=quote.estimated_days, service_slug=quote.service_slug,
        signature_tracking=quote.signature_tracking,
        protection_scope=quote.protection_scope,
        full_value_damage_cover=quote.full_value_damage_cover,
        protection_warning=quote.protection_warning,
    ) for quote in quotes]


@router.post("/{build_id}/insurance-quote", response_model=InsuranceQuoteOut)
async def get_build_insurance_quote(
    build_id: int,
    listing_value_gbp: float = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Get a live Figural premium for the full current listing value.

    Price lookup only: this endpoint cannot create, reserve, or charge for an
    insurance policy. Cover is purchased later, after the item sells.
    """
    result = await db.execute(select(ManualBuild.id).where(ManualBuild.id == build_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, "Build not found")
    try:
        quote = await get_insurance_quote(listing_value_gbp)
    except FiguralError as error:
        raise HTTPException(error.status_code or 502, str(error))
    return InsuranceQuoteOut(
        provider="Figural",
        insured_value_gbp=quote.insured_value_gbp,
        price_gbp=quote.price_gbp,
        currency=quote.currency,
    )


@router.post("/{build_id}/insurance-policy")
async def create_build_insurance_policy(
    build_id: int,
    body: CreateInsurancePolicyRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Create one actual provider policy after fresh quote and explicit confirmation."""
    settings = get_settings()
    if not settings.secursus_live_parcel_creation_enabled:
        raise HTTPException(409, "Live insurance purchase is disabled until the provider approves this account and shipment use.")
    if not all((
        body.confirm_terms,
        body.confirm_live_purchase,
        body.confirm_customer_data_share,
        body.confirm_signed_for_delivery,
        body.confirm_double_packaging,
        body.confirm_discreet_packaging,
        body.confirm_rigid_outer_container,
        body.confirm_contents_not_deducible,
        body.confirm_direct_signature,
        body.confirm_official_carrier_handover,
    )):
        raise HTTPException(422, "Confirm new double packaging, rigid outer packaging, discreet contents, direct signature, official carrier handover, insurer terms, customer data sharing, and the displayed premium before purchase.")

    build = (await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id).with_for_update()
    )).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status != "sold":
        raise HTTPException(409, "Insurance can be purchased only after the build is sold")
    if build.shipping_insurance_policy_id:
        return {
            "status": "created",
            "policy_id": build.shipping_insurance_policy_id,
            "invoice_id": build.shipping_insurance_invoice_id,
            "cost_gbp": build.shipping_insurance_cost_gbp,
            "idempotent": True,
        }
    if build.shipping_insurance_status in {"creating", "creation_uncertain"}:
        raise HTTPException(409, "A policy request may already have reached the insurer. Reconcile the provider account before retrying.")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Insurance cannot be purchased after physical courier handover or delivery.")
    if build.shipment_booking_state != "booked" or not build.tracking_number or not build.shipment_booked_at:
        raise HTTPException(409, "Book the signed-for courier and obtain its tracking number before purchasing cover.")
    booking_confirmation = (build.evidence_data or {}).get("shipment_booking_confirmation") or {}
    if not booking_confirmation.get("signature_extra_included"):
        raise HTTPException(409, "Obtain a fresh courier quote and book a service with the Signature extra before buying insurance")
    evidence_job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build.id)
    )).scalar_one_or_none()
    missing_photos = _missing_verified_dispatch_evidence(
        evidence_job, build.id, INSURANCE_REQUIRED_PHOTO_CATEGORIES
    )
    if missing_photos:
        raise HTTPException(
            409,
            "Approved pre-shipment photos are missing or have changed; re-upload and review: "
            + ", ".join(missing_photos),
        )

    value_gbp = build.sale_price_actual
    delivery = dict(build.buyer_address_json or {})
    customer_email = build.customer_email
    buyer_name = build.buyer_name or delivery.get("contact_name") or ""
    linked_order = None
    if build.storefront_product_id:
        linked_order = (await db.execute(
            select(Order)
            .join(Product, Product.sold_order_id == Order.id)
            .where(Product.id == build.storefront_product_id)
            .limit(1)
        )).scalar_one_or_none()
    if linked_order:
        value_gbp = linked_order.customer_price
        customer = await db.get(Customer, linked_order.customer_id)
        customer_email = customer_email or (customer.email if customer else None)
        buyer_name = buyer_name or (customer.name if customer else "")
        order_specs = linked_order.specs or {}
        delivery = delivery or order_specs.get("delivery_address") or order_specs.get("shipping_address") or {}
        if not delivery and customer and customer.address:
            try:
                parsed_address = json.loads(customer.address)
                delivery = parsed_address if isinstance(parsed_address, dict) else {}
            except (TypeError, ValueError):
                delivery = {}
    if not value_gbp or value_gbp <= 0:
        raise HTTPException(409, "A confirmed paid sale value is required before insuring this parcel.")
    if not customer_email or not buyer_name or not delivery:
        raise HTTPException(409, "The buyer's verified name, email and delivery address must be on the order before insurance is created.")

    country_map = {"GBR": "gb", "GB": "gb", "UK": "gb", "USA": "us", "US": "us"}
    destination_country = str(delivery.get("country_code") or delivery.get("country") or "").strip().upper()
    origin_country = str(settings.seller_address_country_iso or "GB").strip().upper()
    destination_country = country_map.get(destination_country, destination_country.lower())
    origin_country = country_map.get(origin_country, origin_country.lower())
    if len(destination_country) != 2 or len(origin_country) != 2:
        raise HTTPException(422, "The insurer requires valid two-letter origin and destination country codes.")

    quote = await get_insurance_quote(value_gbp)
    if str(quote.currency or "").upper() != "GBP":
        raise HTTPException(502, "The insurer returned a premium outside GBP. No policy was created; check the provider configuration.")
    if not _gbp_amounts_match_to_penny(quote.price_gbp, body.quoted_price_gbp):
        raise HTTPException(409, f"The fresh premium is £{quote.price_gbp:.2f}; review and confirm the new price before buying.")

    name_parts = buyer_name.strip().split(maxsplit=1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else first_name
    address_lines = [
        delivery.get("address_line1") or delivery.get("line1"),
        delivery.get("address_line2") or delivery.get("line2"),
        delivery.get("city"),
        delivery.get("state_or_province") or delivery.get("county"),
        delivery.get("postal_code") or delivery.get("postcode"),
        delivery.get("country_name") or delivery.get("country") or destination_country.upper(),
    ]
    full_address = ", ".join(str(line).strip() for line in address_lines if line)
    if not all([address_lines[0], address_lines[2], address_lines[4]]):
        raise HTTPException(409, "The insurer requires a street address, town/city and postcode.")
    cart_data = {
        "build_id": build.id,
        "build_name": build.name,
        "sale_value_gbp": round(float(value_gbp), 2),
        "components": build.components or [],
        "tracking_number": build.tracking_number,
    }
    policy_payload = {
        "parcel_value": round(float(value_gbp) * 100),
        "first_name": first_name,
        "last_name": last_name,
        "email": customer_email,
        "full_address": full_address,
        "country_origin": origin_country,
        "country_destination": destination_country,
        "internal_reference": f"BUILD-{build.id}",
        "cart_data": cart_data,
        "recipient_email": customer_email,
        "recipient_lang": "en",
    }
    if not booking_confirmation.get("signed_for_delivery_confirmed"):
        booking_confirmation = {
            "signed_for_delivery_confirmed": True,
            "service_slug": build.parcel2go_service_slug,
            "confirmed_at": datetime.utcnow().isoformat(),
            "confirmed_during_insurance_purchase": True,
        }
        build.evidence_data = {
            **(build.evidence_data or {}),
            "shipment_booking_confirmation": booking_confirmation,
        }
    evidence_data = dict(build.evidence_data or {})
    evidence_data["insurance_packaging_confirmation"] = {
        "new_resistant_double_packaging_confirmed": True,
        "rigid_outer_container_confirmed": True,
        "contents_not_deducible_by_touch_confirmed": True,
        "double_packaging_confirmed": True,
        "discreet_packaging_confirmed": True,
        "direct_signature_confirmed": True,
        "official_carrier_handover_confirmed": True,
        "confirmed_at": datetime.utcnow().isoformat(),
        "confirmed_by": getattr(admin, "email", None) or "admin",
    }
    evidence_data["insurance_policy_creation"] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "attempted_by": getattr(admin, "email", None) or "admin",
        "attempted_by_admin_id": getattr(admin, "id", None),
        "confirmed_premium_gbp": round(float(quote.price_gbp), 2),
        "insured_value_gbp": round(float(value_gbp), 2),
        "currency": quote.currency,
    }
    build.evidence_data = evidence_data
    build.shipping_insurance_status = "creating"
    await db.commit()

    try:
        policy = await create_insurance_policy(policy_payload)
    except FiguralError as error:
        locked = await db.get(ManualBuild, build_id)
        if locked:
            locked.shipping_insurance_status = "creation_uncertain" if (error.status_code or 500) >= 500 else "creation_failed"
            await db.commit()
        raise HTTPException(error.status_code or 502, str(error)) from error

    locked = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id).with_for_update())).scalar_one()
    response_mismatches = []
    provider_policy_id = str(policy.policy_id or "").strip()
    policy_id_usable = (
        bool(provider_policy_id)
        and len(provider_policy_id) <= 200
        and not any(ord(character) < 32 or ord(character) == 127 for character in provider_policy_id)
    )
    if not policy_id_usable:
        response_mismatches.append("provider policy ID is missing or invalid")
    if not _gbp_amounts_match_to_penny(policy.insured_value_gbp, value_gbp):
        response_mismatches.append("insured value differs from the recorded sale value")
    if not _gbp_amounts_match_to_penny(policy.price_gbp, quote.price_gbp):
        response_mismatches.append("provider premium differs from the confirmed quote")
    if str(policy.currency or "").upper() != "GBP":
        response_mismatches.append("provider currency is not GBP")
    if str(policy.mode or "").casefold() != "production":
        response_mismatches.append("provider policy is not in production mode")
    if response_mismatches:
        evidence = dict(locked.evidence_data or {})
        attempt = dict(evidence.get("insurance_policy_creation") or {})
        # Keep the returned provider reference for operator reconciliation,
        # but do not attach it to the dispatch-valid policy fields until an
        # administrator has checked the provider account and resolved it.
        attempt["provider_response"] = {
            "policy_id": provider_policy_id if policy_id_usable else None,
            "invoice_id": policy.invoice_id,
            "insured_value_gbp": policy.insured_value_gbp,
            "price_gbp": policy.price_gbp,
            "currency": policy.currency,
            "mode": policy.mode,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "mismatches": response_mismatches,
        }
        evidence["insurance_policy_creation"] = attempt
        locked.evidence_data = evidence
        locked.shipping_insurance_status = "creation_uncertain"
        await db.commit()
        raise HTTPException(
            409,
            f"The insurer returned policy {provider_policy_id if policy_id_usable else '(no usable policy reference)'}, but its policy ID, insured value, premium, currency or mode did not match live cover requirements. Dispatch remains blocked; check the provider account and reconcile this policy before proceeding.",
        )

    locked.shipping_insurance_policy_id = policy.policy_id
    locked.shipping_insurance_invoice_id = policy.invoice_id
    locked.shipping_insurance_cost_gbp = policy.price_gbp
    locked.shipping_insurance_created_at = datetime.utcnow()
    locked.shipping_insurance_status = "created"
    locked.shipping_damage_cover_confirmed = True
    await db.commit()
    return {
        "status": "created",
        "policy_id": policy.policy_id,
        "invoice_id": policy.invoice_id,
        "insured_value_gbp": policy.insured_value_gbp,
        "cost_gbp": policy.price_gbp,
        "currency": policy.currency,
        "mode": policy.mode,
        "idempotent": False,
    }


@router.post("/{build_id}/insurance-policy/reconcile")
async def reconcile_build_insurance_policy(
    build_id: int,
    body: ReconcileInsurancePolicyRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Resolve an uncertain insurer create request after checking its account."""
    if not body.provider_checked:
        raise HTTPException(422, "Confirm that you checked the insurer account before reconciling this request")
    build = (await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id).with_for_update()
    )).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Insurance reconciliation is closed after physical handover")
    if build.status != "sold":
        raise HTTPException(409, "Insurance reconciliation is available only for a sold build")
    if build.shipment_booking_state != "booked" or not build.tracking_number or not build.shipment_booked_at:
        raise HTTPException(409, "Insurance reconciliation requires this build's confirmed courier booking and tracking number")
    evidence = dict(build.evidence_data or {})
    attempt = evidence.get("insurance_policy_creation") or {}
    raw_reconciliations = evidence.get("insurance_policy_reconciliations")
    reconciliation_history = [item for item in raw_reconciliations if isinstance(item, dict)] if isinstance(raw_reconciliations, list) else []
    if build.shipping_insurance_policy_id:
        if body.resolution == "policy_exists" and body.policy_id == build.shipping_insurance_policy_id:
            if (not body.provider_tracking_number or not build.tracking_number
                    or body.provider_tracking_number.strip().casefold() != build.tracking_number.strip().casefold()):
                raise HTTPException(409, "The provider policy tracking number does not match this build's booked parcel")
            if (body.cost_gbp is not None and build.shipping_insurance_cost_gbp is not None
                    and not _gbp_amounts_match_to_penny(body.cost_gbp, build.shipping_insurance_cost_gbp)):
                raise HTTPException(409, "The supplied premium conflicts with the linked insurer policy")
            linked_insured_value = (
                attempt.get("insured_value_gbp")
                if isinstance(attempt, dict) and attempt.get("insured_value_gbp") is not None
                else build.sale_price_actual
            )
            if (body.insured_value_gbp is not None and linked_insured_value is not None
                    and not _gbp_amounts_match_to_penny(body.insured_value_gbp, linked_insured_value)):
                raise HTTPException(409, "The supplied insured value conflicts with the linked insurer policy")
            return {"status": "created", "policy_id": build.shipping_insurance_policy_id, "idempotent": True}
        raise HTTPException(409, "A policy is already linked; this reconciliation conflicts with the saved policy")
    if (build.shipping_insurance_status == "creation_failed" and body.resolution == "no_policy"
            and reconciliation_history and isinstance(reconciliation_history[-1], dict)
            and reconciliation_history[-1].get("resolution") == "no_policy"):
        return {"status": "creation_failed", "policy_id": None, "idempotent": True}
    if build.shipping_insurance_status not in {"creating", "creation_uncertain"}:
        raise HTTPException(409, "Only an uncertain policy creation can be reconciled")
    if build.shipping_insurance_status == "creating":
        started_at = (attempt.get("started_at") if isinstance(attempt, dict) else None) or (
            build.updated_at.isoformat() if build.updated_at else None
        )
        try:
            started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise HTTPException(409, "The in-flight insurer request has no reliable start time; do not reconcile or retry it automatically")
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - started.astimezone(timezone.utc) < timedelta(minutes=2):
            raise HTTPException(409, "The insurer request may still be in flight. Wait at least two minutes, then check the provider account before reconciling.")

    if body.resolution == "policy_exists":
        if (not body.policy_id or not body.policy_id.strip() or not body.provider_tracking_number
                or body.cost_gbp is None or body.insured_value_gbp is None):
            raise HTTPException(422, "Enter the provider policy ID, parcel tracking number, insured value and premium shown in the insurer account")
        provider_response = attempt.get("provider_response") if isinstance(attempt, dict) else None
        if isinstance(provider_response, dict):
            reported_policy_id = str(provider_response.get("policy_id") or "").strip()
            if not reported_policy_id or reported_policy_id != body.policy_id.strip():
                raise HTTPException(409, "The original insurer response did not provide this policy ID; keep dispatch blocked and resolve the policy with the provider before attaching it")
            if str(provider_response.get("currency") or "").upper() != "GBP":
                raise HTTPException(409, "The insurer response was not in GBP. Keep dispatch blocked and resolve the policy with the provider before attaching it")
            if str(provider_response.get("mode") or "").casefold() != "production":
                raise HTTPException(409, "The insurer response is not a production policy. Keep dispatch blocked and obtain valid live cover before proceeding")
            if not _gbp_amounts_match_to_penny(provider_response.get("insured_value_gbp"), body.insured_value_gbp):
                raise HTTPException(409, "The reconciled insured value conflicts with the policy returned by the original request")
            if not _gbp_amounts_match_to_penny(provider_response.get("price_gbp"), body.cost_gbp):
                raise HTTPException(409, "The reconciled premium conflicts with the policy returned by the original request")
        if not build.tracking_number or body.provider_tracking_number.strip().casefold() != build.tracking_number.strip().casefold():
            raise HTTPException(409, "The provider policy tracking number does not match this build's booked parcel")
        expected_sale_value = build.sale_price_actual
        if build.storefront_product_id:
            sold_order = (await db.execute(
                select(Order)
                .join(Product, Product.sold_order_id == Order.id)
                .where(Product.id == build.storefront_product_id)
                .limit(1)
            )).scalar_one_or_none()
            if sold_order:
                expected_sale_value = sold_order.customer_price
        if not expected_sale_value or not _gbp_amounts_match_to_penny(expected_sale_value, body.insured_value_gbp):
            raise HTTPException(409, "The provider policy insured value does not match this build's recorded sale value")
        build.shipping_insurance_policy_id = body.policy_id.strip()
        build.shipping_insurance_invoice_id = body.invoice_id.strip() if body.invoice_id else None
        build.shipping_insurance_cost_gbp = body.cost_gbp
        build.shipping_insurance_created_at = build.shipping_insurance_created_at or datetime.utcnow()
        build.shipping_insurance_status = "created"
        build.shipping_damage_cover_confirmed = True
    else:
        build.shipping_insurance_status = "creation_failed"

    reconciliations = reconciliation_history
    reconciliations.append({
        "resolution": body.resolution,
        "provider_checked": True,
        "policy_id": body.policy_id.strip() if body.policy_id else None,
        "invoice_id": body.invoice_id.strip() if body.invoice_id else None,
        "provider_tracking_number": body.provider_tracking_number.strip() if body.provider_tracking_number else None,
        "insured_value_gbp": body.insured_value_gbp,
        "cost_gbp": body.cost_gbp,
        "note": body.note.strip(),
        "actor": getattr(admin, "email", None) or "admin",
        "recorded_at": datetime.utcnow().isoformat(),
    })
    evidence["insurance_policy_reconciliations"] = reconciliations[-100:]
    build.evidence_data = evidence
    build.updated_at = datetime.utcnow()
    await db.commit()
    return {
        "status": build.shipping_insurance_status,
        "policy_id": build.shipping_insurance_policy_id,
        "cost_gbp": build.shipping_insurance_cost_gbp,
        "idempotent": False,
    }


@router.post("/{build_id}/sync-ebay-order", response_model=SyncEbayOrderResult)
async def sync_ebay_order(build_id: int, db: AsyncSession = Depends(get_db)):
    """Fetches this build's real eBay order — buyer name, actual delivery
    address, actual sale price — once it's sold. This data only exists
    after a real buyer has paid; it's never available at listing time.
    Requires ebay_listing_id to already be set (i.e. the build was actually
    posted to eBay). Safe to call again later — it just re-fetches and
    overwrites with the current order state."""
    # Unlocked existence/precondition check first — fast-fail path, no lock
    # held across the eBay API call below.
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.ebay_listing_id:
        raise HTTPException(400, "This build has no eBay listing ID — it hasn't been posted to eBay yet.")

    settings = get_settings()
    try:
        order = await find_order_for_listing(
            build.ebay_listing_id, environment=settings.ebay_listing_environment, db=db
        )
    except EbayOrderSyncError as e:
        raise HTTPException(e.status_code or 502, str(e))

    if order is None:
        raise HTTPException(
            404,
            "No paid order found for this listing yet — it may not have sold, "
            "or the sale is older than the lookback window.",
        )

    # FOR UPDATE taken only now, right before the write — not across the eBay
    # API call above. Global lock order across this codebase's cross-channel
    # paths is always ManualBuild before Product (see cross_channel_guard.py
    # and public_showcase.py's confirm_checkout), to avoid an ABBA deadlock
    # between this route and the storefront-checkout route, which both touch
    # the same ManualBuild/Product pair when a sale is confirmed.
    locked_result = await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id).with_for_update()
    )
    build = locked_result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    build.ebay_order_id = order.order_id
    build.buyer_name = order.buyer_address.contact_name
    # line_item_id is embedded here (not its own column) since it's only
    # ever needed alongside the address, to push tracking back in
    # book_shipment below.
    build.buyer_address_json = {**order.buyer_address.to_dict(), "line_item_id": order.line_item_id}
    if build.customer_id:
        customer = await db.get(Customer, build.customer_id)
        if customer:
            customer.address = json.dumps(build.buyer_address_json)
            customer.phone = build.buyer_address_json.get("phone")
    build.sale_price_actual = order.sale_price
    build.status = "sold"
    from app.services.getting_started_jobs import ensure_manual_build_job
    await ensure_manual_build_job(db, manual_build_id=build.id)
    if build.warranty_started_at or build.delivered_at:
        from app.services.warranty_service import ensure_manual_build_reserve, recalculate_reserve_status
        reserve = await ensure_manual_build_reserve(
            db, build, build.warranty_started_at or build.delivered_at
        )
        if reserve is not None:
            await recalculate_reserve_status(db, reserve)
    from app.services.inventory_lifecycle import record_sale
    await record_sale(db, build, order.sale_price)
    build.updated_at = datetime.utcnow()
    await db.flush()

    # This build just sold on eBay — pull any matching storefront listing
    # so the same physical unit can't also sell there. See
    # app/services/cross_channel_guard.py. Still within the ManualBuild lock
    # taken above, then takes the Product lock — ManualBuild-before-Product,
    # matching the global order.
    await withdraw_storefront_for_sold_build(build, db)
    await db.commit()

    return SyncEbayOrderResult(
        ebay_order_id=order.order_id,
        buyer_name=order.buyer_address.contact_name,
        buyer_address=BuyerAddressOut(**order.buyer_address.to_dict()),
        sale_price_actual=order.sale_price,
    )


@router.post("/{build_id}/book-shipment", response_model=BookShipmentResult)
async def book_shipment(
    build_id: int,
    body: BookShipmentRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Books and pays for a real Parcel2Go shipment using the build's real,
    already-synced buyer address (see sync_ebay_order above). The tracking
    number is pushed to eBay only after physical carrier handover is confirmed
    by the separate dispatch action.

    This is the one step in the whole shipping flow that spends real money —
    it only runs when explicitly called from the "Book & Pay" button the
    seller clicks after reviewing the quoted price, never automatically."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id).with_for_update())
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    if build.status != "sold":
        raise HTTPException(409, "Courier booking is available only after the build is sold")

    if build.shipment_booking_state == "booked" or build.parcel2go_order_id and build.shipment_booked_at:
        return BookShipmentResult(
            success=True,
            tracking_number=build.tracking_number,
            shipping_label_url=build.shipping_label_url,
            parcel2go_order_id=build.parcel2go_order_id,
            warning="This shipment was already booked; returning its saved booking.",
        )
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "A courier shipment cannot be created after physical handover")
    if build.shipment_booking_state in {"creating_order", "order_created", "paying", "reconciliation_required"}:
        raise HTTPException(
            409,
            "A previous Parcel2Go request may have created or paid for a shipment. Reconcile the provider order before any retry.",
        )
    if not body.confirm_live_purchase:
        raise HTTPException(409, "Explicit confirmation of this live courier purchase is required")

    if not build.buyer_address_json:
        raise HTTPException(400, "Add the buyer's delivery address before booking a shipment.")
    if not body.signed_for_delivery_confirmed:
        raise HTTPException(409, "Confirm that this courier service is signed-for. Figural cover does not apply to unsigned delivery.")
    evidence_job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build.id)
    )).scalar_one_or_none()
    if evidence_job is None:
        raise HTTPException(409, "Complete the Getting Ready workflow before buying the courier label.")
    incomplete_actions = incomplete_checklist_actions(
        evidence_job.checklist,
        COURIER_BOOKING_BLOCKING_ACTIONS,
        evidence_job.purchased_ai_services,
    )
    if incomplete_actions:
        raise HTTPException(
            409,
            "Complete the Getting Ready dispatch checklist before buying the courier label: "
            + ", ".join(incomplete_actions),
        )

    grant_required, printable_claim = await _portal_grant_required_for_build(db, build)
    if grant_required and printable_claim is None:
        raise HTTPException(409, "Issue a private buyer portal claim and print its QR leaflet before buying this courier label")
    if grant_required:
        checklist = evidence_job.checklist or {}
        leaflet_reviews = [
            item for item in (checklist.get("_audit") or [])
            if isinstance(item, dict) and item.get("action") == "leaflet_printed"
        ]
        last_leaflet_review = leaflet_reviews[-1] if leaflet_reviews else None
        if (
            checklist.get("leaflet_printed") != "complete"
            or not last_leaflet_review
            or last_leaflet_review.get("status") != "complete"
            or last_leaflet_review.get("portal_grant_id") != printable_claim.id
        ):
            raise HTTPException(409, "Print and scan-test the current portal claim leaflet again before courier booking")
    missing = [
        field
        for field in ("package_weight_kg", "package_length_cm", "package_width_cm", "package_height_cm")
        if getattr(build, field) is None
    ]
    if missing:
        raise HTTPException(400, f"Set the build's package dimensions first (missing: {', '.join(missing)}).")

    settings = get_settings()
    buyer_address = BuyerAddress(
        contact_name=build.buyer_address_json.get("contact_name", build.buyer_name or "Unknown"),
        address_line1=build.buyer_address_json.get("address_line1"),
        address_line2=build.buyer_address_json.get("address_line2"),
        city=build.buyer_address_json.get("city"),
        state_or_province=build.buyer_address_json.get("state_or_province"),
        postal_code=build.buyer_address_json.get("postal_code"),
        country_code=build.buyer_address_json.get("country_code", "GB"),
        phone=build.buyer_address_json.get("phone"),
    )
    value_gbp = build.sale_price_actual or build.ebay_price or build.total_cost or 0.0

    delivery_country = str(build.buyer_address_json.get("country_code") or "GBR").upper()
    if delivery_country == "GB":
        delivery_country = "GBR"
    try:
        fresh_quotes = await get_tracked_quotes(
            weight_kg=build.package_weight_kg,
            length_cm=build.package_length_cm,
            width_cm=build.package_width_cm,
            height_cm=build.package_height_cm,
            value_gbp=value_gbp,
            delivery_country=delivery_country,
        )
    except Parcel2GoError as error:
        raise HTTPException(error.status_code or 502, str(error)) from error
    selected_quote = next((quote for quote in fresh_quotes if quote.service_slug == body.service_slug), None)
    if not selected_quote or not selected_quote.signature_tracking:
        raise HTTPException(409, "That courier quote is no longer available with the required Signature extra. Request a fresh quote.")
    if not _gbp_amounts_match_to_penny(selected_quote.price_gbp, body.price_gbp):
        raise HTTPException(409, f"The courier price has changed to £{selected_quote.price_gbp:.2f}. Review and confirm the fresh quote.")

    # Commit a durable in-flight marker before calling either provider
    # endpoint. A concurrent request or retry after timeout will now stop
    # instead of creating and paying for a duplicate label.
    build.shipment_booking_state = "creating_order"
    build.shipment_booking_attempted_at = datetime.utcnow()
    build.shipment_booking_error_code = None
    build.parcel2go_service_slug = body.service_slug
    build.evidence_data = {
        **(build.evidence_data or {}),
        "shipment_booking_confirmation": {
            "signed_for_delivery_confirmed": True,
            "signature_extra_included": True,
            "provider_order_total_gbp": None,
            "live_purchase_confirmed": True,
            "service_slug": body.service_slug,
            # The selected quote was re-fetched and compared to the
            # operator-confirmed amount above. Persist that exact provider
            # price in GBP for the audit record.
            "confirmed_price_gbp": selected_quote.price_gbp,
            "confirmed_by_admin_id": getattr(admin, "id", None),
            "confirmed_by_admin_name": getattr(admin, "name", None),
            "confirmed_at": datetime.utcnow().isoformat(),
        },
    }
    build.dispatch_status = "booking_in_progress"
    build.updated_at = datetime.utcnow()
    await db.commit()

    try:
        order_id, order_hash, order_line_id, provider_total = await create_parcel2go_order(
            service_slug=body.service_slug,
            weight_kg=build.package_weight_kg,
            length_cm=build.package_length_cm,
            width_cm=build.package_width_cm,
            height_cm=build.package_height_cm,
            value_gbp=value_gbp,
            buyer_address=buyer_address,
            upsells=["Signature"],
            environment=settings.parcel2go_environment,
        )
    except Parcel2GoBookingError as error:
        build.shipment_booking_state = "failed_retryable" if 400 <= (error.status_code or 0) < 500 else "reconciliation_required"
        build.shipment_booking_error_code = f"create_order_http_{error.status_code}" if error.status_code else "create_order_outcome_unknown"
        build.dispatch_status = "awaiting_dispatch" if build.shipment_booking_state == "failed_retryable" else "booking_reconciliation_required"
        build.updated_at = datetime.utcnow()
        await db.commit()
        return BookShipmentResult(success=False, error=str(error))
    except Exception as error:
        log.exception("shipment.booking.create_order_outcome_unknown", build_id=build_id)
        build.shipment_booking_state = "reconciliation_required"
        build.shipment_booking_error_code = type(error).__name__[:80]
        build.dispatch_status = "booking_reconciliation_required"
        build.updated_at = datetime.utcnow()
        await db.commit()
        return BookShipmentResult(success=False, error="Parcel2Go's response was unclear. Check the provider account before retrying.")

    booking_confirmation = dict((build.evidence_data or {}).get("shipment_booking_confirmation") or {})
    booking_confirmation["provider_order_total_gbp"] = provider_total
    build.evidence_data = {**(build.evidence_data or {}), "shipment_booking_confirmation": booking_confirmation}

    # Parent and shipment-line references are durable before payment. The
    # provider hash remains secret; callbacks use the shipment-line ID.
    build.parcel2go_order_id = order_id
    build.parcel2go_order_line_id = order_line_id
    build.shipment_booking_state = "order_created"
    build.dispatch_status = "booking_payment_pending"
    build.updated_at = datetime.utcnow()
    await db.commit()

    if provider_total is None or not _gbp_amounts_match_to_penny(provider_total, selected_quote.price_gbp):
        build.shipment_booking_state = "reconciliation_required"
        build.shipment_booking_error_code = "created_order_total_missing_or_changed"
        build.dispatch_status = "booking_reconciliation_required"
        build.updated_at = datetime.utcnow()
        await db.commit()
        return BookShipmentResult(
            success=False,
            parcel2go_order_id=order_id,
            error=(
                "Parcel2Go created an unpaid order whose total did not match the confirmed quote. "
                "No payment was attempted; reconcile the provider order before retrying."
            ),
        )

    if not order_line_id:
        build.shipment_booking_state = "reconciliation_required"
        build.shipment_booking_error_code = "missing_order_line_id"
        build.dispatch_status = "booking_reconciliation_required"
        build.updated_at = datetime.utcnow()
        await db.commit()
        return BookShipmentResult(
            success=False,
            parcel2go_order_id=order_id,
            error="Parcel2Go did not return the shipment reference needed for tracking. No payment was attempted; reconcile the unpaid order before retrying.",
        )

    build.shipment_booking_state = "paying"
    await db.commit()
    try:
        booked = await pay_order_with_prepay(order_id, order_hash, environment=settings.parcel2go_environment)
    except Exception as error:
        log.exception("shipment.booking.payment_outcome_unknown", build_id=build_id, parcel2go_order_id=order_id)
        build.shipment_booking_state = "reconciliation_required"
        build.shipment_booking_error_code = f"pay_order_{type(error).__name__}"[:80]
        build.dispatch_status = "booking_reconciliation_required"
        build.updated_at = datetime.utcnow()
        await db.commit()
        return BookShipmentResult(success=False, parcel2go_order_id=order_id,
                                  error="Payment outcome is unclear. Check Parcel2Go before attempting another booking.")

    # Persist immediately — payment has already happened at this point, so
    # this must be saved even if the eBay push below fails.
    build.parcel2go_order_id = booked.parcel2go_order_id
    build.parcel2go_service_slug = body.service_slug
    build.tracking_number = booked.tracking_number
    build.shipping_label_url = booked.label_url
    booking_confirmation = dict((build.evidence_data or {}).get("shipment_booking_confirmation") or {})
    booking_confirmation["tracking_url"] = booked.tracking_url
    build.evidence_data = {**(build.evidence_data or {}), "shipment_booking_confirmation": booking_confirmation}
    build.shipment_booked_at = datetime.utcnow()
    build.shipment_booking_state = "booked"
    build.shipment_booking_error_code = None
    build.dispatch_status = "booked"
    build.updated_at = datetime.utcnow()
    await db.commit()

    return BookShipmentResult(
        success=True,
        tracking_number=booked.tracking_number,
        shipping_label_url=booked.label_url,
        parcel2go_order_id=booked.parcel2go_order_id,
        ebay_marked_shipped=False,
        warning=(
            "Courier booked and paid. Confirm physical handover with Dispatch only after the parcel is handed to the courier."
            if booked.tracking_number else
            "Courier booked and paid, but no tracking number was returned. Resolve tracking before dispatch."
        ),
    )


@router.post("/{build_id}/shipment-booking/reconcile")
async def reconcile_shipment_booking(
    build_id: int,
    body: ShipmentBookingReconciliationRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Attach a provider booking or reopen only after a documented provider check."""
    if not body.provider_checked:
        raise HTTPException(409, "Confirm that you checked the Parcel2Go account before resolving this attempt.")
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id).with_for_update())
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if _manual_build_has_physical_handover(build):
        raise HTTPException(409, "Shipment booking reconciliation is closed after physical handover")
    attaching_tracking_reference = body.resolution == "attach_tracking_reference"
    if attaching_tracking_reference:
        if not build.shipment_booked_at:
            raise HTTPException(409, "A verified existing booking is required before attaching its tracking reference.")
        if not build.parcel2go_order_id or not build.tracking_number:
            raise HTTPException(409, "The existing parent order ID and tracking number are required.")
        if build.parcel2go_order_line_id:
            raise HTTPException(409, "This booking already has a Parcel2Go tracking reference.")
        if body.provider_order_id != build.parcel2go_order_id or body.tracking_number != build.tracking_number:
            raise HTTPException(409, "The provider order ID and tracking number must match the saved booking.")
        if not body.provider_order_line_id:
            raise HTTPException(422, "Enter the shipment OrderLineId from the verified Parcel2Go booking.")
    else:
        if build.shipment_booking_state not in {"reconciliation_required", "creating_order", "order_created", "paying"}:
            raise HTTPException(409, "This build has no uncertain shipment booking to reconcile.")
        if build.shipment_booked_at or build.tracking_number:
            raise HTTPException(409, "A tracking record exists; this shipment is already reconciled.")

    if body.resolution == "paid_booking" and (
        not body.provider_order_id or not body.provider_order_line_id or not body.tracking_number
    ):
        raise HTTPException(422, "Enter the paid booking's order ID, shipment line ID and tracking number.")
    if body.shipping_label_url:
        parsed_label_url = urlparse(body.shipping_label_url)
        if parsed_label_url.scheme != "https" or not parsed_label_url.netloc:
            raise HTTPException(422, "The existing shipping label link must use HTTPS.")
    if body.resolution == "no_active_booking" and not body.provider_checked:
        raise HTTPException(409, "Confirm that Parcel2Go has no active or paid booking before reopening.")

    evidence = dict(build.evidence_data or {})
    history = list(evidence.get("shipment_booking_reconciliation") or [])
    history.append({
        "actor": getattr(admin, "email", None) or "admin",
        "note": body.note,
        "resolution": body.resolution,
        "provider_checked": True,
        "previous_state": build.shipment_booking_state,
        "previous_provider_order_id": build.parcel2go_order_id,
        "resolved_provider_order_id": body.provider_order_id,
        "resolved_provider_order_line_id": body.provider_order_line_id,
        "resolved_tracking_number": body.tracking_number,
        "recorded_at": datetime.utcnow().isoformat(),
    })
    evidence["shipment_booking_reconciliation"] = history[-50:]
    build.evidence_data = evidence
    if attaching_tracking_reference:
        build.parcel2go_order_line_id = body.provider_order_line_id
        build.shipment_booking_state = "booked"
    elif body.resolution == "paid_booking":
        build.parcel2go_order_id = body.provider_order_id
        build.parcel2go_order_line_id = body.provider_order_line_id
        build.tracking_number = body.tracking_number
        build.shipping_label_url = body.shipping_label_url
        build.shipment_booked_at = datetime.utcnow()
        build.shipment_booking_state = "booked"
        build.shipment_booking_error_code = None
        build.dispatch_status = "booked"
    else:
        build.shipment_booking_state = "failed_retryable"
        build.shipment_booking_error_code = None
        build.parcel2go_order_id = None
        build.parcel2go_order_line_id = None
        build.dispatch_status = "awaiting_dispatch"
    build.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "shipment_booking_state": build.shipment_booking_state}


@router.post("/{build_id}/dispatch")
async def dispatch_booked_build(
    build_id: int,
    body: DispatchBuildInput,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mark a booked parcel dispatched only after explicit physical handover."""
    if not body.confirm_physical_handover:
        raise HTTPException(409, "Confirm that the sealed parcel has been handed to the courier")
    build, job = await lock_manual_build_then_getting_started_job(db, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status != "sold":
        raise HTTPException(409, "Dispatch is available only after the build is sold")
    if _manual_build_has_physical_handover(build):
        final_status = "delivered" if build.delivered_at or build.dispatch_status == "delivered" else "dispatched"
        if build.dispatch_status != final_status:
            build.dispatch_status = final_status
            await db.commit()
        return {"success": True, "dispatch_status": final_status, "tracking_number": build.tracking_number, "already_dispatched": True}
    if not build.parcel2go_order_id or not build.tracking_number or not build.shipment_booked_at:
        raise HTTPException(409, "Book the courier and resolve its tracking number before dispatch")
    if build.shipping_insurance_status != "created" or not build.shipping_insurance_policy_id:
        raise HTTPException(409, "Register the confirmed shipment insurance policy before physical handover")
    booking_confirmation = (build.evidence_data or {}).get("shipment_booking_confirmation") or {}
    if not booking_confirmation.get("signed_for_delivery_confirmed") or not booking_confirmation.get("signature_extra_included"):
        raise HTTPException(409, "A provider-quoted signature extra must be included and confirmed before dispatch")
    missing_photos = _missing_verified_dispatch_evidence(
        job, build.id, ("working_pc", *INSURANCE_REQUIRED_PHOTO_CATEGORIES)
    )
    if missing_photos:
        raise HTTPException(
            409,
            "Approved pre-shipment evidence is missing or has changed; re-upload and review: "
            + ", ".join(missing_photos),
        )
    incomplete = incomplete_checklist_actions(
        job.checklist if job else {},
        DISPATCH_BLOCKING_ACTIONS,
        job.purchased_ai_services if job else None,
    )
    if incomplete:
        raise HTTPException(409, "Complete the Getting Ready dispatch checklist: " + ", ".join(incomplete))

    handover_at = datetime.utcnow()
    evidence_data = dict(build.evidence_data or {})
    evidence_data["physical_handover_confirmation"] = {
        "confirmed": True,
        "confirmed_at": handover_at.isoformat(),
        "confirmed_by_admin_id": admin.id,
        "confirmed_by_admin_name": admin.name,
        "tracking_number": build.tracking_number,
        "parcel2go_order_id": build.parcel2go_order_id,
    }
    build.evidence_data = evidence_data
    build.dispatch_status = "dispatched"
    build.updated_at = datetime.utcnow()
    linked_order = (await db.execute(
        select(Order)
        .join(Build, Build.manual_build_id == build.id)
        .outerjoin(Product, Product.build_id == Build.id)
        .where(or_(Build.order_id == Order.id, Product.sold_order_id == Order.id))
        .limit(1)
    )).scalar_one_or_none()
    courier_name = (build.parcel2go_service_slug or "courier").split("-")[0]
    booking_confirmation = (build.evidence_data or {}).get("shipment_booking_confirmation") or {}
    tracking_url = _safe_provider_tracking_url(booking_confirmation.get("tracking_url"))
    if linked_order:
        linked_order.tracking_number = build.tracking_number
        linked_order.carrier = courier_name
        linked_order.shipped_at = linked_order.shipped_at or datetime.utcnow()
        linked_order.status = OrderStatus.SHIPPED
        linked_order.updated_at = datetime.utcnow()
    dispatch_event = ShipmentTrackingEvent(
        order_id=linked_order.id if linked_order else None,
        manual_build_id=None if linked_order else build.id,
        provider=courier_name,
        provider_event_id=f"dispatch:{build.id}:{build.shipment_booked_at.isoformat()}",
        status_code="dispatched",
        description="Your sealed FlipFlop build has been handed to the courier.",
        tracking_url=tracking_url,
        material=True,
        occurred_at=handover_at,
    )
    db.add(dispatch_event)
    await db.commit()
    dispatch_event_id = dispatch_event.id
    ebay_order_id = build.ebay_order_id
    ebay_line_item_id = (build.buyer_address_json or {}).get("line_item_id", "")
    dispatch_tracking_number = build.tracking_number

    email_sent = False
    portal_claim_email_sent: bool | None = None
    portal_grant_id: int | None = None
    portal_claim_email_status: str | None = None
    is_direct_storefront_sale = bool(
        linked_order and linked_order.customer_id and not build.ebay_order_id
    )
    if build.storefront_product_id:
        sold_product = await db.get(Product, build.storefront_product_id)
        if sold_product and sold_product.sold_via_channel is not None:
            channel = getattr(sold_product.sold_via_channel, "value", sold_product.sold_via_channel)
            is_direct_storefront_sale = channel == "storefront"
    if is_direct_storefront_sale and linked_order:
        dispatch_event.customer_notification_attempts += 1
        dispatch_event.customer_notification_attempted_at = datetime.utcnow()
        await db.commit()
        direct_customer = await db.get(Customer, linked_order.customer_id)
        if direct_customer and direct_customer.email:
            customer_email = direct_customer.email
            customer_name = direct_customer.name or "there"
            order_reference = linked_order.order_id
            order_id = linked_order.id
            tracking_number = build.tracking_number
            dispatched_build_name = build.name
            has_customer_account = bool(
                direct_customer.password_hash
                or direct_customer.google_id
                or direct_customer.github_id
            )
            tracking_url = _safe_provider_tracking_url(
                ((build.evidence_data or {}).get("shipment_booking_confirmation") or {}).get("tracking_url")
            )
            tracking_email_attempted = False
            if has_customer_account:
                email_sent = await send_shipment_update_email(
                    customer_email,
                    customer_name,
                    order_reference,
                    courier_name,
                    tracking_number,
                    tracking_url,
                    None,
                    order_id,
                )
            else:
                build_name = str(
                    (linked_order.specs or {}).get("build_name")
                    or (linked_order.specs or {}).get("case_name")
                    or dispatched_build_name
                )
                existing_portal_grant = await find_printable_portal_claim(
                    db, order_id=linked_order.id, channel="direct_guest", include_claimed=True
                )
                if existing_portal_grant:
                    # Preserve the claim whose QR was printed before courier
                    # booking. Rotating it here would invalidate the leaflet
                    # already packed with the machine.
                    portal_grant_id = existing_portal_grant.id
                    portal_claim_email_status = existing_portal_grant.email_status
                    tracking_email_attempted = True
                    email_sent = await send_shipment_update_email(
                        customer_email,
                        customer_name,
                        order_reference,
                        courier_name,
                        tracking_number,
                        tracking_url,
                        None,
                        order_id,
                    )
                else:
                    portal_claim_email_sent = False
                    try:
                        grant, claim_url = await issue_direct_order_portal_claim(
                            db,
                            linked_order,
                            build_name=build_name,
                            contact_email=customer_email,
                            manual_build_id=build.id,
                        )
                        await db.commit()
                        portal_grant_id = grant.id
                        portal_claim_email_status = grant.email_status
                        claim_email_sent = await send_dispatched_guest_portal_email(
                            customer_email,
                            customer_name,
                            build_name,
                            claim_url,
                            grant.expires_at,
                            order_reference,
                            courier_name,
                            tracking_number,
                            tracking_url,
                        )
                        await record_portal_claim_email_result(db, grant, sent=claim_email_sent)
                        portal_claim_email_sent = claim_email_sent
                        portal_claim_email_status = grant.email_status
                        email_sent = portal_claim_email_sent
                    except Exception as error:
                        await db.rollback()
                        log.exception(
                            "Could not issue direct guest portal claim at dispatch",
                            build_id=build_id,
                            order_id=order_id,
                            error=str(error),
                        )
                if not email_sent and not tracking_email_attempted:
                    email_sent = await send_shipment_update_email(
                        customer_email,
                        customer_name,
                        order_reference,
                        courier_name,
                        tracking_number,
                        tracking_url,
                        None,
                        order_id,
                    )
            if email_sent:
                saved_dispatch_event = await db.get(ShipmentTrackingEvent, dispatch_event_id)
                if saved_dispatch_event:
                    saved_dispatch_event.customer_notified_at = datetime.utcnow()
                await db.commit()
    ebay_marked_shipped = False
    ebay_warning = None
    if ebay_order_id:
        try:
            await mark_order_shipped(
                order_id=ebay_order_id,
                line_item_id=ebay_line_item_id,
                tracking_number=dispatch_tracking_number,
                courier_name=courier_name,
                environment=get_settings().ebay_listing_environment,
            )
            ebay_marked_shipped = True
        except EbayShippingFulfillmentError as error:
            ebay_warning = f"Dispatch saved, but eBay tracking update failed: {error}"
    return {
        "success": True,
        "dispatch_status": "dispatched",
        "tracking_number": dispatch_tracking_number,
        "email_sent": email_sent,
        "portal_claim_email_sent": portal_claim_email_sent,
        "portal_grant_id": portal_grant_id,
        "portal_claim_email_status": portal_claim_email_status,
        "ebay_marked_shipped": ebay_marked_shipped,
        "warning": ebay_warning,
    }


@router.patch("/{build_id}/aspects", response_model=ManualBuildOut)
async def update_aspects(build_id: int, body: UpdateAspectsRequest, db: AsyncSession = Depends(get_db)):
    """Manually edit/correct the generated Item Specifics before listing."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    problems = validate_aspects_for_ebay(body.aspects)
    if problems:
        raise HTTPException(400, "Invalid Item Specifics: " + "; ".join(problems))

    build.generated_aspects = body.aspects
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.put("/{build_id}/evidence-data", response_model=ManualBuildOut)
async def update_evidence_data(build_id: int, body: UpdateEvidenceDataRequest, db: AsyncSession = Depends(get_db)):
    """Stores the structured factual data (JSON) behind the spec card,
    registration plate, or performance card for this build — this is what
    actually gets sent to the LLM for listing generation, as plain text.
    The rendered PNG images (uploaded separately via /photos and
    /photos/branded) are just a visual rendering of this same data for the
    seller's own reference and for the eBay listing photos themselves."""
    if body.kind not in ("spec_card", "registration_plate", "performance_card"):
        raise HTTPException(400, "kind must be 'spec_card', 'registration_plate' or 'performance_card'")

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    evidence = dict(build.evidence_data or {})
    evidence[body.kind] = body.data
    build.evidence_data = evidence
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.patch("/{build_id}/listing-title", response_model=ManualBuildOut)
async def update_listing_title(build_id: int, body: UpdateListingTitleRequest, db: AsyncSession = Depends(get_db)):
    """Persist the editable title used by every publishing channel."""
    runtime = os.getenv("FLIPFLOP_RUNTIME_ENV", "development").strip().lower()
    if runtime not in {"live", "production", "prod"}:
        raise HTTPException(
            409,
            "Parcel2Go booking and payment are disabled outside LIVE mode; delivery quotes remain available.",
        )

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    build.generated_title = body.title.strip()
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.patch("/{build_id}/ebay-config", response_model=ManualBuildOut)
async def update_ebay_config(
    build_id: int, body: UpdateEbayListingConfigRequest, db: AsyncSession = Depends(get_db)
):
    """Update eBay listing configuration (condition, price, shipping, offers)."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    if body.ebay_condition is not None:
        build.ebay_condition = body.ebay_condition
    if body.ebay_price is not None:
        build.ebay_price = body.ebay_price
    if body.allow_offers is not None:
        build.allow_offers = body.allow_offers
    if body.auto_reject_below_price is not None:
        build.auto_reject_below_price = body.auto_reject_below_price
    if body.auction_start_price is not None:
        build.auction_start_price = body.auction_start_price
    if body.return_days is not None:
        build.return_days = body.return_days
    if body.shipping_method is not None:
        build.shipping_method = body.shipping_method
    if body.shipping_cost is not None:
        build.shipping_cost = body.shipping_cost
    if body.shipping_insurance_cost is not None:
        build.shipping_insurance_cost = max(0.0, body.shipping_insurance_cost)
    if body.packaging_cost is not None:
        build.packaging_cost = max(0.0, body.packaging_cost)
    if body.warranty_reserve_pct is not None:
        build.warranty_reserve_pct = min(25.0, max(5.0, body.warranty_reserve_pct))
    if body.marketplace_fees_actual is not None:
        build.marketplace_fees_actual = max(0.0, body.marketplace_fees_actual)
    if body.promotion_cost_actual is not None:
        build.promotion_cost_actual = max(0.0, body.promotion_cost_actual)
    if body.refund_amount is not None:
        build.refund_amount = max(0.0, body.refund_amount)
    if body.warranty_claim_cost is not None:
        build.warranty_claim_cost = max(0.0, body.warranty_claim_cost)
    if body.handling_time_days is not None:
        build.handling_time_days = body.handling_time_days
    if body.ships_to_countries is not None:
        build.ships_to_countries = body.ships_to_countries
    if body.domestic_only is not None:
        build.domestic_only = body.domestic_only
    if body.fulfillment_policy_id is not None:
        build.fulfillment_policy_id = body.fulfillment_policy_id
    if body.package_weight_kg is not None:
        build.package_weight_kg = body.package_weight_kg
    if body.package_length_cm is not None:
        build.package_length_cm = body.package_length_cm
    if body.package_width_cm is not None:
        build.package_width_cm = body.package_width_cm
    if body.package_height_cm is not None:
        build.package_height_cm = body.package_height_cm
    # Unlike the fields above, deferred_publish_at must be explicitly
    # clearable (the user cancels a scheduled time), so this checks whether
    # the field was sent at all rather than whether it's non-null.
    if "deferred_publish_at" in body.model_fields_set:
        build.deferred_publish_at = body.deferred_publish_at
    if body.traffic_band is not None:
        build.traffic_band = body.traffic_band
    if body.recreate_price_step_pct is not None:
        build.recreate_price_step_pct = body.recreate_price_step_pct
    if body.markdown_event_opt_in is not None:
        build.markdown_event_opt_in = body.markdown_event_opt_in
    if body.promoted_enabled is not None:
        build.promoted_enabled = body.promoted_enabled
    if body.promoted_ad_rate_pct is not None:
        build.promoted_ad_rate_pct = body.promoted_ad_rate_pct

    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.delete("/{build_id}/ebay-listing", response_model=ManualBuildOut)
async def end_ebay_listing(build_id: int, db: AsyncSession = Depends(get_db)):
    """End the live eBay offer while preserving the build for editing/relisting."""
    import structlog

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.ebay_listing_id:
        raise HTTPException(409, "This build does not have a live eBay listing to end")
    if not build.ebay_sku:
        raise HTTPException(
            409,
            "This listing has no saved eBay SKU, so it cannot be ended safely from FlipFlop",
        )

    listing_id = build.ebay_listing_id
    sku = build.ebay_sku
    settings = get_settings()
    log = structlog.get_logger(__name__)

    try:
        await withdraw_listing_by_sku(sku, environment=settings.ebay_listing_environment)
    except EbayListingWithdrawError as exc:
        log.error(
            "manual_build.ebay_listing_end_failed",
            build_id=build_id,
            listing_id=listing_id,
            sku=sku,
            ebay_status=exc.status_code,
        )
        raise HTTPException(
            502,
            "eBay could not end the listing. Nothing was changed in FlipFlop; please try again.",
        ) from exc

    # Preserve the ended listing ID/SKU as historical evidence. Publishing
    # logic keys off ebay_listing_status, not mere ID presence, so the next
    # publish creates a fresh offer rather than trying to revise this one.
    build.ebay_listing_status = "ended"
    build.ebay_listing_status_checked_at = datetime.utcnow()
    build.ebay_listing_end_reason = "ended_early"
    build.deferred_publish_at = None
    if build.status == "listed":
        build.status = "built"
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    build.ebay_live = False

    log.info(
        "manual_build.ebay_listing_ended",
        build_id=build_id,
        listing_id=listing_id,
        sku=sku,
    )
    return build


@router.post("/{build_id}/post-to-ebay", response_model=PostToEbayResult)
async def post_to_ebay(build_id: int, body: PostToEbayRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    # A draft is a real eBay offer, so don't create a second offer for the
    # same build when the user clicks the draft button more than once. Live
    # listings are likewise protected from an accidental duplicate listing.
    # A stored Inventory offer/listing ID does not mean a Seller Hub draft
    # exists. Seller Hub draft uploads are intentionally allowed here so an
    # old API-only record cannot block creation of the requested draft. The
    # production Seller Hub feed is the source of truth for this operation.

    # Persist the seller's asking price as build configuration before making
    # the external eBay request. This keeps the value after reloads and also
    # preserves it when eBay rejects a listing update.
    build.ebay_price = body.price
    build.updated_at = datetime.utcnow()
    await db.flush()

    if not build.generated_title or not build.generated_description:
        raise HTTPException(400, "Generate the listing content before posting to eBay")

    # FAQ choices can be changed after the description was generated. Always
    # refresh the deterministic FAQ block immediately before publication.
    build.generated_description = prepare_ebay_listing_description(
        _description_with_selected_faqs(build.generated_description, build)
    )

    # Do not allow an older generated description to bypass the customer-facing
    # delivery/returns/support wording added to the current listing workflow.
    if "data-flipflop-customer-policy" not in build.generated_description:
        return_period = (
            f"{build.return_days}-day returns" if build.return_days else "No voluntary returns period set"
        )
        policy_html = f"""
<section data-flipflop-customer-policy="true" style="margin-top:24px;padding:20px;border:1px solid #d7dce2;border-radius:12px;background:#f7f9fb;color:#17202a;">
  <h2 style="margin:0 0 12px;font-size:20px;">Delivery, returns &amp; support</h2>
  <p><strong>Dispatch:</strong> Within {build.handling_time_days or 1} working day(s), followed by tracked delivery.</p>
  <p><strong>Returns:</strong> {return_period}. The buyer pays return postage for a change of mind; flipflop pays reasonable return postage if the PC is faulty, damaged or misdescribed.</p>
  <p><strong>Your rights:</strong> UK statutory consumer rights are not affected. Manufacturer warranties are passed on where transferable.</p>
  <p><strong>Support:</strong> Direct setup and after-sales support is available from flipflop.</p>
</section>
"""
        build.generated_description = prepare_ebay_listing_description(
            build.generated_description + policy_html
        )
        build.updated_at = datetime.utcnow()
        await db.flush()

    # Builds generated before cardinality validation can still contain arrays
    # such as Brand=[AMD, NVIDIA, Corsair] and Storage Type=[SSD, HDD]. Repair
    # those deterministic legacy cases and persist them before validation and
    # submission so the user does not have to re-enter otherwise valid data.
    repaired_aspects = repair_legacy_aspect_cardinality(build.generated_aspects or {})
    if repaired_aspects != (build.generated_aspects or {}):
        build.generated_aspects = repaired_aspects
        build.updated_at = datetime.utcnow()
        await db.flush()

    missing_required = [a for a in ("Brand", "Type") if not (build.generated_aspects or {}).get(a)]
    if missing_required:
        raise HTTPException(
            400,
            f"Item Specifics are incomplete (missing: {', '.join(missing_required)}). "
            "Generate or fill in the listing's Specifics section before posting to eBay.",
        )
    # Defensive re-check even though update_aspects now validates on save —
    # catches aspects written before that validation existed (like the
    # over-length "Connectivity" free-text value that first surfaced this
    # bug), turning what would be a slow eBay API rejection into an
    # immediate, fixable local error.
    aspect_problems = validate_aspects_for_ebay(build.generated_aspects or {})
    if aspect_problems:
        raise HTTPException(
            400,
            "Item Specifics have invalid values — fix these in the Specifics section before posting: "
            + "; ".join(aspect_problems),
        )

    # Get image URLs from build photos (already public URLs)
    image_urls = list(body.images or [])
    if not image_urls and build.photos:
        for photo in build.photos:
            # Photo is stored as {"url": "https://www.theflipflop.shop/api/uploads/...", "kind": "photo"}
            photo_url = photo.get("url") if isinstance(photo, dict) else photo
            if photo_url:
                image_urls.append(photo_url)

    if not image_urls:
        raise HTTPException(400, "Upload at least one photo before listing on eBay")

    # Listing/publishing target (sandbox vs production) is driven by
    # EBAY_LISTING_ENVIRONMENT — credentials, token, and business policies
    # all switch together with it. Token is auto-renewed via the stored
    # refresh token when possible, falling back to the static one.
    from app.services.ebay_token_manager import get_valid_ebay_access_token

    settings = get_settings()
    listing_environment = settings.ebay_listing_environment

    try:
        oauth_token = await get_valid_ebay_access_token(listing_environment, db=db)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if listing_environment == "production":
        payment_policy_id = settings.ebay_production_payment_policy_id
        return_policy_id = settings.ebay_production_return_policy_id
        fulfillment_policy_id = settings.ebay_production_fulfillment_policy_id
    else:
        payment_policy_id = settings.ebay_sandbox_payment_policy_id
        return_policy_id = settings.ebay_sandbox_return_policy_id
        fulfillment_policy_id = settings.ebay_sandbox_fulfillment_policy_id

    # Per-build shipping-destination choice (picked from the seller's real
    # eBay fulfillment policies via the Shipping & Delivery section) wins
    # over the single global default every other listing falls back to.
    if build.fulfillment_policy_id:
        fulfillment_policy_id = build.fulfillment_policy_id

    # Policy IDs are account- and marketplace-specific. A saved ID can become
    # stale when the seller edits/deletes a policy, or when a build was copied
    # from another eBay environment. Resolve it against the connected
    # production account before sending the Inventory API request.
    try:
        available_fulfillment_policies = await list_fulfillment_policies(
            listing_environment,
            marketplace_id="EBAY_GB",
            access_token=oauth_token,
        )
    except EbayFulfillmentPoliciesError as exc:
        raise HTTPException(
            exc.status_code or 502,
            f"Could not verify the eBay shipping policy: {exc}",
        ) from exc

    valid_fulfillment_ids = {
        policy.policy_id
        for policy in available_fulfillment_policies
        if not policy.marketplace_id or policy.marketplace_id == "EBAY_GB"
    }
    if fulfillment_policy_id not in valid_fulfillment_ids:
        replacement_policy = next(
            (policy.policy_id for policy in available_fulfillment_policies if policy.policy_id in valid_fulfillment_ids),
            None,
        )
        if not replacement_policy:
            raise HTTPException(
                400,
                "No valid EBAY_GB fulfillment policy exists in the connected eBay account. "
                "Create a shipping policy in Seller Hub, then retry.",
            )
        log.warning(
            "manual_builds.replacing_stale_fulfillment_policy",
            build_id=build_id,
            stale_policy_id=fulfillment_policy_id,
            replacement_policy_id=replacement_policy,
        )
        fulfillment_policy_id = replacement_policy
        build.fulfillment_policy_id = replacement_policy
        build.updated_at = datetime.utcnow()

    try:
        # Use eBay's native item-draft endpoint for a draft. The Seller Hub
        # feed mapper currently accepts the upload but completes with an empty
        # error report, so it cannot reliably create a draft row.
        if not body.publish:
            poster = EbayListingPoster(environment=listing_environment, access_token=oauth_token)
            draft_result = await poster.create_item_draft(
                title=build.generated_title,
                description=build.generated_description,
                price=body.price,
                image_urls=image_urls,
                category_id="179",
                condition=body.condition,
                aspects=build.generated_aspects or {},
            )
            if not draft_result.get("success"):
                error = draft_result.get("error", "eBay rejected the Seller Hub draft")
                if "403" in error or "401" in error:
                    error += (
                        " The eBay application keyset must have the Item Draft API permission enabled; "
                        "after enabling it in the eBay Developer Portal, reconnect eBay."
                    )
                return PostToEbayResult(success=False, error=error)
            build.ebay_draft_id = draft_result.get("draft_id")
            build.ebay_draft_url = draft_result.get("draft_url")
            build.ebay_offer_id = None
            build.ebay_sku = None
            build.ebay_listing_status = "draft"
            build.ebay_listing_status_checked_at = datetime.utcnow()
            build.ebay_listing_end_reason = None
            build.updated_at = datetime.utcnow()
            await db.flush()
            return PostToEbayResult(
                success=True,
                action="drafted",
                draft_id=draft_result.get("draft_id"),
                draft_url=draft_result.get("draft_url"),
            )

        # Reconcile before choosing create vs revise. An ID by itself only
        # proves this build was listed historically; it does not prove that
        # the offer is still live.
        if not build.ebay_listing_id and build.ebay_listing_url:
            legacy_id_match = re.search(
                r"/(?:itm/)?(\d{9,15})(?:[/?#]|$)",
                urlparse(build.ebay_listing_url).path,
            ) or re.search(r"/itm/[^/]+/(\d{9,15})(?:[/?#]|$)", build.ebay_listing_url)
            if legacy_id_match:
                build.ebay_listing_id = legacy_id_match.group(1)
        if build.ebay_listing_id:
            from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
            remote_state = await reconcile_manual_build_listing(
                build,
                db,
                force=True,
                access_token=oauth_token,
                environment=listing_environment,
            )
        else:
            remote_state = "never_listed"
        if remote_state == "unknown":
            raise HTTPException(
                503,
                "eBay listing status could not be verified. No listing was created or updated; retry when eBay is reachable.",
            )
        if remote_state == "sold":
            raise HTTPException(409, "eBay confirms this build has sold; it cannot be relisted.")
        if remote_state not in {"active", "ended", "missing", "never_listed"}:
            raise HTTPException(503, "eBay listing state is not safe to relist. Refresh the listing status and retry.")
        is_relisting = remote_state == "active"

        if is_relisting:
            # Update existing eBay listing
            result = await post_flip_to_ebay(
                title=build.generated_title,
                description=build.generated_description,
                price=body.price,
                image_urls=image_urls,
                access_token=oauth_token,
                environment=listing_environment,
                condition=body.condition,
                payment_policy_id=payment_policy_id,
                return_policy_id=return_policy_id,
                fulfillment_policy_id=fulfillment_policy_id,
                aspects=build.generated_aspects or {},
                listing_id=build.ebay_listing_id,  # Pass existing ID to update
                sku=build.ebay_sku,
            )
        else:
            # Create new eBay listing
            result = await post_flip_to_ebay(
                title=build.generated_title,
                description=build.generated_description,
                price=body.price,
                image_urls=image_urls,
                access_token=oauth_token,
                environment=listing_environment,
                condition=body.condition,
                payment_policy_id=payment_policy_id,
                return_policy_id=return_policy_id,
                fulfillment_policy_id=fulfillment_policy_id,
                aspects=build.generated_aspects or {},
                publish=body.publish,
            )

        if result["success"]:
            if not body.publish:
                build.ebay_offer_id = result.get("offer_id")
                build.ebay_sku = result.get("sku")
                build.ebay_listing_status = "draft"
                build.ebay_listing_status_checked_at = datetime.utcnow()
                build.ebay_listing_end_reason = None
                build.updated_at = datetime.utcnow()
                await db.flush()
                return PostToEbayResult(success=True, offer_id=result.get("offer_id"), action="drafted")

            from app.services.traffic_bands import jittered_recreate_slot, DEFAULT_BAND

            build.ebay_listing_id = result["listing_id"]
            build.ebay_offer_id = None
            build.ebay_listing_url = result["url"]
            build.ebay_sku = result.get("sku")
            build.status = "listed"
            build.ebay_listing_status = "active"
            build.ebay_listing_status_checked_at = datetime.utcnow()
            build.ebay_listing_end_reason = None
            build.deferred_publish_at = None
            build.updated_at = datetime.utcnow()
            if not build.ebay_price:
                build.ebay_price = body.price
            if build.listed_at is None:
                # Rows 1/2/5/6/9: start the recreate/relist cycle clock the
                # first time this build actually goes live, whichever path
                # got it there (manual "List on eBay" here, or the deferred
                # scheduler in manual_build_scheduler.py).
                build.listed_at = datetime.utcnow()
                policy = (
                    await db.execute(
                        select(AppSettings).where(AppSettings.name == "default")
                    )
                ).scalar_one_or_none()
                interval_days = policy.relist_interval_days if policy else 7
                build.next_recreate_at = (
                    build.listed_at + timedelta(days=interval_days or 7)
                    if build.relist_enabled
                    else None
                )

            # Row 40: promote automatically if opted in — a failure here
            # doesn't undo the listing itself, just logs.
            if build.promoted_enabled:
                try:
                    from app.services.ebay_marketing import set_promoted_ad

                    rate = build.promoted_ad_rate_pct
                    if rate is None:
                        suggestion = pricing_engine.suggest_promoted_ad_rate(
                            estimated_profit=body.price - (build.total_cost or 0),
                            total_cost=build.total_cost or 0,
                        )
                        rate = suggestion["suggested_ad_rate_pct"] * 100 if not suggestion["too_thin_to_promote"] else None
                    if rate is not None:
                        await set_promoted_ad(build.ebay_listing_id, rate, oauth_token, listing_environment)
                except Exception as exc:
                    log.warning("manual_builds.promote_failed", build_id=build.id, error=str(exc))

            await db.flush()
            action = "updated" if is_relisting else "posted"
            return PostToEbayResult(success=True, listing_id=result["listing_id"], url=result["url"], action=action, offer_id=result.get("offer_id"))

        return PostToEbayResult(success=False, error=result.get("error", f"Failed to {'update' if is_relisting else 'post'} listing"))
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        return PostToEbayResult(success=False, error=f"Error {'updating' if locals().get('is_relisting') else 'posting'} to eBay: {error_msg}")


@router.post("/{build_id}/publish-ebay-draft", response_model=PostToEbayResult)
async def publish_ebay_draft(build_id: int, db: AsyncSession = Depends(get_db)):
    """Publish a legacy Inventory offer, if present.

    eBay-native Seller Hub drafts are completed in eBay's listing experience;
    their response contains the continuation URL and they do not expose the
    Inventory API publishOffer lifecycle.
    """
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.ebay_draft_id:
        raise HTTPException(
            409,
            "This is an eBay Seller Hub draft. Open the saved eBay draft URL to review and publish it there.",
            headers={"X-EBAY-DRAFT-URL": build.ebay_draft_url or ""},
        )
    if not build.ebay_offer_id:
        raise HTTPException(400, "Create an eBay draft before publishing it.")

    settings = get_settings()
    try:
        from app.services.ebay_token_manager import get_valid_ebay_access_token
        oauth_token = await get_valid_ebay_access_token(settings.ebay_listing_environment, db=db)
        poster = EbayListingPoster(environment=settings.ebay_listing_environment, access_token=oauth_token)
        published = await poster.publish_offer(build.ebay_offer_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if not published.get("success"):
        return PostToEbayResult(success=False, error=published.get("error", "eBay rejected the draft publication."))

    build.ebay_listing_id = published["listing_id"]
    build.ebay_listing_url = published["url"]
    build.ebay_offer_id = None
    build.ebay_draft_id = None
    build.ebay_draft_url = None
    build.ebay_listing_status = "active"
    build.ebay_listing_status_checked_at = datetime.utcnow()
    build.ebay_listing_end_reason = None
    build.status = "listed"
    build.updated_at = datetime.utcnow()
    await db.flush()
    return PostToEbayResult(success=True, listing_id=published["listing_id"], url=published["url"], action="posted")


@router.post("/{build_id}/photos", response_model=ManualBuildOut)
async def upload_photos(
    build_id: int,
    files: list[UploadFile] = File(...),
    kind: str = Form("photo"),
    db: AsyncSession = Depends(get_db),
):
    """kind defaults to "photo" (regular listing photos) but also accepts
    "performance_card" — the build-specific benchmark/performance renders
    uploaded from the build detail page's Performance Card section. Tagging
    them lets generate-listing find exactly this build's performance
    evidence rather than relying on any shared/global file."""
    if kind not in ("photo", "performance_card"):
        raise HTTPException(400, "kind must be 'photo' or 'performance_card'")

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    photos = list(build.photos or [])

    uploaded_urls = []
    for file in files:
        content_type = file.content_type or "image/jpeg"
        if content_type not in _IMAGE_TYPES:
            raise HTTPException(415, f"Unsupported image type: {content_type}. Use JPEG, PNG or WebP.")
        image_bytes = await file.read()
        if len(image_bytes) > _MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image too large (max 15 MB)")

        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]
        filename = f"{uuid.uuid4().hex}.{ext}"

        asset_dir = "Performance" if kind == "performance_card" else "Media"
        local_path, public_url = _build_named_asset_path(build_id, filename, asset_dir)
        local_path.write_bytes(image_bytes)

        # Served directly from the build-owned Media directory.
        photos.append({"url": public_url, "kind": kind, "original_filename": Path(file.filename or "photo").name[:120]})
        uploaded_urls.append(public_url)

    build.photos = photos
    if kind == "photo" and not build.hero_photo_url and uploaded_urls:
        build.hero_photo_url = uploaded_urls[0]
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.get("/{build_id}/photos/download")
async def download_build_photos(build_id: int, db: AsyncSession = Depends(get_db)):
    """Download the original regular build photos as a ZIP archive."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    archive = io.BytesIO()
    used_names: set[str] = set()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
        for photo in build.photos or []:
            if not isinstance(photo, dict) or photo.get("kind") != "photo":
                continue
            url = str(photo.get("url") or "")
            filename = Path(url.split("?", 1)[0].rsplit("/", 1)[-1]).name
            if not filename:
                continue
            build_root = (_BUILD_ASSETS_ROOT / str(build_id)).resolve()
            padded_root = (_BUILD_ASSETS_ROOT / f"{build_id:03d}").resolve()
            legacy_root = (_UPLOADS_ROOT / str(build_id)).resolve()
            candidate_paths = [
                build_root / "Media" / filename,
                padded_root / "Media" / filename,
                legacy_root / filename,
                _PUBLIC_MEDIA_ROOT / filename,
            ]
            source_path = next((candidate.resolve() for candidate in candidate_paths if candidate.is_file()), None)
            if source_path is None:
                continue

            original_name = Path(str(photo.get("original_filename") or filename)).name
            stem, suffix = Path(original_name).stem, Path(original_name).suffix
            archive_name = original_name
            duplicate_index = 2
            while archive_name.lower() in used_names:
                archive_name = f"{stem} ({duplicate_index}){suffix}"
                duplicate_index += 1
            used_names.add(archive_name.lower())
            zip_file.write(source_path, archive_name)

    if not used_names:
        raise HTTPException(404, "No saved build photos found")

    archive.seek(0)
    safe_build_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in build.name).strip("-") or f"build-{build_id}"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_build_name}-photos.zip"'},
    )


@router.get("/{build_id}/performance/download")
async def download_performance_card(build_id: int, db: AsyncSession = Depends(get_db)):
    """Download the saved performance-card ZIP for this build."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    roots = [_BUILD_ASSETS_ROOT / str(build_id), _BUILD_ASSETS_ROOT / f"{build_id:03d}"]
    zip_path = next((root / "Performance" / "performance-card-sections.zip" for root in roots
                     if (root / "Performance" / "performance-card-sections.zip").is_file()), None)
    if zip_path is None:
        raise HTTPException(404, "No saved performance card found")
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in build.name).strip("-") or f"build-{build_id}"
    return FileResponse(zip_path, media_type="application/zip", filename=f"{safe_name}-performance-card.zip")


@router.post("/{build_id}/photos/branded", response_model=ManualBuildOut)
async def upload_branded_asset(
    build_id: int,
    kind: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Store a client-rendered branded card (spec card / registration plate)."""
    if kind not in ("spec_card", "registration_plate"):
        raise HTTPException(400, "kind must be 'spec_card' or 'registration_plate'")
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    image_bytes = await file.read()
    filename = f"{kind}-{uuid.uuid4().hex}.png"
    asset_dir = "Registration" if kind == "registration_plate" else "Specifications"
    local_path, public_url = _build_named_asset_path(build_id, filename, asset_dir)
    local_path.write_bytes(image_bytes)

    photos = [p for p in (build.photos or []) if p.get("kind") != kind]
    photos.append({"url": public_url, "kind": kind})
    build.photos = photos
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/model-3d", response_model=ManualBuildOut)
async def upload_build_3d_model(
    build_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Store one self-contained GLB for the completed-build web viewer."""
    if not (file.filename or "").lower().endswith(".glb"):
        raise HTTPException(400, "Upload a self-contained .glb model")
    model_bytes = await file.read()
    if not model_bytes:
        raise HTTPException(400, "The GLB file is empty")
    if len(model_bytes) > 100 * 1024 * 1024:
        raise HTTPException(413, "The GLB must be 100 MB or smaller")
    # Binary glTF begins with the ASCII magic bytes 'glTF'. This rejects a
    # renamed ZIP/OBJ before it can reach the public storefront.
    if model_bytes[:4] != b"glTF":
        raise HTTPException(400, "The uploaded file is not a valid binary GLB")

    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    filename = f"model-3d-{uuid.uuid4().hex}.glb"
    local_path, public_url = _build_3d_asset_path(build_id, filename)
    local_path.write_bytes(model_bytes)
    _persist_build_model_download(build_id, filename, local_path)
    build.model_3d_url = public_url
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.get("/{build_id}/model-3d/download")
async def download_build_3d_model(build_id: int, db: AsyncSession = Depends(get_db)):
    """Serve a downloadable copy from the build's dedicated 3D Model folder.

    Browsers control the user's actual local Downloads location. This endpoint
    controls the server-side default location and supplies an attachment name.
    """
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build or not build.model_3d_url:
        raise HTTPException(404, "No 3D model is saved for this build")

    filename = Path(urlparse(build.model_3d_url).path).name
    if not filename or not filename.lower().endswith(".glb"):
        raise HTTPException(404, "The saved 3D model file is invalid")
    source = _existing_build_model_path(build_id, filename)
    if source is None:
        raise HTTPException(404, "The saved 3D model file could not be found")

    download_path = _persist_build_model_download(build_id, filename, source)
    return FileResponse(download_path, media_type="model/gltf-binary", filename=filename)


@router.delete("/{build_id}/photos", response_model=ManualBuildOut)
async def remove_photo(build_id: int, body: RemovePhotoRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    photos = [p for p in (build.photos or []) if p.get("url") != body.url]
    build.photos = photos
    if build.hero_photo_url == body.url:
        build.hero_photo_url = photos[0]["url"] if photos else None
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.put("/{build_id}/photos/order", response_model=ManualBuildOut)
async def reorder_photos(build_id: int, body: ReorderPhotosRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    existing = list(build.photos or [])
    by_url = {p["url"]: p for p in existing if p.get("kind") == "photo"}
    if set(body.urls) != set(by_url.keys()):
        raise HTTPException(400, "urls must be exactly the build's current photo URLs")

    non_photo = [p for p in existing if p.get("kind") != "photo"]
    reordered = [by_url[u] for u in body.urls]
    build.photos = reordered + non_photo
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/photos/hero", response_model=ManualBuildOut)
async def set_hero_photo(build_id: int, body: SetHeroPhotoRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not any(p.get("url") == body.url for p in (build.photos or [])):
        raise HTTPException(400, "That photo isn't attached to this build")

    build.hero_photo_url = body.url
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/list-on-storefront", response_model=ListOnStorefrontResult)
async def list_on_storefront(
    build_id: int,
    body: ListOnStorefrontRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish this build to the FlipFlop.shop pre-built showcase — the first
    code path in this codebase that actually creates a Product row (Build →
    Product has been a schema-only relationship until now).
    """
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status not in ("built", "listed", "sold"):
        raise HTTPException(400, "Mark this build as built before listing it on the storefront")
    if not build.hero_photo_url:
        raise HTTPException(400, "Choose a hero photo before listing on the storefront")
    if not build.generated_title or not build.generated_description:
        raise HTTPException(400, "Generate the listing title/description before listing on the storefront")
    assignment = (build.evidence_data or {}).get("playbook_assignment") or {}

    if build.storefront_product_id:
        product_result = await db.execute(select(Product).where(Product.id == build.storefront_product_id))
        product = product_result.scalar_one_or_none()
        if product:
            product.price = body.price
            product.status = ProductStatus.LISTED
            product.hero_photo_url = build.hero_photo_url
            product.title = build.generated_title
            product.description = build.generated_description
            product.model_3d_url = build.model_3d_url
            product.item_specifics = _direct_storefront_item_specifics(build)
            product.platform_category_id = _PC_BUILD_PLATFORM_CATEGORY_ID
            product.platform_category_name = _PC_BUILD_PLATFORM_CATEGORY_NAME
            product.selected_faqs = selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides)
            product.playbook_id = assignment.get("playbook_id")
            product.fulfilment_type = "prebuilt"
            product.handling_min_days = 1
            product.handling_max_days = 1
            product.delivery_min_days = 1
            product.delivery_max_days = 2
            await db.flush()
            return ListOnStorefrontResult(product_id=product.id, build_id=product.build_id, storefront_url=f"/ready-to-ship/{product.id}")

    orchestration_build = Build(
        build_type=BuildType.PREBUILT,
        manual_build_id=build.id,
        spec_json=build.components,
        status=BuildStatus.FINALISED,
    )
    db.add(orchestration_build)
    await db.flush()
    await db.refresh(orchestration_build)

    product = Product(
        product_type=ProductType.PREBUILT,
        build_id=orchestration_build.id,
        title=build.generated_title,
        description=build.generated_description,
        price=body.price,
        status=ProductStatus.LISTED,
        hero_photo_url=build.hero_photo_url,
        model_3d_url=build.model_3d_url,
        item_specifics=_direct_storefront_item_specifics(build),
        platform_category_id=_PC_BUILD_PLATFORM_CATEGORY_ID,
        platform_category_name=_PC_BUILD_PLATFORM_CATEGORY_NAME,
        selected_faqs=selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides),
        playbook_id=assignment.get("playbook_id"),
        fulfilment_type="prebuilt",
        handling_min_days=1,
        handling_max_days=1,
        delivery_min_days=1,
        delivery_max_days=2,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)

    build.storefront_product_id = product.id
    build.updated_at = datetime.utcnow()
    await db.flush()

    return ListOnStorefrontResult(product_id=product.id, build_id=orchestration_build.id, storefront_url=f"/ready-to-ship/{product.id}")
