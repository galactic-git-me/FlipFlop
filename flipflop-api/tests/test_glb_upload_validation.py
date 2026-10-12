import json
import struct

import pytest

from app.api.assets_admin import _validate_uploaded_glb


def _glb(version: int = 2, declared_length: int | None = None) -> bytes:
    document = json.dumps({"asset": {"version": "2.0"}}, separators=(",", ":")).encode()
    document += b" " * (-len(document) % 4)
    chunk = struct.pack("<II", len(document), 0x4E4F534A) + document
    length = 12 + len(chunk) if declared_length is None else declared_length
    return b"glTF" + struct.pack("<II", version, length) + chunk


def test_accepts_well_formed_glb_v2_header():
    _validate_uploaded_glb(_glb())


@pytest.mark.parametrize("content", [b"", b"glTF", b"not-a-glb".ljust(20, b"\0")])
def test_rejects_missing_or_invalid_glb_header(content: bytes):
    with pytest.raises(ValueError, match="valid binary GLB"):
        _validate_uploaded_glb(content)


def test_rejects_unsupported_glb_version():
    with pytest.raises(ValueError, match="version 2"):
        _validate_uploaded_glb(_glb(version=1))


def test_rejects_declared_size_that_differs_from_uploaded_bytes():
    with pytest.raises(ValueError, match="header size"):
        _validate_uploaded_glb(_glb(declared_length=4096))
