"""One-off comparison test: text-to-3D generation for a specific case model,
built entirely from its published spec sheet (dimensions, fan layout, panel
material) — no reference imagery used as input. Not wired into the
production catalogue/family-bucket pipeline (cases are excluded from that
system by design — see component_family_classifier.py). Prints the result
GLB/preview URLs for manual review; doesn't write to the database.
Safe to delete after the comparison is done.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.meshy_generation import generate_family_asset

PROMPT = (
    "A premium ATX mid-tower PC case, 230mm wide, 464mm deep, 502mm tall. "
    "Rectangular boxy silhouette. Full mesh perforated front panel covering "
    "three 140mm fans arranged vertically. Tempered glass side panel. Metal "
    "chassis with a colour-shifting iridescent purple-to-teal finish that "
    "changes hue depending on viewing angle. Small feet at the base. "
    "Minimal front I/O cutout near the top. No visible branding or logos."
)


async def main():
    print("Submitting text-to-3D generation...")
    print(f"Prompt: {PROMPT}\n")
    result = await generate_family_asset(PROMPT)
    if result is None:
        print("FAILED: no result (check MESHY_API_KEY)")
        return
    print(f"Status: {result.status}")
    print(f"GLB: {result.glb_url}")
    print(f"Preview: {result.thumbnail_url}")


if __name__ == "__main__":
    asyncio.run(main())
