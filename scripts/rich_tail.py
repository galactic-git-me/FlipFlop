#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import time
from collections import deque
from pathlib import Path

from rich.console import Console
from rich.text import Text

_ENDPOINT_STYLES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\s/api/schedule(?:/|\\s|$)"), "bright_cyan"),
    (re.compile(r"\s/api/sources(?:/|\\s|$)"), "bright_magenta"),
    (re.compile(r"\s/api/listings(?:/|\\s|$)"), "bright_green"),
    (re.compile(r"\s/api/demand(?:/|\\s|$)"), "bright_yellow"),
    (re.compile(r"\s/api/search-telemetry(?:/|\\s|$)"), "bright_blue"),
    (re.compile(r"\s/api/swarms(?:/|\\s|$)"), "bright_white"),
]


def style_line(line: str) -> Text:
    t = Text(line.rstrip("\n"))
    low = line.lower()
    if "error" in low or "failed" in low or "exception" in low:
        t.stylize("bold red")
    elif "warn" in low:
        t.stylize("yellow")
    elif "http/1.1" in low and "/api/" in low:
        for patt, style in _ENDPOINT_STYLES:
            if patt.search(low):
                t.stylize(style)
                break
        else:
            t.stylize("cyan")
    elif "ready" in low or "compiled successfully" in low or "started" in low:
        t.stylize("green")
    elif "info" in low:
        t.stylize("cyan")
    elif "debug" in low:
        t.stylize("dim")
    return t


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True)
    p.add_argument("--title", default="Logs")
    p.add_argument("--lines", type=int, default=120)
    args = p.parse_args()

    path = Path(args.file)
    console = Console()
    buf: deque[str] = deque(maxlen=max(20, args.lines))
    fh = None
    inode = None

    console.print(f"[bold]{args.title}[/bold]: {path}")
    console.print("")

    while True:
        try:
            if path.exists():
                st = path.stat()
                curr_inode = (st.st_dev, st.st_ino)
                if fh is None or inode != curr_inode:
                    if fh:
                        fh.close()
                    fh = path.open("r", encoding="utf-8", errors="replace")
                    inode = curr_inode
                    for ln in fh.readlines()[-buf.maxlen :]:
                        buf.append(ln.rstrip("\n"))
                    console.clear()
                    console.print(f"[bold]{args.title}[/bold]: {path}\n")
                    for ln in list(buf):
                        console.print(style_line(ln))

                while fh:
                    ln = fh.readline()
                    if not ln:
                        break
                    buf.append(ln.rstrip("\n"))
                    console.print(style_line(ln))
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            console.print(f"[red]tailer error:[/red] {exc}")
            time.sleep(1.0)
        time.sleep(0.15)


if __name__ == "__main__":
    raise SystemExit(main())
