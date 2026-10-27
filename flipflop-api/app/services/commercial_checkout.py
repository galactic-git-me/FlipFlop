"""Customer-safe commercial quotes and immutable acceptance before Stripe."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.models.commerce_evidence import (
    PriceQuoteSnapshot, WorkshopCapacityEvidence, WorkshopCapacityReservation,
    WorkshopCapacityReservationEvent,
)
from app.models.playbook import Playbook
from app.models.order_checkout_snapshot import OrderCheckoutSnapshot
from app.schemas.commercial_quote import CellCommercialPolicy
from app.services.commercial_quote_evidence import assess_stored_cell, definition_hash
from app.services.curated_build_policy import definitions
from app.services.workshop_capacity import latest_capacity_evidence, lock_build_week, capacity_evidence_is_current


def configuration_hash(config) -> str:
    data = config.model_dump(mode="json", exclude={"chosen_week"})
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_configuration(policy, config):
    expected = {slot: variant for slot, (variant, _) in policy.checkout_slot_parts.items()}
    if (config.slot_selections != expected or not policy.checkout_case or config.case_id != policy.checkout_case[0]
            or config.upgrade_candidate_indexes):
        raise HTTPException(409, "Customer delivery pricing needs a reviewed quote for this exact component and case selection")


async def load_checkout_policy(db, config, *, allow_pending=False):
    playbook = (await db.execute(select(Playbook).where(
        Playbook.id == config.playbook_id, Playbook.status == "active",
    ).with_for_update())).scalar_one_or_none()
    if playbook is None:
        raise HTTPException(404, "Active Playbook not found")
    from app.services.commercial_configuration import configuration_definition, validate_configuration_policy
    exact = await configuration_definition(db, config)
    exact_raw = ((playbook.pricing_model or {}).get("commercial_configurations") or {}).get(definition_hash(exact))
    if exact_raw is not None:
        try:
            policy = CellCommercialPolicy.model_validate(exact_raw)
        except ValidationError as exc:
            raise HTTPException(409, "This configuration's pricing policy needs review") from exc
        validate_configuration_policy(policy, exact)
        if not policy.checkout_enabled:
            raise HTTPException(409, "This configuration's customer delivery pricing policy is awaiting review")
        return playbook, exact, policy
    if not config.curated_build_id:
        if allow_pending:
            return None
        raise HTTPException(409, "Review this configuration's customer delivery pricing before payment")
    raw = ((playbook.pricing_model or {}).get("commercial_cells") or {}).get(config.curated_build_id)
    if raw is None:
        if allow_pending:
            return None
        raise HTTPException(409, "Review this configuration's customer delivery pricing before payment")
    try:
        policy = CellCommercialPolicy.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(409, "This build's pricing policy needs review") from exc
    try:
        validate_configuration(policy, config)
    except HTTPException:
        if allow_pending:
            return None
        raise
    # A configured policy owns its commercial path; it must never silently fall
    # back to a legacy price after an operator disables it.
    if not policy.checkout_enabled:
        raise HTTPException(409, "This build's customer delivery pricing policy is awaiting review")
    definition = next((item for item in definitions()["builds"] if item["id"] == config.curated_build_id), None)
    if (definition is None or definition["segment"] != playbook.name
            or definition_hash(definition) != policy.definition_sha256):
        raise HTTPException(409, "The build changed; its pricing policy needs review")
    return playbook, definition, policy


async def current_capacity_ids(db):
    """Return optional schedule hints without treating them as sales capacity."""
    now = datetime.now(timezone.utc)
    rows = (await db.execute(select(WorkshopCapacityEvidence).where(
        WorkshopCapacityEvidence.observed_at >= now - timedelta(hours=24),
    ).order_by(WorkshopCapacityEvidence.build_week, WorkshopCapacityEvidence.id.desc()))).scalars().all()
    seen = set()
    for row in rows:
        if row.build_week in seen:
            continue
        seen.add(row.build_week)
        if capacity_evidence_is_current(row, now):
            return {name: row.id for name in ("fast_track", "standard", "flexible")}
    return {}


async def assess_checkout(db, loaded, config):
    from app.services.strict_configuration_fit import require_configuration_fit

    await require_configuration_fit(db, config)
    playbook, definition, policy = loaded
    capacity_ids = await current_capacity_ids(db)
    # Shared adapter records this exact server-owned request with its evidence.
    body = SimpleNamespace(curated_build_id=config.curated_build_id,
                           capacity_evidence_ids=capacity_ids, nonnew_consent=False,
                           model_dump=lambda **_: {"playbook_id": config.playbook_id,
                               "curated_build_id": config.curated_build_id,
                               "capacity_evidence_ids": capacity_ids, "nonnew_consent": False})
    return await assess_stored_cell(db, playbook, definition, policy, body)


def customer_modes(result):
    fields = ("offerable", "price_gbp", "difference_from_standard_gbp",
              "delivery_working_days", "delivery_promised", "expires_at", "reason")
    return {name: {key: quote.get(key) for key in fields} for name, quote in result["modes"].items()}


async def create_checkout_quote(db, config):
    loaded = await load_checkout_policy(db, config, allow_pending=True)
    if loaded is None:
        from app.services.commercial_configuration import configuration_definition
        definition = await configuration_definition(db, config)
        key = f"playbook:{config.playbook_id}:configuration:{definition_hash(definition)}"
        pending = (await db.execute(select(PriceQuoteSnapshot).where(
            PriceQuoteSnapshot.product_key == key,
            PriceQuoteSnapshot.status == "configuration_review",
        ).limit(1))).scalar_one_or_none()
        if pending is None:
            pending = PriceQuoteSnapshot(product_key=key, status="configuration_review",
                created_by_admin_id=0, evidence_json={"build_config": config.model_dump(mode="json"),
                    "definition": definition}, decision_json={"purchasable": False})
            db.add(pending)
            await db.flush()
        return {"pricing_mode": "commercial", "quote_snapshot_id": None,
                "review_required": True, "modes": {name: {"offerable": False,
                    "price_gbp": None, "difference_from_standard_gbp": None,
                    "delivery_working_days": None, "expires_at": None,
                    "reason": "This exact configuration is awaiting commercial review"}
                    for name in ("fast_track", "standard", "flexible")}}
    result, evidence = await assess_checkout(db, loaded, config)
    evidence["configuration_sha256"] = configuration_hash(config)
    snapshot = PriceQuoteSnapshot(
        product_key=f"playbook:{config.playbook_id}:cell:{config.curated_build_id}",
        status="checkout_quote", created_by_admin_id=0,
        evidence_json=evidence, decision_json=result,
    )
    db.add(snapshot)
    await db.flush()
    return {"pricing_mode": "commercial", "quote_snapshot_id": snapshot.id,
            "policy_version": result["policy_version"], "modes": customer_modes(result)}


async def accept_checkout_quote(db, config, quote_id, mode, customer_id, loaded, build_snapshot):
    # Revalidate before the idempotent replay path too: a previously accepted
    # quote cannot survive a later source-fact invalidation.
    from app.services.strict_configuration_fit import require_configuration_fit

    await require_configuration_fit(db, config)
    if not quote_id:
        raise HTTPException(409, "Refresh the customer delivery quote before continuing to payment")
    snapshot = (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.id == quote_id,
    ).with_for_update())).scalar_one_or_none()
    if (snapshot is None or snapshot.status != "checkout_quote"
            or snapshot.evidence_json.get("configuration_sha256") != configuration_hash(config)):
        raise HTTPException(409, "This delivery quote does not match the selected build")
    accepted_key = f"accepted:{quote_id}:{customer_id}:{mode}"
    existing = (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.product_key == accepted_key,
        PriceQuoteSnapshot.status == "checkout_accepted",
    ))).scalar_one_or_none()
    if existing:
        if datetime.fromisoformat(existing.decision_json["accepted_at"]) + timedelta(minutes=15) <= datetime.now(timezone.utc):
            raise HTTPException(409, "The accepted checkout expired; refresh the customer delivery quote")
        return existing
    quoted = snapshot.decision_json.get("modes", {}).get(mode)
    now = datetime.now(timezone.utc)
    if (not quoted or not quoted.get("offerable") or not quoted.get("expires_at")
            or datetime.fromisoformat(quoted["expires_at"]) <= now):
        raise HTTPException(409, "This delivery price expired or is unavailable; refresh your options")
    current, evidence = await assess_checkout(db, loaded, config)
    choice = current["modes"][mode]
    # Changed price, timing, policy or supplier selection requires new consent.
    keys = ("price_gbp", "delivery_working_days", "supplier_offer_ids", "capacity_evidence_id")
    if (not choice["offerable"] or current["policy_sha256"] != snapshot.decision_json.get("policy_sha256")
            or any(choice.get(key) != quoted.get(key) for key in keys)):
        raise HTTPException(409, "Availability or pricing changed; review refreshed delivery options")
    capacity_id = choice.get("capacity_evidence_id")
    capacity = await db.get(WorkshopCapacityEvidence, capacity_id) if capacity_id is not None else None
    if capacity_id is not None:
        if capacity is None:
            raise HTTPException(409, "Workshop schedule evidence changed; refresh delivery options")
        await lock_build_week(db, capacity.build_week)
        latest = await latest_capacity_evidence(db, capacity.build_week)
        if latest is None or latest.id != capacity.id or not capacity_evidence_is_current(capacity, now):
            raise HTTPException(409, "Workshop schedule estimate changed; refresh delivery options")
    accepted = PriceQuoteSnapshot(
        product_key=accepted_key, status="checkout_accepted", created_by_admin_id=0,
        evidence_json={**evidence, "source_quote_id": quote_id,
                       "configuration_sha256": configuration_hash(config), "customer_id": customer_id,
                       "build_config": config.model_dump(mode="json"), "build_snapshot": build_snapshot},
        decision_json={"mode": mode, "quote": choice, "accepted_at": now.isoformat(),
                       "policy_version": current["policy_version"], "policy_sha256": current["policy_sha256"]},
    )
    db.add(accepted)
    await db.flush()
    if capacity is not None:
        hold = WorkshopCapacityReservation(
            quote_snapshot_id=accepted.id, capacity_evidence_id=capacity.id, build_week=capacity.build_week,
            status="held", expires_at=now + timedelta(minutes=15), created_by_admin_id=0,
        )
        db.add(hold)
        await db.flush()
        db.add(WorkshopCapacityReservationEvent(reservation_id=hold.id, event_type="held",
            reason="Customer commercial quote accepted before payment; planning only, no sales cap", admin_id=0))
    return accepted


def accepted_summary(accepted):
    decision = accepted.decision_json
    return {"quote_snapshot_id": accepted.id, "source_quote_id": accepted.evidence_json["source_quote_id"],
            "policy_version": decision["policy_version"], "delivery_option": decision["mode"],
            "price_gbp": decision["quote"]["price_gbp"], "accepted_at": decision["accepted_at"]}


def accepted_delivery(accepted):
    quote = accepted.decision_json["quote"]
    mode = accepted.decision_json["mode"]
    difference = Decimal(quote.get("difference_from_standard_gbp") or "0")
    build_config = accepted.evidence_json["build_config"]
    return {"fulfilment_type": "curated" if build_config.get("curated_build_id") else "custom", "speedy_delivery": mode == "fast_track",
            "delivery_option": mode, "fee_gbp": max(Decimal(0), difference) if mode == "fast_track" else Decimal(0),
            "delivery_days": None if mode == 'flexible' else quote["delivery_working_days"], "same_day_dispatch": False,
            "promise": ("Flexible pace — no promised delivery date." if mode=='flexible'
                else f"Estimated delivery within {quote['delivery_working_days']} working days."),
            "delivery_estimate_source": "playbook_commercial_quote"}


async def commercial_order_snapshot(db, metadata, customer_id, paid_amount):
    """Both confirmation paths recover the exact accepted commercial contract."""
    value = str(metadata.get("commercial_quote_snapshot_id") or "")
    if not value:
        return None
    if not value.isdigit():
        raise ValueError("Invalid accepted commercial quote reference")
    accepted = await db.get(PriceQuoteSnapshot, int(value))
    if (accepted is None or accepted.status != "checkout_accepted"
            or accepted.evidence_json.get("customer_id") != customer_id
            or Decimal(accepted.decision_json["quote"]["price_gbp"]) != Decimal(str(paid_amount))):
        raise ValueError("Paid amount or customer does not match the accepted commercial quote")
    from app.services.storefront_delivery import checkout_metadata
    result = dict(accepted.evidence_json["build_snapshot"])
    result.update(checkout_metadata(accepted_delivery(accepted)))
    result["commercial_quote"] = accepted_summary(accepted)
    result["parts_total"] = float(accepted.decision_json["quote"]["fixed_costs_gbp"]["landed_parts_including_risk"])
    result["labour"] = float(accepted.decision_json["quote"]["fixed_costs_gbp"]["build_labour"])
    result["overhead"] = float(accepted.decision_json["quote"]["fixed_costs_gbp"]["allocated_overhead"])
    return result


def commercial_promised_date(snapshot):
    if not snapshot or snapshot.get('delivery_option') == 'flexible' or snapshot.get('delivery_days') is None:
        return None
    from zoneinfo import ZoneInfo
    from app.services.storefront_delivery import add_working_days
    start = datetime.fromisoformat(snapshot["commercial_quote"]["accepted_at"]).astimezone(ZoneInfo("Europe/London")).replace(tzinfo=None)
    return add_working_days(start, int(snapshot["delivery_days"]))


async def checkout_snapshot_for_payment(db, intent_id, customer_id, metadata):
    keys = [intent_id]
    accepted_id = str(metadata.get("commercial_quote_snapshot_id") or "")
    if accepted_id.isdigit():
        keys.append(f"commercial:{accepted_id}")
    return (await db.execute(select(OrderCheckoutSnapshot).where(
        OrderCheckoutSnapshot.payment_intent_id.in_(keys),
        OrderCheckoutSnapshot.customer_id == customer_id,
    ).with_for_update())).scalar_one_or_none()
