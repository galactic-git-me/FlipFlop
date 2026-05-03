"""
Facebook cookie management — status check + renewal endpoint.
"""
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/facebook", tags=["facebook"])

FB_COOKIES_PATH = Path(__file__).parent.parent.parent / "fb_cookies.json"

KEY_COOKIES = {"c_user", "xs", "datr", "sb"}   # If any of these expire, FB access breaks


def _cookie_status() -> dict:
    """Return a status dict describing the current state of fb_cookies.json."""
    if not FB_COOKIES_PATH.exists():
        return {
            "exists": False,
            "valid": False,
            "expired": False,
            "expires_at": None,
            "expiry_warning": True,
            "message": "fb_cookies.json not found — Facebook Marketplace will be limited to ~20 local items.",
        }

    try:
        cookies = json.loads(FB_COOKIES_PATH.read_text())
    except Exception:
        return {
            "exists": True,
            "valid": False,
            "expired": False,
            "expires_at": None,
            "expiry_warning": True,
            "message": "fb_cookies.json is malformed — please re-export from your browser.",
        }

    now = datetime.utcnow().timestamp()
    key_cookies = [c for c in cookies if c.get("name") in KEY_COOKIES]
    if not key_cookies:
        return {
            "exists": True,
            "valid": False,
            "expired": False,
            "expires_at": None,
            "expiry_warning": True,
            "message": "No key cookies found (c_user, xs, datr, sb). Try re-exporting.",
        }

    # Find the soonest-expiring key cookie
    expirations = [
        c["expirationDate"] for c in key_cookies
        if "expirationDate" in c and c.get("expirationDate")
    ]
    if not expirations:
        # Session cookies — no fixed expiry, assume valid
        return {
            "exists": True,
            "valid": True,
            "expired": False,
            "expires_at": None,
            "expiry_warning": False,
            "message": "Cookies loaded (session-only — no fixed expiry).",
        }

    min_expiry = min(expirations)
    days_remaining = (min_expiry - now) / 86400

    if min_expiry < now:
        return {
            "exists": True,
            "valid": False,
            "expired": True,
            "expires_at": datetime.utcfromtimestamp(min_expiry).isoformat(),
            "expiry_warning": True,
            "message": "Facebook cookies have expired — Marketplace scraping will fail. Please re-export.",
        }

    warning = days_remaining < 14   # warn 2 weeks before expiry
    return {
        "exists": True,
        "valid": True,
        "expired": False,
        "expires_at": datetime.utcfromtimestamp(min_expiry).isoformat(),
        "expiry_warning": warning,
        "days_remaining": round(days_remaining, 1),
        "message": (
            f"Cookies expire in {round(days_remaining)} days — please re-export soon."
            if warning else
            f"Cookies valid for {round(days_remaining)} days."
        ),
    }


@router.get("/status")
async def get_facebook_status():
    return _cookie_status()


class CookieUpdate(BaseModel):
    cookies_json: str   # Raw JSON string pasted from Cookie Editor export


@router.put("/cookies")
async def update_facebook_cookies(body: CookieUpdate):
    """Replace fb_cookies.json with new cookie JSON pasted from Cookie Editor."""
    try:
        parsed = json.loads(body.cookies_json)
        if not isinstance(parsed, list):
            raise ValueError("Expected a JSON array")
        # Validate at least one key cookie is present
        names = {c.get("name") for c in parsed}
        if not names & KEY_COOKIES:
            raise ValueError(f"No key cookies found — expected at least one of {KEY_COOKIES}")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(400, f"Invalid cookie JSON: {exc}")

    FB_COOKIES_PATH.write_text(json.dumps(parsed, indent=2))
    return {"ok": True, "message": "Cookies updated.", "status": _cookie_status()}
