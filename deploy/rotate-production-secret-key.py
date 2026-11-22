#!/usr/bin/env python3
"""Safely rotate a too-short production SECRET_KEY while retaining read access."""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile


KEY_LINE = re.compile(r"^(?:export\s+)?(SECRET_KEY|SECRET_KEY_PREVIOUS)\s*=\s*(.*)$")


def parse_value(raw: str, name: str) -> str:
    # Refuse syntax whose interpretation could differ across dotenv/shell parsers.
    if not raw or raw != raw.strip() or any(char in raw for char in "\t\r\n\"'`#$"):
        raise ValueError(f"{name} has unsupported dotenv syntax; no changes made")
    return raw


def rotate(path: Path) -> str:
    if path.name != ".env.local" or path.is_symlink() or not path.is_file():
        raise ValueError("Expected an existing regular .env.local file; no changes made")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    found: dict[str, list[tuple[int, str]]] = {"SECRET_KEY": [], "SECRET_KEY_PREVIOUS": []}
    for index, line in enumerate(lines):
        match = KEY_LINE.match(line.rstrip("\r\n"))
        if match:
            found[match.group(1)].append((index, parse_value(match.group(2), match.group(1))))
    if len(found["SECRET_KEY"]) != 1 or len(found["SECRET_KEY_PREVIOUS"]) > 1:
        raise ValueError("Expected exactly one SECRET_KEY and at most one previous key; no changes made")

    current = found["SECRET_KEY"][0][1]
    if len(current) >= 32:
        return "Current production key already meets the minimum length; no rotation needed."
    if found["SECRET_KEY_PREVIOUS"]:
        raise ValueError("A previous key is already configured but the current key is short; manual review required")

    new_current = secrets.token_urlsafe(48)
    key_index = found["SECRET_KEY"][0][0]
    line_ending = "\r\n" if lines[key_index].endswith("\r\n") else "\n"
    lines[key_index] = f"SECRET_KEY={new_current}{line_ending}"
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += line_ending
    lines.append(f"SECRET_KEY_PREVIOUS={current}{line_ending}")

    mode = stat.S_IMODE(path.stat().st_mode)
    temp_path: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".env.local.", dir=path.parent)
        temp_path = Path(temp_name)
        os.fchmod(fd, mode & 0o600 or 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.writelines(lines)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, path)
        if os.name == "posix":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
    return "Production key rotated atomically; previous key retained for verification and decryption."


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: rotate-production-secret-key.py /path/to/.env.local", file=sys.stderr)
        return 2
    try:
        print(rotate(Path(sys.argv[1])))
    except Exception as error:
        print(f"Rotation stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
