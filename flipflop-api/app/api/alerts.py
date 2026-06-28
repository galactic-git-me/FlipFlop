from fastapi import APIRouter, Depends, Query
from app.api.deps import require_operator
from app.services.alerts import list_alerts, ack_alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def get_alerts(
    limit: int = Query(100, ge=1, le=1000),
    include_acked: bool = Query(False),
):
    return await list_alerts(limit=limit, include_acked=include_acked)


@router.post("/{alert_id}/ack", dependencies=[Depends(require_operator)])
async def acknowledge_alert(alert_id: int):
    return await ack_alert(alert_id)
