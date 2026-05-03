"""
In-memory scan state — shared across the process.
Tracks which sites are being scanned and their individual progress.
"""
from datetime import datetime
from typing import Optional

_state: dict = {
    "running": False,
    "total": 0,
    "completed": 0,
    "current_sites": [],   # sites actively being scanned right now
    "sites": [],           # list of {name, url, status, found, gems, error}
    "started_at": None,
    "finished_at": None,
    "total_found": 0,
    "total_gems": 0,
}


def get_state() -> dict:
    return dict(_state)


def scan_started(sources: list) -> None:
    _state["running"] = True
    _state["total"] = len(sources)
    _state["completed"] = 0
    _state["current_sites"] = []
    _state["started_at"] = datetime.utcnow().isoformat()
    _state["finished_at"] = None
    _state["total_found"] = 0
    _state["total_gems"] = 0
    _state["sites"] = [
        {"name": s.name, "url": s.url, "status": "pending", "found": 0, "gems": 0, "error": None}
        for s in sources
    ]


def site_started(name: str) -> None:
    _state["current_sites"] = list(set(_state["current_sites"] + [name]))
    for s in _state["sites"]:
        if s["name"] == name:
            s["status"] = "scanning"
            break


def site_done(name: str, found: int, gems: int) -> None:
    _state["current_sites"] = [s for s in _state["current_sites"] if s != name]
    _state["completed"] += 1
    _state["total_found"] += found
    _state["total_gems"] += gems
    for s in _state["sites"]:
        if s["name"] == name:
            s["status"] = "done"
            s["found"] = found
            s["gems"] = gems
            break


def site_error(name: str, error: str) -> None:
    _state["current_sites"] = [s for s in _state["current_sites"] if s != name]
    _state["completed"] += 1
    for s in _state["sites"]:
        if s["name"] == name:
            s["status"] = "error"
            s["error"] = error
            break


def scan_finished() -> None:
    _state["running"] = False
    _state["current_sites"] = []
    _state["finished_at"] = datetime.utcnow().isoformat()
