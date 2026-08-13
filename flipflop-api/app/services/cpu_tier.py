"""
Shared CPU-tier classification — used by FlipIntelligence (analytics),
PricingBias (row 49's fast-sale anchor bias), and anywhere else that needs
to group builds by rough CPU class as a "similar build" proxy.
"""


def extract_cpu_tier(cpu: str | None) -> str | None:
    if not cpu:
        return None
    cpu_lower = cpu.lower()
    if "xeon" in cpu_lower:
        return "Xeon"
    if "i9" in cpu_lower:
        return "i9"
    if "i7" in cpu_lower:
        return "i7"
    if "i5" in cpu_lower:
        return "i5"
    if "i3" in cpu_lower:
        return "i3"
    if "ryzen 9" in cpu_lower:
        return "Ryzen 9"
    if "ryzen 7" in cpu_lower:
        return "Ryzen 7"
    if "ryzen 5" in cpu_lower:
        return "Ryzen 5"
    if "ryzen 3" in cpu_lower:
        return "Ryzen 3"
    return cpu.split()[0] if cpu else None
