"""
Public Ready-to-Ship product endpoints — no auth required.
Consumed by the theflipflop.shop storefront /ready-to-ship pages.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.product import Product, ProductStatus, ProductType
from app.models.cx_document import CXDocument, CXDocumentType, CXDocumentStatus
from app.models.capture_3d import Capture3DAsset, Capture3DStatus

router = APIRouter(prefix="/public", tags=["public-products"])

# A product is a real, purchasable Ready-to-Ship unit only while LISTED.
# RESERVED/SOLD/WITHDRAWN/DRAFT must never appear as available — a sold
# machine must not remain falsely listed.
_AVAILABLE = (ProductStatus.LISTED,)


def _summary_payload(p: Product) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "price": p.price,
        "status": p.status.value,
        "hero_photo_url": p.hero_photo_url,
        "has_benchmark_report": p.benchmark_report_document_id is not None,
        "has_3d_twin": p.capture_3d_asset_id is not None or bool(p.model_3d_url),
        "model_3d_url": p.model_3d_url,
        "fulfilment": {
            "type": p.fulfilment_type,
            "handling_min_days": p.handling_min_days,
            "handling_max_days": p.handling_max_days,
            "delivery_min_days": p.delivery_min_days,
            "delivery_max_days": p.delivery_max_days,
        },
    }


@router.get("/products")
async def public_list_products(db: AsyncSession = Depends(get_db)):
    """Ready-to-Ship products currently available for direct purchase."""
    result = await db.execute(
        select(Product)
        .where(
            Product.product_type == ProductType.PREBUILT,
            Product.status.in_(_AVAILABLE),
        )
        .order_by(Product.created_at.desc())
    )
    return [_summary_payload(p) for p in result.scalars().all()]


@router.get("/products/{product_id}")
async def public_product_detail(product_id: int, db: AsyncSession = Depends(get_db)):
    """Full Ready-to-Ship product detail: spec, benchmark report, 3D twin."""
    product = (
        await db.execute(
            select(Product)
            .options(selectinload(Product.build))
            .where(Product.id == product_id)
        )
    ).scalar_one_or_none()
    if not product or product.product_type != ProductType.PREBUILT:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.status not in _AVAILABLE:
        raise HTTPException(status_code=404, detail="Product no longer available")

    build_spec = None
    if product.build is not None:
        build_spec = product.build.spec_json

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
                select(Capture3DAsset).where(
                    Capture3DAsset.id == product.capture_3d_asset_id,
                    Capture3DAsset.status == Capture3DStatus.PUBLISHED,
                )
            )
        ).scalar_one_or_none()
        if cap:
            twin = {
                "optimized_asset_ref": cap.optimized_asset_ref,
                "preview_image_ref": cap.preview_image_ref,
                "ar_ready": cap.ar_ready,
            }

    return {
        **_summary_payload(product),
        "description": product.description,
        "spec": build_spec,
        # Measured results only — never presented alongside estimates.
        "benchmark_report": benchmark,
        "twin_3d": twin or ({"optimized_asset_ref": product.model_3d_url, "preview_image_ref": None, "ar_ready": False} if product.model_3d_url else None),
        "customer_policies": {
            "returns": "30-day returns. For a change of mind, the customer pays return postage; faulty or misdescribed goods are returned at FlipFlop's cost. Statutory rights are unaffected.",
            "warranty": "UK statutory consumer rights apply. Any remaining transferable manufacturer warranty is identified with the build; no unsupported manufacturer cover is implied.",
            "delivery": "Ready-to-ship PCs are dispatched after 1 working day handling, with an estimated 1–2 working day tracked delivery window.",
            "support": "Direct setup, troubleshooting and upgrade support is available through the personalised owner portal.",
        },
    }
