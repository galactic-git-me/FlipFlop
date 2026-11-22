"""Optional secure Sheets publishing for completed GEM build-QA events.

No credentials are checked in. Publishing is off unless both the explicit
feature flag and a mounted service-account file are configured at runtime.
"""
from __future__ import annotations

import os
from urllib.parse import quote


def _append_rows(spreadsheet_id: str, credential_file: str, platform: str,
                 run_id: str, rows: list[list]) -> dict:
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    creds = service_account.Credentials.from_service_account_file(
        credential_file,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    session = AuthorizedSession(creds)
    tab = f"AM{platform[-1]} GEM QA"
    encoded = quote(f"'{tab}'!A:C", safe="")
    base = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values"
    existing = session.get(f"{base}/{encoded}", timeout=20)
    existing.raise_for_status()
    values = existing.json().get("values") or []
    if any(len(row) >= 3 and str(row[2]) == run_id for row in values[1:]):
        return {"status": "already_written", "rows": 0}

    append_range = quote(f"'{tab}'!A:L", safe="")
    response = session.post(
        f"{base}/{append_range}:append",
        params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
        json={"values": rows},
        timeout=30,
    )
    response.raise_for_status()
    return {"status": "written", "rows": len(rows)}


def publish_snapshot(snapshot: dict) -> dict:
    """Append a fully compatible snapshot; return a safe disabled/error state otherwise."""
    runtime = os.getenv("FLIPFLOP_RUNTIME_ENV", "development").strip().casefold()
    from app.config import get_settings
    app_env = get_settings().app_env.strip().casefold()
    if runtime in {"live", "production"} or app_env not in {"dev", "development", "local"}:
        return {"status": "live_write_blocked", "rows": 0}
    if os.getenv("GEM_BUILD_QA_SHEETS_ENABLED", "false").strip().casefold() != "true":
        return {"status": "disabled", "rows": 0}
    spreadsheet_id = os.getenv("GEM_BUILD_QA_SPREADSHEET_ID", "").strip()
    credential_file = os.getenv("GEM_BUILD_QA_GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not spreadsheet_id or not credential_file or not os.path.isfile(credential_file):
        return {"status": "needs_credentials", "rows": 0}
    run_id = str(snapshot.get("sweep_run_id") or "")
    if not run_id:
        return {"status": "missing_run_id", "rows": 0}
    rows = []
    for item in snapshot.get("rows") or []:
        rows.append([
            item.get("scrape_completed_at"), item.get("environment"), item.get("scan_run_id"),
            item.get("platform"), item.get("component_slot"), item.get("candidate_item"),
            item.get("price_gbp"), item.get("condition"), item.get("seller_source"),
            item.get("listing_url"), item.get("compatibility_status"), item.get("evidence_or_blockers"),
        ])
    if not rows:
        return {"status": "no_candidate_rows", "rows": 0}
    return _append_rows(spreadsheet_id, credential_file, str(snapshot["platform"]), run_id, rows)
