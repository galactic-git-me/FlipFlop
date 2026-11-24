"""Current motherboard bundle listings may identify chipsets, not sockets."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.gem_radar import _is_current_gen, _is_motherboard_bundle_gem


def test_z790_bundle_is_a_current_motherboard_gem():
    title = (
        "Intel Core i5-14400F 10 core 4.7GHz Processor, "
        "ASUS PRIME Z790-P WIFI Motherboard CPU Bundle"
    )

    assert _is_motherboard_bundle_gem(title)
    assert _is_current_gen(title, "motherboard")


def test_obsolete_motherboard_bundle_is_not_current_gen():
    title = "PENTIUM G 645 INTEL GH61WW 4GB RAM, Motherboard Bundle"

    assert _is_motherboard_bundle_gem(title)
    assert not _is_current_gen(title, "motherboard")
