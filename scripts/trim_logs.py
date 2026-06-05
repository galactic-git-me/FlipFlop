"""
Trim .run-logs/ files to only keep entries from the last 24 hours.
Run hourly to prevent unbounded log growth.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / ".run-logs"
CUTOFF = datetime.now() - timedelta(hours=24)
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def _parse_ts(line: str) -> datetime | None:
    m = TS_RE.match(line)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return None


def trim_file(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    kept: list[str] = []
    current_ts: datetime | None = None

    for line in lines:
        ts = _parse_ts(line)
        if ts is not None:
            current_ts = ts
        if current_ts is None or current_ts >= CUTOFF:
            kept.append(line)

    removed = len(lines) - len(kept)
    if removed > 0:
        path.write_text("".join(kept), encoding="utf-8")
        print(f"[trim_logs] {path.name}: removed {removed} lines older than 24h")
    else:
        print(f"[trim_logs] {path.name}: nothing to trim")


if __name__ == "__main__":
    for log_file in sorted(LOG_DIR.glob("*.log")):
        try:
            trim_file(log_file)
        except Exception as exc:
            print(f"[trim_logs] ERROR {log_file.name}: {exc}", file=sys.stderr)
