"""Shared stored-evidence adapter for admin review and customer quote validation."""
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit
from sqlalchemy import select
from app.models.commerce_evidence import SupplierOfferEvidence, WorkshopCapacityEvidence
from app.services.commerce_pricing import Condition, SupplierOffer
from app.services.playbook_commercial_quote import CapacityEvidence, PartEvidence, quote_delivery_modes
from app.services.workshop_capacity import active_hold_count, capacity_evidence_is_current, latest_capacity_evidence

def definition_hash(definition: dict) -> str:
    return hashlib.sha256(json.dumps(definition, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def supplier_identity(supplier, reference):
    try:
        host = (urlsplit(reference or "").hostname or "").casefold()
    except ValueError:
        host = ""
    for domain, name in (("amazon.co.uk", "amazon"), ("overclockers.co.uk", "overclockers"),
                         ("releases.ubuntu.com", "ubuntu"),
                         ("royalcdkeys.com", "royalcdkeys"),
                         ("gamers-outlet.net", "gamers_outlet"),
                         ("ebay.co.uk", "ebay"), ("ebay.com", "ebay"), ("vinted.co.uk", "vinted")):
        if host == domain or host.endswith("." + domain):
            return name
    name = (supplier or "").strip().casefold()
    return "overclockers" if name == "overclockers uk" else name


def latest_listing_observations(rows):
    """A newer unavailable listing supersedes its older in-stock observation."""
    latest = {}
    for row in rows:
        key = (row.part_key, supplier_identity(row.supplier, row.evidence_ref), row.evidence_ref)
        previous = latest.get(key)
        if previous is None or (row.observed_at, row.id) > (previous.observed_at, previous.id):
            latest[key] = row
    return list(latest.values())


def _working_days_until(start: date, target: date) -> int:
    days = max(0, (target - start).days)
    return sum((start.weekday() + offset) % 7 < 5 for offset in range(1, days + 1))


async def assess_stored_cell(db, playbook, definition, policy, body):
    rows = latest_listing_observations((await db.execute(select(SupplierOfferEvidence).where(
        SupplierOfferEvidence.part_key.in_(policy.required_part_keys),
    ))).scalars().all())
    parts = [PartEvidence(row.id, row.part_key, SupplierOffer(
        supplier=row.supplier, channel=row.channel, condition=Condition(row.condition),
        item_gbp=Decimal(row.item_gbp), delivery_gbp=Decimal(row.delivery_gbp),
        fees_gbp=Decimal(row.fees_gbp), risk_gbp=Decimal(row.risk_gbp),
        observed_at=row.observed_at.isoformat(), stock_confirmed=row.stock_confirmed,
        approved=True, delivery_working_days=row.delivery_working_days,
        supplier_confidence=Decimal(row.supplier_confidence), prime_eligible=row.prime_eligible,
    )) for row in rows]
    now = datetime.now(timezone.utc)
    capacities = {}
    capacity_snapshot = {}
    for mode, evidence_id in body.capacity_evidence_ids.items():
        capacity = await db.get(WorkshopCapacityEvidence, evidence_id)
        if capacity is None:
            continue
        latest = await latest_capacity_evidence(db, capacity.build_week)
        holds = await active_hold_count(db, capacity.build_week, now)
        current = capacity_evidence_is_current(capacity, now)
        year, week = capacity.build_week.split("-W")
        wait = _working_days_until(now.date(), date.fromisocalendar(int(year), int(week), 1))
        capacities[mode] = CapacityEvidence(
            capacity.id, capacity.observed_at.isoformat(),
            latest is not None and latest.id == capacity.id and current,
            wait,
        )
        capacity_snapshot[mode] = {
            "id": capacity.id, "observed_at": capacity.observed_at.isoformat(),
            "build_week": capacity.build_week, "planning_build_count": capacity.available_builds,
            "active_quote_holds": holds, "wait_working_days": wait,
            "sales_limit_applied": False,
            "evidence_source": capacity.evidence_source, "evidence_ref": capacity.evidence_ref,
        }
    result = quote_delivery_modes(policy, parts, capacities, nonnew_consent=body.nonnew_consent, now=now)
    result.update(playbook_id=playbook.id, curated_build_id=body.curated_build_id,
                  definition_sha256=policy.definition_sha256,
                  policy_sha256=hashlib.sha256(json.dumps(policy.model_dump(mode="json"),
                      sort_keys=True, separators=(",", ":")).encode()).hexdigest())
    evidence = {
            "contract_version": 1, "request": body.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"), "definition": definition,
            "capacities": capacity_snapshot,
            "supplier_offers": [{
                "id": row.id, "part_key": row.part_key, "supplier": row.supplier,
                "channel": row.channel, "condition": row.condition,
                "observed_at": row.observed_at.isoformat(), "stock_confirmed": row.stock_confirmed,
                "item_gbp": str(row.item_gbp), "delivery_gbp": str(row.delivery_gbp),
                "fees_gbp": str(row.fees_gbp), "risk_gbp": str(row.risk_gbp),
                "delivery_working_days": row.delivery_working_days,
                "delivery_estimate_source": row.delivery_estimate_source,
                "supplier_confidence": str(row.supplier_confidence),
                "evidence_source": row.evidence_source, "evidence_ref": row.evidence_ref,
            } for row in rows],
        }
    return result, evidence
