"""Upgrade intake, expert advice and material scope approval."""
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.customer import Customer
from app.models.upgrade_assessment import UpgradeAssessment
from app.routes.admin_auth import get_current_admin
from app.routes.auth import get_current_user

router = APIRouter(prefix="/upgrades", tags=["upgrades"])
admin_router = APIRouter(prefix="/admin/upgrades", tags=["admin-upgrades"], dependencies=[Depends(get_current_admin)])


class AdviceKind(str, Enum):
    KEEP = "KEEP"
    UPGRADE = "UPGRADE"
    OPTIONAL = "OPTIONAL"
    DONT_SPEND_HERE = "DONT_SPEND_HERE"
    TRANSFORM = "TRANSFORM"


class UpgradeIntake(BaseModel):
    submitted_spec: dict = Field(default_factory=dict)
    desired_outcome: str = Field(min_length=10, max_length=3000)
    budget_gbp: int = Field(ge=0, le=20000)
    photo_urls: list[str] = Field(default_factory=list, max_length=12)
    system_report_url: str | None = None


class UpgradeAdvice(BaseModel):
    recommendation: AdviceKind
    explanation: str = Field(min_length=20)
    keep: list[str] = Field(default_factory=list)
    upgrade: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    dont_spend_here: list[str] = Field(default_factory=list)
    transform: list[str] = Field(default_factory=list)
    quoted_price_gbp: int | None = Field(default=None, ge=0)
    material_change: bool = False


def _payload(row: UpgradeAssessment) -> dict:
    return {
        "id": row.id, "status": row.status, "submitted_spec": row.submitted_spec,
        "desired_outcome": row.desired_outcome, "budget_gbp": row.budget_gbp,
        "photo_urls": row.photo_urls, "system_report_url": row.system_report_url,
        "advice": row.advice, "scope_revision": row.scope_revision,
        "approval_required": row.approval_required, "approved_revision": row.approved_revision,
        "created_at": row.created_at,
    }


@router.post("", status_code=201)
async def submit_upgrade(
    body: UpgradeIntake, customer: Customer = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> dict:
    row = UpgradeAssessment(customer_id=customer.id, **body.model_dump(), status="submitted",
                            scope_revision=0, approval_required=False)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _payload(row)


@router.get("/mine")
async def my_upgrades(customer: Customer = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(UpgradeAssessment).where(UpgradeAssessment.customer_id == customer.id)
                             .order_by(UpgradeAssessment.created_at.desc()))).scalars().all()
    return [_payload(row) for row in rows]


@router.get("/{assessment_id}")
async def get_upgrade(
    assessment_id: int, customer: Customer = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> dict:
    row = (await db.execute(select(UpgradeAssessment).where(UpgradeAssessment.id == assessment_id,
                                                       UpgradeAssessment.customer_id == customer.id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Assessment not found")
    return _payload(row)


@router.post("/{assessment_id}/approve")
async def approve_scope(
    assessment_id: int, customer: Customer = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> dict:
    row = (await db.execute(select(UpgradeAssessment).where(UpgradeAssessment.id == assessment_id,
                                                       UpgradeAssessment.customer_id == customer.id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Assessment not found")
    if not row.approval_required or row.advice is None:
        raise HTTPException(409, "No material change is awaiting approval")
    row.approved_revision = row.scope_revision
    row.approval_required = False
    row.status = "scope_approved"
    await db.commit()
    return _payload(row)


@admin_router.get("")
async def admin_list_upgrades(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(UpgradeAssessment).order_by(UpgradeAssessment.created_at.desc()).limit(200))).scalars().all()
    return [_payload(row) for row in rows]


@admin_router.put("/{assessment_id}/advice")
async def publish_advice(assessment_id: int, body: UpgradeAdvice, db: AsyncSession = Depends(get_db)) -> dict:
    row = (await db.execute(select(UpgradeAssessment).where(UpgradeAssessment.id == assessment_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Assessment not found")
    row.scope_revision += 1
    row.advice = body.model_dump(mode="json")
    row.approval_required = body.material_change
    row.approved_revision = None
    row.status = "approval_required" if body.material_change else "advice_ready"
    await db.commit()
    return _payload(row)
