"""Optimize GLB assets before publication and retain their source bytes."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

_OPTIMIZER_TIMEOUT_SECONDS = 600


class GlbOptimizationError(RuntimeError):
    """Raised when a GLB cannot be safely optimized for browser delivery."""


@dataclass(frozen=True)
class OptimizedGlb:
    content: bytes
    original_sha256: str
    original_bytes: int
    output_bytes: int
    compressed: bool


def _glb_geometry_signature(content: bytes) -> tuple[tuple[int, int], ...]:
    """Read primitive modes and index/vertex counts from a GLB v2 document."""
    if len(content) < 20:
        raise GlbOptimizationError("GLB is too small to contain a glTF document")
    magic, version, total = struct.unpack_from("<III", content)
    json_length, json_type = struct.unpack_from("<II", content, 12)
    if magic != 0x46546C67 or version != 2 or total != len(content):
        raise GlbOptimizationError("Invalid GLB v2 container")
    if json_type != 0x4E4F534A or json_length % 4 or json_length > len(content) - 20:
        raise GlbOptimizationError("Invalid GLB JSON chunk")
    try:
        document = json.loads(content[20 : 20 + json_length].decode("utf-8").rstrip(" \t\r\n\0"))
        if not isinstance(document, dict) or (document.get("asset") or {}).get("version") != "2.0":
            raise GlbOptimizationError("GLB JSON is missing glTF 2.0 asset metadata")
        offset = 12
        chunk_index = 0
        while offset < len(content):
            if offset + 8 > len(content):
                raise GlbOptimizationError("GLB contains a truncated chunk header")
            chunk_length, chunk_type = struct.unpack_from("<II", content, offset)
            if chunk_length % 4 or offset + 8 + chunk_length > len(content):
                raise GlbOptimizationError("GLB contains an invalid chunk length")
            if chunk_index == 0 and (chunk_type != 0x4E4F534A or chunk_length != json_length):
                raise GlbOptimizationError("The first GLB chunk must contain the declared JSON document")
            offset += 8 + chunk_length
            chunk_index += 1
        if offset != len(content) or chunk_index == 0:
            raise GlbOptimizationError("GLB chunks do not match the declared container size")
        accessors = document.get("accessors", [])
        signature = []
        for mesh in document.get("meshes", []):
            for primitive in mesh.get("primitives", []):
                if "indices" in primitive:
                    count = accessors[primitive["indices"]]["count"]
                else:
                    count = accessors[primitive["attributes"]["POSITION"]]["count"]
                signature.append((primitive.get("mode", 4), count))
        return tuple(signature)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, struct.error) as exc:
        raise GlbOptimizationError("GLB geometry metadata is invalid") from exc


def validate_glb(content: bytes) -> None:
    """Validate a complete GLB v2 before accepting it into the asset pipeline."""
    _glb_geometry_signature(content)


def _optimizer_command() -> list[str]:
    configured = os.getenv("GLTF_TRANSFORM_BIN")
    if configured:
        return [configured]

    executable = shutil.which("gltf-transform")
    if executable and Path(executable).suffix.lower() not in {".cmd", ".ps1", ".bat"}:
        return [executable]

    # Support the globally installed npm CLI on Windows developer machines.
    node = shutil.which("node")
    npm_root = os.getenv("APPDATA")
    if node and npm_root:
        cli = Path(npm_root) / "npm" / "node_modules" / "@gltf-transform" / "cli" / "bin" / "cli.js"
        if cli.is_file():
            return [node, str(cli)]

    raise GlbOptimizationError(
        "GLB optimizer is unavailable; install @gltf-transform/cli 4.2.1 in the API image"
    )


def optimize_glb(content: bytes) -> OptimizedGlb:
    """Run the production Meshopt/WebP profile without changing mesh topology."""
    before_geometry = _glb_geometry_signature(content)
    original_sha = hashlib.sha256(content).hexdigest()
    with tempfile.TemporaryDirectory(prefix="flipflop-glb-") as temporary_dir:
        source = Path(temporary_dir) / "source.glb"
        output = Path(temporary_dir) / "optimized.glb"
        source.write_bytes(content)
        command = [
            *_optimizer_command(),
            "optimize",
            str(source),
            str(output),
            "--compress",
            "meshopt",
            "--texture-compress",
            "webp",
            "--texture-size",
            "2048",
            "--simplify",
            "false",
            "--flatten",
            "false",
            "--join",
            "false",
            "--instance",
            "false",
            "--palette",
            "false",
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=_OPTIMIZER_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = getattr(exc, "stderr", None) or str(exc)
            raise GlbOptimizationError(f"GLB optimization failed: {str(detail).strip()[:800]}") from exc
        if not output.is_file():
            raise GlbOptimizationError("GLB optimizer completed without producing an output file")
        optimized = output.read_bytes()

    after_geometry = _glb_geometry_signature(optimized)
    if after_geometry != before_geometry:
        raise GlbOptimizationError("GLB optimization changed primitive topology or index/vertex counts")

    # Optimization must never inflate a public asset. The original is still
    # persisted separately by persist_optimized_glb for audit/reprocessing.
    chosen = optimized if len(optimized) < len(content) else content
    compressed = chosen is optimized
    log.info(
        "glb.optimized",
        original_bytes=len(content),
        output_bytes=len(chosen),
        reduction_pct=round((1 - len(chosen) / len(content)) * 100, 1) if content else 0,
        compressed=compressed,
        optimizer_output_bytes=len(optimized),
    )
    return OptimizedGlb(
        content=chosen,
        original_sha256=original_sha,
        original_bytes=len(content),
        output_bytes=len(chosen),
        compressed=compressed,
    )


def _write_atomically(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def persist_optimized_glb(content: bytes, destination: Path, originals_root: Path) -> OptimizedGlb:
    """Compress in a worker thread, preserve original bytes, then atomically publish."""
    original_sha256 = hashlib.sha256(content).hexdigest()
    original_path = originals_root / f"{destination.stem}-{original_sha256[:16]}.original.glb"
    if original_path.exists():
        existing_hash = hashlib.sha256(original_path.read_bytes()).hexdigest()
        if existing_hash != original_sha256:
            raise GlbOptimizationError(f"Existing GLB original backup does not match: {original_path.name}")
    else:
        await asyncio.to_thread(_write_atomically, original_path, content)
    optimized = await asyncio.to_thread(optimize_glb, content)
    await asyncio.to_thread(_write_atomically, destination, optimized.content)
    return optimized
