from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
import hashlib
import hmac
import re
import uuid
from typing import Any, Literal
from pydantic import BaseModel, Field
from urllib.parse import quote
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile
from app.database import get_db, AsyncSessionLocal
from app.models import Order, BuildCapacity, BuildCapacityOverride, CustomerProblem, CXDocument, Capture3DAsset, Capture3DStatus, Product, Build, WarrantyReserve, WarrantyClaim, ShipmentTrackingEvent, PortalAccessGrant
from app.models.customer_problem_shipment import CustomerProblemShipment
from app.models.customer_problem_notification import CustomerProblemNotification
from app.models.order import OrderStatus
from app.models.build import BuildStatus
from app.models.manual_build import ManualBuild
from app.models.alert_event import AlertEvent
from app.models.getting_started_job import GettingStartedJob
from app.models.ai_setup_purchase import AISetupPurchase
from app.models.app_settings import AppSettings
from app.models.playbook import Playbook
from app.models.benchmark import HardwareBenchmark
from app.models.customer import Customer
from app.routes.auth import get_current_user
from app.routes.admin_auth import get_current_admin
from app.services.auth_service import get_customer_by_token
from app.services.admin_auth_service import get_admin_by_token
from app.services.product_faqs import selected_faqs
from app.services.email_service import (
    send_order_status_email,
    send_guest_portal_claim_email,
)
from app.services.customer_problem_notifications import deliver_customer_problem_notification
from app.services.parcel2go_notifications import deliver_tracking_event_notification
from app.services.payment_service import PaymentService
from app.services.parcel2go_booking import _safe_provider_tracking_url
from app.schemas.order import (
    CapacitySlotsOut,
    AdminOrderOut,
    AdminOrderUpdateIn,
    BuildCapacityOut,
    CapacityOverrideIn,
    MyOrderOut,
    MyOrderSlotOut,
)
from app.schemas.customer_portal import (
    AdminCustomerRepairShipmentOut,
    AdminCustomerProblemOut,
    CustomerDocumentOut,
    CustomerProblemCreate,
    CustomerProblemOut,
    CustomerProblemStatusUpdate,
    CustomerRepairTrackingEventOut,
    CustomerRepairShipmentEventOut,
    CustomerRepairShipmentOut,
)
from jose import jwt, JWTError
from app.config import get_settings
from app.services.software_catalogue import SOFTWARE_CATALOGUE, SOFTWARE_BY_ID, estimate_saved_minutes
from app.services.getting_started_service import (
    customer_software_selection_changed,
    invalidate_ready_to_ship_reviewed_package,
    save_customer_software_selection,
)
from app.services.getting_started_jobs import lock_manual_build_then_getting_started_job
from app.services.ai_setup_offers import public_ai_setup_offers
from app.services.getting_ready_package import (
    package_path,
    GettingReadyPackageError,
    create_portal_leaflet,
    is_customer_package_document_name,
)
from app.services.warranty_service import (
    WARRANTY_CASE_CATEGORIES,
    public_warranty_summary,
    recalculate_reserve_status,
    lock_warranty_reserve_then_claim,
    lock_warranty_sale_owner,
    lock_warranty_owner_then_reserve,
    ensure_order_reserve,
    ensure_manual_build_reserve,
)
from app.services.portal_access import (
    GUEST_PORTAL_TOKEN_DAYS,
    find_printable_portal_claim,
    guest_portal_token_has_capability,
    new_claim_secret,
    redeem_claim_secret,
    record_portal_claim_email_result,
    verify_guest_portal_token,
)

router = APIRouter(prefix="/api/orders", tags=["orders"])
_CUSTOMER_CASE_EVIDENCE_ROOT = Path(__file__).resolve().parents[2] / "data" / "customer_problem_evidence"
_CUSTOMER_CASE_EVIDENCE_TYPES = {
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/webp": ("webp", b"RIFF"),
    "application/pdf": ("pdf", b"%PDF-"),
}
_CUSTOMER_CASE_EVIDENCE_MAX_BYTES = 10 * 1024 * 1024
_CUSTOMER_CASE_MAX_FILES = 12
_CUSTOMER_VISIBLE_GETTING_STARTED_CHECKLIST = (
    "software_selection_submitted",
    "components_ordered",
    "machine_setup_run",
    "windows_deployment_completed",
    "drivers_updates_complete",
    "ai_services_complete",
    "rgb_theme_applied",
    "qa_recheck_passed",
)


def _customer_case_evidence_path(storage_key: str) -> Path:
    root = _CUSTOMER_CASE_EVIDENCE_ROOT.resolve()
    relative = PurePosixPath(storage_key)
    if relative.is_absolute() or not relative.parts or any(part in {".", ".."} for part in relative.parts):
        raise HTTPException(404, "Case evidence not found")
    path = (root / Path(*relative.parts)).resolve()
    if root not in path.parents:
        raise HTTPException(404, "Case evidence not found")
    return path


def _guest_portal_owns_problem(problem: CustomerProblem, grant: PortalAccessGrant) -> bool:
    return bool(
        (grant.order_id is not None and problem.order_id == grant.order_id)
        or (grant.manual_build_id is not None and problem.manual_build_id == grant.manual_build_id)
    )


def _guest_manual_grant_matches_build(grant: PortalAccessGrant, build: ManualBuild) -> bool:
    """Indirect printed claims bind by possession and build ID, not email."""
    printed_channels = {"ebay", "vinted", "marketplace", "printed_insert"}
    if grant.channel == "direct_guest":
        return bool(
            grant.contact_email
            and build.customer_email
            and build.customer_email.strip().lower() == grant.contact_email.strip().lower()
        )
    if grant.channel not in printed_channels:
        return False
    if not grant.contact_email:
        return True
    return bool(
        build.customer_email
        and build.customer_email.strip().lower() == grant.contact_email.strip().lower()
    )


def _guest_support_recovery_message(grant: PortalAccessGrant) -> str:
    if grant.channel == "direct_guest" or grant.order_id is not None:
        return "This portal claim does not allow support requests. Contact FlipFlop using the verified email on your direct order."
    return "This portal claim does not allow support requests. Contact FlipFlop through the marketplace you bought from."


async def _store_customer_case_evidence(problem: CustomerProblem, file: UploadFile) -> dict:
    content_type = file.content_type or ""
    media = _CUSTOMER_CASE_EVIDENCE_TYPES.get(content_type)
    if not media:
        raise HTTPException(415, "Upload a JPEG, PNG, WebP, or PDF evidence file")
    content = await file.read(_CUSTOMER_CASE_EVIDENCE_MAX_BYTES + 1)
    if not content:
        raise HTTPException(400, "The evidence file is empty")
    if len(content) > _CUSTOMER_CASE_EVIDENCE_MAX_BYTES:
        raise HTTPException(413, "Each evidence file must be 10 MB or smaller")
    extension, signature = media
    if content_type == "image/webp":
        valid = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    else:
        valid = content.startswith(signature)
    if not valid:
        raise HTTPException(415, "The file contents do not match the selected file type")

    evidence_id = uuid.uuid4().hex
    storage_key = f"{problem.id}/{evidence_id}.{extension}"
    destination = _customer_case_evidence_path(storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    raw_name = (file.filename or f"evidence.{extension}").replace("\\", "/").rsplit("/", 1)[-1]
    display_name = "".join(character for character in raw_name if ord(character) >= 32 and ord(character) != 127)[:160]
    return {
        "id": evidence_id,
        "filename": display_name or f"evidence.{extension}",
        "content_type": content_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "storage_key": storage_key,
        "uploaded_at": datetime.utcnow().isoformat(),
    }

# The customer storefront is deployed separately from this API. Keep the
# public destination in the portal contract so the storefront can render a
# review CTA without duplicating deployment-specific routing logic.
PUBLIC_REVIEWS_URL = "https://theflipflop.shop/reviews.html"


class GettingStartedSelectionsIn(BaseModel):
    software_package_ids: list[str]


class AISetupPurchaseCreateIn(BaseModel):
    offer_id: str


class OrderCancellationOut(BaseModel):
    order_id: int
    status: str
    refund_status: str
    refund_id: str | None = None


class CustomerBuildChangeRequestIn(BaseModel):
    request_text: str = Field(min_length=20, max_length=3000)


class CustomerBuildChangeResponseIn(BaseModel):
    decision: Literal["decline_quote", "withdraw"]


class AdminBuildChangeReviewIn(BaseModel):
    action: Literal["quote", "reject"]
    customer_message: str = Field(min_length=12, max_length=2000)
    proposed_specs: dict[str, Any] | None = None
    proposed_customer_price: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    internal_note: str | None = Field(default=None, max_length=2000)


def _portal_grant_delivery_guidance(channel: str) -> str:
    if channel == "ebay":
        return "Print and include the QR leaflet in the parcel. Do not send the external claim URL through eBay messages or eBay-mediated email; check eBay's current communication policy before any exception."
    if channel == "vinted":
        return "Print and include the QR leaflet in the parcel. Keep communication on Vinted and do not send the external claim URL or personal contact details in Vinted messages."
    if channel == "printed_insert":
        return "Print and include the QR leaflet in the parcel. Do not post the private claim URL publicly."
    if channel == "direct_guest":
        return "Send the one-time claim link to the verified direct-order email. If email delivery is unavailable, print and include the QR leaflet."
    return "Print and include the QR leaflet unless a current written channel-policy review approves another delivery route."


async def _ensure_refund_reconciliation_alert(db: AsyncSession, order: Order) -> None:
    code = f"order_refund_reconcile_{order.id}"
    existing = (await db.execute(select(AlertEvent).where(AlertEvent.code == code))).scalar_one_or_none()
    if not existing:
        db.add(AlertEvent(
            code=code,
            source="order_cancellation",
            severity="critical",
            message=f"Full refund reconciliation required for cancelled order {order.order_id}.",
            link_url=f"/orders/{order.id}",
        ))


async def _mark_cancelled_order_build_records(db: AsyncSession, order: Order) -> None:
    """Keep the customer portal and build lifecycle aligned after a full refund."""
    job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.order_id == order.id).with_for_update()
    )).scalar_one_or_none()
    if job:
        job.status = "cancelled"
        job.checklist = {
            **(job.checklist or {}),
            "order_cancelled": "complete",
            "customer_selections_locked": "complete",
        }
        job.completed_at = job.completed_at or order.cancelled_at or datetime.utcnow()
        job.updated_at = datetime.utcnow()
    build = (await db.execute(
        select(Build).where(Build.order_id == order.id).with_for_update()
    )).scalar_one_or_none()
    if build:
        build.status = BuildStatus.CANCELLED
        build.updated_at = datetime.utcnow()


class WarrantyClaimUpdateIn(BaseModel):
    status: str
    approved_cost_gbp: float = 0.0
    outcome: str | None = None


class WarrantyReleaseIn(BaseModel):
    confirm_release: bool
    note: str


class ShipmentEventIn(BaseModel):
    order_id: int | None = None
    manual_build_id: int | None = None
    provider: str
    provider_event_id: str | None = None
    status_code: str
    description: str
    location: str | None = None
    tracking_url: str | None = None
    live_map_url: str | None = None
    occurred_at: datetime
    material: bool = False


class PortalGrantCreateIn(BaseModel):
    order_id: int | None = None
    manual_build_id: int | None = None
    contact_email: str | None = None
    channel: str = "direct_guest"
    expires_in_days: int = 400


class PortalGrantRedeemIn(BaseModel):
    claim_token: str


def _tracking_event_dict(event: ShipmentTrackingEvent) -> dict:
    return {
        "id": event.id,
        "provider": event.provider,
        "status_code": event.status_code,
        "description": event.description,
        "location": event.location,
        "tracking_url": _safe_provider_tracking_url(event.tracking_url),
        "live_map_url": _safe_provider_tracking_url(event.live_map_url),
        "occurred_at": event.occurred_at.isoformat(),
    }


def _manual_build_tracking_url(
    build: ManualBuild | None,
    tracking_events: list[ShipmentTrackingEvent],
) -> str | None:
    """Use event tracking first, then the safe URL saved with the booking.

    The booking fallback keeps existing dispatched orders trackable when their
    handover event predates persistence of the tracking URL.
    """
    event_url = next(
        (
            safe_url
            for event in tracking_events
            if (safe_url := _safe_provider_tracking_url(event.tracking_url))
        ),
        None,
    )
    if event_url or not build:
        return event_url
    evidence = build.evidence_data if isinstance(build.evidence_data, dict) else {}
    booking = evidence.get("shipment_booking_confirmation")
    if not isinstance(booking, dict):
        return None
    return _safe_provider_tracking_url(booking.get("tracking_url"))


async def _portal_actor(authorization: str | None, db: AsyncSession):
    """Accept either the buyer JWT or the separate admin JWT.

    The short-lived preview token identifies the build; it is deliberately
    not itself a login credential.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Sign in to access this customer portal")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    token = parts[1]
    customer = await get_customer_by_token(db, token)
    if customer:
        return "customer", customer
    admin = await get_admin_by_token(db, token)
    if admin:
        return "admin", admin
    raise HTTPException(status_code=401, detail="Invalid or expired login")


@router.get("/portal-preview/{preview_token}")
async def get_portal_preview(
    preview_token: str,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    actor_type, actor = await _portal_actor(authorization, db)
    try:
        claims = jwt.decode(preview_token, get_settings().secret_key, algorithms=[get_settings().jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Preview expired or invalid")
    if claims.get("typ") != "portal_preview" or claims.get("scope") != "read":
        raise HTTPException(status_code=403, detail="Invalid preview scope")
    build_id = int(claims.get("build_id") or 0)
    order_id = int(claims.get("order_id") or 0)
    if build_id and not order_id:
        build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
        if not build or build.status not in {"built", "listed", "sold"} or not build.model_3d_url:
            raise HTTPException(status_code=404, detail="Build portal not found")
        buyer_order = None
        if actor_type != "admin":
            # A buyer can access a manual build only through the storefront
            # order that sold its linked product.
            buyer_order = (await db.execute(
                select(Order).join(Product, Product.sold_order_id == Order.id)
                .join(Build, Build.id == Product.build_id)
                .where(Build.manual_build_id == build.id, Order.customer_id == actor.id)
            )).scalar_one_or_none()
            if not buyer_order:
                raise HTTPException(status_code=404, detail="Build portal not found")
        ready_job = (await db.execute(select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build.id))).scalar_one_or_none()
        reserve = await _manual_build_portal_warranty_reserve(
            db,
            build,
            order_id=buyer_order.id if buyer_order else None,
        )
        events = (await db.execute(select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.manual_build_id == build.id).order_by(ShipmentTrackingEvent.occurred_at.desc()))).scalars().all()
        return _manual_build_to_portal_out(build, ready_job, reserve, list(events))

    if order_id:
        order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        if order and (actor_type == "admin" or order.customer_id == actor.id):
            asset = (await db.execute(select(Capture3DAsset).where(Capture3DAsset.order_id == order.id))).scalar_one_or_none()
            manual_build = await _manual_build_sold_on_order(db, order.id)
            getting_started_job = (await db.execute(select(GettingStartedJob).where(GettingStartedJob.order_id == order.id))).scalar_one_or_none()
            reserve = (await db.execute(select(WarrantyReserve).where(WarrantyReserve.order_id == order.id))).scalar_one_or_none()
            events = (await db.execute(select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.order_id == order.id).order_by(ShipmentTrackingEvent.occurred_at.desc()))).scalars().all()
            return _order_to_my_order_out(order, asset, manual_build, getting_started_job, reserve, list(events))
    raise HTTPException(status_code=404, detail="Build portal not found")


async def _manual_build_portal_warranty_reserve(
    db: AsyncSession,
    build: ManualBuild,
    *,
    order_id: int | None = None,
) -> WarrantyReserve | None:
    """Use the sale-owned reserve for a linked order, otherwise the build reserve."""
    if order_id is None and build.storefront_product_id:
        product = await db.get(Product, build.storefront_product_id)
        order_id = product.sold_order_id if product else None
    if order_id is not None:
        order_reserve = (await db.execute(
            select(WarrantyReserve).where(WarrantyReserve.order_id == order_id)
        )).scalar_one_or_none()
        if order_reserve is not None:
            return order_reserve
    return (await db.execute(
        select(WarrantyReserve).where(WarrantyReserve.manual_build_id == build.id)
    )).scalar_one_or_none()


@router.post("/guest-portal/redeem")
async def redeem_guest_portal_claim(body: PortalGrantRedeemIn, db: AsyncSession = Depends(get_db)):
    if len(body.claim_token) < 32 or len(body.claim_token) > 200:
        raise HTTPException(401, "This portal claim link is invalid or has expired")
    redeemed = await redeem_claim_secret(db, body.claim_token)
    if not redeemed:
        raise HTTPException(401, "This portal claim link is invalid, expired or already used")
    grant, access_token = redeemed
    await db.commit()
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in_days": GUEST_PORTAL_TOKEN_DAYS,
        "order_id": grant.order_id,
        "manual_build_id": grant.manual_build_id,
    }


@router.get("/guest-portal", response_model=MyOrderOut)
async def get_guest_portal(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Guest portal access token required")
    grant = await verify_guest_portal_token(db, parts[1])
    if not grant:
        raise HTTPException(401, "Guest portal access has expired or been revoked")
    if grant.order_id:
        order = await db.get(Order, grant.order_id)
        if not order:
            raise HTTPException(404, "Order portal not found")
        asset = (await db.execute(select(Capture3DAsset).where(Capture3DAsset.order_id == order.id))).scalar_one_or_none()
        manual_build = await _manual_build_sold_on_order(db, order.id)
        job = (await db.execute(select(GettingStartedJob).where(GettingStartedJob.order_id == order.id))).scalar_one_or_none()
        reserve = (await db.execute(select(WarrantyReserve).where(WarrantyReserve.order_id == order.id))).scalar_one_or_none()
        events = (await db.execute(select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.order_id == order.id).order_by(ShipmentTrackingEvent.occurred_at.desc()))).scalars().all()
        portal = _order_to_my_order_out(order, asset, manual_build, job, reserve, list(events))
        if portal.customer_hub is not None:
            portal.customer_hub["getting_started_setup"] = _getting_started_portal_summary(job, guest=True)
        portal.portal_support_case_create_allowed = guest_portal_token_has_capability(parts[1], "support:create")
        return portal
    build = await db.get(ManualBuild, grant.manual_build_id)
    if not build:
        raise HTTPException(404, "Build portal not found")
    job = (await db.execute(select(GettingStartedJob).where(GettingStartedJob.manual_build_id == build.id))).scalar_one_or_none()
    reserve = await _manual_build_portal_warranty_reserve(db, build)
    events = (await db.execute(select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.manual_build_id == build.id).order_by(ShipmentTrackingEvent.occurred_at.desc()))).scalars().all()
    portal = _manual_build_to_portal_out(build, job, reserve, list(events))
    if portal.customer_hub is not None:
        portal.customer_hub["getting_started_setup"] = _getting_started_portal_summary(job, guest=True)
    portal.portal_support_case_create_allowed = guest_portal_token_has_capability(parts[1], "support:create")
    return portal


@router.get("/guest-portal/problems", response_model=list[CustomerProblemOut])
async def list_guest_portal_problems(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Guest portal access token required")
    grant = await verify_guest_portal_token(db, parts[1])
    if not grant:
        raise HTTPException(401, "Guest portal access has expired or been revoked")
    query = select(CustomerProblem).where(
        CustomerProblem.order_id == grant.order_id
        if grant.order_id
        else CustomerProblem.manual_build_id == grant.manual_build_id
    ).order_by(CustomerProblem.created_at.desc())
    problems = list((await db.execute(query)).scalars().all())
    return await _customer_problem_outputs(db, problems)


@router.post("/guest-portal/problems", response_model=CustomerProblemOut, status_code=201)
async def create_guest_portal_problem(
    body: CustomerProblemCreate,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Guest portal access token required")
    grant = await verify_guest_portal_token(db, parts[1])
    if not grant:
        raise HTTPException(401, "Guest portal access has expired or been revoked")
    if not guest_portal_token_has_capability(parts[1], "support:create"):
        raise HTTPException(403, _guest_support_recovery_message(grant))
    recent_count = await db.scalar(
        select(func.count()).select_from(CustomerProblem).where(
            CustomerProblem.portal_grant_id == grant.id,
            CustomerProblem.created_at >= datetime.utcnow() - timedelta(hours=24),
        )
    )
    if int(recent_count or 0) >= 10:
        raise HTTPException(429, "This portal has reached its daily support request limit. Contact FlipFlop if you need urgent help.")
    if grant.order_id:
        order = await db.get(Order, grant.order_id)
        if not order:
            raise HTTPException(404, "Order portal not found")
        customer = await db.get(Customer, order.customer_id)
        if not grant.contact_email or not customer or customer.email.strip().lower() != grant.contact_email.strip().lower():
            raise HTTPException(403, "The verified contact for this portal no longer matches the order")
        return await _create_customer_problem(
            db, order=order, build=None, customer_id=customer.id, grant=grant,
            category=body.category, description=body.description,
        )
    build = await db.get(ManualBuild, grant.manual_build_id)
    if not build:
        raise HTTPException(404, "Build portal not found")
    if not _guest_manual_grant_matches_build(grant, build):
        raise HTTPException(403, "This marketplace portal claim does not match its build. Contact FlipFlop through the marketplace you bought from.")
    return await _create_customer_problem(
        db, order=None, build=build, customer_id=build.customer_id, grant=grant,
        category=body.category, description=body.description,
    )


@router.post("/guest-portal/problems/{problem_id}/evidence", status_code=201)
async def upload_guest_problem_evidence(
    problem_id: int,
    file: UploadFile = File(...),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Guest portal access token required")
    grant = await verify_guest_portal_token(db, parts[1])
    if not grant:
        raise HTTPException(401, "Guest portal access has expired or been revoked")
    if not guest_portal_token_has_capability(parts[1], "support:create"):
        raise HTTPException(403, "This guest portal cannot upload support evidence")
    problem = (await db.execute(select(CustomerProblem).where(CustomerProblem.id == problem_id).with_for_update())).scalar_one_or_none()
    if not problem or not _guest_portal_owns_problem(problem, grant):
        raise HTTPException(404, "Support case not found in this portal")
    evidence_files = list(problem.evidence_files or [])
    if len(evidence_files) >= _CUSTOMER_CASE_MAX_FILES:
        raise HTTPException(413, f"A support case can contain up to {_CUSTOMER_CASE_MAX_FILES} images")
    item = await _store_customer_case_evidence(problem, file)
    problem.evidence_files = [*evidence_files, item]
    try:
        await db.commit()
    except Exception:
        _customer_case_evidence_path(item["storage_key"]).unlink(missing_ok=True)
        raise
    return problem.evidence[-1]


@router.get("/guest-portal/problems/{problem_id}/evidence/{evidence_id}")
async def download_guest_problem_evidence(
    problem_id: int,
    evidence_id: str,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Guest portal access token required")
    grant = await verify_guest_portal_token(db, parts[1])
    if not grant:
        raise HTTPException(401, "Guest portal access has expired or been revoked")
    problem = (await db.execute(select(CustomerProblem).where(CustomerProblem.id == problem_id))).scalar_one_or_none()
    if not problem or not _guest_portal_owns_problem(problem, grant):
        raise HTTPException(404, "Support case not found in this portal")
    return _customer_case_evidence_response(problem, evidence_id)


@router.get("/guest-portal/package")
async def download_guest_portal_package(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Download only the reviewed package attached to this guest's one build."""
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Guest portal access token required")
    grant = await verify_guest_portal_token(db, parts[1])
    if not grant:
        raise HTTPException(401, "Guest portal access has expired or been revoked")
    query = select(GettingStartedJob)
    query = query.where(GettingStartedJob.order_id == grant.order_id) if grant.order_id else query.where(GettingStartedJob.manual_build_id == grant.manual_build_id)
    job = (await db.execute(query)).scalar_one_or_none()
    packages = [
        item for item in (job.artifact_index or [])
        if item.get("category") == "customer_package"
    ] if job and job.reviewed_at else []
    if not packages:
        raise HTTPException(404, "The reviewed Getting Ready package is not available yet")
    artifact = max(packages, key=lambda item: int(item.get("version") or 0))
    return _customer_package_archive_response(artifact)


@router.get("/guest-portal/document")
async def download_guest_portal_document(
    name: str,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Guest portal access token required")
    grant = await verify_guest_portal_token(db, parts[1])
    if not grant:
        raise HTTPException(401, "Guest portal access has expired or been revoked")
    query = select(GettingStartedJob)
    query = query.where(GettingStartedJob.order_id == grant.order_id) if grant.order_id else query.where(GettingStartedJob.manual_build_id == grant.manual_build_id)
    job = (await db.execute(query)).scalar_one_or_none()
    _artifact, content, media_type = _read_customer_package_document(job, name)
    filename = PurePosixPath(name).name
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


_CUSTOMER_PACKAGE_DOCUMENTS = {
    "01-build-plaque.pdf": ("Your build plaque", "application/pdf"),
    "01-build-plaque.json": ("Build plaque details", "application/json"),
    "02-build-specification.pdf": ("Build specification", "application/pdf"),
    "02-build-specification.json": ("Build specification data", "application/json"),
    "03-benchmark-results.pdf": ("Benchmark results", "application/pdf"),
    "03-benchmark-results.json": ("Benchmark results data", "application/json"),
    "04-getting-started-guide.md": ("Getting started guide", "text/markdown; charset=utf-8"),
    "08-upgrade-path.html": ("Upgrade path", "text/html; charset=utf-8"),
    "10-personalized-portal-leaflet.pdf": ("Your portal leaflet", "application/pdf"),
}


def _customer_package_document_index(artifact: dict, *, guest: bool, order_id: int | None) -> list[dict]:
    package_names = _allowlisted_customer_document_names(artifact)
    endpoint = "/api/orders/guest-portal/document" if guest or not order_id else f"/api/orders/{order_id}/getting-started/document"
    entries: list[dict] = []
    for name in sorted(package_names):
        if name in _CUSTOMER_PACKAGE_DOCUMENTS:
            title, media_type = _CUSTOMER_PACKAGE_DOCUMENTS[name]
        else:
            title = f"Component manual: {PurePosixPath(name).stem.split('-', 1)[-1].replace('-', ' ').title()}"
            media_type = "application/pdf"
        entries.append({
            "title": title,
            "filename": PurePosixPath(name).name,
            "download_url": f"{endpoint}?name={quote(name, safe='')}",
            "media_type": media_type,
        })
    return entries


def _allowlisted_customer_document_names(artifact: dict) -> set[str]:
    raw_names = artifact.get("documents")
    if not isinstance(raw_names, (list, tuple, set)):
        return set()
    return {name for name in raw_names if is_customer_package_document_name(name)}


def _verify_customer_package_members(path: Path, artifact: dict) -> None:
    """Ensure a trusted archive flag cannot expose a mixed workshop ZIP."""
    allowed_documents = _allowlisted_customer_document_names(artifact)
    expected_names = allowed_documents | {"CHECKSUMS.sha256"}
    try:
        with ZipFile(path) as archive:
            member_names = archive.namelist()
            if len(member_names) != len(set(member_names)):
                raise HTTPException(409, "The reviewed customer package contains duplicate files")
            actual_names = set(member_names)
    except (OSError, BadZipFile) as error:
        raise HTTPException(409, "The reviewed customer package is not a valid ZIP") from error
    if not allowed_documents or actual_names != expected_names:
        raise HTTPException(409, "The reviewed customer package contains unapproved or missing files")


def _customer_package_archive_response(artifact: dict) -> Response:
    """Serve customer documents only, sanitizing older mixed-content ZIPs."""
    try:
        path = package_path(str(artifact["storage_key"]))
    except GettingReadyPackageError as error:
        raise HTTPException(404, str(error)) from error
    if not path.is_file():
        raise HTTPException(404, "The reviewed Getting Ready package file is missing")
    _verify_customer_package_archive(path, artifact)
    filename = str(artifact.get("filename") or "customer-documents.zip")
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
    }
    if artifact.get("customer_safe") is True:
        _verify_customer_package_members(path, artifact)
        return FileResponse(path, media_type="application/zip", filename=filename, headers=headers)

    # Previously generated archives combined workshop scripts with customer
    # documents. Keep them safe after upgrade without requiring a database
    # migration or waiting for package regeneration.
    customer_documents = _allowlisted_customer_document_names(artifact)
    if not customer_documents:
        raise HTTPException(404, "The reviewed package contains no customer documents")
    try:
        with ZipFile(path) as source, BytesIO() as output:
            with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as customer_archive:
                checksums = {}
                for name in sorted(customer_documents):
                    content = source.read(name)
                    customer_archive.writestr(name, content)
                    checksums[name] = hashlib.sha256(content).hexdigest()
                customer_archive.writestr(
                    "CHECKSUMS.sha256",
                    "\n".join(f"{digest}  {name}" for name, digest in checksums.items()) + "\n",
                )
            content = output.getvalue()
    except (GettingReadyPackageError, OSError, KeyError, BadZipFile) as error:
        raise HTTPException(404, "Customer documents are unavailable") from error
    headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
    return Response(content, media_type="application/zip", headers=headers)


def _verify_customer_package_archive(path: Path, artifact: dict) -> None:
    """Fail closed if the reviewed archive no longer matches its stored digest."""
    expected = artifact.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise HTTPException(409, "The reviewed customer package has no valid integrity record")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as package_file:
            for chunk in iter(lambda: package_file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise HTTPException(404, "The reviewed Getting Ready package file is missing") from error
    if not hmac.compare_digest(digest.hexdigest(), expected.lower()):
        raise HTTPException(409, "The reviewed customer package failed its integrity check")


def _read_customer_package_document(job: GettingStartedJob | None, name: str) -> tuple[dict, bytes, str]:
    """Read only a customer-facing entry named in the latest reviewed ZIP."""
    safe_name = PurePosixPath(name)
    if not name or safe_name.is_absolute() or ".." in safe_name.parts or "\\" in name:
        raise HTTPException(404, "Customer document not found")
    packages = [item for item in (job.artifact_index or []) if item.get("category") == "customer_package"] if job and job.reviewed_at else []
    if not packages:
        raise HTTPException(404, "The reviewed Getting Ready package is not available yet")
    artifact = max(packages, key=lambda item: int(item.get("version") or 0))
    if name not in _allowlisted_customer_document_names(artifact):
        raise HTTPException(404, "Customer document not found")
    try:
        path = package_path(str(artifact["storage_key"]))
        if not path.is_file():
            raise GettingReadyPackageError("The reviewed package file is missing")
        _verify_customer_package_archive(path, artifact)
        with ZipFile(path) as archive:
            content = archive.read(name)
    except (GettingReadyPackageError, OSError, KeyError, BadZipFile) as error:
        raise HTTPException(404, "Customer document is unavailable") from error
    media_type = _CUSTOMER_PACKAGE_DOCUMENTS.get(name, ("", "application/pdf"))[1]
    return artifact, content, media_type


def _customer_visible_ai_setup_services(value: Any) -> list[dict[str, Any]]:
    """Expose confirmed purchase details without payment-provider or worker metadata."""
    allowed = (
        "id",
        "name",
        "description",
        "included_automations",
        "price_gbp",
        "requires_vram_gb",
        "payment_status",
        "purchased_at",
    )
    visible = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict) or item.get("payment_status") != "paid":
            continue
        visible.append({key: item[key] for key in allowed if key in item})
    return visible


def _getting_started_portal_summary(job: GettingStartedJob | None, *, guest: bool = False) -> dict | None:
    if not job:
        return None
    raw_checklist = job.checklist or {}
    customer_checklist = {
        key: raw_checklist[key]
        for key in _CUSTOMER_VISIBLE_GETTING_STARTED_CHECKLIST
        if isinstance(raw_checklist.get(key), (str, bool))
    }
    software_selection_submitted = raw_checklist.get("software_selection_submitted") is True
    selected_package_ids = [
        package_id for package_id in (job.customer_software_selections or [])
        if software_selection_submitted
        and isinstance(package_id, str)
        and package_id in SOFTWARE_BY_ID
    ]
    selected_apps = [
        {
            "package_id": package_id,
            "name": SOFTWARE_BY_ID[package_id]["name"],
            "category": SOFTWARE_BY_ID[package_id]["category"],
            "estimated_minutes_saved": SOFTWARE_BY_ID[package_id]["estimated_minutes_saved"],
            "license_note": SOFTWARE_BY_ID[package_id]["license_note"],
        }
        for package_id in selected_package_ids
    ]
    summary = {
        "status": job.status,
        "source_type": job.source_type,
        "software_selections": selected_package_ids,
        "software_selection": {
            "submitted": software_selection_submitted,
            "apps": selected_apps,
            "estimated_time_saved_minutes": estimate_saved_minutes(selected_package_ids),
            "time_estimate_basis": "Indicative internal estimate for avoiding manual search/download/setup; it is not benchmarked or guaranteed.",
        },
        "purchased_ai_services": _customer_visible_ai_setup_services(job.purchased_ai_services),
        # Internal notes, actor identifiers, drive serials, and audit evidence
        # remain private to Dispatch Centre and never enter customer/guest APIs.
        "checklist": customer_checklist,
        "last_updated": job.updated_at.isoformat() if job.updated_at else None,
    }
    if job.reviewed_at and job.manifest:
        packages = [item for item in (job.artifact_index or []) if item.get("category") == "customer_package"]
        if packages:
            latest = max(packages, key=lambda item: int(item.get("version") or 0))
            summary["customer_package"] = {
                "version": latest.get("version"),
                "filename": latest.get("filename"),
                "size_bytes": latest.get("size_bytes"),
                "sha256": latest.get("sha256"),
                "download_url": "/api/orders/guest-portal/package" if guest or not job.order_id
                else f"/api/orders/{job.order_id}/getting-started/package",
            }
            summary["customer_documents"] = _customer_package_document_index(latest, guest=guest, order_id=job.order_id)
    return summary


async def _getting_started_recommendation_profile(db, order, job, manual_build) -> dict:
    """Resolve saved recommendations, reconstructing the exact cell for legacy orders."""
    profile = (order.specs or {}).get("software_profile") or {}
    assignment = (
        ((manual_build.evidence_data or {}).get("playbook_assignment") or {})
        if manual_build else {}
    )
    if not profile:
        profile = assignment.get("software_profile") or {}
    playbook_id = job.playbook_id or getattr(order, "playbook_id", None)
    if profile or not playbook_id:
        return profile

    playbook = await db.get(Playbook, playbook_id)
    if not playbook:
        return {}

    from app.services.product_software import (
        software_profile_for_curated_cell_from_db,
        software_profile_for_playbook_cell_from_db,
    )

    order_specs = order.specs or {}
    curated_build_id = str(
        order_specs.get("curated_build_id") or assignment.get("curated_build_id") or ""
    ).strip()
    budget_tier = str(order_specs.get("budget_tier") or "").strip()
    if curated_build_id:
        return await software_profile_for_curated_cell_from_db(
            db, curated_build_id, playbook.name, playbook.software_profile
        )
    if budget_tier and job.source_type == "made_by_you":
        return await software_profile_for_playbook_cell_from_db(
            db, playbook.name, budget_tier, playbook.software_profile
        )
    return playbook.software_profile or {}


async def _customer_problem_outputs(
    db: AsyncSession,
    problems: list[CustomerProblem],
    *,
    admin: bool = False,
) -> list[CustomerProblemOut]:
    """Render allow-listed repair tracking history without exposing provider linkage or admin audit."""
    problem_ids = [problem.id for problem in problems]
    events_by_problem: dict[int, list[CustomerRepairTrackingEventOut]] = {}
    shipments_by_problem: dict[int, list[AdminCustomerRepairShipmentOut]] = {}
    if problem_ids:
        shipments = (await db.execute(
            select(CustomerProblemShipment)
            .where(CustomerProblemShipment.customer_problem_id.in_(problem_ids))
            .order_by(CustomerProblemShipment.created_at.asc(), CustomerProblemShipment.id.asc())
        )).scalars().all()
        shipment_ids = [shipment.id for shipment in shipments]
        events = (await db.execute(
            select(ShipmentTrackingEvent)
            .where(ShipmentTrackingEvent.customer_problem_shipment_id.in_(shipment_ids))
            .order_by(ShipmentTrackingEvent.occurred_at.desc(), ShipmentTrackingEvent.id.desc())
        )).scalars().all() if shipment_ids else []
        events_by_shipment: dict[int, list[CustomerRepairShipmentEventOut]] = {}
        for event in events:
            events_by_shipment.setdefault(event.customer_problem_shipment_id, []).append(
                CustomerRepairShipmentEventOut(
                    status_code=event.status_code,
                    description=event.description,
                    location=event.location,
                    occurred_at=event.occurred_at,
                    tracking_url=event.tracking_url,
                )
            )
        for shipment in shipments:
            item = AdminCustomerRepairShipmentOut.model_validate(shipment)
            item.events = events_by_shipment.get(shipment.id, [])
            shipments_by_problem.setdefault(shipment.customer_problem_id, []).append(item)

        # Read legacy case-attached events during a rolling migration window.
        legacy_events = (await db.execute(
            select(ShipmentTrackingEvent)
            .where(ShipmentTrackingEvent.customer_problem_id.in_(problem_ids))
            .order_by(ShipmentTrackingEvent.occurred_at.desc(), ShipmentTrackingEvent.id.desc())
        )).scalars().all()
        for event in legacy_events:
            events_by_problem.setdefault(event.customer_problem_id, []).append(
                CustomerRepairTrackingEventOut(
                    status_code=event.status_code,
                    description=event.description,
                    location=event.location,
                    occurred_at=event.occurred_at,
                    tracking_url=event.tracking_url,
                )
            )

    output: list[CustomerProblemOut] = []
    for problem in problems:
        response = (
            AdminCustomerProblemOut.model_validate(problem)
            if admin
            else CustomerProblemOut.model_validate(problem)
        )
        if response.repair_tracking:
            response.repair_tracking = response.repair_tracking.model_copy(
                update={"events": events_by_problem.get(problem.id, [])}
            )
        items = shipments_by_problem.get(problem.id, [])
        if admin:
            response.repair_shipments = items
        else:
            response.repair_shipments = [
                CustomerRepairShipmentOut.model_validate(item.model_dump()) for item in items
            ]
        output.append(response)
    return output


def _confirmed_gpu_vram_gb(value: object) -> float | None:
    """Read only explicit benchmark VRAM fields; never infer from GPU names."""
    if isinstance(value, dict):
        values: list[float] = []
        explicit = value.get("gpu_vram_gb")
        if isinstance(explicit, (int, float)) and not isinstance(explicit, bool) and explicit >= 0:
            values.append(float(explicit))
        gpu = value.get("gpu")
        if isinstance(gpu, dict):
            raw = gpu.get("vram_gb")
            if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw >= 0:
                values.append(float(raw))
        for key, child in value.items():
            if key == "gpu":
                continue
            found = _confirmed_gpu_vram_gb(child)
            if found is not None:
                values.append(found)
        return max(values) if values else None
    elif isinstance(value, list):
        values = []
        for child in value:
            found = _confirmed_gpu_vram_gb(child)
            if found is not None:
                values.append(found)
        return max(values) if values else None
    return None


async def _order_gpu_vram_gb(db: AsyncSession, order: Order) -> float | None:
    found = _confirmed_gpu_vram_gb(order.specs or {})
    if found is not None:
        return found
    manual_build = await _manual_build_sold_on_order(db, order.id)
    if manual_build:
        found = _confirmed_gpu_vram_gb(manual_build.evidence_data or {})
        if found is not None:
            return found

    gpu_names: set[str] = set()
    specs = order.specs or {}
    slots = specs.get("slots") if isinstance(specs, dict) else None
    if isinstance(slots, list):
        for item in slots:
            if isinstance(item, dict) and str(item.get("slot_type") or "").casefold() in {"gpu", "graphics"}:
                title = item.get("title") or item.get("name")
                if isinstance(title, str) and title.strip():
                    gpu_names.add(title.strip())
    if manual_build and isinstance(manual_build.components, list):
        for item in manual_build.components:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("component_type") or item.get("slot_type") or item.get("type") or "").casefold()
            if kind in {"gpu", "graphics", "graphics_card"}:
                title = item.get("name") or item.get("model") or item.get("title")
                if isinstance(title, str) and title.strip():
                    gpu_names.add(title.strip())
    if not gpu_names:
        return None
    from app.services.benchmark_normaliser import normalise_gpu
    normalized_names = {value for name in gpu_names if (value := normalise_gpu(name))}
    if not normalized_names:
        return None
    benchmarks = (await db.execute(
        select(HardwareBenchmark).where(
            HardwareBenchmark.component_type == "gpu",
            HardwareBenchmark.normalized_model.in_(normalized_names),
            HardwareBenchmark.vram_gb.is_not(None),
            HardwareBenchmark.source_url.is_not(None),
            HardwareBenchmark.confidence_score >= 0.7,
        ).order_by(HardwareBenchmark.confidence_score.desc())
    )).scalars().all()
    if not benchmarks:
        return None
    return float(benchmarks[0].vram_gb)


def _manual_build_customer_hub(build: ManualBuild, getting_started_job: GettingStartedJob | None = None, warranty_reserve: WarrantyReserve | None = None) -> dict:
    evidence = dict(build.evidence_data or {})
    performance = dict(evidence.get("performance_card") or {})
    evaluation = dict(build.last_evaluation or {})
    upgrades = evaluation.get("upgrade_plan") or evaluation.get("upgrades") or []
    if isinstance(upgrades, dict):
        upgrades = [upgrades]
    return {
        "build_name": build.generated_title or build.name,
        "hero_photo_url": build.hero_photo_url,
        "model": {"url": build.model_3d_url, "preview_image_url": build.hero_photo_url, "status": "published", "ar_ready": True},
        "performance": {
            "available": bool(performance),
            "data": performance,
            "message": "Measured results for this specific build." if performance else "Performance data will appear when benchmark results are published.",
        },
        "upgrade_plan": {
            "title": "Upgrade path",
            "intro": "Compatibility must be checked against the exact components in this build before any upgrade.",
            "items": upgrades,
        },
        "getting_started": [
            "Remove transit protection and check that all internal components are secure.",
            "Connect the display to the graphics card where one is fitted.",
            "Connect keyboard, mouse and network, then run Windows Update.",
            "Keep the packaging until the machine has been checked and accepted.",
        ],
        "getting_started_setup": _getting_started_portal_summary(getting_started_job),
        "warranty": public_warranty_summary(
            warranty_reserve,
            started_at=build.warranty_started_at or build.delivered_at,
        ),
        "troubleshooting": [
            {"title": "No display", "steps": ["Check power to the monitor and PC.", "Check the display cable is connected to the graphics card.", "Try the supplied cable and another monitor input."]},
            {"title": "No power", "steps": ["Check the rear PSU switch and wall socket.", "Reseat the mains cable.", "Do not open the PSU; contact support if the issue remains."]},
            {"title": "Network or audio issue", "steps": ["Run Windows Update and restart.", "Check the selected output device and network connection.", "Contact support with the exact symptom if it persists."]},
        ],
        "downloads": ([{"title": "Exact build 3D model (GLB)", "url": build.model_3d_url, "kind": "3d_model"}] if build.model_3d_url else []),
        "driver_note": "No build-specific driver bundle has been published. Use the component manufacturer's support page for the exact part shown in the specification.",
        "policies": {
            "returns": "For online purchases, notify us within 14 days of delivery and return the machine within the following 14 days. FlipFlop pays reasonable return costs for faulty, damaged, or misdescribed goods; change-of-mind return postage is paid by the customer.",
            "warranty": "Your build includes a 12-month FlipFlop warranty. It does not replace or reduce your statutory consumer rights; see the full Warranty & Support policy.",
            "delivery": f"Your order-specific estimate and courier tracking are shown below. The usual post-dispatch delivery window is {build.delivery_min_days}-{build.delivery_max_days} days, subject to courier conditions.",
            "support": "Use the private support form in this portal and include the build ID and any error message.",
        },
        "reviews": {
            "url": f"{PUBLIC_REVIEWS_URL}?build={build.id}",
            "label": "Leave a review",
            "description": "Tell us how your FlipFlop build is performing.",
        },
        "faqs": selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides),
    }


def _order_customer_hub(
    model_url: str | None,
    preview_image_url: str | None = None,
    order_id: int | str | None = None,
    warranty_reserve: WarrantyReserve | None = None,
    warranty_started_at: datetime | None = None,
) -> dict:
    """Baseline hub for a normal customer order when no ManualBuild row is linked."""
    return {
        "model": {"url": model_url, "preview_image_url": preview_image_url, "status": "published" if model_url else "pending", "ar_ready": bool(model_url)},
        "performance": {"available": False, "data": {}, "message": "Benchmark data will appear here when it has been published for this build."},
        "upgrade_plan": {"title": "Upgrade path", "intro": "Compatibility must be checked against the exact components in this build before any upgrade.", "items": []},
        "getting_started": ["Remove transit protection and check that all internal components are secure.", "Connect the display to the graphics card where one is fitted.", "Connect keyboard, mouse and network, then run Windows Update.", "Keep the packaging until the machine has been checked and accepted."],
        "troubleshooting": [{"title": "No display", "steps": ["Check power to the monitor and PC.", "Check the display cable is connected to the graphics card.", "Contact support if the issue remains."]}],
        "warranty": public_warranty_summary(warranty_reserve, started_at=warranty_started_at),
        "downloads": ([{"title": "Exact build 3D model (GLB)", "url": model_url, "kind": "3d_model"}] if model_url else []),
        "driver_note": "No build-specific driver bundle has been published. Use the component manufacturer's support page for the exact part shown in the specification.",
        "policies": {"returns": "For online purchases, notify us within 14 days of delivery and return the machine within the following 14 days. FlipFlop pays reasonable return costs for faulty, damaged, or misdescribed goods; change-of-mind return postage is paid by the customer.", "warranty": "Your build includes a 12-month FlipFlop warranty. It does not replace or reduce your statutory consumer rights; see the full Warranty & Support policy.", "delivery": "Your saved order estimate and courier tracking are shown in the order tracking section.", "support": "Use the private support form in this portal."},
        "reviews": {
            "url": f"{PUBLIC_REVIEWS_URL}?order={order_id}" if order_id else PUBLIC_REVIEWS_URL,
            "label": "Leave a review",
            "description": "Tell us how your FlipFlop build is performing.",
        },
        "faqs": [],
    }


def _manual_build_to_portal_out(build: ManualBuild, getting_started_job: GettingStartedJob | None = None, warranty_reserve: WarrantyReserve | None = None, tracking_events: list[ShipmentTrackingEvent] | None = None) -> MyOrderOut:
    """Represent a ready-to-ship build in the existing owner-portal contract."""
    components = list(build.components or [])
    case = next(
        (item for item in components if str(item.get("slot", "")).lower() in {"case", "chassis"}),
        None,
    )
    slots = [
        MyOrderSlotOut(
            slot_id=index,
            slot_type=str(item.get("slot") or "component"),
            variant_id=int(item.get("part_id") or 0),
            title=str(item.get("name") or "Component"),
            price=float(item.get("price_paid") or 0),
        )
        for index, item in enumerate(components, start=1)
        if item is not case
    ]
    asking_price = float(build.ebay_price or (build.last_evaluation or {}).get("mid") or 0)
    tracking_events = tracking_events or []
    latest_live_map = next((event.live_map_url for event in tracking_events if event.live_map_url), None)
    latest_tracking_url = _manual_build_tracking_url(build, tracking_events)
    return MyOrderOut(
        id=build.id,
        order_id=f"BUILD-{build.id}",
        status=build.status,
        customer_price=asking_price,
        component_costs=float(build.total_cost or 0),
        slots=slots,
        case_name=str(case.get("name")) if case else None,
        case_price=float(case.get("price_paid") or 0) if case else 0.0,
        capture_3d={
            "status": "published",
            "optimized_asset_ref": build.model_3d_url,
            "preview_image_ref": build.hero_photo_url,
            "ar_ready": True,
        },
        model_3d_url=build.model_3d_url,
        delivered_at=build.delivered_at,
        tracking_number=build.tracking_number,
        carrier=(build.parcel2go_service_slug or "").split("-")[0] or None,
        tracking_url=latest_tracking_url,
        live_tracking_available=bool(latest_live_map),
        live_map_url=latest_live_map,
        tracking_events=[_tracking_event_dict(event) for event in tracking_events],
        customer_hub=_manual_build_customer_hub(build, getting_started_job, warranty_reserve),
        review_url=f"{PUBLIC_REVIEWS_URL}?build={build.id}",
        created_at=build.created_at,
    )


async def _manual_build_sold_on_order(
    db: AsyncSession, order_id: int, *, for_update: bool = False
) -> ManualBuild | None:
    """Load the pre-sale workshop build attached to a sold Product order."""
    query = (
        select(ManualBuild)
        .join(Build, Build.manual_build_id == ManualBuild.id)
        .outerjoin(Product, Product.build_id == Build.id)
        .where(or_(Product.sold_order_id == order_id, Build.order_id == order_id))
        .limit(1)
    )
    if for_update:
        query = query.with_for_update(of=ManualBuild).execution_options(populate_existing=True)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def _sync_linked_manual_build_delivery(
    db: AsyncSession, order_id: int, delivered_at: datetime
) -> ManualBuild | None:
    """Mirror confirmed order delivery onto its linked physical-build record."""
    build = await _manual_build_sold_on_order(db, order_id, for_update=True)
    if not build:
        return None
    build.delivered_at = min(
        value for value in (build.delivered_at, delivered_at) if value is not None
    )
    build.warranty_started_at = min(
        value for value in (build.warranty_started_at, build.delivered_at)
        if value is not None
    )
    build.dispatch_status = "delivered"
    return build


def _order_to_my_order_out(
    order: Order,
    capture_3d: Capture3DAsset | None = None,
    manual_build: ManualBuild | None = None,
    getting_started_job: GettingStartedJob | None = None,
    warranty_reserve: WarrantyReserve | None = None,
    tracking_events: list[ShipmentTrackingEvent] | None = None,
) -> MyOrderOut:
    specs = order.specs or {}
    cancellation_retryable = order.cancellation_status in {"refund_pending", "refund_failed"}
    cancellation_before_parts = (
        order.status == OrderStatus.AWAITING_SOURCING
        and bool(order.stripe_payment_intent_id)
        and not (getting_started_job and (getting_started_job.checklist or {}).get("components_ordered") is True)
    )
    carrier = (order.carrier or "").strip()
    tracking_url = None
    carrier_urls = {
        "royal_mail": "https://www.royalmail.com/track-your-item#/tracking-results/{}",
        "parcelforce": "https://www.parcelforce.com/track-trace?trackNumber={}",
        "dpd": "https://track.dpd.co.uk/parcels/{}",
        "ups": "https://www.ups.com/track?loc=en_GB&tracknum={}",
        "dhl": "https://www.dhl.com/gb-en/home/tracking/tracking-express.html?submit=1&tracking-id={}",
        "fedex": "https://www.fedex.com/fedextrack/?trknbr={}",
    }
    if order.tracking_number:
        template = carrier_urls.get(carrier.lower().replace(" ", "_"))
        tracking_url = template.format(order.tracking_number) if template else None
    tracking_events = tracking_events or []
    latest_live_map = next((event.live_map_url for event in tracking_events if event.live_map_url), None)
    latest_tracking_url = _manual_build_tracking_url(manual_build, tracking_events)
    tracking_url = latest_tracking_url or tracking_url
    published_model_url = (
        capture_3d.optimized_asset_ref
        if capture_3d and capture_3d.status == Capture3DStatus.PUBLISHED and capture_3d.optimized_asset_ref
        else manual_build.model_3d_url if manual_build and manual_build.model_3d_url else None
    )
    slots = [MyOrderSlotOut(**s) for s in specs.get("slots", [])]
    case_name = specs.get("case_name")
    case_price = specs.get("case_price", 0.0)
    if manual_build:
        components = list(manual_build.components or [])
        case = next((item for item in components if str(item.get("slot", "")).lower() in {"case", "chassis"}), None)
        if not slots:
            slots = [
                MyOrderSlotOut(
                    slot_id=index,
                    slot_type=str(item.get("slot") or "component"),
                    variant_id=int(item.get("part_id") or 0),
                    title=str(item.get("name") or "Component"),
                    price=float(item.get("price_paid") or 0),
                )
                for index, item in enumerate(components, start=1)
                if item is not case
            ]
        case_name = case_name or (str(case.get("name")) if case else None)
        case_price = case_price or (float(case.get("price_paid") or 0) if case else 0.0)
    hub = _manual_build_customer_hub(manual_build, warranty_reserve=warranty_reserve) if manual_build else _order_customer_hub(
        published_model_url,
        capture_3d.preview_image_ref if capture_3d else None,
        order.id,
        warranty_reserve,
        order.delivered_at or order.actual_delivery_date,
    )
    hub["getting_started_setup"] = _getting_started_portal_summary(getting_started_job)
    raw_change_request = order.change_request if isinstance(order.change_request, dict) else None
    customer_change_request = None
    if raw_change_request:
        customer_change_request = {
            key: raw_change_request[key]
            for key in (
                "status", "request_text", "requested_at", "customer_message",
                "proposed_specs", "proposed_customer_price", "customer_responded_at",
            )
            if key in raw_change_request
        }
    return MyOrderOut(
        id=order.id,
        order_id=order.order_id,
        status=("cancelled" if order.cancelled_at or order.status == OrderStatus.CANCELLED else order.status.value if hasattr(order.status, "value") else str(order.status)),
        customer_price=order.customer_price,
        component_costs=order.component_costs,
        slots=slots,
        case_name=case_name,
        case_price=case_price,
        chosen_week=specs.get("chosen_week"),
        promised_delivery_date=order.promised_delivery_date,
        actual_delivery_date=order.actual_delivery_date,
        estimated_delivery=order.estimated_delivery,
        delivery_option=(order.specs or {}).get("delivery_option"),
        delivery_promise=(order.specs or {}).get("delivery_promise"),
        delivery_estimate_source=(order.specs or {}).get("delivery_estimate_source"),
        supplier_delivery_days=(int((order.specs or {}).get("supplier_delivery_days")) if str((order.specs or {}).get("supplier_delivery_days") or "").isdigit() else None),
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
        cancellation_status=order.cancellation_status,
        cancelled_at=order.cancelled_at,
        change_request=customer_change_request,
        can_cancel=cancellation_retryable or (cancellation_before_parts and not order.cancellation_requested_at),
        tracking_number=order.tracking_number,
        carrier=carrier or None,
        tracking_url=tracking_url,
        live_tracking_available=bool(latest_live_map),
        live_map_url=latest_live_map,
        tracking_events=[_tracking_event_dict(event) for event in tracking_events],
        capture_3d=(
            {"status": capture_3d.status.value if hasattr(capture_3d.status, "value") else str(capture_3d.status),
             "optimized_asset_ref": capture_3d.optimized_asset_ref,
             "preview_image_ref": capture_3d.preview_image_ref,
             "ar_ready": bool(capture_3d.ar_ready)}
            if capture_3d and capture_3d.status == Capture3DStatus.PUBLISHED and capture_3d.optimized_asset_ref else None
            ) or (
                {"status": "published", "optimized_asset_ref": manual_build.model_3d_url,
                 "preview_image_ref": manual_build.hero_photo_url, "ar_ready": True}
                if manual_build and manual_build.model_3d_url else None
            ),
        model_3d_url=published_model_url,
        customer_hub=hub,
        fulfilment_type=specs.get("fulfilment_type", "prebuilt" if manual_build else "made_to_order"),
        build_status=manual_build.status if manual_build else None,
        review_url=f"{PUBLIC_REVIEWS_URL}?order={order.id}",
        created_at=order.created_at,
    )


def get_iso_week(dt: date) -> str:
    """Returns ISO week string format: YYYY-Www"""
    iso_calendar = dt.isocalendar()
    return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"


def parse_iso_week(week_str: str) -> date:
    """Parses ISO week string to Monday of that week"""
    year, week = week_str.split("-W")
    d = datetime.strptime(f"{year}-W{int(week)}-1", "%Y-W%W-%w")
    return d.date()


async def count_business_days_until(from_date: date, to_date: date) -> int:
    """Count business days (Mon-Fri) between from_date (exclusive) and to_date (inclusive)"""
    count = 0
    current = from_date + timedelta(days=1)
    while current <= to_date:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


@router.get("/slots", response_model=list[CapacitySlotsOut])
async def get_available_slots(db: AsyncSession = Depends(get_db)):
    """
    Returns next 8 weeks with available build slots.
    Excludes weeks within 5 business days.
    Excludes weeks with 0 available capacity.
    """
    today = date.today()

    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    build_capacity = capacity_result.scalar()
    if not build_capacity:
        default_capacity = 3
    else:
        default_capacity = build_capacity.default_per_week

    result = []

    for i in range(16):
        current_date = today + timedelta(weeks=i)
        week_start = current_date - timedelta(days=current_date.weekday())
        week_str = get_iso_week(week_start)

        business_days_until = await count_business_days_until(today, week_start)
        if business_days_until < 5:
            continue

        override_result = await db.execute(
            select(BuildCapacityOverride).where(BuildCapacityOverride.week == week_str)
        )
        override = override_result.scalar()

        if override and override.max_builds is None:
            continue

        capacity = override.max_builds if override else default_capacity

        booked_result = await db.execute(
            select(func.count(Order.id)).where(
                and_(
                    Order.assigned_build_week == week_str,
                    Order.status.in_(["confirmed", "building", "shipped"]),
                )
            )
        )
        booked_count = booked_result.scalar() or 0

        available = max(0, capacity - booked_count)

        if available > 0:
            result.append(
                CapacitySlotsOut(
                    week=week_str,
                    week_start=week_start.isoformat(),
                    available=available,
                    capacity=capacity,
                )
            )

        if len(result) >= 8:
            break

    return result


@router.get("/me", response_model=list[MyOrderOut])
async def list_my_orders(
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The logged-in customer's own orders — real fields only, no fabricated
    reference/playbook_name/etc."""
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == customer.id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    assets = (await db.execute(select(Capture3DAsset).where(Capture3DAsset.order_id.in_([o.id for o in orders])))).scalars().all() if orders else []
    assets_by_order = {asset.order_id: asset for asset in assets}
    getting_started_jobs = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.order_id.in_([o.id for o in orders]))
    )).scalars().all() if orders else []
    jobs_by_order = {job.order_id: job for job in getting_started_jobs}
    reserves = (await db.execute(select(WarrantyReserve).where(WarrantyReserve.order_id.in_([o.id for o in orders])))).scalars().all() if orders else []
    reserves_by_order = {reserve.order_id: reserve for reserve in reserves}
    events = (await db.execute(select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.order_id.in_([o.id for o in orders])).order_by(ShipmentTrackingEvent.occurred_at.desc()))).scalars().all() if orders else []
    events_by_order: dict[int, list[ShipmentTrackingEvent]] = {}
    for event in events:
        events_by_order.setdefault(event.order_id, []).append(event)
    manual_rows = (await db.execute(
        select(Product.sold_order_id, ManualBuild)
        .join(Build, Build.id == Product.build_id)
        .join(ManualBuild, ManualBuild.id == Build.manual_build_id)
        .where(Product.sold_order_id.in_([o.id for o in orders]))
    )).all() if orders else []
    manual_by_order = {order_id: build for order_id, build in manual_rows}
    return [_order_to_my_order_out(o, assets_by_order.get(o.id), manual_by_order.get(o.id), jobs_by_order.get(o.id), reserves_by_order.get(o.id), events_by_order.get(o.id, [])) for o in orders]


@router.get("/{order_id}", response_model=MyOrderOut)
async def get_my_order(
    order_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A single order — scoped to the requesting customer. Deliberately not
    a public by-reference lookup (the old one was schema-incompatible and
    would have leaked other customers' orders to anyone with a reference)."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order or order.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Order not found")
    asset = (await db.execute(select(Capture3DAsset).where(Capture3DAsset.order_id == order.id))).scalar_one_or_none()
    manual_build = await _manual_build_sold_on_order(db, order.id)
    getting_started_job = (await db.execute(select(GettingStartedJob).where(GettingStartedJob.order_id == order.id))).scalar_one_or_none()
    reserve = (await db.execute(select(WarrantyReserve).where(WarrantyReserve.order_id == order.id))).scalar_one_or_none()
    events = (await db.execute(select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.order_id == order.id).order_by(ShipmentTrackingEvent.occurred_at.desc()))).scalars().all()
    return _order_to_my_order_out(order, asset, manual_build, getting_started_job, reserve, list(events))


async def _owned_order(order_id: int, customer: Customer, db: AsyncSession) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id, Order.customer_id == customer.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/{order_id}/cancel", response_model=OrderCancellationOut)
async def cancel_my_order(
    order_id: int,
    background_tasks: BackgroundTasks,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel before components are ordered and issue an idempotent full refund."""
    order = (await db.execute(
        select(Order).where(Order.id == order_id, Order.customer_id == customer.id).with_for_update()
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == OrderStatus.CANCELLED or order.cancelled_at:
        return OrderCancellationOut(
            order_id=order.id, status="cancelled", refund_status=order.cancellation_status or "succeeded",
            refund_id=order.refund_id,
        )

    retryable = order.cancellation_status in {"refund_pending", "refund_failed"}
    is_new_cancellation = not order.cancellation_requested_at
    if not retryable:
        if order.status != OrderStatus.AWAITING_SOURCING:
            raise HTTPException(409, "This order can no longer be cancelled automatically because components may have been ordered")
        job = (await db.execute(
            select(GettingStartedJob).where(GettingStartedJob.order_id == order.id).with_for_update()
        )).scalar_one_or_none()
        prebuilt_product = (await db.execute(
            select(Product).where(Product.sold_order_id == order.id).with_for_update()
        )).scalar_one_or_none()
        if (job and job.source_type == "ready_to_ship") or (
            prebuilt_product and prebuilt_product.product_type == ProductType.PREBUILT
        ):
            raise HTTPException(409, "Ready-to-Ship components were already ordered before listing; contact support if you need to cancel")
        if job and (job.checklist or {}).get("components_ordered") is True:
            raise HTTPException(409, "This order can no longer be cancelled automatically because components have been ordered")
        if not order.stripe_payment_intent_id:
            raise HTTPException(409, "This order has no online payment reference; contact support to arrange cancellation")
        order.cancellation_requested_at = datetime.utcnow()
        order.cancellation_status = "refund_pending"
        # Commit the sourcing hold before contacting Stripe. Repeating the
        # request uses the same provider idempotency key after any interruption.
        await db.commit()
    elif not order.stripe_payment_intent_id:
        raise HTTPException(409, "The refund needs administrator reconciliation")

    payment_service = PaymentService()
    try:
        if order.refund_id:
            refund = await payment_service.get_refund_status(order.refund_id)
            if refund.get("status") == "pending":
                return OrderCancellationOut(
                    order_id=order.id,
                    status="cancellation_pending",
                    refund_status="refund_pending",
                    refund_id=order.refund_id,
                )
            if refund.get("status") != "succeeded":
                order.cancellation_status = "refund_requires_support"
                await _ensure_refund_reconciliation_alert(db, order)
                await db.commit()
                raise HTTPException(409, "The payment provider could not complete this refund. Support must reconcile it before another attempt.")
        else:
            refund = await payment_service.refund_payment(
                intent_id=order.stripe_payment_intent_id,
                reason="requested_by_customer",
                idempotency_key=f"flipflop-order-cancel-{order.id}",
            )
    except ValueError as exc:
        order = (await db.execute(
            select(Order).where(Order.id == order_id, Order.customer_id == customer.id).with_for_update()
        )).scalar_one()
        order.cancellation_status = "refund_failed"
        await _ensure_refund_reconciliation_alert(db, order)
        await db.commit()
        raise HTTPException(502, "The cancellation is paused while the refund is reconciled. Please retry or contact support.") from exc

    order = (await db.execute(
        select(Order).where(Order.id == order_id, Order.customer_id == customer.id).with_for_update()
    )).scalar_one()
    order.refund_id = refund.get("refund_id")
    if refund.get("status") == "succeeded":
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.utcnow()
        order.cancellation_status = "succeeded"
        await _mark_cancelled_order_build_records(db, order)
    else:
        order.cancellation_status = "refund_pending"
    await db.commit()
    notify_status = "cancelled" if order.cancelled_at else "cancellation_pending" if is_new_cancellation else None
    if notify_status:
        background_tasks.add_task(
            send_order_status_email,
            customer.email,
            customer.name or "there",
            order.order_id,
            notify_status,
            order.id,
        )
    return OrderCancellationOut(
        order_id=order.id,
        status="cancelled" if order.cancelled_at else "cancellation_pending",
        refund_status=order.cancellation_status or "refund_pending",
        refund_id=order.refund_id,
    )


@router.post("/{order_id}/change-requests", status_code=201)
async def request_my_build_change(
    order_id: int,
    body: CustomerBuildChangeRequestIn,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause made-to-order sourcing while an owner change request is reviewed."""
    order = (await db.execute(
        select(Order).where(Order.id == order_id, Order.customer_id == customer.id)
        .with_for_update()
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status != OrderStatus.AWAITING_SOURCING:
        raise HTTPException(409, "Build changes can only be requested before components are ordered")
    if order.cancellation_requested_at or order.cancelled_at:
        raise HTTPException(409, "This order is cancelled or its refund is being reconciled")
    job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.order_id == order.id).with_for_update()
    )).scalar_one_or_none()
    if job and job.source_type == "ready_to_ship":
        raise HTTPException(409, "Ready-to-Ship stock was sourced before listing; contact support about a change")
    if job and (job.checklist or {}).get("components_ordered") is True:
        raise HTTPException(409, "Build changes close once components are ordered")
    previous = order.change_request if isinstance(order.change_request, dict) else None
    if previous and previous.get("status") in {"requested", "quote_ready", "customer_approved"}:
        raise HTTPException(409, "A build change request is already open for this order")
    now = datetime.utcnow().isoformat()
    history = list((previous or {}).get("history") or [])
    if previous:
        history.append({key: value for key, value in previous.items() if key != "history"})
    order.change_request = {
        "status": "requested",
        "request_text": body.request_text.strip(),
        "requested_at": now,
        "customer_id": customer.id,
        "history": history[-20:],
    }
    db.add(AlertEvent(
        code=f"order_change_request_{order.id}_{uuid.uuid4().hex}",
        source="order_change_request",
        severity="warning",
        message=f"Customer requested a build change for order {order.order_id}; sourcing is paused pending review.",
        link_url=f"/orders/{order.id}",
    ))
    order.updated_at = datetime.utcnow()
    await db.commit()
    return {"order_id": order.id, "change_request": order.change_request}


@router.post("/{order_id}/change-requests/respond")
async def respond_to_my_build_change_quote(
    order_id: int,
    body: CustomerBuildChangeResponseIn,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = (await db.execute(
        select(Order).where(Order.id == order_id, Order.customer_id == customer.id)
        .with_for_update()
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    request = dict(order.change_request or {})
    state = request.get("status")
    if body.decision == "withdraw":
        if state != "requested":
            raise HTTPException(409, "A request can only be withdrawn before FlipFlop has prepared a quote")
        request["status"] = "withdrawn"
    elif body.decision == "decline_quote":
        if state != "quote_ready":
            raise HTTPException(409, "There is no revised quote to decline")
        request["status"] = "declined"
    else:
        # Quote acceptance is intentionally absent from the request schema
        # until repricing, payment settlement, and paid-order application form
        # one atomic/recoverable workflow.
        raise HTTPException(409, "Quote acceptance is unavailable until revised pricing and payment are ready")
    request["customer_responded_at"] = datetime.utcnow().isoformat()
    order.change_request = request
    order.updated_at = datetime.utcnow()
    await db.commit()
    return {"order_id": order.id, "change_request": order.change_request}


@router.get("/{order_id}/getting-started")
async def get_my_getting_started_options(
    order_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the Playbook's software picks and editable app list for this order."""
    order = await _owned_order(order_id, customer, db)
    job = (await db.execute(select(GettingStartedJob).where(GettingStartedJob.order_id == order.id))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Getting Started setup is not available for this order")
    manual_build = (
        await _manual_build_sold_on_order(db, order.id)
        if job.source_type == "ready_to_ship"
        else None
    )
    profile = await _getting_started_recommendation_profile(db, order, job, manual_build)
    recommended_ids = [
        package_id for package_id in profile.get("recommended_package_ids", [])
        if package_id in SOFTWARE_BY_ID
    ]
    already_submitted = bool((job.checklist or {}).get("software_selection_submitted"))
    selected_ids = list(job.customer_software_selections or []) if already_submitted else recommended_ids
    app_settings = (await db.execute(select(AppSettings).where(AppSettings.name == "default"))).scalar_one_or_none()
    gpu_vram_gb = await _order_gpu_vram_gb(db, order)
    ai_hardware_ready = job.source_type == "ready_to_ship" or (job.checklist or {}).get("components_ordered") is True
    return {
        "order_id": order.id,
        "job_status": job.status,
        "recommendation_rationale": profile.get("rationale", "A simple starter selection, chosen for this build's Playbook segment."),
        "apps": SOFTWARE_CATALOGUE,
        "recommended_package_ids": recommended_ids,
        "selected_package_ids": selected_ids,
        "estimated_time_saved_minutes": estimate_saved_minutes(selected_ids),
        "time_estimate_basis": "Indicative internal estimate for avoiding manual search/download/setup. It is not benchmarked or guaranteed.",
        "software_selection_edit_until": (
            "dispatch" if job.source_type == "ready_to_ship" else "components_ordered"
        ),
        "purchased_ai_services": _customer_visible_ai_setup_services(job.purchased_ai_services),
        "ai_setup_offers": public_ai_setup_offers(
            app_settings.ai_setup_offers if app_settings else None,
            gpu_vram_gb,
        ),
        "gpu_vram_gb_confirmed": gpu_vram_gb,
        "can_purchase_ai_services": (
            not order.cancelled_at
            and not order.cancellation_requested_at
            and ai_hardware_ready
            and job.status not in {"package_ready", "ready_for_delivery", "complete", "cancelled"}
        ),
        "ai_services_availability_message": (
            None if ai_hardware_ready else "These optional setup services become available after your components have been ordered and the hardware is confirmed."
        ),
        "can_edit": (
            not order.cancelled_at
            and not order.cancellation_requested_at
            and job.status != "cancelled"
            and (
                job.source_type == "ready_to_ship"
                or job.status not in {"package_ready", "ready_for_delivery", "complete"}
            )
            and (
                (
                    job.source_type == "ready_to_ship"
                    and str(order.status.value if hasattr(order.status, "value") else order.status) not in {"shipped", "completed"}
                    and (manual_build is None or manual_build.dispatch_status not in {"dispatched", "delivered"})
                ) or (
                    job.source_type != "ready_to_ship"
                    and (job.checklist or {}).get("components_ordered") is not True
                )
            )
        ),
    }


@router.post("/{order_id}/getting-started/ai-services/payment-intent", status_code=201)
async def create_ai_setup_payment_intent(
    order_id: int,
    body: AISetupPurchaseCreateIn,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a server-priced Stripe intent for one eligible Getting Ready add-on."""
    order = await _owned_order(order_id, customer, db)
    order = (await db.execute(select(Order).where(Order.id == order.id).with_for_update())).scalar_one()
    if order.cancelled_at or order.cancellation_requested_at:
        raise HTTPException(409, "AI setup cannot be purchased for a cancelled or refund-pending order")
    job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.order_id == order.id).with_for_update()
    )).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Getting Ready setup is not available for this order")
    existing = (await db.execute(
        select(AISetupPurchase).where(
            AISetupPurchase.order_id == order.id,
            AISetupPurchase.offer_id == body.offer_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if existing and existing.status == "paid":
        raise HTTPException(409, "This AI setup option has already been purchased for this build")
    payment_service = PaymentService()
    if existing and existing.status == "pending":
        try:
            intent = await payment_service.get_payment_intent(existing.stripe_payment_intent_id)
        except ValueError as error:
            raise HTTPException(503, "Could not retrieve the existing AI setup payment") from error
        if intent["status"] == "canceled":
            existing.status = "cancelled"
            await db.commit()
        elif intent["status"] in {"succeeded", "processing"}:
            raise HTTPException(409, "This payment is being reconciled. Refresh the portal before trying again")
        else:
            return {
                "intent_id": intent["intent_id"],
                "client_secret": intent["client_secret"],
                "publishable_key": payment_service.config.publishable_key,
                "amount": existing.amount_gbp,
                "currency": "gbp",
                "offer_id": body.offer_id,
            }
    if job.status in {"package_ready", "ready_for_delivery", "complete", "cancelled"}:
        raise HTTPException(409, "Getting Ready options are locked for this order")
    if job.source_type != "ready_to_ship" and (job.checklist or {}).get("components_ordered") is not True:
        raise HTTPException(409, "AI setup can be purchased after components have been ordered and this build's hardware is confirmed")

    app_settings = (await db.execute(select(AppSettings).where(AppSettings.name == "default"))).scalar_one_or_none()
    offers = public_ai_setup_offers(
        app_settings.ai_setup_offers if app_settings else None,
        await _order_gpu_vram_gb(db, order),
    )
    offer = next((item for item in offers if item["id"] == body.offer_id), None)
    if not offer:
        raise HTTPException(404, "This AI setup option is not currently available")
    if not offer["eligible"]:
        raise HTTPException(422, offer["eligibility_message"] or "This build does not meet the option requirements")

    amount = float(offer["price_gbp"])
    snapshot = {
        "id": offer["id"],
        "name": offer["name"],
        "description": offer["description"],
        "included_automations": offer.get("included_automations", []),
        "price_gbp": amount,
        "requires_vram_gb": offer["requires_vram_gb"],
    }
    try:
        intent_data = await payment_service.create_payment_intent(
            customer_id=customer.id,
            budget=amount,
            quote_data={},
            metadata={
                "purchase_type": "ai_setup_service",
                "order_id": str(order.id),
                "offer_id": offer["id"],
                "offer_price_pence": str(round(amount * 100)),
            },
            description=f"Getting Ready AI setup — {offer['name']}",
            idempotency_key=f"ai-setup-order-{order.id}-{offer['id']}-{uuid.uuid4().hex}",
        )
    except ValueError as error:
        raise HTTPException(503, "AI setup payments are temporarily unavailable") from error
    if existing:
        existing.stripe_payment_intent_id = intent_data["intent_id"]
        existing.amount_gbp = amount
        existing.status = "pending"
        existing.offer_snapshot = snapshot
        existing.updated_at = datetime.utcnow()
    else:
        db.add(AISetupPurchase(
            order_id=order.id,
            customer_id=customer.id,
            offer_id=offer["id"],
            stripe_payment_intent_id=intent_data["intent_id"],
            amount_gbp=amount,
            status="pending",
            offer_snapshot=snapshot,
        ))
    await db.commit()
    return {**intent_data, "offer_id": offer["id"]}


@router.post("/{order_id}/getting-started/ai-services/{offer_id}/cancel-payment")
async def cancel_my_ai_setup_payment(
    order_id: int,
    offer_id: str,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel only an unpaid AI setup attempt; Stripe decides the final state."""
    await _owned_order(order_id, customer, db)
    purchase = (await db.execute(
        select(AISetupPurchase).where(
            AISetupPurchase.order_id == order_id,
            AISetupPurchase.customer_id == customer.id,
            AISetupPurchase.offer_id == offer_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not purchase:
        raise HTTPException(404, "No payment attempt exists for this setup option")
    if purchase.status == "paid":
        raise HTTPException(409, "This setup has already been paid for")
    try:
        intent = await PaymentService().cancel_payment_intent(purchase.stripe_payment_intent_id)
    except ValueError as error:
        raise HTTPException(502, "Could not confirm the payment status with Stripe") from error
    if intent["status"] in {"succeeded", "processing"}:
        raise HTTPException(409, "This payment is completing and cannot be cancelled. Refresh the portal for its status")
    if intent["status"] != "canceled":
        raise HTTPException(409, "Stripe has not confirmed cancellation. Refresh the portal before trying again")
    purchase.status = "cancelled"
    purchase.updated_at = datetime.utcnow()
    await db.commit()
    return {"order_id": order_id, "offer_id": offer_id, "payment_status": "cancelled", "can_retry": True}


@router.put("/{order_id}/getting-started/selections")
async def save_my_getting_started_selections(
    order_id: int,
    body: GettingStartedSelectionsIn,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the customer's free app selections; paid AI choices are never accepted here."""
    await _owned_order(order_id, customer, db)
    job_ref = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.order_id == order_id)
    )).scalar_one_or_none()
    if job_ref is None:
        raise HTTPException(404, "Getting Started setup is not available for this order")
    build = None
    if job_ref.source_type == "ready_to_ship" and job_ref.manual_build_id is not None:
        build, job = await lock_manual_build_then_getting_started_job(db, job_ref.manual_build_id)
        if build is None or job is None or job.order_id != order_id:
            raise HTTPException(409, "The Ready-to-Ship build is no longer linked to this order")
        order = (await db.execute(
            select(Order).where(Order.id == order_id)
            .execution_options(populate_existing=True)
        )).scalar_one()
    else:
        order = (await db.execute(
            select(Order).where(Order.id == order_id).with_for_update()
            .execution_options(populate_existing=True)
        )).scalar_one()
        job = (await db.execute(
            select(GettingStartedJob).where(GettingStartedJob.order_id == order.id).with_for_update()
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
        if not job:
            raise HTTPException(404, "Getting Started setup is not available for this order")
    order_status = str(order.status.value if hasattr(order.status, "value") else order.status)
    if order.cancelled_at or order_status == "cancelled" or order.cancellation_requested_at or job.status == "cancelled":
        raise HTTPException(409, "Software choices are locked because this order is cancelled or its refund is being reconciled")
    if job.source_type == "ready_to_ship" and (
        order_status in {"shipped", "completed"}
        or (build is not None and build.dispatch_status in {"dispatched", "delivered"})
    ):
        raise HTTPException(409, "Software choices are locked once the build has been dispatched")
    if job.source_type != "ready_to_ship":
        if job.status in {"package_ready", "ready_for_delivery", "complete"}:
            raise HTTPException(409, "Software choices are locked because the reviewed dispatch package has been created")
        if (job.checklist or {}).get("components_ordered") is True:
            raise HTTPException(409, "Software choices are locked after components have been ordered")
    try:
        selection_changed = customer_software_selection_changed(job, body.software_package_ids)
        saved = save_customer_software_selection(job, body.software_package_ids)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if selection_changed and job.source_type == "ready_to_ship" and build is not None:
        invalidate_ready_to_ship_reviewed_package(job, build)
    if selection_changed:
        # Invalidate a draft if it could contain a different app list. Package
        # approval must regenerate and review content made from the new choices.
        job.manifest = None
        job.generated_at = None
        if job.status != "awaiting_build":
            job.status = "awaiting_admin_review"
        job.checklist = {
            **(job.checklist or {}),
            "content_manifest": "not_ready",
            "artifacts_generated": "not_ready",
            "artifacts_reviewed": "not_ready",
            "customer_package": "not_ready",
        }
        job.updated_at = datetime.utcnow()
    await db.commit()
    return {
        "order_id": order.id,
        **saved,
    }


@router.get("/{order_id}/getting-started/package")
async def download_my_getting_ready_package(
    order_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the latest admin-reviewed package for the signed-in owner."""
    order = await _owned_order(order_id, customer, db)
    job = (await db.execute(
        select(GettingStartedJob).where(GettingStartedJob.order_id == order.id)
    )).scalar_one_or_none()
    packages = [item for item in (job.artifact_index or []) if item.get("category") == "customer_package"] if job and job.reviewed_at else []
    if not packages:
        raise HTTPException(404, "The reviewed Getting Ready package is not available yet")
    artifact = max(packages, key=lambda item: int(item.get("version") or 0))
    return _customer_package_archive_response(artifact)


@router.get("/{order_id}/getting-started/document")
async def download_my_getting_ready_document(
    order_id: int,
    name: str,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await _owned_order(order_id, customer, db)
    job = (await db.execute(select(GettingStartedJob).where(GettingStartedJob.order_id == order.id))).scalar_one_or_none()
    _artifact, content, media_type = _read_customer_package_document(job, name)
    filename = PurePosixPath(name).name
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/{order_id}/documents", response_model=list[CustomerDocumentOut])
async def list_my_order_documents(
    order_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return only generated documents belonging to the signed-in customer's order."""
    await _owned_order(order_id, customer, db)
    result = await db.execute(select(CXDocument).where(CXDocument.order_id == order_id).order_by(CXDocument.created_at.desc()))
    return [CustomerDocumentOut(
        id=document.id,
        document_type=document.document_type.value if hasattr(document.document_type, "value") else str(document.document_type),
        status=document.status.value if hasattr(document.status, "value") else str(document.status),
        version=document.version or 1,
        pdf_url=document.pdf_url,
        generated_at=document.generated_at,
        content_json=document.content_json if (document.status.value if hasattr(document.status, "value") else str(document.status)) == "ready" else None,
    ) for document in result.scalars().all()]


@router.get("/{order_id}/problems", response_model=list[CustomerProblemOut])
async def list_my_order_problems(
    order_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _owned_order(order_id, customer, db)
    result = await db.execute(select(CustomerProblem).where(CustomerProblem.order_id == order_id).order_by(CustomerProblem.created_at.desc()))
    return await _customer_problem_outputs(db, list(result.scalars().all()))


def _customer_case_evidence_response(problem: CustomerProblem, evidence_id: str) -> Response:
    item = next((item for item in (problem.evidence_files or []) if item.get("id") == evidence_id), None)
    if not item:
        raise HTTPException(404, "Case evidence not found")
    path = _customer_case_evidence_path(str(item.get("storage_key") or ""))
    if not path.is_file():
        raise HTTPException(404, "Case evidence file is missing")
    if path.stat().st_size <= 0 or path.stat().st_size > _CUSTOMER_CASE_EVIDENCE_MAX_BYTES:
        raise HTTPException(409, "Case evidence size is outside the supported range; the file was not served")
    expected_digest = str(item.get("sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise HTTPException(409, "Case evidence has no valid integrity record; ask support to review the attachment")
    content = path.read_bytes()
    actual_digest = hashlib.sha256(content).hexdigest()
    if actual_digest != expected_digest:
        raise HTTPException(409, "Case evidence failed its integrity check; the file was not served")
    filename = str(item.get("filename") or "case-evidence")
    return Response(
        content=content,
        media_type=str(item.get("content_type") or "application/octet-stream"),
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
        },
    )


@router.post("/{order_id}/problems/{problem_id}/evidence", status_code=201)
async def upload_my_order_problem_evidence(
    order_id: int,
    problem_id: int,
    file: UploadFile = File(...),
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _owned_order(order_id, customer, db)
    problem = (await db.execute(select(CustomerProblem).where(
        CustomerProblem.id == problem_id,
        CustomerProblem.order_id == order_id,
        CustomerProblem.customer_id == customer.id,
    ).with_for_update())).scalar_one_or_none()
    if not problem:
        raise HTTPException(404, "Support case not found")
    evidence_files = list(problem.evidence_files or [])
    if len(evidence_files) >= _CUSTOMER_CASE_MAX_FILES:
        raise HTTPException(413, f"A support case can contain up to {_CUSTOMER_CASE_MAX_FILES} images")
    item = await _store_customer_case_evidence(problem, file)
    problem.evidence_files = [*evidence_files, item]
    try:
        await db.commit()
    except Exception:
        _customer_case_evidence_path(item["storage_key"]).unlink(missing_ok=True)
        raise
    return problem.evidence[-1]


@router.get("/{order_id}/problems/{problem_id}/evidence/{evidence_id}")
async def download_my_order_problem_evidence(
    order_id: int,
    problem_id: int,
    evidence_id: str,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _owned_order(order_id, customer, db)
    problem = (await db.execute(select(CustomerProblem).where(
        CustomerProblem.id == problem_id,
        CustomerProblem.order_id == order_id,
        CustomerProblem.customer_id == customer.id,
    ))).scalar_one_or_none()
    if not problem:
        raise HTTPException(404, "Support case not found")
    return _customer_case_evidence_response(problem, evidence_id)


async def _create_customer_problem(
    db: AsyncSession,
    *,
    order: Order | None,
    build: ManualBuild | None,
    customer_id: int | None,
    grant: PortalAccessGrant | None,
    category: str,
    description: str,
) -> CustomerProblem:
    is_warranty = category.strip().lower() in WARRANTY_CASE_CATEGORIES
    if is_warranty and order is not None:
        locked_order = await lock_warranty_sale_owner(db, order_id=order.id)
        if locked_order is None:
            raise HTTPException(404, "Order not found")
        order = locked_order
    elif is_warranty and build is not None:
        locked_build = await lock_warranty_sale_owner(db, manual_build_id=build.id)
        if locked_build is None:
            raise HTTPException(404, "Build not found")
        build = locked_build
    problem = CustomerProblem(
        order_id=order.id if order else None,
        manual_build_id=build.id if build else None,
        customer_id=customer_id,
        portal_grant_id=grant.id if grant else None,
        category=category,
        description=description,
    )
    db.add(problem)
    await db.flush()
    if is_warranty:
        if order:
            reserve = (await db.execute(
                select(WarrantyReserve).where(WarrantyReserve.order_id == order.id)
            )).scalar_one_or_none()
            started_at = order.delivered_at or order.actual_delivery_date
            if reserve or started_at:
                # Reconciliation also attaches any earlier warranty reports
                # that arrived before delivery was recorded.
                await ensure_order_reserve(db, order, started_at or reserve.warranty_started_at)
        elif build:
            reserve = (await db.execute(
                select(WarrantyReserve).where(WarrantyReserve.manual_build_id == build.id)
            )).scalar_one_or_none()
            started_at = build.warranty_started_at or build.delivered_at
            if reserve or started_at:
                await ensure_manual_build_reserve(db, build, started_at or reserve.warranty_started_at)
    db.add(AlertEvent(
        code=f"customer_problem_{problem.id}",
        source="warranty" if is_warranty else "customer_support",
        severity="warning" if is_warranty else "info",
        message=f"New {'warranty/repair claim' if is_warranty else 'customer support request'} for {('order ' + str(order.id)) if order else ('build ' + str(build.id))} (case {problem.id}).",
        link_url="/problems",
    ))
    await db.flush()
    await db.refresh(problem)
    return problem


@router.post("/{order_id}/problems", response_model=CustomerProblemOut, status_code=201)
async def create_my_order_problem(
    order_id: int,
    body: CustomerProblemCreate,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await _owned_order(order_id, customer, db)
    return await _create_customer_problem(
        db,
        order=order,
        build=None,
        customer_id=customer.id,
        grant=None,
        category=body.category,
        description=body.description,
    )


admin_router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@admin_router.patch("/orders/{order_id}/change-request")
async def review_order_change_request(
    order_id: int,
    body: AdminBuildChangeReviewIn,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    order = (await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    request = dict(order.change_request or {})
    if request.get("status") != "requested":
        raise HTTPException(409, "There is no unreviewed customer build-change request")
    if order.status != OrderStatus.AWAITING_SOURCING or order.cancellation_requested_at:
        raise HTTPException(409, "This order is no longer eligible for a pre-sourcing build change")
    if body.action == "quote":
        if body.proposed_specs is None or body.proposed_customer_price is None:
            raise HTTPException(422, "A revised specification and price are required for a customer quote")
        request.update({
            "status": "quote_ready",
            "proposed_specs": body.proposed_specs,
            "proposed_customer_price": round(body.proposed_customer_price, 2),
            "customer_message": body.customer_message.strip(),
            "reviewed_at": datetime.utcnow().isoformat(),
            "reviewed_by": getattr(admin, "email", None) or "admin",
            "internal_note": body.internal_note.strip() if body.internal_note else None,
        })
    else:
        request.update({
            "status": "rejected",
            "customer_message": body.customer_message.strip(),
            "reviewed_at": datetime.utcnow().isoformat(),
            "reviewed_by": getattr(admin, "email", None) or "admin",
            "internal_note": body.internal_note.strip() if body.internal_note else None,
            "resolved_at": datetime.utcnow().isoformat(),
        })
    order.change_request = request
    order.updated_at = datetime.utcnow()
    await db.commit()
    return {"order_id": order.id, "change_request": order.change_request}


@admin_router.post("/orders/{order_id}/refund/reconcile")
async def reconcile_order_refund(
    order_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Refresh an existing cancellation refund; this never creates a refund."""
    order = (await db.execute(select(Order).where(Order.id == order_id).with_for_update())).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if not order.cancellation_requested_at or not order.refund_id:
        raise HTTPException(409, "There is no existing cancellation refund to reconcile")
    if order.status == OrderStatus.CANCELLED:
        return {"order_id": order.id, "status": "cancelled", "refund_status": order.cancellation_status, "refund_id": order.refund_id}

    try:
        refund = await PaymentService().get_refund_status(order.refund_id)
    except ValueError as exc:
        raise HTTPException(502, "Could not retrieve the existing refund from the payment provider") from exc

    provider_status = refund.get("status")
    if provider_status == "succeeded":
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = order.cancelled_at or datetime.utcnow()
        order.cancellation_status = "succeeded"
        await _mark_cancelled_order_build_records(db, order)
        alert = (await db.execute(select(AlertEvent).where(AlertEvent.code == f"order_refund_reconcile_{order.id}").with_for_update())).scalar_one_or_none()
        if alert:
            alert.acked = True
            alert.acked_at = datetime.utcnow()
        customer = await db.get(Customer, order.customer_id)
        await db.commit()
        if customer:
            background_tasks.add_task(send_order_status_email, customer.email, customer.name or "there", order.order_id, "cancelled", order.id)
    elif provider_status in {"failed", "canceled"}:
        order.cancellation_status = "refund_requires_support"
        await _ensure_refund_reconciliation_alert(db, order)
        await db.commit()
    else:
        order.cancellation_status = "refund_pending"
        await db.commit()
    return {"order_id": order.id, "status": "cancelled" if order.cancelled_at else "cancellation_pending", "refund_status": order.cancellation_status, "refund_id": order.refund_id}


@admin_router.post("/portal-access-grants", status_code=201)
async def create_portal_access_grant(
    body: PortalGrantCreateIn,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if (body.order_id is None) == (body.manual_build_id is None):
        raise HTTPException(400, "Provide exactly one order_id or manual_build_id")
    email = body.contact_email.strip().lower() if body.contact_email else None
    if email is not None and ("@" not in email or len(email) > 320):
        raise HTTPException(400, "Enter a valid email address or leave it blank for a printed marketplace claim")
    if body.channel not in {"direct_guest", "ebay", "vinted", "marketplace", "printed_insert"}:
        raise HTTPException(400, "Unsupported portal access channel")
    if body.expires_in_days < 1 or body.expires_in_days > 400:
        raise HTTPException(400, "Claim links may remain valid for 1 to 400 days")

    if body.order_id:
        if body.channel != "direct_guest":
            raise HTTPException(400, "Order-linked claims must use the direct guest channel")
        if not email:
            raise HTTPException(400, "A verified order email is required for a direct guest claim")
        order = (await db.execute(
            select(Order).where(Order.id == body.order_id).with_for_update()
        )).scalar_one_or_none()
        if not order:
            raise HTTPException(404, "Order not found")
        if order.status == OrderStatus.CANCELLED:
            raise HTTPException(409, "A cancelled order cannot receive a customer portal claim")
        customer = await db.get(Customer, order.customer_id)
        if not customer or customer.email.lower() != email:
            raise HTTPException(409, "Contact email must match the verified order email")
        if body.channel == "direct_guest":
            linked_manual_build = (await db.execute(
                select(ManualBuild)
                .join(Build, Build.manual_build_id == ManualBuild.id)
                .outerjoin(Product, Product.build_id == Build.id)
                .where(or_(Build.order_id == order.id, Product.sold_order_id == order.id))
                .limit(1)
            )).scalar_one_or_none()
            if (linked_manual_build
                    and linked_manual_build.shipment_booking_state in {
                        "creating_order", "order_created", "paying", "booked", "reconciliation_required",
                    }
                    and linked_manual_build.dispatch_status != "dispatched"
                    and await find_printable_portal_claim(
                        db, order_id=order.id, channel="direct_guest", include_claimed=True
                    )):
                raise HTTPException(
                    409,
                    "The guest portal claim is locked between courier booking and handover so the printed QR stays valid",
                )
        leaflet_build_id = order.id
        leaflet_build_name = str((order.specs or {}).get("build_name") or (order.specs or {}).get("case_name") or order.order_id)
    else:
        if body.channel == "direct_guest":
            raise HTTPException(409, "Direct guest claim email must be linked to a verified direct order")
        build = (await db.execute(
            select(ManualBuild).where(ManualBuild.id == body.manual_build_id).with_for_update()
        )).scalar_one_or_none()
        if not build:
            raise HTTPException(404, "Build not found")
        if email and (not build.customer_email or build.customer_email.strip().lower() != email):
            raise HTTPException(409, "Contact email must match the verified marketplace order email")
        if build.shipment_booking_state in {
            "creating_order", "order_created", "paying", "booked", "reconciliation_required",
        } or build.dispatch_status == "dispatched":
            existing_grant = await find_printable_portal_claim(
                db, manual_build_id=build.id, include_claimed=True
            )
            if existing_grant:
                raise HTTPException(
                    409,
                    "The printed-channel portal claim is locked after courier booking; reissuing it would invalidate the QR leaflet already prepared for the buyer",
                )
        leaflet_build_id = build.id
        leaflet_build_name = build.generated_title or build.name

    prior_query = select(PortalAccessGrant).where(PortalAccessGrant.claimed_at.is_(None), PortalAccessGrant.revoked == False)  # noqa: E712
    prior_query = prior_query.where(PortalAccessGrant.order_id == body.order_id) if body.order_id else prior_query.where(PortalAccessGrant.manual_build_id == body.manual_build_id)
    for prior in (await db.execute(prior_query)).scalars().all():
        prior.revoked = True

    secret, digest = new_claim_secret()
    grant = PortalAccessGrant(
        order_id=body.order_id,
        manual_build_id=body.manual_build_id,
        contact_email=email,
        token_hash=digest,
        channel=body.channel,
        expires_at=datetime.utcnow() + timedelta(days=body.expires_in_days),
        created_by=getattr(admin, "email", None) or "admin",
        email_status="pending" if body.channel == "direct_guest" else None,
    )
    db.add(grant)
    await db.flush()
    claim_url = f"{get_settings().frontend_url.rstrip('/')}/claim-build#token={secret}"
    try:
        leaflet = create_portal_leaflet(
            build_id=leaflet_build_id,
            build_name=leaflet_build_name,
            grant_id=grant.id,
            claim_url=claim_url,
        )
    except GettingReadyPackageError as error:
        raise HTTPException(409, str(error)) from error
    grant.leaflet_storage_key = leaflet["storage_key"]
    job_query = select(GettingStartedJob).where(GettingStartedJob.order_id == body.order_id) if body.order_id else select(GettingStartedJob).where(GettingStartedJob.manual_build_id == body.manual_build_id)
    job = (await db.execute(job_query)).scalar_one_or_none()
    if job:
        artifacts = [item for item in (job.artifact_index or []) if not (item.get("category") == "portal_leaflet" and item.get("grant_id") == grant.id)]
        artifacts.append({**leaflet, "category": "portal_leaflet", "private": True})
        job.artifact_index = artifacts
    await db.commit()
    email_sent = False
    if body.channel == "direct_guest" and body.order_id:
        customer = await db.get(Customer, order.customer_id)
        if customer and customer.email and customer.email.lower() == email:
            email_sent = await send_guest_portal_claim_email(
                customer.email,
                customer.name or "there",
                leaflet_build_name,
                claim_url,
                grant.expires_at,
                order.order_id,
            )
        await record_portal_claim_email_result(db, grant, sent=email_sent)
    delivery_guidance = _portal_grant_delivery_guidance(grant.channel)
    if grant.channel == "direct_guest" and not email_sent:
        delivery_guidance = "Claim email was not confirmed as sent. Print and include the private QR leaflet, or retry by issuing a new claim link."
    return {
        "id": grant.id,
        # Indirect-channel access is delivered only by the private printed
        # leaflet. Do not return its bearer URL to Dispatch Centre clients.
        "claim_url": claim_url if grant.channel == "direct_guest" else None,
        "expires_at": grant.expires_at,
        "channel": grant.channel,
        "contact_email": grant.contact_email,
        "leaflet_download_url": f"/api/admin/portal-access-grants/{grant.id}/leaflet",
        "email_sent": email_sent,
        "email_status": grant.email_status,
        "delivery_guidance": delivery_guidance,
    }


@admin_router.get("/portal-access-grants/{grant_id}/leaflet")
async def download_portal_access_leaflet(grant_id: int, db: AsyncSession = Depends(get_db)):
    grant = await db.get(PortalAccessGrant, grant_id)
    if not grant or not grant.leaflet_storage_key:
        raise HTTPException(404, "Portal leaflet not found")
    try:
        path = package_path(grant.leaflet_storage_key)
    except GettingReadyPackageError as error:
        raise HTTPException(404, str(error)) from error
    if not path.is_file():
        raise HTTPException(404, "Portal leaflet file is missing")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@admin_router.post("/portal-access-grants/{grant_id}/revoke")
async def revoke_portal_access_grant(grant_id: int, db: AsyncSession = Depends(get_db)):
    grant = await db.get(PortalAccessGrant, grant_id)
    if not grant:
        raise HTTPException(404, "Portal access grant not found")
    grant.revoked = True
    await db.flush()
    return {"ok": True, "id": grant.id, "revoked": True}


@admin_router.get("/customer-problems", response_model=list[AdminCustomerProblemOut])
async def list_customer_problems(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(CustomerProblem).order_by(CustomerProblem.created_at.desc())
    if status:
        query = query.where(CustomerProblem.status == status)
    result = await db.execute(query)
    return await _customer_problem_outputs(db, list(result.scalars().all()), admin=True)


@admin_router.get("/customer-problems/{problem_id}/evidence/{evidence_id}")
async def download_admin_customer_problem_evidence(
    problem_id: int,
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
):
    problem = await db.get(CustomerProblem, problem_id)
    if not problem:
        raise HTTPException(404, "Customer problem not found")
    return _customer_case_evidence_response(problem, evidence_id)


@admin_router.patch("/customer-problems/{problem_id}", response_model=AdminCustomerProblemOut)
async def update_customer_problem(
    problem_id: int,
    body: CustomerProblemStatusUpdate,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    # Claim changes use reserve -> claim -> problem so they serialize with the
    # release path's owner -> reserve locks without leaving an open claim on a
    # reserve that was just released.
    claim_reference = (await db.execute(
        select(WarrantyClaim).where(WarrantyClaim.customer_problem_id == problem_id)
    )).scalar_one_or_none()
    locked_reserve = None
    claim = None
    if claim_reference:
        locked_reserve, claim = await lock_warranty_reserve_then_claim(db, claim_reference.id)
        if not claim:
            raise HTTPException(status_code=404, detail="Warranty claim not found")
    problem = (await db.execute(
        select(CustomerProblem)
        .where(CustomerProblem.id == problem_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem report not found")
    previous_status = problem.status
    problem.status = body.status
    tracking_fields = {
        "repair_tracking_purpose", "repair_carrier", "repair_tracking_number", "repair_tracking_url",
        "repair_tracking_provider_reference",
    }
    repair_tracking_changed = False
    if body.model_fields_set.intersection(tracking_fields):
        category = str(problem.category or "").strip().casefold()
        if category not in WARRANTY_CASE_CATEGORIES:
            raise HTTPException(422, "Repair tracking can only be added to a warranty or repair case")
        expected_status = {
            "customer_return": "return_in_transit",
            "replacement": "replacement_dispatched",
        }.get(body.repair_tracking_purpose)
        if not expected_status or body.status != expected_status:
            raise HTTPException(422, "Return tracking requires the return-in-transit stage; replacement tracking requires replacement-dispatched")
        carrier = (body.repair_carrier or "").strip()
        tracking_number = (body.repair_tracking_number or "").strip()
        tracking_url = str(body.repair_tracking_url or "").strip()
        note = (body.repair_tracking_note or "").strip()
        if not carrier or not tracking_number or not tracking_url or len(note) < 12:
            raise HTTPException(422, "Provide the carrier, tracking number, HTTPS tracking link, and a meaningful audit note")
        provider_reference = (
            (body.repair_tracking_provider_reference or "").strip()
            if "repair_tracking_provider_reference" in body.model_fields_set
            else problem.repair_tracking_provider_reference
        )
        if "repair_tracking_provider_reference" in body.model_fields_set and body.repair_tracking_provider_reference and not provider_reference:
            raise HTTPException(422, "Parcel2Go OrderLineId cannot be blank")
        if provider_reference:
            if "parcel2go" not in carrier.casefold():
                raise HTTPException(422, "Automatic repair tracking currently requires the Parcel2Go carrier")
            conflicting_case = await db.scalar(select(CustomerProblemShipment.id).where(
                CustomerProblemShipment.provider == "parcel2go",
                CustomerProblemShipment.provider_reference == provider_reference,
                ~and_(
                    CustomerProblemShipment.customer_problem_id == problem.id,
                    CustomerProblemShipment.purpose == body.repair_tracking_purpose,
                ),
            ))
            conflicting_legacy_case = await db.scalar(select(CustomerProblem.id).where(
                CustomerProblem.repair_tracking_provider_reference == provider_reference,
            ))
            conflicting_build = await db.scalar(select(ManualBuild.id).where(
                ManualBuild.parcel2go_order_line_id == provider_reference,
            ))
            if conflicting_case or conflicting_legacy_case or conflicting_build:
                raise HTTPException(409, "This Parcel2Go OrderLineId is already linked to another shipment")
        next_tracking = {
            "purpose": body.repair_tracking_purpose,
            "carrier": carrier,
            "tracking_number": tracking_number,
            "tracking_url": tracking_url,
        }
        shipment = (await db.execute(
            select(CustomerProblemShipment).where(
                CustomerProblemShipment.customer_problem_id == problem.id,
                CustomerProblemShipment.purpose == body.repair_tracking_purpose,
            ).with_for_update()
        )).scalar_one_or_none()
        current_tracking_identity = {
            key: (problem.repair_tracking or {}).get(key)
            for key in ("purpose", "carrier", "tracking_number", "tracking_url")
            if key in (problem.repair_tracking or {})
        }
        repair_tracking_changed = (
            next_tracking != current_tracking_identity
            or provider_reference != (
                shipment.provider_reference if shipment else problem.repair_tracking_provider_reference
            )
        )
        if repair_tracking_changed:
            if shipment and shipment.provider_reference != provider_reference:
                linked_events = await db.scalar(select(ShipmentTrackingEvent.id).where(
                    ShipmentTrackingEvent.customer_problem_shipment_id == shipment.id
                ).limit(1))
                if linked_events:
                    raise HTTPException(409, "This shipment already has courier history. Keep its reference and add a new shipment leg instead of reusing it.")
            if shipment is None:
                shipment = CustomerProblemShipment(
                    customer_problem_id=problem.id,
                    purpose=body.repair_tracking_purpose,
                    carrier=carrier,
                    tracking_number=tracking_number,
                    tracking_url=tracking_url,
                    provider="parcel2go" if provider_reference else None,
                    provider_reference=provider_reference,
                )
                db.add(shipment)
            else:
                shipment.carrier = carrier
                shipment.tracking_number = tracking_number
                shipment.tracking_url = tracking_url
                shipment.provider = "parcel2go" if provider_reference else None
                shipment.provider_reference = provider_reference
            problem.repair_tracking = next_tracking
            # Provider linkage lives on each shipment leg, never on the case.
            problem.repair_tracking_provider = None
            problem.repair_tracking_provider_reference = None
            audit = list(problem.repair_tracking_audit or [])
            audit.append({
                **next_tracking,
                "provider": problem.repair_tracking_provider,
                "provider_reference": provider_reference,
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by_admin_id": admin.id,
                "updated_by_admin_name": admin.name,
                "note": note,
            })
            problem.repair_tracking_audit = audit
    if claim:
        claim.status = {
            "received": "open", "reviewing": "reviewing", "claim_opened": "open",
            "resolved": "resolved", "rejected": "rejected", "closed": "closed",
        }.get(body.status, body.status)
        claim.resolved_at = datetime.utcnow() if claim.status in {"resolved", "rejected", "closed"} else None
        if locked_reserve:
            await recalculate_reserve_status(db, locked_reserve)
    if problem.status != previous_status or repair_tracking_changed:
        await _queue_direct_case_status_email(db, problem, background_tasks)
    await db.flush()
    await db.commit()
    await db.refresh(problem)
    return (await _customer_problem_outputs(db, [problem], admin=True))[0]


async def _queue_direct_case_status_email(
    db: AsyncSession,
    problem: CustomerProblem,
    background_tasks: BackgroundTasks,
) -> None:
    """Persist notices for linked storefront orders, never marketplace-only builds."""
    aftercare_email_categories = WARRANTY_CASE_CATEGORIES | {"delivery_damage", "delivery_missing", "insurance_claim"}
    if not problem.order_id or str(problem.category or "").strip().casefold() not in aftercare_email_categories:
        return
    order = await db.get(Order, problem.order_id)
    if not order:
        return
    notification = CustomerProblemNotification(
        problem_id=problem.id,
        order_id=order.id,
        source_key=f"case-status:{problem.id}:{uuid.uuid4().hex}",
        status_code=problem.status,
        repair_tracking_snapshot=dict(problem.repair_tracking or {}),
    )
    db.add(notification)
    await db.flush()
    background_tasks.add_task(deliver_customer_problem_notification, notification.id)


def _reserve_admin_dict(reserve: WarrantyReserve, claims: list[WarrantyClaim]) -> dict:
    return {
        "id": reserve.id,
        "order_id": reserve.order_id,
        "manual_build_id": reserve.manual_build_id,
        "sale_value_gbp": reserve.sale_value_gbp,
        "reserve_pct": reserve.reserve_pct,
        "reserved_amount_gbp": reserve.reserved_amount_gbp,
        "allocated_claim_amount_gbp": reserve.allocated_claim_amount_gbp,
        "available_amount_gbp": round(max(0.0, reserve.reserved_amount_gbp - reserve.allocated_claim_amount_gbp - reserve.released_amount_gbp), 2),
        "released_amount_gbp": reserve.released_amount_gbp,
        "status": reserve.status,
        "warranty_started_at": reserve.warranty_started_at,
        "warranty_expires_at": reserve.warranty_expires_at,
        "eligible_at": reserve.eligible_at,
        "released_at": reserve.released_at,
        "claims": [{
            "id": claim.id, "customer_problem_id": claim.customer_problem_id,
            "status": claim.status, "issue_summary": claim.issue_summary,
            "approved_cost_gbp": claim.approved_cost_gbp, "outcome": claim.outcome,
            "opened_at": claim.opened_at, "resolved_at": claim.resolved_at,
        } for claim in claims],
    }


@admin_router.get("/warranty-reserves")
async def list_warranty_reserves(db: AsyncSession = Depends(get_db)):
    reserves = (await db.execute(select(WarrantyReserve).order_by(WarrantyReserve.warranty_expires_at))).scalars().all()
    claims = (await db.execute(select(WarrantyClaim))).scalars().all()
    claims_by_reserve: dict[int, list[WarrantyClaim]] = {}
    for claim in claims:
        claims_by_reserve.setdefault(claim.reserve_id, []).append(claim)
    return [_reserve_admin_dict(reserve, claims_by_reserve.get(reserve.id, [])) for reserve in reserves]


@admin_router.patch("/warranty-claims/{claim_id}")
async def update_warranty_claim(
    claim_id: int,
    body: WarrantyClaimUpdateIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    allowed = {
        "open", "reviewing", "approved", "awaiting_customer_return", "return_in_transit",
        "received_for_inspection", "repair_in_progress", "waiting_for_parts",
        "replacement_ordered", "replacement_dispatched", "resolved", "rejected", "closed",
    }
    if body.status not in allowed:
        raise HTTPException(400, "Invalid warranty claim status")
    if body.approved_cost_gbp < 0:
        raise HTTPException(400, "Approved cost cannot be negative")
    reserve, claim = await lock_warranty_reserve_then_claim(db, claim_id)
    if not claim:
        raise HTTPException(404, "Warranty claim not found")
    previous_status = claim.status
    claim.status = body.status
    claim.approved_cost_gbp = round(body.approved_cost_gbp, 2)
    claim.outcome = body.outcome
    claim.resolved_at = datetime.utcnow() if body.status in {"resolved", "rejected", "closed"} else None
    problem = await db.get(CustomerProblem, claim.customer_problem_id)
    if problem:
        problem.status = {
            "open": "claim_opened",
            "reviewing": "reviewing",
        }.get(body.status, body.status)
        if claim.status != previous_status:
            await _queue_direct_case_status_email(db, problem, background_tasks)
    if reserve:
        await recalculate_reserve_status(db, reserve)
    await db.flush()
    if problem and claim.status != previous_status:
        await db.commit()
    return _reserve_admin_dict(reserve, [claim]) if reserve else {"claim_id": claim.id, "status": claim.status}


@admin_router.post("/warranty-reserves/{reserve_id}/release")
async def release_warranty_reserve(
    reserve_id: int,
    body: WarrantyReleaseIn,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if not body.confirm_release:
        raise HTTPException(400, "Explicit release confirmation is required")
    if len(body.note.strip()) < 5:
        raise HTTPException(400, "Record a release note")
    reserve = await lock_warranty_owner_then_reserve(db, reserve_id)
    if not reserve:
        raise HTTPException(404, "Warranty reserve not found")
    await recalculate_reserve_status(db, reserve)
    if reserve.status != "eligible_for_release":
        raise HTTPException(409, "Reserve is not eligible: warranty may be active or a claim remains open")
    reserve.released_amount_gbp = round(max(0.0, reserve.reserved_amount_gbp - reserve.allocated_claim_amount_gbp), 2)
    reserve.status = "released"
    reserve.released_at = datetime.utcnow()
    reserve.released_by = getattr(admin, "email", None) or "admin"
    reserve.release_note = body.note.strip()
    await db.flush()
    return _reserve_admin_dict(reserve, [])


@admin_router.post("/shipment-events", status_code=201)
async def record_shipment_event(
    body: ShipmentEventIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Record a verified courier event without making any external purchase.

    Provider-specific webhook adapters should authenticate and normalise their
    payload before calling this contract. Only courier-supplied live-map URLs
    are persisted and shown to customers.
    """
    if (body.order_id is None) == (body.manual_build_id is None):
        raise HTTPException(400, "Provide exactly one order_id or manual_build_id")
    if not body.provider.strip() or len(body.provider) > 80:
        raise HTTPException(400, "Provider is required")
    if not body.status_code.strip() or len(body.status_code) > 80:
        raise HTTPException(400, "Status code is required")
    if not body.description.strip() or len(body.description) > 2000:
        raise HTTPException(400, "Description is required")
    normalized_provider = body.provider.strip().lower()
    normalized_event_id = body.provider_event_id.strip() if body.provider_event_id else None
    if normalized_event_id is not None and not normalized_event_id:
        normalized_event_id = None
    if normalized_event_id and len(normalized_event_id) > 200:
        raise HTTPException(400, "Provider event ID must be 200 characters or fewer")
    if body.location and len(body.location) > 300:
        raise HTTPException(400, "Location must be 300 characters or fewer")
    for label, url in (("tracking", body.tracking_url), ("live map", body.live_map_url)):
        if url and (len(url) > 1000 or not url.lower().startswith("https://")):
            raise HTTPException(400, f"{label.title()} URL must be a secure HTTPS URL")
    order = None
    if body.order_id:
        order = (await db.execute(
            select(Order).where(Order.id == body.order_id).with_for_update()
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
    build = None
    if body.manual_build_id:
        build = (await db.execute(
            select(ManualBuild).where(ManualBuild.id == body.manual_build_id).with_for_update()
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
    if body.order_id and not order:
        raise HTTPException(404, "Order not found")
    if body.manual_build_id and not build:
        raise HTTPException(404, "Build not found")
    if build is not None:
        linked_order_ids = set((await db.scalars(
            select(Build.order_id).where(
                Build.manual_build_id == build.id,
                Build.order_id.is_not(None),
            )
        )).all())
        linked_order_ids.update((await db.scalars(
            select(Product.sold_order_id)
            .join(Build, Product.build_id == Build.id)
            .where(
                Build.manual_build_id == build.id,
                Product.sold_order_id.is_not(None),
            )
        )).all())
        if len(linked_order_ids) > 1:
            raise HTTPException(
                409,
                "This physical build is linked to conflicting orders; reconcile the sale owner before recording delivery",
            )
        if linked_order_ids:
            linked_order_id = next(iter(linked_order_ids))
            raise HTTPException(
                409,
                f"This build belongs to order {linked_order_id}; record shipment events against that order to keep tracking and warranty records together",
            )
    if normalized_event_id:
        existing = (await db.execute(
            select(ShipmentTrackingEvent).where(
                ShipmentTrackingEvent.provider == normalized_provider,
                ShipmentTrackingEvent.provider_event_id == normalized_event_id,
            )
        )).scalar_one_or_none()
        if existing:
            if existing.order_id != body.order_id or existing.manual_build_id != body.manual_build_id:
                raise HTTPException(409, "This provider event ID is already attached to another shipment")
            return _tracking_event_dict(existing)

    event_occurred_at = body.occurred_at
    if event_occurred_at.tzinfo is not None:
        event_occurred_at = event_occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
    normalized_status_code = body.status_code.strip().lower()
    delivered_codes = {"delivered", "delivery_confirmed", "proof_of_delivery"}
    if normalized_status_code in delivered_codes and event_occurred_at > datetime.utcnow():
        raise HTTPException(422, "A delivery event cannot have a future occurrence time")
    event = ShipmentTrackingEvent(
        order_id=body.order_id,
        manual_build_id=body.manual_build_id,
        provider=normalized_provider,
        provider_event_id=normalized_event_id,
        status_code=normalized_status_code,
        description=body.description.strip(),
        location=body.location.strip() if body.location else None,
        tracking_url=body.tracking_url,
        live_map_url=body.live_map_url,
        occurred_at=event_occurred_at,
        material=body.material,
    )
    db.add(event)
    if event.status_code in delivered_codes:
        delivered_at = event_occurred_at
        if order:
            order.delivered_at = min(
                value for value in (order.delivered_at, delivered_at) if value is not None
            )
            order.actual_delivery_date = min(
                value for value in (order.actual_delivery_date, order.delivered_at) if value is not None
            )
            order.status = OrderStatus.COMPLETED
            reserve = await ensure_order_reserve(db, order, order.delivered_at)
            await recalculate_reserve_status(db, reserve)
            # A Ready-to-Ship physical build can be represented by both an
            # Order and a ManualBuild. Keep the build's operational delivery
            # fields aligned with the order event, while retaining the single
            # order-owned financial warranty reserve.
            await _sync_linked_manual_build_delivery(db, order.id, order.delivered_at)
        if build:
            build.delivered_at = min(
                value for value in (build.delivered_at, delivered_at) if value is not None
            )
            build.warranty_started_at = min(
                value for value in (build.warranty_started_at, build.delivered_at) if value is not None
            )
            build.dispatch_status = "delivered"
            reserve = await ensure_manual_build_reserve(db, build, build.warranty_started_at)
            if reserve is not None:
                await recalculate_reserve_status(db, reserve)
    await db.flush()
    event_id = event.id
    if event.order_id is not None and event.material and event.provider_event_id is None:
        event.provider_event_id = f"operator:{event_id}"
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if normalized_event_id:
            duplicate = (await db.execute(
                select(ShipmentTrackingEvent).where(
                    ShipmentTrackingEvent.provider == normalized_provider,
                    ShipmentTrackingEvent.provider_event_id == normalized_event_id,
                )
            )).scalar_one_or_none()
            if duplicate:
                if duplicate.order_id != body.order_id or duplicate.manual_build_id != body.manual_build_id:
                    raise HTTPException(409, "This provider event ID is already attached to another shipment")
                return _tracking_event_dict(duplicate)
        raise

    if event.material and event.order_id is not None:
        background_tasks.add_task(deliver_tracking_event_notification, event_id)
    return _tracking_event_dict(event)


@admin_router.get("/orders", response_model=list[AdminOrderOut])
async def list_orders(
    status: str = None,
    week: str = None,
    email: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List orders with optional filtering"""
    query = select(Order)

    if status:
        query = query.where(Order.status == status)
    if week:
        query = query.where(Order.assigned_build_week == week)
    if email:
        query = query.where(Order.customer_email.ilike(f"%{email}%"))

    query = query.order_by(Order.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@admin_router.patch("/orders/{order_id}", response_model=AdminOrderOut)
async def update_order(
    order_id: int,
    update: AdminOrderUpdateIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Update order status or notes"""
    order_result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
        .execution_options(populate_existing=True)
    )
    order = order_result.scalar()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status.value if hasattr(order.status, "value") else str(order.status)
    if update.status:
        change_request_status = (order.change_request or {}).get("status") if isinstance(order.change_request, dict) else None
        if change_request_status in {"requested", "quote_ready", "customer_approved"} and update.status != OrderStatus.AWAITING_SOURCING.value:
            raise HTTPException(409, "Sourcing is paused while the customer build-change request is open")
        if update.status == "cancelled":
            raise HTTPException(409, "Use the owner-verified cancellation and refund action; do not change cancellation status manually")
        if order.status == OrderStatus.CANCELLED or order.cancellation_requested_at:
            raise HTTPException(409, "This order is cancelled or has a refund pending reconciliation")
        if update.status == OrderStatus.SHIPPED.value:
            raise HTTPException(409, "Use Dispatch Centre's booked-shipment handover action after evidence and insurance checks")
        if update.status == "completed" and order.delivered_at is None:
            raise HTTPException(
                409,
                "Record the confirmed delivery event and its occurrence time before completing this order",
            )
        order.status = update.status
        if update.status in {"parts_ordered", "building", "qa", "ready_to_package", "packaging_in_progress", "ready_to_ship", "shipped", "completed"}:
            getting_started_job = (await db.execute(
                select(GettingStartedJob).where(GettingStartedJob.order_id == order.id)
            )).scalar_one_or_none()
            if getting_started_job:
                getting_started_job.checklist = {
                    **(getting_started_job.checklist or {}),
                    "components_ordered": True,
                }
        if update.status == "completed":
            await ensure_order_reserve(db, order, order.delivered_at)
            await _sync_linked_manual_build_delivery(db, order.id, order.delivered_at)
            existing_event = (await db.execute(
                select(ShipmentTrackingEvent).where(
                    ShipmentTrackingEvent.order_id == order.id,
                    ShipmentTrackingEvent.status_code.in_({"delivered", "delivery_confirmed", "proof_of_delivery"}),
                )
            )).scalar_one_or_none()
            if not existing_event:
                db.add(ShipmentTrackingEvent(
                    order_id=order.id, provider=order.carrier or "operator",
                    provider_event_id=f"admin-delivered:{order.id}", status_code="delivered",
                    description="Your courier delivery has been recorded as delivered.",
                    material=True, occurred_at=order.delivered_at,
                ))
        if update.status == "shipped":
            order.shipped_at = order.shipped_at or datetime.utcnow()
            existing_event = (await db.execute(select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.provider_event_id == f"admin-dispatch:{order.id}"))).scalar_one_or_none()
            if not existing_event:
                db.add(ShipmentTrackingEvent(
                    order_id=order.id, provider=order.carrier or "operator",
                    provider_event_id=f"admin-dispatch:{order.id}", status_code="dispatched",
                    description="Your order has been handed to the courier.",
                    material=True, occurred_at=order.shipped_at,
                ))
    if update.note is not None:
        pass

    order.updated_at = datetime.utcnow()
    await db.commit()

    if update.status and update.status != old_status:
        customer_result = await db.execute(select(Customer).where(Customer.id == order.customer_id))
        customer = customer_result.scalar_one_or_none()
        if customer:
            background_tasks.add_task(
                send_order_status_email,
                customer.email,
                customer.name,
                order.order_id,
                update.status,
                order.id,
            )

    return order


@admin_router.get("/capacity", response_model=BuildCapacityOut)
async def get_capacity(db: AsyncSession = Depends(get_db)):
    """Get global default capacity"""
    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    capacity = capacity_result.scalar()

    if not capacity:
        return BuildCapacityOut(default_per_week=3)

    return capacity


@admin_router.patch("/capacity/default")
async def update_capacity_default(
    default_per_week: int,
    db: AsyncSession = Depends(get_db),
):
    """Update global default capacity"""
    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    capacity = capacity_result.scalar()

    if not capacity:
        capacity = BuildCapacity(default_per_week=default_per_week)
        db.add(capacity)
    else:
        capacity.default_per_week = default_per_week

    capacity.updated_at = datetime.utcnow()
    await db.commit()

    return BuildCapacityOut(default_per_week=capacity.default_per_week)


@admin_router.put("/capacity/overrides/{week}")
async def set_capacity_override(
    week: str,
    override: CapacityOverrideIn,
    db: AsyncSession = Depends(get_db),
):
    """Set or remove week override (null max_builds = week closed)"""
    override_result = await db.execute(
        select(BuildCapacityOverride).where(BuildCapacityOverride.week == week)
    )
    existing = override_result.scalar()

    if existing:
        existing.max_builds = override.max_builds
        existing.note = override.note
    else:
        existing = BuildCapacityOverride(
            week=week,
            max_builds=override.max_builds,
            note=override.note,
        )
        db.add(existing)

    await db.commit()

    return {
        "week": existing.week,
        "max_builds": existing.max_builds,
        "note": existing.note,
    }
