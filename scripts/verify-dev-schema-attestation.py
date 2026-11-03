#!/usr/bin/env python3
"""Fail closed unless the release's complete Alembic history passed in DEV."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "docs/database/dev-schema-validation.json"
MIGRATIONS = "flipflop-api/alembic/versions"


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def is_ancestor(ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        check=False,
        capture_output=True,
    ).returncode == 0


def migration_head(ref: str, paths: list[str]) -> str:
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in paths:
        content = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
        tree = ast.parse(content, filename=path)
        values: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                if value is None:
                    continue
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        values[target.id] = ast.literal_eval(value)
        revision = values.get("revision")
        if not isinstance(revision, str):
            continue
        revisions.add(revision)
        parent = values.get("down_revision")
        if isinstance(parent, str):
            parents.add(parent)
        elif isinstance(parent, (tuple, list)):
            parents.update(item for item in parent if isinstance(item, str))
    heads = revisions - parents
    if len(heads) != 1:
        raise RuntimeError(f"Expected one Alembic head, found {sorted(heads)}")
    return next(iter(heads))


def tracked_migration_hashes(ref: str) -> dict[str, str]:
    paths = git("ls-tree", "-r", "--name-only", ref, "--", MIGRATIONS).splitlines()
    result: dict[str, str] = {}
    for relative in paths:
        if not relative.endswith(".py") or relative.endswith("/__init__.py"):
            continue
        content = subprocess.run(
            ["git", "show", f"{ref}:{relative}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        result[relative] = hashlib.sha256(content).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-ref", default="HEAD")
    parser.add_argument("--dev-ref", default="origin/dev")
    parser.add_argument("--require-dev-ancestor", action="store_true")
    args = parser.parse_args()

    manifest_text = git("show", f"{args.release_ref}:{MANIFEST}", check=False)
    if not manifest_text:
        raise RuntimeError(f"Release has no {MANIFEST}; production DB migration is blocked")
    manifest = json.loads(manifest_text)
    release_sha = git("rev-parse", f"{args.release_ref}^{{commit}}")
    source_commit = manifest.get("source_commit", "")
    if not source_commit or subprocess.run(
        ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    ).returncode != 0:
        raise RuntimeError("DEV schema attestation source commit is missing from Git history")
    if not is_ancestor(source_commit, release_sha):
        raise RuntimeError("DEV schema attestation source is not an ancestor of the release")
    if args.require_dev_ancestor and not is_ancestor(source_commit, args.dev_ref):
        raise RuntimeError("Attested DEV validation commit has not reached origin/dev")

    release_hashes = tracked_migration_hashes(args.release_ref)
    if manifest.get("migration_sha256") != release_hashes:
        raise RuntimeError("Migration files changed since the local DEV validation")

    head = migration_head(args.release_ref, list(release_hashes))
    if manifest.get("schema_head") != head:
        raise RuntimeError(
            f"Attested schema head {manifest.get('schema_head')!r} does not match release head {head!r}"
        )
    if manifest.get("validation") != {
        "alembic_upgrade": "passed",
        "isolated_migration_tests": "passed",
        "local_schema_check": "passed",
    }:
        raise RuntimeError("DEV schema validation record is incomplete")

    print(f"DEV schema attestation verified: head={head}, source={source_commit[:12]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"DEV schema attestation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
