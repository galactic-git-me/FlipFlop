"""Admin-only economic assessments; these do not create customer offers."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.commerce_evidence import (
    PriceQuoteSnapshot, SupplierOfferEvidence, WorkshopCapacityEvidence,
    WorkshopCapacityReservation, WorkshopCapacityReservationEvent,
)
from app.routes.admin_auth import get_current_admin
from app.services.commerce_pricing import Condition, ConditionPolicy, CostStack, FulfilmentMode, MarketEvidence, SupplierOffer, eligible_offers, evaluate_price
from app.services.gem_economics import GemCosts, assess_gem
from app.services.procurement_optimizer import ApprovedPart, optimise_bom
from app.services.workshop_capacity import (
    active_hold_count, capacity_evidence_is_current, latest_capacity_evidence, lock_build_week,
)

router = APIRouter(prefix="/commerce-intelligence", tags=["commerce-intelligence"], dependencies=[Depends(get_current_admin)])


class CostStackInput(BaseModel):
    landed_parts: Decimal = Field(ge=0)
    build_labour: Decimal = Field(ge=0)
    packaging: Decimal = Field(ge=0)
    outbound_delivery: Decimal = Field(ge=0)
    payment_cost: Decimal = Field(ge=0)
    warranty_reserve: Decimal = Field(ge=0)
    returns_reserve: Decimal = Field(ge=0)
    expected_failure_cost: Decimal = Field(ge=0)
    allocated_overhead: Decimal = Field(ge=0)
    other_variable_costs: Decimal = Field(default=Decimal("0"), ge=0)


class MarketEvidenceInput(BaseModel):
    condition: Condition
    sold_median_gbp: Decimal | None = Field(default=None, ge=0)
    sold_sample_size: int = Field(ge=0)
    observed_at: str | None = None
    active_median_gbp: Decimal | None = Field(default=None, ge=0)


class PriceAssessmentRequest(BaseModel):
    costs: CostStackInput
    market: MarketEvidenceInput
    condition: Condition
    minimum_contribution_gbp: Decimal = Field(ge=0)
    minimum_margin_fraction: Decimal = Field(ge=0, lt=1)
    premium_gbp: Decimal = Field(default=Decimal("0"), ge=0)


class SupplierOfferEvidenceInput(BaseModel):
    part_key: str = Field(min_length=1, max_length=160)
    supplier: str = Field(min_length=1, max_length=160)
    channel: str = Field(pattern="^(retail|marketplace)$")
    condition: Condition
    item_gbp: Decimal = Field(ge=0)
    delivery_gbp: Decimal = Field(ge=0)
    fees_gbp: Decimal = Field(ge=0)
    risk_gbp: Decimal = Field(ge=0)
    observed_at: datetime
    stock_confirmed: bool
    delivery_working_days: int | None = Field(default=None, ge=0)
    supplier_confidence: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    evidence_source: str = Field(min_length=1, max_length=160)
    evidence_ref: str = Field(min_length=1, max_length=500)


@router.post("/supplier-offers", status_code=201)
async def capture_supplier_offer(
    body: SupplierOfferEvidenceInput,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    observed_at = body.observed_at
    if observed_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="observed_at must include a timezone")
    if observed_at > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="observed_at cannot be in the future")
    row = SupplierOfferEvidence(
        part_key=body.part_key, supplier=body.supplier, channel=body.channel,
        condition=body.condition.value, item_gbp=body.item_gbp, delivery_gbp=body.delivery_gbp,
        fees_gbp=body.fees_gbp, risk_gbp=body.risk_gbp, observed_at=observed_at,
        stock_confirmed=body.stock_confirmed, delivery_working_days=body.delivery_working_days,
        supplier_confidence=body.supplier_confidence, evidence_source=body.evidence_source,
        evidence_ref=body.evidence_ref, captured_by_admin_id=admin.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "part_key": row.part_key, "status": "captured", "captured_at": row.captured_at.isoformat()}


class QuoteSnapshotRequest(BaseModel):
    product_key: str = Field(min_length=1, max_length=160)
    required_part_keys: list[str] = Field(min_length=1)
    supplier_offer_ids: list[int] = Field(min_length=1)
    capacity_evidence_id: int | None = Field(default=None, gt=0)
    costs: CostStackInput
    market: MarketEvidenceInput
    market_evidence_source: str = Field(min_length=1, max_length=160)
    market_evidence_ref: str = Field(min_length=1, max_length=500)
    condition: Condition
    fulfilment_mode: FulfilmentMode
    condition_policy: ConditionPolicy
    nonnew_consent: bool = False
    minimum_contribution_gbp: Decimal = Field(ge=0)
    minimum_margin_fraction: Decimal = Field(ge=0, lt=1)
    premium_gbp: Decimal = Field(default=Decimal("0"), ge=0)


@router.post("/quote-snapshots", status_code=201)
async def create_quote_snapshot(
    body: QuoteSnapshotRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    if len(set(body.supplier_offer_ids)) != len(body.supplier_offer_ids):
        raise HTTPException(status_code=422, detail="supplier_offer_ids must be unique")
    result = await db.execute(select(SupplierOfferEvidence).where(SupplierOfferEvidence.id.in_(body.supplier_offer_ids)))
    rows = list(result.scalars().all())
    if len(rows) != len(body.supplier_offer_ids):
        raise HTTPException(status_code=422, detail="One or more supplier offer evidence records do not exist")

    capacity = None
    if body.fulfilment_mode != FulfilmentMode.READY_TO_SHIP:
        if body.capacity_evidence_id is None:
            return await _save_quote_snapshot(
                db, body, admin, rows, None,
                {"offerable": False, "reason": "Current workshop capacity evidence is required"},
            )
        capacity = await db.get(WorkshopCapacityEvidence, body.capacity_evidence_id)
        if capacity is None:
            raise HTTPException(status_code=422, detail="Workshop capacity evidence record does not exist")
        now = datetime.now(timezone.utc)
        latest = await latest_capacity_evidence(db, capacity.build_week)
        active_holds = await active_hold_count(db, capacity.build_week, now)
        if (
            latest is None or latest.id != capacity.id
            or not capacity_evidence_is_current(capacity, now)
            or active_holds >= capacity.available_builds
        ):
            return await _save_quote_snapshot(
                db, body, admin, rows, None,
                {"offerable": False, "reason": "Workshop capacity evidence is superseded, stale, full, or for a past build week"},
                capacity,
            )
    offers = [SupplierOffer(
        supplier=row.supplier, channel=row.channel, condition=Condition(row.condition),
        item_gbp=Decimal(row.item_gbp), delivery_gbp=Decimal(row.delivery_gbp), fees_gbp=Decimal(row.fees_gbp),
        risk_gbp=Decimal(row.risk_gbp), observed_at=row.observed_at.isoformat(), stock_confirmed=row.stock_confirmed,
        approved=True, delivery_working_days=row.delivery_working_days,
        supplier_confidence=Decimal(row.supplier_confidence),
    ) for row in rows]
    eligible = eligible_offers(
        offers, body.fulfilment_mode, body.condition_policy, body.nonnew_consent,
        priority_capacity=capacity is not None,
    )
    part_keys = [row.part_key for row in rows]
    required_keys = body.required_part_keys
    if (
        len(set(required_keys)) != len(required_keys)
        or len(set(part_keys)) != len(part_keys)
        or set(part_keys) != set(required_keys)
        or len(eligible) != len(rows)
    ):
        return await _save_quote_snapshot(
            db, body, admin, rows, None,
            {"offerable": False, "reason": "Supplier evidence is stale, incomplete, mismatched, or ineligible for this fulfilment mode"},
            capacity,
        )

    costs_input = CostStack(**body.costs.model_dump())
    costs = CostStack(**{
        **costs_input.__dict__,
        "landed_parts": sum((offer.landed_gbp + offer.risk_gbp for offer in eligible), Decimal("0")),
    })
    market = MarketEvidence(**body.market.model_dump())
    decision = evaluate_price(
        costs, market, body.condition, body.minimum_contribution_gbp,
        body.minimum_margin_fraction, premium_gbp=body.premium_gbp,
    )
    result_json = {
        "offerable": decision.offerable,
        "price_gbp": str(decision.price_gbp) if decision.price_gbp is not None else None,
        "required_base_gbp": str(decision.required_base_gbp),
        "true_cost_gbp": str(costs.true_cost),
        "reason": decision.reason,
    }
    return await _save_quote_snapshot(db, body, admin, rows, costs, result_json, capacity)


async def _save_quote_snapshot(db, body, admin, rows, costs, decision, capacity=None) -> dict:
    evidence = {
        "request": body.model_dump(mode="json"),
        "supplier_offers": [{
            "id": row.id, "part_key": row.part_key, "supplier": row.supplier, "channel": row.channel,
            "condition": row.condition, "item_gbp": str(row.item_gbp), "delivery_gbp": str(row.delivery_gbp),
            "fees_gbp": str(row.fees_gbp), "risk_gbp": str(row.risk_gbp), "observed_at": row.observed_at.isoformat(),
            "stock_confirmed": row.stock_confirmed, "evidence_source": row.evidence_source, "evidence_ref": row.evidence_ref,
        } for row in rows],
        "workshop_capacity": ({
            "id": capacity.id,
            "build_week": capacity.build_week,
            "available_builds": capacity.available_builds,
            "observed_at": capacity.observed_at.isoformat(),
            "evidence_source": capacity.evidence_source,
            "evidence_ref": capacity.evidence_ref,
        } if capacity else None),
        "calculated_costs": {key: str(value) for key, value in costs.__dict__.items()} if costs else None,
    }
    status = "offerable" if decision["offerable"] else "not_offerable"
    snapshot = PriceQuoteSnapshot(
        product_key=body.product_key, status=status, evidence_json=evidence,
        decision_json=decision, created_by_admin_id=admin.id,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return {"status": status, "quote_snapshot_id": snapshot.id, **decision}


class WorkshopCapacityEvidenceInput(BaseModel):
    build_week: str = Field(pattern=r"^\d{4}-W\d{2}$")
    available_builds: int = Field(ge=0)
    observed_at: datetime
    evidence_source: str = Field(min_length=1, max_length=160)
    evidence_ref: str = Field(min_length=1, max_length=500)


def _parse_iso_week(value: str) -> tuple[int, int]:
    year, week = value.split("-W", maxsplit=1)
    parsed = date.fromisocalendar(int(year), int(week), 1)
    iso = parsed.isocalendar()
    return iso.year, iso.week


@router.post("/workshop-capacity-evidence", status_code=201)
async def capture_workshop_capacity(
    body: WorkshopCapacityEvidenceInput,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    if body.observed_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="observed_at must include a timezone")
    if body.observed_at > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="observed_at cannot be in the future")
    try:
        _parse_iso_week(body.build_week)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail="build_week must be a valid ISO week") from exc
    row = WorkshopCapacityEvidence(
        **body.model_dump(), captured_by_admin_id=admin.id,
    )
    await lock_build_week(db, body.build_week)
    db.add(row)
    await db.flush()
    now = datetime.now(timezone.utc)
    active_result = await db.execute(
        select(WorkshopCapacityReservation)
        .where(
            WorkshopCapacityReservation.build_week == body.build_week,
            WorkshopCapacityReservation.status == "held",
            WorkshopCapacityReservation.expires_at > now,
        )
        .order_by(WorkshopCapacityReservation.created_at.desc(), WorkshopCapacityReservation.id.desc())
        .with_for_update()
    )
    active = list(active_result.scalars().all())
    for reservation in active[:max(0, len(active) - body.available_builds)]:
        reservation.status = "released"
        reservation.released_at = now
        db.add(WorkshopCapacityReservationEvent(
            reservation_id=reservation.id, event_type="released",
            reason=f"Capacity reduced by evidence {row.id}", admin_id=admin.id, created_at=now,
        ))
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id, "build_week": row.build_week, "available_builds": row.available_builds,
        "status": "captured", "captured_at": row.captured_at.isoformat(),
    }


@router.get("/workshop-capacity-evidence")
async def list_workshop_capacity_evidence(
    build_week: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(WorkshopCapacityEvidence)
    if build_week is not None:
        try:
            _parse_iso_week(build_week)
        except (ValueError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail="build_week must be a valid ISO week") from exc
        query = query.where(WorkshopCapacityEvidence.build_week == build_week)
    result = await db.execute(query.order_by(WorkshopCapacityEvidence.captured_at.desc()).limit(limit))
    return {"items": [{
        "id": row.id, "build_week": row.build_week, "available_builds": row.available_builds,
        "observed_at": row.observed_at.isoformat(), "evidence_source": row.evidence_source,
        "evidence_ref": row.evidence_ref, "captured_at": row.captured_at.isoformat(),
    } for row in result.scalars().all()]}


@router.get("/quote-snapshots/{snapshot_id}")
async def get_quote_snapshot(snapshot_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    snapshot = await db.get(PriceQuoteSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Quote snapshot not found")
    return {
        "id": snapshot.id, "product_key": snapshot.product_key, "status": snapshot.status,
        "evidence": snapshot.evidence_json, "decision": snapshot.decision_json,
        "created_at": snapshot.created_at.isoformat(),
    }


def _timestamp_recent(value: str | None, now: datetime, maximum_age: timedelta) -> bool:
    if not value:
        return False
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is None:
        return False
    return timedelta(0) <= now - observed <= maximum_age


class ReserveCapacityRequest(BaseModel):
    quote_snapshot_id: int = Field(gt=0)


@router.post("/capacity-reservations", status_code=201)
async def reserve_workshop_capacity(
    body: ReserveCapacityRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    quote_snapshot_id = body.quote_snapshot_id
    snapshot = await db.get(PriceQuoteSnapshot, quote_snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Quote snapshot not found")
    capacity_ref = (snapshot.evidence_json or {}).get("workshop_capacity")
    if snapshot.status != "offerable" or not capacity_ref:
        raise HTTPException(status_code=409, detail="A passing made-to-order assessment is required")
    build_week = capacity_ref.get("build_week")
    try:
        _parse_iso_week(build_week)
    except (TypeError, AttributeError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=409, detail="Quote snapshot has invalid capacity evidence") from exc
    await lock_build_week(db, build_week)
    now = datetime.now(timezone.utc)

    existing_result = await db.execute(
        select(WorkshopCapacityReservation).where(
            WorkshopCapacityReservation.quote_snapshot_id == quote_snapshot_id
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if existing.status == "held" and existing.expires_at > now:
            return {"id": existing.id, "status": "held", "build_week": build_week, "expires_at": existing.expires_at.isoformat()}
        raise HTTPException(status_code=409, detail="This assessment's hold has ended; create a new assessment")

    if not _timestamp_recent(snapshot.created_at.isoformat(), now, timedelta(minutes=15)):
        raise HTTPException(status_code=409, detail="Quote assessment has expired")
    request_evidence = snapshot.evidence_json.get("request") or {}
    market_time = (request_evidence.get("market") or {}).get("observed_at")
    if not _timestamp_recent(market_time, now, timedelta(days=30)):
        raise HTTPException(status_code=409, detail="Sold-market evidence has expired")
    if any(
        not offer.get("stock_confirmed")
        or not _timestamp_recent(offer.get("observed_at"), now, timedelta(hours=24))
        for offer in snapshot.evidence_json.get("supplier_offers") or []
    ):
        raise HTTPException(status_code=409, detail="Supplier evidence has expired")

    capacity = await latest_capacity_evidence(db, build_week)
    if (
        capacity is None or capacity.id != capacity_ref.get("id")
        or not capacity_evidence_is_current(capacity, now)
        or await active_hold_count(db, build_week, now) >= capacity.available_builds
    ):
        raise HTTPException(status_code=409, detail="Workshop capacity is no longer available")

    reservation = WorkshopCapacityReservation(
        quote_snapshot_id=quote_snapshot_id, capacity_evidence_id=capacity.id,
        build_week=build_week, status="held", expires_at=now + timedelta(minutes=15),
        created_by_admin_id=admin.id, created_at=now,
    )
    db.add(reservation)
    await db.flush()
    db.add(WorkshopCapacityReservationEvent(
        reservation_id=reservation.id, event_type="held", admin_id=admin.id, created_at=now,
    ))
    await db.commit()
    return {
        "id": reservation.id, "status": "held", "build_week": build_week,
        "expires_at": reservation.expires_at.isoformat(),
    }


class ReleaseCapacityRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


@router.post("/capacity-reservations/{reservation_id}/release")
async def release_workshop_capacity(
    reservation_id: int,
    body: ReleaseCapacityRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    reservation = await db.get(WorkshopCapacityReservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Capacity reservation not found")
    await lock_build_week(db, reservation.build_week)
    await db.refresh(reservation)
    if reservation.status == "released":
        return {"id": reservation.id, "status": "released"}
    now = datetime.now(timezone.utc)
    reservation.status = "released"
    reservation.released_at = now
    db.add(WorkshopCapacityReservationEvent(
        reservation_id=reservation.id, event_type="released", reason=body.reason,
        admin_id=admin.id, created_at=now,
    ))
    await db.commit()
    return {"id": reservation.id, "status": "released"}


@router.get("/capacity-reservations/{reservation_id}")
async def get_workshop_capacity_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    reservation = await db.get(WorkshopCapacityReservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Capacity reservation not found")
    events = await db.execute(
        select(WorkshopCapacityReservationEvent)
        .where(WorkshopCapacityReservationEvent.reservation_id == reservation_id)
        .order_by(WorkshopCapacityReservationEvent.id)
    )
    return {
        "id": reservation.id, "quote_snapshot_id": reservation.quote_snapshot_id,
        "capacity_evidence_id": reservation.capacity_evidence_id, "build_week": reservation.build_week,
        "status": "expired" if reservation.status == "held" and reservation.expires_at <= datetime.now(timezone.utc) else reservation.status,
        "expires_at": reservation.expires_at.isoformat(),
        "events": [{
            "event_type": event.event_type, "reason": event.reason,
            "admin_id": event.admin_id, "created_at": event.created_at.isoformat(),
        } for event in events.scalars().all()],
    }


@router.post("/price-assessment")
def price_assessment(body: PriceAssessmentRequest) -> dict:
    costs = CostStack(**body.costs.model_dump())
    market = MarketEvidence(**body.market.model_dump())
    decision = evaluate_price(
        costs, market, body.condition, body.minimum_contribution_gbp,
        body.minimum_margin_fraction, premium_gbp=body.premium_gbp,
    )
    return {
        "offerable": decision.offerable,
        "price_gbp": decision.price_gbp,
        "required_base_gbp": decision.required_base_gbp,
        "true_cost_gbp": costs.true_cost,
        "reason": decision.reason,
        "status": "assessment_only",
    }


class GemCostsInput(BaseModel):
    asking_price: Decimal = Field(ge=0)
    inbound_delivery: Decimal = Field(ge=0)
    buyer_protection: Decimal = Field(ge=0)
    repairs_and_upgrades: Decimal = Field(ge=0)
    build_labour: Decimal = Field(ge=0)
    outbound_delivery: Decimal = Field(ge=0)
    marketplace_fees: Decimal = Field(ge=0)
    warranty_and_returns_reserve: Decimal = Field(ge=0)
    risk_reserve: Decimal = Field(ge=0)


class GemAssessmentRequest(BaseModel):
    costs: GemCostsInput
    conservative_resale_gbp: Decimal = Field(ge=0)
    minimum_net_contribution_gbp: Decimal = Field(ge=0)
    estimated_days_to_sell: int | None = Field(default=None, gt=0)
    remaining_speculative_budget_gbp: Decimal = Field(ge=0)
    sold_sample_size: int = Field(ge=0)


@router.post("/gem-assessment")
def gem_assessment(body: GemAssessmentRequest) -> dict:
    return assess_gem(
        GemCosts(**body.costs.model_dump()), body.conservative_resale_gbp,
        body.minimum_net_contribution_gbp, body.estimated_days_to_sell,
        body.remaining_speculative_budget_gbp, sold_sample_size=body.sold_sample_size,
    )


class ProcurementAssessmentRequest(BaseModel):
    hard_minimums: dict
    candidates: list[ApprovedPart]
    mode: FulfilmentMode
    condition_policy: ConditionPolicy
    nonnew_consent: bool = False
    priority_capacity: bool = False
    parts_cost_ceiling_gbp: Decimal | None = Field(default=None, ge=0)


@router.post("/procurement-assessment")
def procurement_assessment(body: ProcurementAssessmentRequest) -> dict:
    plan = optimise_bom(
        body.hard_minimums, body.candidates, body.mode, body.condition_policy,
        body.nonnew_consent, priority_capacity=body.priority_capacity,
        parts_cost_ceiling_gbp=body.parts_cost_ceiling_gbp,
    )
    return {"status": "assessment_only", "plan": plan}
