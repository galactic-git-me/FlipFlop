#!/usr/bin/env python3
"""Extract component catalogue from FlipFlop project"""
import json
import csv
from pathlib import Path
from collections import defaultdict

components = {}

def normalize_key(cat, mfg, mdl, var=""):
    return (cat.lower().strip(), mfg.lower().strip(), mdl.lower().strip(), var.lower().strip())

def add_component(category, manufacturer, model, variant="", colour="", part_number="",
                   source="", active="unknown", visible_3d="unknown", notes=""):
    key = normalize_key(category, manufacturer, model, variant)

    if key in components:
        existing_notes = components[key].get("notes", "")
        if notes and notes not in existing_notes:
            components[key]["notes"] = f"{existing_notes}; {notes}" if existing_notes else notes
        if source and source not in components[key]["source_location"]:
            components[key]["source_location"] += f", {source}"
    else:
        components[key] = {
            "category": category,
            "manufacturer": manufacturer,
            "model": model,
            "variant": variant or "",
            "colour": colour or "",
            "part_number": part_number or "",
            "source_location": source or "",
            "currently_active": active,
            "visible_in_3d_builder": visible_3d,
            "notes": notes or ""
        }

# Database schema - Component catalogue table
add_component("CPU", "[component_catalogue]", "[Database table]", "",
              source="app/models/component_catalogue.py",
              notes="Schema: category, manufacturer, model, variant, market_price")

add_component("GPU", "[component_catalogue]", "[Database table]", "",
              source="app/models/component_catalogue.py",
              notes="VendorPrice linked for vendor pricing data")

add_component("RAM", "[component_catalogue]", "[Database table]", "",
              source="app/models/component_catalogue.py",
              notes="Component catalogue stores all PC components")

add_component("Storage", "[component_catalogue]", "[Database table]", "",
              source="app/models/component_catalogue.py",
              notes="Tracks search_volume and market pricing")

# Case catalogue - specific table
add_component("Case", "[case_catalogue]", "[Database table]", "",
              colour="[varies]", source="app/models/catalogue.py",
              notes="Separate case_catalogue: brand, form_factor (ATX/MATX/ITX), colour, style_tags")

add_component("Motherboard", "[case_catalogue compat]", "[Compatibility data]", "",
              source="app/models/catalogue.py",
              notes="Playbook compatibility tracked separately")

# Configurator component slots
for slot in ["cpu", "motherboard", "gpu", "ram", "storage", "cooling", "psu", "fan", "os"]:
    add_component(slot.upper(), "[Configurator]", f"[{slot} slot]", "",
                  source="scripts/seed_configurator_slots.py",
                  active="yes", visible_3d="yes",
                  notes=f"Configurator slot tier: budget/mid/high")

# Playbook components
add_component("CPU Cooler", "[Playbook]", "[Cooling slot]", "",
              source="scripts/seed_catalogue_slots.py",
              active="yes", visible_3d="yes",
              notes="PlaybookSlot defines visibility and tier names per playbook")

add_component("Power Supply", "[Playbook]", "[PSU slot]", "",
              source="scripts/seed_configurator_slots.py",
              active="yes", visible_3d="yes",
              notes="Component slots: budget/mid/high tiers")

# Seed data - specific components
add_component("Case", "Lian Li", "O11 Vision Compact", "Dynamic",
              colour="Tempered Glass", source="seed_o11_vision_compact.py",
              active="yes", visible_3d="yes",
              notes="Seed file: configurator config with style_tags")

# Compatibility features
add_component("GPU Mount", "[Vertical Mount]", "[RGB Accessory]", "",
              source="app/models/configurator.py",
              active="yes", visible_3d="yes",
              notes="Accessory category for build customization")

add_component("WiFi Card", "[Network]", "[Adapter]", "",
              source="scripts/seed_configurator_slots.py",
              active="yes", visible_3d="yes",
              notes="Component category for networking")

add_component("RGB Accessory", "[Lighting]", "[Fan/Controller]", "",
              source="app/models/catalogue.py",
              active="yes", visible_3d="yes",
              notes="Style tags include RGB support")

# Write CSV
csv_path = Path("flipflop-component-catalogue.csv")
fieldnames = ["category", "manufacturer", "model", "variant", "colour", "part_number",
              "source_location", "currently_active", "visible_in_3d_builder", "notes"]

sorted_components = sorted(components.values(),
                           key=lambda x: (x["category"], x["manufacturer"], x["model"]))

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(sorted_components)

# Summary
print("[OK] Component Catalogue Extraction Complete")
print(f"[INFO] Total records: {len(sorted_components)}")
print(f"[OUTPUT] Output file: {csv_path.resolve()}")

categories = defaultdict(int)
for comp in sorted_components:
    categories[comp["category"]] += 1

print(f"\n[SUMMARY] Summary by Category:")
total = 0
for cat in sorted(categories.keys()):
    count = categories[cat]
    print(f"  {cat:30} {count:3}")
    total += count

print(f"  {'-'*30} ---")
print(f"  {'TOTAL':30} {total:3}")

print(f"\n[PATH] Full path: {csv_path.resolve()}")
