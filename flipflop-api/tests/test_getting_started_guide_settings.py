from hashlib import sha256
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.api import settings_router


@pytest.mark.asyncio
async def test_getting_started_guide_upload_normalizes_utf8_and_reports_saved_checksum(
    monkeypatch, tmp_path
):
    guide_path = tmp_path / "data" / "getting-started-guide.md"
    monkeypatch.setattr(settings_router, "GETTING_STARTED_GUIDE_PATH", guide_path)
    uploaded = UploadFile(
        filename="customer-guide.MD",
        file=BytesIO(b"\xef\xbb\xbf  Welcome to your FlipFlop PC.  \n"),
    )

    result = await settings_router.upload_getting_started_guide(uploaded)
    expected = b"Welcome to your FlipFlop PC.\n"

    assert guide_path.read_bytes() == expected
    assert result == {
        "uploaded": True,
        "filename": "getting-started-guide.md",
        "sha256": sha256(expected).hexdigest(),
        "size_bytes": len(expected),
    }
    assert await settings_router.getting_started_guide_status() == result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, content, expected_status",
    [
        ("guide.pdf", b"not a text guide", 415),
        ("guide.md", b"", 413),
        ("guide.txt", b"\xff", 422),
        ("guide.md", b" \n\t", 422),
    ],
)
async def test_getting_started_guide_upload_rejects_invalid_content(
    monkeypatch, tmp_path, filename, content, expected_status
):
    guide_path = tmp_path / "data" / "getting-started-guide.md"
    guide_path.parent.mkdir(parents=True)
    guide_path.write_bytes(b"Existing approved guide\n")
    monkeypatch.setattr(
        settings_router,
        "GETTING_STARTED_GUIDE_PATH",
        guide_path,
    )
    with pytest.raises(HTTPException) as raised:
        await settings_router.upload_getting_started_guide(
            UploadFile(filename=filename, file=BytesIO(content))
        )
    assert raised.value.status_code == expected_status
    assert guide_path.read_bytes() == b"Existing approved guide\n"


@pytest.mark.asyncio
async def test_getting_started_guide_upload_rejects_content_above_one_megabyte(
    monkeypatch, tmp_path
):
    guide_path = tmp_path / "data" / "getting-started-guide.md"
    monkeypatch.setattr(settings_router, "GETTING_STARTED_GUIDE_PATH", guide_path)
    guide_path.parent.mkdir(parents=True)
    guide_path.write_bytes(b"Existing approved guide\n")
    oversized_content = b"a" * (settings_router.GETTING_STARTED_GUIDE_LIMIT + 1)

    with pytest.raises(HTTPException) as raised:
        await settings_router.upload_getting_started_guide(
            UploadFile(filename="guide.md", file=BytesIO(oversized_content))
        )

    assert raised.value.status_code == 413
    assert guide_path.read_bytes() == b"Existing approved guide\n"
