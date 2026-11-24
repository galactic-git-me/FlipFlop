from types import SimpleNamespace

from app.services.ai_build_generator import _valid_optional_component


def _listing(category: str, title: str):
    return SimpleNamespace(category=category, title=title)


def test_accessories_are_not_accepted_as_build_components():
    assert not _valid_optional_component(_listing("psu", "Computer fan mesh power supply cover"))
    assert not _valid_optional_component(_listing("ssd", "Gridfinity M.2 SSD storage protection case"))
    assert not _valid_optional_component(_listing("case", "PCI slot dust shutter computer case panel"))
    assert not _valid_optional_component(_listing("cooler", "Mini heatsinks with thermal tape for VRM"))


def test_real_supporting_components_are_accepted():
    assert _valid_optional_component(_listing("psu", "Corsair RM750e 750W ATX Power Supply PSU"))
    assert _valid_optional_component(_listing("ssd", "Samsung 990 Pro 1TB NVMe SSD"))
    assert _valid_optional_component(_listing("case", "Corsair 4000D Airflow ATX Mid Tower PC Case"))
    assert _valid_optional_component(_listing("cooler", "Arctic Liquid Freezer 360mm AIO Cooler"))
