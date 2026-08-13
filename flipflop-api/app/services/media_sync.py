"""
Media Sync — pushes uploaded build photos to the flipflop-shop VPS so they're
immediately reachable at https://theflipflop.shop/media/<filename>.

Caddy on that VPS serves /media/* directly from disk (file_server), so a
plain scp is enough — no app restart or cache invalidation needed on the
remote end.
"""

import asyncio
import subprocess
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

_REMOTE_HOST = "mac@andromeda-ts"
_REMOTE_MEDIA_DIR = "/home/mac/CODING/flipflop-shop/public/media/"


async def sync_to_public_media(local_path: Path) -> bool:
    """
    Copies a file to the flipflop-shop VPS's public media directory via scp.
    Best-effort: logs and returns False on failure rather than raising, so a
    sync hiccup never blocks the upload response the user is waiting on.
    """
    def _scp() -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                "scp",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=10",
                str(local_path),
                f"{_REMOTE_HOST}:{_REMOTE_MEDIA_DIR}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    try:
        result = await asyncio.to_thread(_scp)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.error("media_sync.failed", file=local_path.name, error=str(exc))
        return False

    if result.returncode != 0:
        log.error("media_sync.failed", file=local_path.name, stderr=result.stderr)
        return False

    log.info("media_sync.synced", file=local_path.name)
    return True
