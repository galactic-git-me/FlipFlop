from pathlib import Path

from app.api import manual_builds


def test_model_download_dir_uses_unpadded_build_id() -> None:
    assert manual_builds._build_model_download_dir(2) == (
        manual_builds._BUILD_ASSETS_ROOT / "2" / "3D Model"
    )


def test_model_download_dir_is_under_builds_root() -> None:
    path = manual_builds._build_model_download_dir(123)
    assert path == Path(manual_builds._BUILD_ASSETS_ROOT, "123", "3D Model")
