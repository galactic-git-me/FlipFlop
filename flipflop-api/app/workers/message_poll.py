"""
Buyer-message response-time alert — Algorithm Playbook row 47.

Polls unanswered buyer messages via the Trading API (GetMemberMessages —
the modern REST surface has no equivalent) and raises an alert for any
unanswered past the threshold. The reply itself stays manual, per the
playbook's explicit spec for this row — this only makes sure an unanswered
message doesn't sit unnoticed.

Default proposed, confirm once: alert threshold = 2 hours unanswered.

Not verifiable against live eBay from this environment (no network egress
to any eBay domain here).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import structlog

from app.config import get_settings
from app.services import ebay_trading_api
from app.services.ebay_token_manager import get_valid_ebay_access_token
from app.services.alerts import emit_alert

log = structlog.get_logger(__name__)

RESPONSE_TIME_THRESHOLD_HOURS = 2

# In-process de-dupe so the same unanswered message doesn't re-alert every poll cycle.
_ALREADY_ALERTED: set[str] = set()


def _parse_ebay_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


async def run_message_poll_job() -> dict:
    settings = get_settings()
    try:
        token = await get_valid_ebay_access_token(settings.ebay_listing_environment)
    except ValueError:
        return {"checked": 0, "flagged": 0, "note": "No eBay refresh token configured."}

    try:
        messages = await ebay_trading_api.get_member_messages(token)
    except Exception as exc:
        log.warning("message_poll.fetch_failed", error=str(exc))
        return {"checked": 0, "flagged": 0, "error": str(exc)}

    now = datetime.utcnow()
    flagged = 0
    for msg in messages:
        received = _parse_ebay_datetime(msg.get("received_at"))
        if not received:
            continue
        if now - received < timedelta(hours=RESPONSE_TIME_THRESHOLD_HOURS):
            continue

        message_id = msg.get("message_id") or ""
        if message_id in _ALREADY_ALERTED:
            continue

        try:
            await emit_alert(
                code="unanswered_buyer_message",
                source="message_poll",
                severity="warning",
                message=(
                    f"Buyer message from {msg.get('sender', 'unknown')} on item "
                    f"{msg.get('item_id', 'unknown')} has been unanswered for over "
                    f"{RESPONSE_TIME_THRESHOLD_HOURS}h: \"{msg.get('subject', '')}\""
                ),
            )
            _ALREADY_ALERTED.add(message_id)
            flagged += 1
        except Exception as exc:
            log.warning("message_poll.alert_failed", message_id=message_id, error=str(exc))

    return {"checked": len(messages), "flagged": flagged}
