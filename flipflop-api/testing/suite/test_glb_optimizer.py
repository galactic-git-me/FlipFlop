import asyncio
import json
import struct
from pathlib import Path

import pytest

from app.services import glb_optimizer
from app.services.glb_optimizer import GlbOptimizationError, OptimizedGlb


def _glb(*, padding: int = 0, index_count: int = 3) -> bytes:
    document = {
        "asset": {"version": "2.0"},
        "accessors": [{"count": index_count}],
        "meshes": [{"primitives": [{"indices": 0}]}],
        "padding": "x" * padding,
    }
    json_chunk = json.dumps(document, separators=(",", ":")).encode()
    json_chunk += b" " * (-len(json_chunk) % 4)
    chunk = struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk


def _mock_optimizer(monkeypatch, output: bytes) -> None:
    monkeypatch.setattr(glb_optimizer, "_optimizer_command", lambda: ["gltf-transform"])

    def run(command, **_kwargs):
        if command[1] == "optimize":
            Path(command[3]).write_bytes(output)

    monkeypatch.setattr(glb_optimizer.subprocess, "run", run)


def test_optimizer_uses_smaller_output_when_geometry_is_unchanged(monkeypatch):
    source = _glb(padding=1024)
    optimized = _glb()
    _mock_optimizer(monkeypatch, optimized)

    result = glb_optimizer.optimize_glb(source)

    assert result.content == optimized
    assert result.original_bytes == len(source)
    assert result.output_bytes == len(optimized)
    assert result.compressed is True


def test_optimizer_keeps_source_when_output_is_not_smaller(monkeypatch):
    source = _glb()
    _mock_optimizer(monkeypatch, _glb(padding=1024))

    result = glb_optimizer.optimize_glb(source)

    assert result.content == source
    assert result.compressed is False


def test_optimizer_rejects_topology_changes(monkeypatch):
    _mock_optimizer(monkeypatch, _glb(index_count=6))

    with pytest.raises(GlbOptimizationError, match="topology"):
        glb_optimizer.optimize_glb(_glb())


def test_optimizer_rejects_malformed_glb():
    with pytest.raises(GlbOptimizationError, match="GLB"):
        glb_optimizer.validate_glb(b"not a glb")


def test_persist_keeps_source_and_atomically_writes_optimized_output(monkeypatch, tmp_path):
    source = _glb(padding=1024)
    optimized = _glb()
    monkeypatch.setattr(
        glb_optimizer,
        "optimize_glb",
        lambda _content: OptimizedGlb(
            content=optimized,
            original_sha256="a" * 64,
            original_bytes=len(source),
            output_bytes=len(optimized),
            compressed=True,
        ),
    )
    destination = tmp_path / "public" / "model.glb"
    originals = tmp_path / "private-originals"

    result = asyncio.run(glb_optimizer.persist_optimized_glb(source, destination, originals))

    assert destination.read_bytes() == optimized
    original_files = list(originals.glob("*.original.glb"))
    assert len(original_files) == 1
    assert original_files[0].read_bytes() == source
    assert result.compressed is True
