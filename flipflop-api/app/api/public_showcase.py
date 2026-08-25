"""
Public Previous Builds showcase endpoints — no auth required.
Consumed by the theflipflop.shop storefront /builds pages.

Presentation note: no 3D "hangar/Earth" asset exists in this codebase yet, and
no per-build 3D twin has been published (capture_3d_assets has no PUBLISHED
rows). Every build below ships in honest photo-mode (hero_photo_url on a
pedestal) until a real twin exists — the frontend never fabricates a 3D
model for a build that doesn't have one.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.product import Product, ProductStatus, ProductType, SoldChannel
from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.models.manual_build import ManualBuild
from app.models.cx_document import CXDocument, CXDocumentType, CXDocumentStatus
from app.models.capture_3d import Capture3DAsset, Capture3DStatus
from app.routes.auth import get_current_user
from app.schemas.product_checkout import (
    ProductCheckoutIntentResponse, ProductCheckoutConfirmRequest, ProductCheckoutConfirmation,
)
from app.services.payment_service import PaymentService
from app.services.email_service import send_order_confirmation_email
from app.services.alerts import emit_alert
from app.services.cross_channel_guard import withdraw_ebay_for_sold_build
from app.config import get_settings

router = APIRouter(prefix="/public", tags=["public-showcase"])

# How long a reservation holds a product out of sale while the buyer is
# mid-checkout — matches Product.reserved_until's documented purpose (Ch.9.6).
_RESERVATION_MINUTES = 15

# A completed build is showcase-worthy once it has sold (proof it was really
# built and delivered) or is listed for sale — draft/withdrawn units are not
# real evidence of finished work.
_SHOWCASE_STATUSES = (ProductStatus.SOLD, ProductStatus.LISTED, ProductStatus.RESERVED)


def _twin_ref(cap: Capture3DAsset | None) -> dict | None:
    if not cap or cap.status != Capture3DStatus.PUBLISHED:
        return None
    return {
        "optimized_asset_ref": cap.optimized_asset_ref,
        "preview_image_ref": cap.preview_image_ref,
    }


@router.get("/showcase-builds")
async def public_list_showcase_builds(db: AsyncSession = Depends(get_db)):
    """Completed FlipFlop builds for the Previous Builds hangar."""
    products = (
        await db.execute(
            select(Product)
            .options(selectinload(Product.build))
            .where(
                Product.product_type == ProductType.PREBUILT,
                Product.status.in_(_SHOWCASE_STATUSES),
                Product.hero_photo_url.isnot(None),
            )
            .order_by(Product.created_at.desc())
        )
    ).scalars().all()

    twin_ids = [p.capture_3d_asset_id for p in products if p.capture_3d_asset_id]
    twins_by_id: dict[int, Capture3DAsset] = {}
    if twin_ids:
        twin_rows = (
            await db.execute(select(Capture3DAsset).where(Capture3DAsset.id.in_(twin_ids)))
        ).scalars().all()
        twins_by_id = {t.id: t for t in twin_rows}

    return [
        {
            "id": p.id,
            "title": p.title,
            "hero_photo_url": p.hero_photo_url,
            "spec_highlights": (p.build.spec_json if p.build else None),
            "twin_3d": _twin_ref(twins_by_id.get(p.capture_3d_asset_id))
            if p.capture_3d_asset_id
            else ({"optimized_asset_ref": p.model_3d_url, "preview_image_ref": None, "ar_ready": False} if p.model_3d_url else None),
            "price": p.price,
            "sold": p.status == ProductStatus.SOLD,
            # RESERVED means someone else is mid-checkout right now — distinct
            # from permanently SOLD, but the frontend shouldn't offer to buy
            # it either way.
            "buyable": p.status == ProductStatus.LISTED,
        }
        for p in products
    ]


@router.get("/showcase-builds/{product_id}")
async def public_showcase_build_detail(product_id: int, db: AsyncSession = Depends(get_db)):
    product = (
        await db.execute(
            select(Product)
            .options(selectinload(Product.build))
            .where(Product.id == product_id)
        )
    ).scalar_one_or_none()
    if (
        not product
        or product.product_type != ProductType.PREBUILT
        or product.status not in _SHOWCASE_STATUSES
        or not product.hero_photo_url
    ):
        raise HTTPException(status_code=404, detail="Build not found")

    benchmark = None
    if product.benchmark_report_document_id:
        doc = (
            await db.execute(
                select(CXDocument).where(
                    CXDocument.id == product.benchmark_report_document_id,
                    CXDocument.document_type == CXDocumentType.BENCHMARK_REPORT,
                    CXDocument.status == CXDocumentStatus.READY,
                )
            )
        ).scalar_one_or_none()
        if doc:
            benchmark = doc.content_json

    twin = None
    if product.capture_3d_asset_id:
        cap = (
            await db.execute(
                select(Capture3DAsset).where(Capture3DAsset.id == product.capture_3d_asset_id)
            )
        ).scalar_one_or_none()
        twin = _twin_ref(cap)

    return {
        "id": product.id,
        "title": product.title,
        "description": product.description,
        "hero_photo_url": product.hero_photo_url,
        "model_3d_url": product.model_3d_url,
        "fulfilment": {
            "type": product.fulfilment_type,
            "handling_min_days": product.handling_min_days,
            "handling_max_days": product.handling_max_days,
            "delivery_min_days": product.delivery_min_days,
            "delivery_max_days": product.delivery_max_days,
        },
        "spec": product.build.spec_json if product.build else None,
        "benchmark_report": benchmark,
        "twin_3d": twin,
        "price": product.price,
        "sold": product.status == ProductStatus.SOLD,
        "buyable": product.status == ProductStatus.LISTED,
    }


async def _load_buyable_product(product_id: int, db: AsyncSession) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product or product.product_type != ProductType.PREBUILT:
        raise HTTPException(404, "Build not found")

    reservation_stale = product.reserved_until is not None and product.reserved_until < datetime.utcnow()
    if product.status == ProductStatus.SOLD:
        raise HTTPException(409, "This build has already been sold.")
    if product.status == ProductStatus.WITHDRAWN:
        raise HTTPException(409, "This build is no longer available.")
    if product.status == ProductStatus.RESERVED and not reservation_stale:
        raise HTTPException(409, "Someone else is currently checking out with this build — try again shortly.")
    if product.price is None or product.price <= 0:
        raise HTTPException(400, "This build has no price set yet.")
    return product


@router.post("/showcase-builds/{product_id}/checkout-intent", response_model=ProductCheckoutIntentResponse)
async def create_checkout_intent(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_user),
):
    """Reserves this specific pre-built unit for 15 minutes and opens a
    Stripe PaymentIntent for its real listed price. Requires the buyer to
    be logged in — reuses the same auth as the rest of the storefront
    (see app/routes/auth.py's get_current_user), since a real delivery
    address/name is needed and the account already holds one."""
    product = await _load_buyable_product(product_id, db)

    product.status = ProductStatus.RESERVED
    product.reserved_until = datetime.utcnow() + timedelta(minutes=_RESERVATION_MINUTES)
    product.updated_at = datetime.utcnow()
    await db.flush()

    try:
        payment_service = PaymentService()
        intent_data = await payment_service.create_payment_intent(
            customer_id=customer.id,
            budget=product.price,
            quote_data={"purchase_type": "product", "product_id": product.id},
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # PaymentService.create_payment_intent doesn't expose a way to set
    # metadata beyond customer_id/budget — patch it in directly via Stripe
    # so the webhook fallback (see routes/webhooks.py) can tell this apart
    # from a configurator purchase.
    import stripe
    stripe.PaymentIntent.modify(
        intent_data["intent_id"],
        metadata={"purchase_type": "product", "product_id": str(product.id), "customer_id": str(customer.id)},
    )

    return ProductCheckoutIntentResponse(**intent_data)


@router.post("/showcase-builds/{product_id}/checkout-confirm", response_model=ProductCheckoutConfirmation)
async def confirm_checkout(
    product_id: int,
    body: ProductCheckoutConfirmRequest,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_user),
):
    """Verifies the Stripe payment actually succeeded, then creates the
    Order and marks this Product sold. This is the primary path — the
    Stripe webhook (routes/webhooks.py) only exists as a fallback for the
    rare case this call never fires (tab closed mid-flow)."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Build not found")
    if product.status == ProductStatus.SOLD:
        raise HTTPException(409, "This build has already been sold.")

    try:
        payment_service = PaymentService()
        payment_data = await payment_service.handle_payment_success(
            intent_id=body.intent_id, customer_id=customer.id, quote_data={},
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Find any linked ManualBuild before taking locks (unlocked — these FKs
    # don't change concurrently), so we can lock it first below. Global lock
    # order across this codebase's cross-channel paths is always ManualBuild
    # before Product (see manual_builds.py's sync_ebay_order and
    # cross_channel_guard.py), to avoid an ABBA deadlock between this route
    # and the eBay-side sale-confirmation route.
    manual_build = None
    if product.build_id:
        from app.models.build import Build
        build_result = await db.execute(select(Build).where(Build.id == product.build_id))
        orchestration_build = build_result.scalar_one_or_none()
        if orchestration_build and orchestration_build.manual_build_id:
            manual_locked = await db.execute(
                select(ManualBuild).where(ManualBuild.id == orchestration_build.manual_build_id).with_for_update()
            )
            manual_build = manual_locked.scalar_one_or_none()

    # Re-check under a row lock right before finalising the sale — closes the
    # race window between the unlocked check above and this write, where a
    # concurrent eBay-side sale (manual_builds.py's sync_ebay_order ->
    # cross_channel_guard.withdraw_storefront_for_sold_build, which takes the
    # same lock) could otherwise also pass its own unlocked check and both
    # sides end up marking this unit sold.
    locked_result = await db.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    product = locked_result.scalar_one_or_none()
    if not product or product.status == ProductStatus.SOLD:
        raise HTTPException(409, "This build has already been sold.")
    if manual_build and manual_build.status == "sold":
        raise HTTPException(409, "This build has already been sold.")

    order = Order(
        order_id=f"ORD-PROD-{body.intent_id[-12:]}",
        customer_id=customer.id,
        status=OrderStatus.READY_TO_PACKAGE,  # already built — nothing left to source/assemble
        specs={"product_id": product.id, "build_title": product.title},
        customer_price=payment_data["amount"],
        component_costs=0.0,
        overhead_amount=0.0,
        stripe_payment_intent_id=body.intent_id,
        notes=f"Pre-built showcase purchase. Product #{product.id}. Intent: {body.intent_id}",
    )
    db.add(order)
    await db.flush()

    product.status = ProductStatus.SOLD
    product.sold_via_channel = SoldChannel.STOREFRONT
    product.sold_order_id = order.id
    product.reserved_until = None
    product.updated_at = datetime.utcnow()

    # Deliberately NOT setting manual_build.status = "sold" here — that must
    # stay unset until after withdraw_ebay_for_sold_build runs below, because
    # that function's own idempotency guard skips the withdrawal entirely
    # once status == "sold". The Product.status = SOLD write above (still
    # under the lock, about to be committed) is the authoritative signal a
    # concurrent sync_ebay_order/cross_channel_guard check relies on, so it's
    # safe to defer this bookkeeping field to the second commit below.
    will_withdraw_ebay = bool(manual_build and manual_build.ebay_sku)

    # Commit the sale now, before any external network calls — the payment
    # already succeeded, so the sale must be durable even if the eBay
    # withdrawal or email below fails or hangs. This also releases the
    # ManualBuild/Product row locks taken above instead of holding them
    # across slow external I/O, which is what turned an unlikely race into a
    # routine deadlock risk between this route and sync_ebay_order.
    await db.commit()

    # Same alert code the admin dashboard's confetti listens for
    # (top-command-bar.tsx), so a direct storefront sale celebrates too.
    try:
        await emit_alert(
            code="flip_resale_detected",
            source="storefront_checkout",
            severity="info",
            message=f"Sale detected: {product.title or 'Pre-built PC'} sold on storefront for £{payment_data['amount']:.2f}.",
        )
    except Exception as e:
        import structlog
        structlog.get_logger(__name__).warning(
            "product_checkout.alert_emit_failed", error=str(e), product_id=product.id
        )

    ebay_withdrawn = None
    if will_withdraw_ebay:
        settings = get_settings()
        await withdraw_ebay_for_sold_build(manual_build, settings.ebay_listing_environment)
        manual_build.status = "sold"
        manual_build.sale_price_actual = payment_data["amount"]
        from app.services.inventory_lifecycle import record_sale
        await record_sale(db, manual_build, payment_data["amount"])
        manual_build.updated_at = datetime.utcnow()
        await db.commit()
        ebay_withdrawn = True

    try:
        await send_order_confirmation_email(
            customer_email=customer.email,
            customer_name=customer.name,
            order_reference=order.order_id,
            build_summary=f"{product.title or 'Pre-built PC'} — £{payment_data['amount']:.2f}",
            assigned_week="Ready to ship",
        )
    except Exception as e:
        import structlog
        structlog.get_logger(__name__).warning(
            "product_checkout.email_send_failed", error=str(e), order_id=order.id
        )

    return ProductCheckoutConfirmation(
        order_id=order.id,
        product_id=product.id,
        status=order.status.value,
        amount=payment_data["amount"],
        currency=payment_data["currency"],
        payment_intent_id=body.intent_id,
        created_at=order.created_at,
        ebay_listing_withdrawn=ebay_withdrawn,
    )
