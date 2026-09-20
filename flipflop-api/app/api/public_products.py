"""
Public Ready-to-Ship product endpoints — no auth required.
Consumed by the theflipflop.shop storefront /ready-to-ship pages.
"""
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from urllib.parse import quote
from html import escape
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.product import Product, ProductStatus, ProductType
from app.models.manual_build import ManualBuild
from app.models.cx_document import CXDocument, CXDocumentType, CXDocumentStatus
from app.models.capture_3d import Capture3DAsset, Capture3DStatus

router = APIRouter(prefix="/public", tags=["public-products"])

# A product is a real, purchasable Ready-to-Ship unit only while LISTED.
# RESERVED/SOLD/WITHDRAWN/DRAFT must never appear as available — a sold
# machine must not remain falsely listed.
_AVAILABLE = (ProductStatus.LISTED,)
_BUILD_ASSETS_ROOT = Path(__file__).resolve().parents[3] / "builds"
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _build_asset_pack(
    build_id: int | None,
    photos: list | None,
    build_name: str | None = None,
    spec: dict | None = None,
    item_specifics: dict | None = None,
) -> dict:
    """Expose the named image groups from the build pack to the storefront."""
    empty = {
        "gallery": [],
        "specifications": [],
        "performance": [],
        "registration": [],
        "model_3d": None,
        "specifications_html": None,
        "performance_html": None,
    }
    if not build_id:
        return empty
    build_dir = _BUILD_ASSETS_ROOT / f"{build_id:03d}"
    if not build_dir.is_dir():
        build_dir = _BUILD_ASSETS_ROOT / str(build_id)
    if not build_dir.is_dir():
        return empty

    def url_for(path: Path) -> str:
        relative = path.relative_to(_BUILD_ASSETS_ROOT).as_posix()
        return f"/api/builds/{quote(relative, safe='/')}"

    def files_in(folder: str) -> list[Path]:
        directory = build_dir / folder
        return sorted((p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES), key=lambda p: p.name) if directory.is_dir() else []

    pack = {key: [] for key in empty if key != "model_3d"}
    pack["model_3d"] = None
    media_files = files_in("Media")
    if media_files:
        # The listing pack is the source of truth. Older database rows can
        # contain one repeated legacy URL, which must not hide the complete
        # Media folder from the storefront.
        pack["gallery"] = [
            {"url": url_for(path), "title": f"Build photograph {index + 1}"}
            for index, path in enumerate(media_files)
        ]
    else:
        photo_rows = photos or []
        seen_urls: set[str] = set()
        pack["gallery"] = []
        for row in photo_rows:
            if not isinstance(row, dict) or not row.get("url"):
                continue
            url = str(row["url"])
            if url in seen_urls:
                continue
            seen_urls.add(url)
            pack["gallery"].append({"url": url, "title": row.get("title") or f"Build photograph {len(pack['gallery']) + 1}"})
    pack["specifications"] = [{"url": url_for(path), "title": f"Specification card {index + 1}"} for index, path in enumerate(files_in("Specifications"))]
    performance_titles = ["Overview and rankings", "Measured results and gaming estimates", "Productivity and system health", "Performance summary"]
    performance_files = files_in("Performance")
    pack["performance"] = [{"url": url_for(path), "title": f"Performance card {index + 1} — {performance_titles[index] if index < len(performance_titles) else path.stem}"} for index, path in enumerate(performance_files)]
    performance_html = build_dir / "Performance" / "performance.html"
    if performance_files and not performance_html.exists():
        performance_html.parent.mkdir(parents=True, exist_ok=True)
        images = "".join(
            f"<figure><img src='{escape(path.name)}' alt='{escape(path.stem)}'><figcaption>{escape(path.stem.replace('-', ' '))}</figcaption></figure>"
            for path in performance_files
        )
        performance_html.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><title>Performance</title><style>body{margin:0;padding:28px;background:#0d1015;color:#f5f7fa;font:15px Arial,sans-serif}h1{color:#b7f36a}main{display:grid;gap:22px}figure{margin:0;padding:12px;background:#151c28;border:1px solid #30425c;border-radius:14px}img{display:block;width:100%;height:auto;border-radius:9px}figcaption{padding:10px 2px 2px;color:#b9d7ff;text-transform:capitalize}</style></head><body><h1>Performance</h1><main>"
            + images + "</main></body></html>", encoding="utf-8"
        )
    if performance_html.is_file():
        pack["performance_html"] = {"url": url_for(performance_html), "title": "Full performance report"}
    registration_files = files_in("Registration")
    pack["registration"] = [{"url": url_for(path), "title": f"Registration plate {index + 1}"} for index, path in enumerate(registration_files)]

    # Keep a self-contained HTML copy of the generated specification document
    # in the pack. This is the canonical portal; image cards remain available
    # as a backwards-compatible fallback for older clients.
    specifications_html = build_dir / "Specifications" / "specifications.html"
    if not specifications_html.exists():
        rows = []
        for key, value in (item_specifics or {}).items():
            rows.append(f"<tr><th>{escape(str(key))}</th><td>{escape(str(value))}</td></tr>")
        if not rows:
            for key, value in (spec or {}).items():
                rows.append(f"<tr><th>{escape(str(key))}</th><td>{escape(json.dumps(value) if isinstance(value, (dict, list)) else str(value))}</td></tr>")
        specifications_html.parent.mkdir(parents=True, exist_ok=True)
        specifications_html.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><title>"
            + escape(build_name or "Build specifications")
            + "</title><style>body{margin:0;padding:32px;background:#0d1015;color:#f5f7fa;font:16px Arial,sans-serif}h1{color:#b7f36a}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:14px;border-bottom:1px solid #26354a}th{color:#ff9a4d;width:35%}td{color:#b9d7ff}</style></head><body><h1>"
            + escape(build_name or "Build specifications")
            + "</h1><table>"
            + "".join(rows)
            + "</table></body></html>",
            encoding="utf-8",
        )
    if specifications_html.is_file():
        pack["specifications_html"] = {"url": url_for(specifications_html), "title": "Full specifications"}

    model_dir = build_dir / "3D Build"
    model_files = sorted(
        (path for path in model_dir.iterdir() if path.is_file() and path.suffix.lower() == ".glb"),
        key=lambda path: ("complete_build" not in path.name.lower(), path.name),
    ) if model_dir.is_dir() else []
    if model_files:
        pack["model_3d"] = {"url": url_for(model_files[0]), "title": "Completed build 3D model"}
    return pack


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
        "platform_category": {
            "id": p.platform_category_id,
            "name": p.platform_category_name,
        } if p.platform_category_id or p.platform_category_name else None,
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
    manual_build = None
    item_specifics = product.item_specifics or {}
    platform_category = {
        "id": product.platform_category_id,
        "name": product.platform_category_name,
    } if product.platform_category_id or product.platform_category_name else None
    if product.build is not None:
        build_spec = product.build.spec_json
        # Backfill the response for older direct listings created before the
        # storefront-specific fields existed. Publishing again will persist
        # these values; this keeps the live product page correct meanwhile.
        if not item_specifics and product.build.manual_build_id:
            manual_build = (
                await db.execute(
                    select(ManualBuild).where(ManualBuild.id == product.build.manual_build_id)
                )
            ).scalar_one_or_none()
            if manual_build:
                item_specifics = {
                    name: ", ".join(str(value) for value in values if value is not None)
                    for name, values in (manual_build.generated_aspects or {}).items()
                    if isinstance(values, list) and any(value is not None for value in values)
                }
                platform_category = {"id": "179", "name": "PC Desktops & All-in-Ones"}
        elif product.build.manual_build_id:
            manual_build = (
                await db.execute(select(ManualBuild).where(ManualBuild.id == product.build.manual_build_id))
            ).scalar_one_or_none()

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
        "build_id": product.build.manual_build_id if product.build else product.id,
        "build_name": manual_build.name if manual_build and manual_build.name else product.title,
        "description": product.description,
        "spec": build_spec,
        "item_specifics": item_specifics,
        "platform_category": platform_category,
        # Measured results only — never presented alongside estimates.
        "benchmark_report": benchmark,
        "twin_3d": twin or ({"optimized_asset_ref": product.model_3d_url, "preview_image_ref": None, "ar_ready": False} if product.model_3d_url else None),
        "asset_pack": _build_asset_pack(
            product.build.manual_build_id if product.build else None,
            manual_build.photos if manual_build else None,
            manual_build.name if manual_build else product.title,
            build_spec,
            item_specifics,
        ),
        "customer_policies": {
            "returns": "30-day returns. For a change of mind, the customer pays return postage; faulty or misdescribed goods are returned at FlipFlop's cost. Statutory rights are unaffected.",
            "warranty": "UK statutory consumer rights apply. Any remaining transferable manufacturer warranty is identified with the build; no unsupported manufacturer cover is implied.",
            "delivery": "Ready-to-ship PCs are dispatched after 1 working day handling, with an estimated 1–2 working day tracked delivery window.",
            "support": "Direct setup, troubleshooting and upgrade support is available through the personalised owner portal.",
        },
        "faqs": product.selected_faqs or [],
    }
