from __future__ import annotations

import json
from datetime import datetime

import structlog
from sqlalchemy import and_, select

from app.database import AsyncSessionLocal
from app.models.flip import Flip, FlipStage
from app.models.outcome_event import OutcomeEvent, RetrainCheckpoint

log = structlog.get_logger(__name__)

RETRAIN_THRESHOLD = 25


async def capture_outcomes_and_check_retrain() -> dict:
    async with AsyncSessionLocal() as db:
        ckpt_result = await db.execute(select(RetrainCheckpoint).where(RetrainCheckpoint.name == "policy"))
        ckpt = ckpt_result.scalar_one_or_none()
        if ckpt is None:
            ckpt = RetrainCheckpoint(name="policy", last_flip_id=0, sold_flips_since=0, ready=False)
            db.add(ckpt)
            await db.flush()

        flips_result = await db.execute(
            select(Flip).where(
                and_(
                    Flip.stage == FlipStage.sold,
                    Flip.id > ckpt.last_flip_id,
                    Flip.actual_profit.is_not(None),
                )
            ).order_by(Flip.id.asc())
        )
        new_sold = list(flips_result.scalars().all())

        if not new_sold:
            return {
                "ok": True,
                "new_sold": 0,
                "sold_flips_since": ckpt.sold_flips_since,
                "retrain_ready": ckpt.ready,
                "threshold": RETRAIN_THRESHOLD,
            }

        for f in new_sold:
            db.add(
                OutcomeEvent(
                    event_type="sold_flip",
                    ref_id=f.id,
                    value=float(f.actual_profit or 0.0),
                    meta_json=json.dumps(
                        {
                            "sale_platform": f.sale_platform,
                            "sold_at": f.sold_at.isoformat() if f.sold_at else None,
                            "actual_sale_price": f.actual_sale_price,
                            "total_cost": f.total_cost,
                        }
                    ),
                )
            )

        ckpt.last_flip_id = max(f.id for f in new_sold)
        ckpt.sold_flips_since = int(ckpt.sold_flips_since or 0) + len(new_sold)

        retrain_triggered = False
        if ckpt.sold_flips_since >= RETRAIN_THRESHOLD:
            ckpt.ready = True
            retrain_triggered = True
            db.add(
                OutcomeEvent(
                    event_type="retrain_trigger",
                    ref_id=ckpt.last_flip_id,
                    value=float(ckpt.sold_flips_since),
                    meta_json=json.dumps(
                        {
                            "threshold": RETRAIN_THRESHOLD,
                            "triggered_at": datetime.utcnow().isoformat(),
                            "checkpoint": "policy",
                        }
                    ),
                )
            )

        await db.commit()

    log.info(
        "outcome_capture.done",
        new_sold=len(new_sold),
        retrain_triggered=retrain_triggered,
    )
    return {
        "ok": True,
        "new_sold": len(new_sold),
        "sold_flips_since": ckpt.sold_flips_since,
        "retrain_ready": ckpt.ready,
        "threshold": RETRAIN_THRESHOLD,
    }
