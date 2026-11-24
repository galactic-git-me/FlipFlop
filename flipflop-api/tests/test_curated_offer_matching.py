"""Matching rules for scripts/resolve_curated_offers.py (no database needed)."""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "resolve_curated_offers", Path(__file__).resolve().parents[1] / "scripts" / "resolve_curated_offers.py"
)
m = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = m
_spec.loader.exec_module(m)

YES = [
    ("cpu", "AMD Ryzen 5 5600", "AMD Ryzen 5 5600 6-Core 3.5GHz AM4 Processor, Boxed with Wraith Stealth"),
    ("cpu", "AMD Ryzen 7 9800X3D", "AMD Ryzen 7 9800X3D 8 Core AM5 CPU"),
    ("cpu", "Intel Core Ultra 5 250K Plus", "Intel Core Ultra 5 250K Plus Desktop Processor LGA1851"),
    ("gpu", "NVIDIA GeForce RTX 5060 Ti 16GB", "MSI GeForce RTX 5060 Ti 16G VENTUS 2X OC"),
    ("gpu", "AMD Radeon RX 9060 XT 16GB", "Sapphire PULSE Radeon RX9060XT 16GB GDDR6"),
    ("gpu", "AMD Radeon RX 9070 16GB", "PowerColor Reaper AMD Radeon RX 9070 16GB GDDR6"),
    ("motherboard", "MSI B550M PRO-VDH WIFI", "MSI B550M PRO-VDH WiFi AM4 Micro-ATX Motherboard"),
    ("psu", "Corsair RM750e 750W 80+ Gold", "Corsair RM750e (2025) 750W Fully Modular ATX 3.1 PSU"),
    ("cooling", "Thermalright Peerless Assassin 120 SE", "Thermalright Peerless Assassin 120 SE ARGB CPU Air Cooler"),
    ("case", "Lian Li LANCOOL 207", "Lian-Li LANCOOL 207 Black Mid Tower Case"),
    ("ram", "32GB (2x16GB) DDR5-6000 CL30", "Corsair Vengeance RGB 32GB (2x16GB) DDR5 6000MHz C30 AMD EXPO"),
    ("ram", "32GB (2x16GB) DDR4-3200", "Kingston FURY Beast 32GB (2 x 16GB) DDR4 3600MHz CL18"),
    ("storage", "1TB PCIe 4.0 NVMe SSD", "Samsung 990 EVO Plus 1TB PCIe 4.0 NVMe M.2 SSD"),
    ("storage", "2TB PCIe 4.0 NVMe SSD", "WD_BLACK SN850X 2TB M.2 NVMe Gen4 SSD"),
]
NO = [
    ("cpu", "AMD Ryzen 5 5600", "AMD Ryzen 5 5600X 6-Core AM4 Processor"),          # X variant
    ("cpu", "AMD Ryzen 5 5600", "Gaming PC Ryzen 5 5600 RTX 4060 16GB"),            # full system
    ("cpu", "Intel Core Ultra 5 250K Plus", "Intel Core Ultra 5 250KF Plus"),       # KF variant
    ("gpu", "NVIDIA GeForce RTX 5060 Ti 16GB", "ASUS Dual GeForce RTX 5060 8GB"),   # non-Ti
    ("gpu", "AMD Radeon RX 9070 16GB", "Sapphire NITRO+ Radeon RX 9070 XT 16GB"),   # XT
    ("gpu", "NVIDIA GeForce RTX 5050 8GB", "RTX 5050 8GB - faulty, for parts"),     # junk
    ("motherboard", "ASUS PRIME X870-P", "ASUS PRIME X870-P WIFI AM5 Motherboard"), # wifi variant
    ("psu", "Corsair RM750e 750W 80+ Gold", "Corsair RM750x 750W Gold"),            # different model
    ("cooling", "Thermalright Assassin X 120 SE", "Thermalright Peerless Assassin 120 SE"),
    ("ram", "32GB (2x16GB) DDR5-6000 CL30", "Corsair Vengeance 32GB (2x16GB) DDR5 6000MHz C36"),  # slower CL
    ("ram", "32GB (2x16GB) DDR5-6000 CL30", "Crucial 32GB (1x32GB) DDR5 6000 CL30"),            # wrong kit
    ("ram", "32GB (2x16GB) DDR4-3200", "Corsair 32GB (2x16GB) DDR4 3200 SODIMM laptop"),        # SODIMM
    ("storage", "1TB PCIe 4.0 NVMe SSD", "Crucial P3 1TB PCIe 3.0 NVMe SSD"),                   # gen 3
    ("storage", "1TB PCIe 4.0 NVMe SSD", "Samsung T7 1TB Portable SSD USB 3.2"),                # external
    ("storage", "2TB PCIe 4.0 NVMe SSD", "Samsung 990 PRO 1TB PCIe 4.0 NVMe"),                  # capacity
]


def test_positive_matches():
    failures = [(s, spec, t) for s, spec, t in YES if not m.spec_matches(s, spec, t)]
    assert not failures, failures


def test_negative_matches():
    failures = [(s, spec, t) for s, spec, t in NO if m.spec_matches(s, spec, t)]
    assert not failures, failures





def test_cpu_codes_are_not_memory_sizes():
    assert "5600g" in m.tokens("AMD Ryzen 5 5600G")
    assert "16gb" in m.tokens("RTX 5060 Ti 16G")


def test_ecc_ram_only_matches_ecc_specs():
    spec = "256GB (8x32GB) DDR5 ECC RDIMM"
    assert m.spec_matches("ram", spec, "Kingston 256GB (8x32GB) DDR5 4800 ECC Registered RDIMM kit")
    assert not m.spec_matches("ram", "64GB (2x32GB) DDR5-6000 CL30", "Kingston 64GB (2x32GB) DDR5 6000 CL30 ECC RDIMM")


def test_integrated_parts_are_detected():
    for spec in ["AMD Radeon 840M integrated", "OEM compact APU mainboard (included)", "32GB LPDDR5X",
                 "External 120W power adapter", "AMD Wraith Stealth", "Premium compact aluminium mini-PC chassis"]:
        assert m.INTEGRATED_PATTERN.search(spec), spec
    assert not m.INTEGRATED_PATTERN.search("Corsair RM750e 750W 80+ Gold")


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("pass", _name)
