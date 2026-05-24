import hashlib
import json

import structlog
from fastapi import APIRouter, Request, Response

from app.config import get_settings

router = APIRouter(prefix="/ebay", tags=["ebay-compliance"])
log = structlog.get_logger(__name__)


@router.get("/marketplace-account-deletion")
async def marketplace_account_deletion_challenge(request: Request):
    """
    eBay challenge endpoint for marketplace account deletion notifications.

    eBay sends:
      GET <callback_url>?challenge_code=<value>

    We must return JSON:
      {"challengeResponse": "<sha256hex>"}

    Hash input order (exact): challengeCode + verificationToken + endpoint
    """
    settings = get_settings()
    challenge_code = (request.query_params.get("challenge_code") or "").strip()

    if not challenge_code:
        return Response(status_code=400, content="missing challenge_code")

    verification_token = (settings.ebay_verification_token or "").strip()
    if not verification_token:
        log.error("ebay.compliance.missing_verification_token")
        return Response(status_code=500, content="missing verification token")

    configured_endpoint = (settings.ebay_notification_endpoint or "").strip()
    endpoint = configured_endpoint or str(request.url).split("?")[0]

    digest = hashlib.sha256((challenge_code + verification_token + endpoint).encode("utf-8")).hexdigest()

    log.info(
        "ebay.compliance.challenge_ok",
        endpoint=endpoint,
        has_configured_endpoint=bool(configured_endpoint),
    )
    return {"challengeResponse": digest}


@router.post("/marketplace-account-deletion")
async def marketplace_account_deletion_notification(request: Request):
    """
    eBay marketplace account deletion notification receiver.

    Requirement: acknowledge quickly with 2xx, then process asynchronously.
    """
    try:
        payload = await request.json()
    except Exception:
        raw = await request.body()
        payload = {"raw": raw.decode("utf-8", errors="ignore")}

    sig = request.headers.get("x-ebay-signature") or request.headers.get("X-EBAY-SIGNATURE")

    # TODO: verify signature with eBay Notification API public keys (recommended by eBay).
    # For now we ack immediately and log payload for traceability.
    try:
        log.info(
            "ebay.compliance.notification_received",
            has_signature=bool(sig),
            payload=payload,
        )
    except Exception:
        log.info(
            "ebay.compliance.notification_received_unserializable",
            has_signature=bool(sig),
            payload_text=json.dumps(str(payload)),
        )

    return Response(status_code=204)
