from __future__ import annotations

from datetime import datetime, timedelta


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def compute_health_score(cfg: dict) -> int:
    failures = int(cfg.get("consecutive_failures", 0) or 0)
    zero_runs = int(cfg.get("zero_results_streak", 0) or 0)
    recent_avg = float(cfg.get("recent_avg_found", 0.0) or 0.0)

    score = 100
    score -= min(60, failures * 20)
    score -= min(25, zero_runs * 5)
    if recent_avg < 1:
        score -= 10
    elif recent_avg < 3:
        score -= 5

    return max(0, min(100, int(score)))


def should_skip_due_to_cooldown(cfg: dict, now: datetime | None = None) -> tuple[bool, str | None]:
    now = now or datetime.utcnow()
    until = parse_iso(cfg.get("cooldown_until"))
    if until and until > now:
        secs = int((until - now).total_seconds())
        return True, f"cooldown_active_{secs}s"
    return False, None


def apply_success(cfg: dict, found: int) -> dict:
    out = dict(cfg or {})
    out["consecutive_failures"] = 0
    out["last_success_at"] = datetime.utcnow().isoformat()

    prev_avg = float(out.get("recent_avg_found", 0.0) or 0.0)
    out["recent_avg_found"] = round((prev_avg * 0.7) + (float(found) * 0.3), 2)

    if found > 0:
        out["zero_results_streak"] = 0
        out.pop("cooldown_until", None)
    else:
        zr = int(out.get("zero_results_streak", 0) or 0) + 1
        out["zero_results_streak"] = zr
        if zr >= 3:
            mins = min(90, 10 * (2 ** min(4, zr - 3)))
            out["cooldown_until"] = (datetime.utcnow() + timedelta(minutes=mins)).isoformat()

    out["health_score"] = compute_health_score(out)
    return out


def apply_error(cfg: dict, failures: int) -> dict:
    out = dict(cfg or {})
    out["consecutive_failures"] = failures
    mins = min(120, 5 * (2 ** min(5, max(0, failures - 1))))
    out["cooldown_until"] = (datetime.utcnow() + timedelta(minutes=mins)).isoformat()
    out["health_score"] = compute_health_score(out)
    return out
