from pathlib import Path

from app.api import manual_builds


def test_customer_hub_dir_uses_unpadded_build_id() -> None:
    assert manual_builds._build_customer_hub_dir(2) == (
        manual_builds._BUILD_ASSETS_ROOT / "2" / "Customer Hub"
    )


def test_customer_hub_entrypoint_is_created_in_requested_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(manual_builds, "_BUILD_ASSETS_ROOT", tmp_path / "builds")

    entrypoint = manual_builds._write_customer_hub_entrypoint(
        27,
        104,
        "preview-token",
        "https://theflipflop.shop",
    )

    assert entrypoint == tmp_path / "builds" / "27" / "Customer Hub" / "index.html"
    assert entrypoint.is_file()
    assert "https://theflipflop.shop/my-builds/104?preview=preview-token" in entrypoint.read_text(encoding="utf-8")
