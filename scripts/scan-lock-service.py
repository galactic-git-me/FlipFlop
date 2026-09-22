"""
Minimal, always-on local service that answers the Gem Radar extension's
scan-lock coordinator calls (GET/POST /api/gem-radar/scan-lock[...]).

Why this exists: the full flipflop-api backend only runs locally for DEV
(production's backend/DB/etc. all live on Andromeda -- see
docs/EXTENSION_ENVIRONMENTS.md and scripts/start-production-remote.sh). But
both the DEV and LIVE extensions hardcode SCAN_LOCK_COORDINATOR_URL to
127.0.0.1:4311 (FlipFlopXtension/src/lib/environment.ts) so they can't both
scan at once. Without something listening there when DEV's backend isn't
running, LIVE's extension would have nothing to coordinate against.

Rather than running the full backend just for this, this is a byte-for-byte
behavioral port of the four endpoints in flipflop-api/app/api/gem_radar.py
(scan_lock_status/_acquire/_renew/_release, lines ~3008-3084): an in-memory
mutex with a TTL, no DB, no other app dependencies. Runs standalone as its
own Windows Service on port 4311 so it's always there regardless of which
of DEV/PROD's other services happen to be up.

IMPORTANT: if flipflop-api/app/api/gem_radar.py's scan-lock logic changes,
mirror the change here too -- there is no shared import between them
(DEV's full backend also serves these same paths on 4311 when it's up,
overlapping with this port; see start-dev-stack's port ownership notes).
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

ADMIN_API_KEY = os.environ.get("SCAN_LOCK_ADMIN_KEY", "")
SCAN_LOCK_TTL_SECONDS = 180

app = FastAPI(title="scan-lock-service")

_scan_lock: dict[str, object] | None = None
_scan_lock_guard = asyncio.Lock()


def require_operator(x_admin_key: str | None = Header(default=None)) -> None:
    if not ADMIN_API_KEY:
        return
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Operator key required")


class ScanLockRequest(BaseModel):
    owner: str
    environment: Literal["DEV", "LIVE"]


class ScanLockResponse(BaseModel):
    acquired: bool
    state: Literal["idle", "held", "waiting"]
    environment: Literal["DEV", "LIVE"]
    holderEnvironment: Literal["DEV", "LIVE"] | None
    waitStartedAt: datetime | None


def _scan_lock_response(environment: Literal["DEV", "LIVE"], acquired: bool) -> ScanLockResponse:
    lease = _scan_lock
    if lease is None:
        return ScanLockResponse(acquired=acquired, state="idle", environment=environment,
                                 holderEnvironment=None, waitStartedAt=None)
    return ScanLockResponse(acquired=acquired, state="held" if acquired else "waiting",
                             environment=environment,
                             holderEnvironment=lease["environment"],
                             waitStartedAt=lease["acquired_at"])


@app.get("/api/gem-radar/scan-lock", response_model=ScanLockResponse)
async def scan_lock_status(_: None = Depends(require_operator)) -> ScanLockResponse:
    global _scan_lock
    async with _scan_lock_guard:
        if _scan_lock is not None and _scan_lock["expires_at"] <= datetime.now(timezone.utc):
            _scan_lock = None
        return _scan_lock_response("DEV", False)


@app.post("/api/gem-radar/scan-lock/acquire", response_model=ScanLockResponse)
async def scan_lock_acquire(payload: ScanLockRequest, _: None = Depends(require_operator)) -> ScanLockResponse:
    global _scan_lock
    async with _scan_lock_guard:
        now = datetime.now(timezone.utc)
        if _scan_lock is not None and _scan_lock["expires_at"] <= now:
            _scan_lock = None
        if _scan_lock is None:
            _scan_lock = {"owner": payload.owner, "environment": payload.environment,
                          "acquired_at": now, "expires_at": now + timedelta(seconds=SCAN_LOCK_TTL_SECONDS)}
            return _scan_lock_response(payload.environment, True)
        if _scan_lock["owner"] == payload.owner:
            _scan_lock["expires_at"] = now + timedelta(seconds=SCAN_LOCK_TTL_SECONDS)
            return _scan_lock_response(payload.environment, True)
        return _scan_lock_response(payload.environment, False)


@app.post("/api/gem-radar/scan-lock/renew", response_model=ScanLockResponse)
async def scan_lock_renew(payload: ScanLockRequest, _: None = Depends(require_operator)) -> ScanLockResponse:
    global _scan_lock
    async with _scan_lock_guard:
        now = datetime.now(timezone.utc)
        if _scan_lock is not None and _scan_lock["owner"] == payload.owner and _scan_lock["expires_at"] > now:
            _scan_lock["expires_at"] = now + timedelta(seconds=SCAN_LOCK_TTL_SECONDS)
            return _scan_lock_response(payload.environment, True)
        return _scan_lock_response(payload.environment, False)


@app.post("/api/gem-radar/scan-lock/release", response_model=ScanLockResponse)
async def scan_lock_release(payload: ScanLockRequest, _: None = Depends(require_operator)) -> ScanLockResponse:
    global _scan_lock
    async with _scan_lock_guard:
        if _scan_lock is not None and _scan_lock["owner"] == payload.owner:
            _scan_lock = None
        return _scan_lock_response(payload.environment, True)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=4311)
