import hashlib
import json
import base64
import time

import structlog
from fastapi import APIRouter, Request, Response
import httpx
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    _CRYPTO_OK = True
except Exception:
    hashes = None
    serialization = None
    ec = None
    _CRYPTO_OK = False

from app.config import get_settings

router = APIRouter(prefix="/ebay", tags=["ebay-compliance"])
log = structlog.get_logger(__name__)
_PUBKEY_CACHE: dict[str, tuple[str, float]] = {}
_TOKEN_CACHE: dict[str, tuple[str, float]] = {"token": ("", 0.0)}


def _ebay_api_root() -> str:
    settings = get_settings()
    env = (settings.ebay_environment or "production").strip().lower()
    return "https://api.sandbox.ebay.com" if env == "sandbox" else "https://api.ebay.com"


def _b64_decode_any(value: str) -> bytes:
    v = value.strip()
    # Add missing padding if needed.
    pad = "=" * ((4 - len(v) % 4) % 4)
    v = v + pad
    try:
        return base64.b64decode(v)
    except Exception:
        return base64.urlsafe_b64decode(v)


async def _get_app_token() -> str | None:
    tok, exp = _TOKEN_CACHE.get("token", ("", 0.0))
    if tok and time.time() < exp - 60:
        return tok

    settings = get_settings()
    app_id = (settings.ebay_app_id or "").strip()
    client_secret = (settings.ebay_client_secret or "").strip()
    if not app_id or not client_secret:
        return None

    creds = f"{app_id}:{client_secret}".encode("utf-8")
    basic = base64.b64encode(creds).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{_ebay_api_root()}/identity/v1/oauth2/token", data=data, headers=headers)
        if resp.status_code != 200:
            log.error("ebay.compliance.token_failed", status=resp.status_code, body=resp.text[:400])
            return None
        payload = resp.json()
        token = str(payload.get("access_token") or "")
        if not token:
            return None
        ttl = int(payload.get("expires_in") or 3600)
        _TOKEN_CACHE["token"] = (token, time.time() + ttl)
        return token


async def _get_notification_public_key(kid: str) -> str | None:
    cached = _PUBKEY_CACHE.get(kid)
    if cached and time.time() < cached[1]:
        return cached[0]

    token = await _get_app_token()
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{_ebay_api_root()}/commerce/notification/v1/public_key/{kid}"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            log.error("ebay.compliance.public_key_fetch_failed", kid=kid, status=resp.status_code, body=resp.text[:400])
            return None
        payload = resp.json() if resp.text else {}
        # eBay docs refer to "public key" value; field name may vary by API version.
        key_val = (
            payload.get("key")
            or payload.get("publicKey")
            or payload.get("public_key")
            or payload.get("keyValue")
        )
        if not key_val:
            log.error("ebay.compliance.public_key_missing", kid=kid, response=payload)
            return None
        key_str = str(key_val)
        _PUBKEY_CACHE[kid] = (key_str, time.time() + 3600)
        return key_str


async def _verify_ebay_signature(sig_header: str, raw_payload: bytes) -> bool:
    """
    Manual verification flow from eBay docs:
      1) base64 decode X-EBAY-SIGNATURE packed header
      2) read kid + signature
      3) fetch public key by kid
      4) verify signature on raw payload (SHA1 with ECDSA)
    """
    try:
        decoded = _b64_decode_any(sig_header).decode("utf-8")
        packed = json.loads(decoded)
    except Exception:
        log.warning("ebay.compliance.signature_header_decode_failed")
        return False

    kid = str(packed.get("kid") or "").strip()
    signature_b64 = str(packed.get("signature") or "").strip()
    alg = str(packed.get("alg") or "").upper()
    digest_hint = str(packed.get("digest") or "").upper()
    if not kid or not signature_b64:
        log.warning("ebay.compliance.signature_header_missing_fields", packed=packed)
        return False

    key_val = await _get_notification_public_key(kid)
    if not key_val:
        return False

    try:
        if "BEGIN PUBLIC KEY" in key_val:
            pub = serialization.load_pem_public_key(key_val.encode("utf-8"))
        else:
            pub = serialization.load_der_public_key(_b64_decode_any(key_val))
    except Exception:
        log.warning("ebay.compliance.public_key_parse_failed", kid=kid)
        return False

    try:
        sig_bytes = _b64_decode_any(signature_b64)
        hash_alg = hashes.SHA1()
        if "SHA256" in digest_hint:
            hash_alg = hashes.SHA256()
        if alg and "ECDSA" not in alg:
            log.warning("ebay.compliance.unexpected_alg", alg=alg, kid=kid)
        pub.verify(sig_bytes, raw_payload, ec.ECDSA(hash_alg))
        return True
    except Exception:
        log.warning("ebay.compliance.signature_verify_failed", kid=kid, alg=alg, digest=digest_hint)
        return False


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
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        payload = {"raw": raw.decode("utf-8", errors="ignore")}

    sig = request.headers.get("x-ebay-signature") or request.headers.get("X-EBAY-SIGNATURE")

    if not sig:
        log.warning("ebay.compliance.signature_missing")
        return Response(status_code=412)

    ok = await _verify_ebay_signature(sig, raw)
    if not ok:
        return Response(status_code=412)

    try:
        log.info(
            "ebay.compliance.notification_received",
            signature_verified=True,
            payload=payload,
        )
    except Exception:
        log.info(
            "ebay.compliance.notification_received_unserializable",
            signature_verified=True,
            payload_text=json.dumps(str(payload)),
        )

    return Response(status_code=200)
    if not _CRYPTO_OK:
        log.error("ebay.compliance.cryptography_missing")
        return False
