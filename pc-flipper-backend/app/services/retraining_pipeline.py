from __future__ import annotations

from datetime import datetime
import json
import statistics

import structlog
from sqlalchemy import desc, select

from app.database import AsyncSessionLocal
from app.models.flip_intelligence import FlipIntelligence
from app.models.model_registry import ModelVersion, TrainingRun
from app.models.outcome_event import RetrainCheckpoint
from app.services.alerts import emit_alert

log = structlog.get_logger(__name__)


def _mk_version() -> str:
    return datetime.utcnow().strftime("v%Y%m%d%H%M%S")


async def run_retraining_if_ready(triggered_by: str = "scheduler") -> dict:
    async with AsyncSessionLocal() as db:
        ckpt_result = await db.execute(select(RetrainCheckpoint).where(RetrainCheckpoint.name == "policy"))
        ckpt = ckpt_result.scalar_one_or_none()
        ready = bool(ckpt and ckpt.ready)

        run = TrainingRun(model_name="policy", status="running", triggered_by=triggered_by, consumed_checkpoint_ready=ready)
        db.add(run)
        await db.flush()

        if not ready:
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            run.message = "Checkpoint not ready"
            await db.commit()
            return {"ok": False, "reason": "checkpoint_not_ready", "run_id": run.id}

        rows = await db.execute(select(FlipIntelligence).order_by(desc(FlipIntelligence.created_at)).limit(5000))
        samples = list(rows.scalars().all())
        run.samples = len(samples)
        if len(samples) < 30:
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            run.message = f"Insufficient samples ({len(samples)})"
            await db.commit()
            return {"ok": False, "reason": "insufficient_samples", "samples": len(samples), "run_id": run.id}

        split = max(5, int(len(samples) * 0.2))
        holdout = samples[:split]
        train = samples[split:]
        train_profit_values = [float(s.profit or 0.0) for s in train] or [0.0]
        train_roi_values = [float(s.roi_pct or 0.0) for s in train] or [0.0]
        baseline_profit = statistics.median(train_profit_values)
        baseline_roi = statistics.median(train_roi_values)

        mae_profit = sum(abs(float(s.profit or 0.0) - baseline_profit) for s in holdout) / max(1, len(holdout))
        mae_roi = sum(abs(float(s.roi_pct or 0.0) - baseline_roi) for s in holdout) / max(1, len(holdout))

        version = _mk_version()
        artifact = f"/tmp/flipflop-models/policy-{version}.json"
        model = ModelVersion(
            model_name="policy",
            version=version,
            status="trained",
            score_profit_mae=round(mae_profit, 4),
            score_roi_mae=round(mae_roi, 4),
            trained_on_samples=len(samples),
            artifact_path=artifact,
            notes=json.dumps(
                {
                    "triggered_by": triggered_by,
                    "validation": "holdout_median_baseline",
                    "holdout_size": len(holdout),
                }
            ),
        )
        db.add(model)

        run.status = "success"
        run.finished_at = datetime.utcnow()
        run.version_produced = version
        run.message = "Training complete"

        if ckpt:
            ckpt.ready = False
            ckpt.sold_flips_since = 0

        await db.commit()

    log.info("retraining.run.done", version=version, samples=len(samples))
    await emit_alert(
        code="model_ready_to_promote",
        source="retraining",
        severity="info",
        message=f"New model candidate {version} trained on {len(samples)} samples and is ready for promotion.",
    )
    return {"ok": True, "version": version, "samples": len(samples), "run_id": run.id}


async def list_model_versions(model_name: str = "policy", limit: int = 20) -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(ModelVersion)
            .where(ModelVersion.model_name == model_name)
            .order_by(ModelVersion.created_at.desc())
            .limit(limit)
        )
        models = list(rows.scalars().all())
    return [
        {
            "id": m.id,
            "model_name": m.model_name,
            "version": m.version,
            "status": m.status,
            "score_profit_mae": m.score_profit_mae,
            "score_roi_mae": m.score_roi_mae,
            "trained_on_samples": m.trained_on_samples,
            "artifact_path": m.artifact_path,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "activated_at": m.activated_at.isoformat() if m.activated_at else None,
        }
        for m in models
    ]


async def list_training_runs(limit: int = 30) -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(select(TrainingRun).order_by(TrainingRun.started_at.desc()).limit(limit))
        runs = list(rows.scalars().all())
    return [
        {
            "id": r.id,
            "model_name": r.model_name,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "samples": r.samples,
            "version_produced": r.version_produced,
            "message": r.message,
            "triggered_by": r.triggered_by,
            "consumed_checkpoint_ready": r.consumed_checkpoint_ready,
        }
        for r in runs
    ]


async def promote_model_version(version: str, model_name: str = "policy") -> dict:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(ModelVersion)
            .where(ModelVersion.model_name == model_name)
            .order_by(ModelVersion.created_at.desc())
        )
        models = list(rows.scalars().all())
        target = next((m for m in models if m.version == version), None)
        if not target:
            return {"ok": False, "reason": "version_not_found"}

        for m in models:
            if m.status == "active":
                m.status = "rolled_back"
        target.status = "active"
        target.activated_at = datetime.utcnow()
        await db.commit()

    return {"ok": True, "active_version": version}


async def rollback_to_previous_active(model_name: str = "policy") -> dict:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(ModelVersion)
            .where(ModelVersion.model_name == model_name)
            .order_by(ModelVersion.created_at.desc())
        )
        models = list(rows.scalars().all())
        current = next((m for m in models if m.status == "active"), None)
        if not current:
            return {"ok": False, "reason": "no_active_model"}

        idx = models.index(current)
        previous = next((m for m in models[idx + 1 :] if m.status in {"trained", "rolled_back", "active"}), None)
        if not previous:
            return {"ok": False, "reason": "no_previous_model"}

        current.status = "rolled_back"
        previous.status = "active"
        previous.activated_at = datetime.utcnow()
        await db.commit()

    return {"ok": True, "active_version": previous.version, "rolled_back_from": current.version}
