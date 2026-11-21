"""Pricing worker: persist daily evidence snapshots and route material median changes."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database import AsyncSessionLocal
from app.models.agent_handoff_event import AgentHandoffEvent
from app.models.component_price_range_snapshot import ComponentPriceRangeSnapshot
from app.schemas.autonomous_agents import AgentEvent
from app.services.agent_skill_loader import load_agent_skill
from app.services.autonomous_agent_handoffs import mark_agent_event, persist_agent_event, process_playbook_event
from app.services.market_pricing_agent import load_component_price_cohorts, price_change_signal


async def run_pricing_agent_cycle() -> dict:
    skill = load_agent_skill("pricing")
    if not skill.strip():
        raise RuntimeError("Pricing agent skill is missing")
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        cohorts = await load_component_price_cohorts(db, now=now)
        snapshot_date = now.date()
        for evidence in cohorts.values():
            values = {
                "cpk": evidence.identity,
                "condition": evidence.condition,
                "market_kind": evidence.market_kind,
                "geography": evidence.geography,
                "currency": evidence.currency,
                "lower_gbp": float(evidence.lower_gbp) if evidence.lower_gbp is not None else None,
                "median_gbp": float(evidence.median_gbp) if evidence.median_gbp is not None else None,
                "upper_gbp": float(evidence.upper_gbp) if evidence.upper_gbp is not None else None,
                "raw_sample_count": evidence.raw_sample_count,
                "accepted_sample_count": evidence.accepted_sample_count,
                "excluded_outlier_count": evidence.excluded_outlier_count,
                "sources": list(evidence.sources), "references": list(evidence.references),
                "confidence": evidence.confidence, "status": evidence.status,
                "observed_from": evidence.observed_from.replace(tzinfo=None) if evidence.observed_from else None,
                "observed_to": evidence.observed_to.replace(tzinfo=None) if evidence.observed_to else None,
                "snapshot_date": snapshot_date, "captured_at": now.replace(tzinfo=None),
            }
            statement = insert(ComponentPriceRangeSnapshot).values(**values)
            statement = statement.on_conflict_do_update(
                constraint="uq_component_price_range_snapshot_key",
                set_={key: value for key, value in values.items() if key not in {
                    "cpk", "condition", "market_kind", "geography", "snapshot_date",
                }},
            )
            await db.execute(statement)
        prior_row = (await db.execute(select(AgentHandoffEvent).where(
            AgentHandoffEvent.event_type == "pricing_snapshot_completed",
            AgentHandoffEvent.processing_status == "completed",
        ).order_by(AgentHandoffEvent.occurred_at.desc()).limit(1))).scalars().first()
        prior = prior_row.payload.get("cohorts", {}) if prior_row and isinstance(prior_row.payload, dict) else {}
        serialised = {}
        changes: list[AgentEvent] = []
        for key, evidence in cohorts.items():
            key_text = "|".join(key)
            row = {
                "identity": evidence.identity, "condition": evidence.condition,
                "market_kind": evidence.market_kind, "geography": evidence.geography,
                "lower_gbp": str(evidence.lower_gbp) if evidence.lower_gbp is not None else None,
                "median_gbp": str(evidence.median_gbp) if evidence.median_gbp is not None else None,
                "upper_gbp": str(evidence.upper_gbp) if evidence.upper_gbp is not None else None,
                "observed_to": evidence.observed_to.isoformat() if evidence.observed_to else None,
                "sample_count": evidence.accepted_sample_count,
                "status": evidence.status, "sources": list(evidence.sources),
                "references": list(evidence.references),
            }
            serialised[key_text] = row
            old = prior.get(key_text) if isinstance(prior, dict) else None
            if not old or not old.get("median_gbp") or not row["median_gbp"]:
                continue
            # Only compare a previous daily snapshot with a new observation day.
            if old.get("observed_to") == row["observed_to"]:
                continue
            from app.services.market_pricing_agent import PriceRangeEvidence
            previous_evidence = PriceRangeEvidence(
                identity=evidence.identity, condition=evidence.condition, market_kind=evidence.market_kind,
                geography=evidence.geography, currency="GBP", lower_gbp=None,
                median_gbp=Decimal(old["median_gbp"]), upper_gbp=None,
                observed_from=None, observed_to=datetime.fromisoformat(old["observed_to"]) if old.get("observed_to") else None,
                raw_sample_count=int(old.get("sample_count", 0)), accepted_sample_count=int(old.get("sample_count", 0)),
                excluded_outlier_count=0, sources=tuple(old.get("sources", [])), references=tuple(old.get("references", [])),
                confidence="medium", status="usable",
            )
            signal = price_change_signal(identity=evidence.identity, condition=evidence.condition,
                                         geography=evidence.geography, previous=previous_evidence, current=evidence)
            if signal:
                event = AgentEvent(
                    event_id=str(uuid5(NAMESPACE_URL, signal["idempotency_key"])),
                    event_type="component_market_price_changed", producer="pricing", occurred_at=now,
                    idempotency_key=signal["idempotency_key"], correlation_id=signal["idempotency_key"],
                    evidence_refs=list(evidence.references),
                    payload={k: v for k, v in signal.items() if k not in {"event_type", "idempotency_key"}},
                )
                await persist_agent_event(db, event)
                changes.append(event)

        snapshot_key = f"pricing-snapshot:{now.strftime('%Y-%m-%d')}"
        snapshot = AgentEvent(
            event_id=str(uuid5(NAMESPACE_URL, snapshot_key)), event_type="pricing_snapshot_completed",
            producer="pricing", occurred_at=now, idempotency_key=snapshot_key,
            correlation_id=snapshot_key, payload={"cohorts": serialised, "skill_loaded": True,
                                                   "range_persistence": "component_price_range_snapshots",
                                                   "complete_build_valuation": "not_available_without_comparable_full_build_evidence"},
        )
        await persist_agent_event(db, snapshot)
        snapshot_row = await db.get(AgentHandoffEvent, snapshot.event_id)
        if snapshot_row:
            snapshot_row.processing_status = "completed"
            snapshot_row.processed_at = now.replace(tzinfo=None)
        await db.commit()

    for event in changes:
        try:
            await process_playbook_event(event)
        except Exception as exc:
            async with AsyncSessionLocal() as db:
                await mark_agent_event(db, event.event_id, status="failed", error=f"{type(exc).__name__}: {exc}")
                await db.commit()
            raise
    return {"ok": True, "cohorts": len(cohorts), "material_changes": len(changes),
            "handoff_event_ids": [event.event_id for event in changes],
            "limitations": ["The legacy GemRadarCpkMarketPrice remains a distinct mixed-market aggregate.",
                            "PCPartPicker UK and comparable full-PC market valuation are not wired to an authorized source."]}
